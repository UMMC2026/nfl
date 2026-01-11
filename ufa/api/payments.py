"""
Stripe payment integration with webhook handling.
"""
import os
import stripe
from datetime import datetime, timedelta
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional

from ufa.db import SessionLocal
from ufa.models.user import User, Subscription, Plan, Payment, PlanTier
from ufa.api.auth import get_current_user

router = APIRouter(prefix="/payments", tags=["payments"])

# Stripe config
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CheckoutRequest(BaseModel):
    plan_id: int


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionStatus(BaseModel):
    plan_name: str
    tier: str
    status: str
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool


@router.get("/plans")
async def list_plans(db: Session = Depends(get_db)):
    """List all available subscription plans."""
    plans = db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_cents)
    ).scalars().all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "tier": p.tier.value,
            "price_cents": p.price_cents,
            "price_display": f"${p.price_cents / 100:.2f}/month",
            "daily_signals": "Unlimited" if p.daily_signals == -1 else p.daily_signals,
            "max_parlays": "Unlimited" if p.max_parlays == -1 else p.max_parlays,
            "can_view_probabilities": p.can_view_probabilities,
            "can_view_ollama_notes": p.can_view_ollama_notes,
            "can_export": p.can_export,
            "spots_remaining": (
                p.max_subscribers - p.current_subscribers 
                if p.max_subscribers else "Unlimited"
            ),
        }
        for p in plans
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    data: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create Stripe checkout session for subscription."""
    plan = db.execute(
        select(Plan).where(Plan.id == data.plan_id, Plan.is_active == True)
    ).scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.tier == PlanTier.FREE:
        raise HTTPException(status_code=400, detail="Cannot checkout free plan")
    
    # Check scarcity limits
    if plan.max_subscribers and plan.current_subscribers >= plan.max_subscribers:
        raise HTTPException(
            status_code=400, 
            detail=f"{plan.name} plan is full. Join the waitlist.",
        )
    
    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=500,
            detail=f"Plan '{plan.name}' not configured for payments (missing stripe_price_id)",
        )

    # Validate Stripe configuration
    if not stripe.api_key or not stripe.api_key.startswith("sk_"):
        raise HTTPException(
            status_code=500,
            detail="Stripe secret key is not configured. Set STRIPE_SECRET_KEY in environment.",
        )
    
    # Get or create Stripe customer
    customer_id = None
    if user.subscription and user.subscription.stripe_customer_id:
        customer_id = user.subscription.stripe_customer_id
    else:
        try:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"user_id": str(user.id)},
            )
            customer_id = customer.id
        except Exception as e:
            logger.exception("Failed to create Stripe customer")
            raise HTTPException(status_code=500, detail=f"Stripe customer creation failed: {e}")
    
    # Create checkout session
    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": plan.stripe_price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/subscription/cancel",
            metadata={
                "user_id": str(user.id),
                "plan_id": str(plan.id),
            },
        )
    except Exception as e:
        logger.exception("Failed to create Stripe checkout session")
        raise HTTPException(status_code=500, detail=f"Stripe checkout session failed: {e}")
    
    return CheckoutResponse(
        checkout_url=session.url,
        session_id=session.id,
    )


@router.get("/debug")
async def payments_debug(db: Session = Depends(get_db)):
    """Minimal diagnostics for payments configuration (safe to expose)."""
    plans = db.execute(select(Plan).order_by(Plan.id)).scalars().all()
    return {
        "stripe_secret_set": bool(stripe.api_key and stripe.api_key.startswith("sk_")),
        "stripe_publishable_set": bool(STRIPE_PUBLISHABLE_KEY and STRIPE_PUBLISHABLE_KEY.startswith("pk_")),
        "webhook_secret_set": bool(STRIPE_WEBHOOK_SECRET and STRIPE_WEBHOOK_SECRET.startswith("whsec_")),
        "frontend_url": FRONTEND_URL,
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "price_cents": p.price_cents,
                "stripe_price_id_present": bool(p.stripe_price_id),
                "stripe_price_id": p.stripe_price_id or None,
            }
            for p in plans
        ],
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    if event_type == "checkout.session.completed":
        await handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_succeeded":
        await handle_payment_succeeded(data, db)
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(data, db)
    
    return {"status": "ok"}


async def handle_checkout_completed(session: dict, db: Session):
    """Process successful checkout."""
    user_id = int(session["metadata"]["user_id"])
    plan_id = int(session["metadata"]["plan_id"])
    subscription_id = session.get("subscription")
    customer_id = session["customer"]
    
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    plan = db.execute(select(Plan).where(Plan.id == plan_id)).scalar_one_or_none()
    
    if not user or not plan:
        return
    
    # Update or create subscription
    if user.subscription:
        # Decrement old plan count
        old_plan = db.execute(
            select(Plan).where(Plan.id == user.subscription.plan_id)
        ).scalar_one_or_none()
        if old_plan and old_plan.current_subscribers > 0:
            old_plan.current_subscribers -= 1
        
        user.subscription.plan_id = plan_id
        user.subscription.stripe_subscription_id = subscription_id
        user.subscription.stripe_customer_id = customer_id
        user.subscription.status = "active"
        user.subscription.started_at = datetime.utcnow()
        user.subscription.expires_at = None
        user.subscription.canceled_at = None
    else:
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
            status="active",
        )
        db.add(subscription)
    
    # Increment new plan subscriber count
    plan.current_subscribers += 1
    db.commit()


async def handle_subscription_updated(subscription: dict, db: Session):
    """Handle subscription changes (upgrade/downgrade)."""
    stripe_sub_id = subscription["id"]
    
    sub = db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()
    
    if not sub:
        return
    
    # Update status
    status = subscription["status"]
    if status in ["active", "trialing"]:
        sub.status = "active"
    elif status == "past_due":
        sub.status = "past_due"
    elif status in ["canceled", "unpaid"]:
        sub.status = "canceled"
    
    # Update expiration
    if subscription.get("current_period_end"):
        sub.expires_at = datetime.fromtimestamp(subscription["current_period_end"])
    
    if subscription.get("cancel_at_period_end"):
        sub.canceled_at = datetime.utcnow()
    
    db.commit()


async def handle_subscription_deleted(subscription: dict, db: Session):
    """Handle subscription cancellation."""
    stripe_sub_id = subscription["id"]
    
    sub = db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()
    
    if not sub:
        return
    
    # Decrement plan subscriber count
    plan = db.execute(
        select(Plan).where(Plan.id == sub.plan_id)
    ).scalar_one_or_none()
    
    if plan and plan.current_subscribers > 0:
        plan.current_subscribers -= 1
    
    # Downgrade to free
    free_plan = db.execute(
        select(Plan).where(Plan.tier == PlanTier.FREE)
    ).scalar_one_or_none()
    
    if free_plan:
        sub.plan_id = free_plan.id
        sub.status = "active"
        sub.stripe_subscription_id = None
        sub.canceled_at = datetime.utcnow()
    
    db.commit()


async def handle_payment_succeeded(invoice: dict, db: Session):
    """Record successful payment."""
    customer_id = invoice["customer"]
    
    sub = db.execute(
        select(Subscription).where(
            Subscription.stripe_customer_id == customer_id
        )
    ).scalar_one_or_none()
    
    if not sub:
        return
    
    payment = Payment(
        user_id=sub.user_id,
        amount_cents=invoice["amount_paid"],
        currency=invoice["currency"],
        status="succeeded",
        stripe_invoice_id=invoice["id"],
        description=f"Subscription payment - {invoice.get('description', '')}",
    )
    db.add(payment)
    db.commit()


async def handle_payment_failed(invoice: dict, db: Session):
    """Handle failed payment."""
    customer_id = invoice["customer"]
    
    sub = db.execute(
        select(Subscription).where(
            Subscription.stripe_customer_id == customer_id
        )
    ).scalar_one_or_none()
    
    if not sub:
        return
    
    sub.status = "past_due"
    
    payment = Payment(
        user_id=sub.user_id,
        amount_cents=invoice["amount_due"],
        currency=invoice["currency"],
        status="failed",
        stripe_invoice_id=invoice["id"],
        description=f"Failed payment - {invoice.get('description', '')}",
    )
    db.add(payment)
    db.commit()


@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current subscription status."""
    plan_name = "Free"
    tier = PlanTier.FREE.value
    status = "active"
    period_end = None
    cancel_at_end = False
    
    if user.subscription:
        plan = db.execute(
            select(Plan).where(Plan.id == user.subscription.plan_id)
        ).scalar_one_or_none()
        
        if plan:
            plan_name = plan.name
            tier = plan.tier.value
        
        status = user.subscription.status
        period_end = user.subscription.expires_at
        cancel_at_end = user.subscription.canceled_at is not None
    
    return SubscriptionStatus(
        plan_name=plan_name,
        tier=tier,
        status=status,
        current_period_end=period_end,
        cancel_at_period_end=cancel_at_end,
    )


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel subscription at end of billing period."""
    if not user.subscription or not user.subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=400, 
            detail="No active paid subscription",
        )
    
    try:
        stripe.Subscription.modify(
            user.subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    user.subscription.canceled_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Subscription will be canceled at end of billing period"}


@router.post("/portal")
async def create_customer_portal(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create Stripe customer portal session for self-service."""
    if not user.subscription or not user.subscription.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No payment history found",
        )
    
    try:
        session = stripe.billing_portal.Session.create(
            customer=user.subscription.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/account",
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {"portal_url": session.url}
