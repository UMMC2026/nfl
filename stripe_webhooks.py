"""Stripe webhook handler for subscription events."""

from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
import stripe
import json

from stripe_config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from stripe_db import User, Subscription
from telegram_notifier import notify_subscription

router = APIRouter(prefix="/stripe", tags=["stripe"])

stripe.api_key = STRIPE_SECRET_KEY


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle events
    if event["type"] == "customer.subscription.created":
        await handle_subscription_created(event["data"]["object"])
    
    elif event["type"] == "customer.subscription.updated":
        await handle_subscription_updated(event["data"]["object"])
    
    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_deleted(event["data"]["object"])
    
    elif event["type"] == "invoice.payment_succeeded":
        await handle_payment_succeeded(event["data"]["object"])
    
    return {"status": "received"}


async def handle_subscription_created(subscription: dict):
    """Handle new subscription."""
    stripe_customer_id = subscription["customer"]
    stripe_subscription_id = subscription["id"]
    
    # Get customer email
    customer = stripe.Customer.retrieve(stripe_customer_id)
    email = customer.email
    
    # Get tier from product
    tier = get_tier_from_subscription(subscription)
    
    # Create/update user
    user_id = User.create(email, stripe_customer_id)
    
    # Create subscription record
    period_start = datetime.fromtimestamp(subscription["current_period_start"])
    period_end = datetime.fromtimestamp(subscription["current_period_end"])
    
    Subscription.create(
        user_id=user_id,
        stripe_subscription_id=stripe_subscription_id,
        tier=tier,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    
    # Notify
    await notify_subscription(email, tier, "created")
    print(f"✅ Subscription created: {email} ({tier})")


async def handle_subscription_updated(subscription: dict):
    """Handle subscription update."""
    stripe_subscription_id = subscription["id"]
    status = subscription["status"]
    
    # Update in DB
    cancel_at = None
    if subscription.get("cancel_at"):
        cancel_at = datetime.fromtimestamp(subscription["cancel_at"])
    
    Subscription.update_status(stripe_subscription_id, status, cancel_at)
    print(f"✅ Subscription updated: {stripe_subscription_id} -> {status}")


async def handle_subscription_deleted(subscription: dict):
    """Handle subscription cancellation."""
    stripe_subscription_id = subscription["id"]
    Subscription.update_status(stripe_subscription_id, "canceled")
    print(f"✅ Subscription canceled: {stripe_subscription_id}")


async def handle_payment_succeeded(invoice: dict):
    """Handle successful payment."""
    stripe_customer_id = invoice["customer"]
    customer = stripe.Customer.retrieve(stripe_customer_id)
    email = customer.email
    
    print(f"✅ Payment succeeded: {email} (${invoice['amount_paid']/100:.2f})")


def get_tier_from_subscription(subscription: dict) -> str:
    """Extract tier from subscription items."""
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return "unknown"
    
    price_id = items[0].get("price", {}).get("id")
    
    # Map price ID to tier (you'll need to update these with your actual price IDs)
    tier_map = {
        # Fill these in from your Stripe dashboard
        "price_1Sk9...": "starter",
        "price_1Sk9...": "pro",
        "price_1Sk9...": "whale",
    }
    
    return tier_map.get(price_id, "unknown")
