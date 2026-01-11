"""
Stripe webhook handlers for subscription lifecycle events.
"""
import os
import stripe
import logging
from fastapi import APIRouter, Request, HTTPException
from ufa.billing.plan_map import tier_for_price
from ufa.billing.subscriptions import update_user_subscription
from ufa.db import SessionLocal
from sqlalchemy import select
from ufa.models.user import User

router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

logger = logging.getLogger(__name__)


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    
    Handles:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    
    if not WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, WEBHOOK_SECRET
        )
    except ValueError:
        logger.warning("Invalid Stripe webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    
    logger.info(f"Processing Stripe webhook: {event_type}")
    
    if event_type == "customer.subscription.created":
        await handle_subscription_created(data)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data)
    else:
        logger.debug(f"Ignoring event type: {event_type}")
    
    return {"ok": True}


async def handle_subscription_created(data: dict):
    """Handle new subscription creation."""
    from ufa.models.user import Subscription
    
    customer_id = data.get("customer")
    price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
    status = data.get("status")
    period_end = data.get("current_period_end")
    subscription_id = data.get("id")
    
    if not customer_id or not price_id:
        logger.warning("Missing customer_id or price_id in subscription.created")
        return
    
    db = SessionLocal()
    try:
        # Query subscription by customer_id, then get user
        subscription = db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        ).scalar_one_or_none()
        
        if not subscription:
            logger.warning(f"No subscription found for customer {customer_id}")
            return
        
        user = subscription.user
        tier = tier_for_price(price_id)
        
        update_user_subscription(
            user_id=user.id,
            tier=tier,
            status=status if status == "active" else "past_due",
            subscription_id=subscription_id,
            period_end=period_end,
            customer_id=customer_id,
        )
        logger.info(f"Created subscription for user {user.id}, tier {tier}")
    finally:
        db.close()


async def handle_subscription_updated(data: dict):
    """Handle subscription updates (e.g., plan changes)."""
    from ufa.models.user import Subscription
    
    customer_id = data.get("customer")
    price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
    status = data.get("status")
    period_end = data.get("current_period_end")
    subscription_id = data.get("id")
    
    if not customer_id:
        logger.warning("Missing customer_id in subscription.updated")
        return
    
    db = SessionLocal()
    try:
        subscription = db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        ).scalar_one_or_none()
        
        if not subscription:
            logger.warning(f"No subscription found for customer {customer_id}")
            return
        
        user = subscription.user
        tier = tier_for_price(price_id) if price_id else user.subscription.plan.tier
        
        update_user_subscription(
            user_id=user.id,
            tier=tier,
            status=status if status == "active" else "past_due",
            subscription_id=subscription_id,
            period_end=period_end,
            customer_id=customer_id,
        )
        logger.info(f"Updated subscription for user {user.id}, tier {tier}")
    finally:
        db.close()


async def handle_subscription_deleted(data: dict):
    """Handle subscription cancellation."""
    from ufa.models.user import Subscription, PlanTier
    
    customer_id = data.get("customer")
    
    if not customer_id:
        logger.warning("Missing customer_id in subscription.deleted")
        return
    
    db = SessionLocal()
    try:
        subscription = db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        ).scalar_one_or_none()
        
        if not subscription:
            logger.warning(f"No subscription found for customer {customer_id}")
            return
        
        user = subscription.user
        
        # Downgrade to free
        update_user_subscription(
            user_id=user.id,
            tier=PlanTier.FREE,
            status="canceled",
            subscription_id=None,
            customer_id=customer_id,
        )
        logger.info(f"Canceled subscription for user {user.id}")
    finally:
        db.close()
