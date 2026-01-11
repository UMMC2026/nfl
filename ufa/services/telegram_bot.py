"""
Telegram Bot for signal delivery with subscription enforcement.

Run with: python -m ufa.services.telegram_bot
"""
import os
import json
import asyncio
import logging
from datetime import datetime, date
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ufa.db import SessionLocal, engine
from ufa.models.user import (
    User, Subscription, Plan, Signal, SignalView, 
    DailyMetrics, PlanTier, SignalResult, Base
)
from ufa.services.telegram_shaper import (
    format_signal_for_telegram,
    format_signal_compact,
    filter_and_shape_signals_for_telegram,
    format_visible_signal,
    format_delay_message,
)
from ufa.signals.shaper import SignalShaper

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SIGNALS_FILE = Path("output/signals_latest.json")
ADMIN_TELEGRAM_IDS = os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")


# Database session helper
def get_db() -> Session:
    return SessionLocal()


def get_main_menu_keyboard():
    """Create main menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Signals", callback_data="menu_signals"),
            InlineKeyboardButton("📈 Results", callback_data="menu_results"),
        ],
        [
            InlineKeyboardButton("💳 Subscribe", callback_data="menu_subscribe"),
            InlineKeyboardButton("📊 Stats", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="menu_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_or_create_user(db: Session, telegram_id: str, username: str = None) -> User:
    """Get existing user or create new one with free tier."""
    user = db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            telegram_username=username,
            display_name=username or f"User_{telegram_id[:8]}",
        )
        db.add(user)
        db.flush()
        
        # Create free subscription
        free_plan = db.execute(
            select(Plan).where(Plan.tier == PlanTier.FREE)
        ).scalar_one_or_none()
        
        if free_plan:
            subscription = Subscription(user_id=user.id, plan_id=free_plan.id)
            db.add(subscription)
        
        db.commit()
        db.refresh(user)
    
    return user


def get_user_plan(db: Session, user: User) -> tuple[Plan, Subscription]:
    """Get user's current plan and subscription."""
    if not user.subscription:
        free_plan = db.execute(
            select(Plan).where(Plan.tier == PlanTier.FREE)
        ).scalar_one_or_none()
        return free_plan, None
    
    plan = db.execute(
        select(Plan).where(Plan.id == user.subscription.plan_id)
    ).scalar_one_or_none()
    
    return plan, user.subscription


def check_daily_limit(db: Session, user: User, limit_type: str = "signals") -> tuple[bool, int, int]:
    """
    Check if user has remaining daily quota.
    Returns: (has_remaining, used, limit)
    """
    plan, sub = get_user_plan(db, user)
    
    if not plan:
        return False, 0, 0
    
    if not sub:
        limit = plan.daily_signals if limit_type == "signals" else plan.max_parlays
        return limit > 0, 0, limit
    
    # Reset daily limits if needed
    sub.reset_daily_limits()
    db.commit()
    
    if limit_type == "signals":
        limit = plan.daily_signals
        used = sub.signals_viewed_today
    else:
        limit = plan.max_parlays
        used = sub.parlays_viewed_today
    
    # -1 means unlimited
    if limit == -1:
        return True, used, 999
    
    return used < limit, used, limit


def increment_usage(db: Session, user: User, limit_type: str = "signals"):
    """Increment daily usage counter."""
    if user.subscription:
        if limit_type == "signals":
            user.subscription.signals_viewed_today += 1
        else:
            user.subscription.parlays_viewed_today += 1
        db.commit()


def load_latest_signals() -> list[dict]:
    """Load signals from the latest pipeline output."""
    if not SIGNALS_FILE.exists():
        # Try alternate paths
        output_dir = Path("output")
        if output_dir.exists():
            json_files = sorted(output_dir.glob("signals_*.json"), reverse=True)
            if json_files:
                with open(json_files[0], "r", encoding="utf-8") as f:
                    return json.load(f)
        return []
    
    with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_signal(signal: dict, show_probability: bool = True, show_notes: bool = False) -> str:
    """
    Format a signal for Telegram (legacy wrapper).
    
    For backward compatibility. Uses WHALE tier (shows all fields).
    New code should use format_signal_for_telegram(signal, tier).
    """
    shaped = SignalShaper.shape(signal, PlanTier.WHALE)
    return format_visible_signal(shaped, show_probability, show_notes)


# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    db = get_db()
    try:
        user = get_or_create_user(
            db, 
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        
        welcome_text = f"""
🏀 **Welcome to Underdog Signals** 🏀

Hey {update.effective_user.first_name}! I deliver high-probability sports picks powered by Monte Carlo simulation and AI analysis.

📊 **Your Plan:** {plan.name if plan else 'Free'}
📈 **Daily Signals:** {plan.daily_signals if plan and plan.daily_signals != -1 else 'Unlimited'}

Ready to win? Use the menu below to get started! 🎯
"""
        await update.message.reply_text(
            welcome_text, 
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
    finally:
        db.close()


async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /signals command - deliver today's picks."""
    db = get_db()
    try:
        # Log command
        logger.info(f"User {update.effective_user.id} requested /signals")
        
        user = get_or_create_user(
            db,
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        
        logger.info(f"User tier: {plan.tier if plan else 'FREE'}")
        
        # Check daily limit
        has_remaining, used, limit = check_daily_limit(db, user, "signals")
        
        if not has_remaining:
            upgrade_text = f"""
⚠️ **Daily Limit Reached**

You've used all {limit} signals for today.

🔓 **Upgrade for more access:**
• Starter ($19.99/mo): 5 signals/day
• Pro ($49.99/mo): 15 signals/day
• Whale ($199.99/mo): Unlimited

Use /subscribe to upgrade!
"""
            await update.message.reply_text(upgrade_text, parse_mode="Markdown")
            return
        
        # Load signals
        logger.info("Loading signals...")
        signals = load_latest_signals()
        logger.info(f"Loaded {len(signals)} signals")
        
        if not signals:
            await update.message.reply_text(
                "📭 No signals available yet. Check back soon!",
                parse_mode="Markdown",
            )
            return
        
        # Get user's tier
        user_tier = plan.tier if plan else PlanTier.FREE
        logger.info(f"Filtering signals for tier {user_tier}")
        
        # Filter and shape signals for user's tier
        shaped_signals, total_available = filter_and_shape_signals_for_telegram(
            signals,
            user_tier,
            limit=limit - used if limit != -1 else -1,
        )
        logger.info(f"After filtering: {len(shaped_signals)} signals (total: {total_available})")
        
        if not shaped_signals:
            await update.message.reply_text(
                "🔔 No signals available for your tier yet.",
                parse_mode="Markdown",
            )
            return
        
        # Check feature access
        show_prob = plan.can_view_probabilities if plan else False
        show_notes = plan.can_view_ollama_notes if plan else False
        
        # Send signals
        header = f"🎯 **Today's Signals** ({len(shaped_signals)} of {total_available})\n"
        header += f"📅 {date.today().strftime('%B %d, %Y')}\n"
        header += "─" * 25
        
        await update.message.reply_text(header, parse_mode="Markdown")
        logger.info(f"Sending {len(shaped_signals)} signals to user")
        
        for i, shaped_signal in enumerate(shaped_signals):
            try:
                # Format signal with tier-based shaping applied
                msg = format_signal_for_telegram(
                    shaped_signal,
                    user_tier,
                    show_probability=show_prob,
                    show_notes=show_notes,
                )
                
                if msg:  # msg is None if delayed
                    await update.message.reply_text(msg, parse_mode="Markdown")
                    increment_usage(db, user, "signals")
                    await asyncio.sleep(0.5)  # Rate limit
                else:
                    logger.warning(f"Signal {i} returned None message")
            except Exception as e:
                logger.error(f"Error formatting signal {i}: {e}", exc_info=True)
                await update.message.reply_text(f"⚠️ Error sending signal {i+1}")
        
        # Show remaining
        _, new_used, _ = check_daily_limit(db, user, "signals")
        remaining = limit - new_used if limit != -1 else "∞"
        
        footer = f"\n📊 Signals remaining today: {remaining}"
        if plan and plan.tier == PlanTier.FREE:
            footer += "\n\n💡 Upgrade for more signals and detailed probabilities!"
        
        await update.message.reply_text(footer)
        
    except Exception as e:
        logger.error(f"Error in /signals command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error loading signals: {str(e)[:100]}")
    
    finally:
        db.close()


async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /results command - show recent performance."""
    db = get_db()
    try:
        # Get last 7 days of metrics
        metrics = db.execute(
            select(DailyMetrics)
            .order_by(DailyMetrics.date.desc())
            .limit(7)
        ).scalars().all()
        
        if not metrics:
            # Calculate from signals if no metrics yet
            recent_signals = db.execute(
                select(Signal)
                .where(Signal.result != SignalResult.PENDING)
                .order_by(Signal.graded_at.desc())
                .limit(50)
            ).scalars().all()
            
            if not recent_signals:
                await update.message.reply_text(
                    "📊 No graded results yet. Check back after games complete!",
                    parse_mode="Markdown",
                )
                return
            
            wins = sum(1 for s in recent_signals if s.result == SignalResult.WIN)
            losses = sum(1 for s in recent_signals if s.result == SignalResult.LOSS)
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
            
            results_text = f"""
📈 **Recent Performance**

🎯 **Last {total} Picks:**
✅ Wins: {wins}
❌ Losses: {losses}
📊 Win Rate: {win_rate:.1f}%

**By Tier:**
"""
            # Group by tier
            for tier in ["SLAM", "STRONG", "LEAN"]:
                tier_signals = [s for s in recent_signals if s.tier == tier]
                tier_wins = sum(1 for s in tier_signals if s.result == SignalResult.WIN)
                tier_total = len([s for s in tier_signals if s.result != SignalResult.PENDING])
                tier_rate = (tier_wins / tier_total * 100) if tier_total > 0 else 0
                
                emoji = {"SLAM": "🔥", "STRONG": "💪", "LEAN": "📊"}.get(tier, "")
                results_text += f"{emoji} {tier}: {tier_wins}/{tier_total} ({tier_rate:.0f}%)\n"
            
            await update.message.reply_text(results_text, parse_mode="Markdown")
            return
        
        # Use metrics
        total_wins = sum(m.total_wins for m in metrics)
        total_losses = sum(m.total_losses for m in metrics)
        total = total_wins + total_losses
        win_rate = (total_wins / total * 100) if total > 0 else 0
        
        results_text = f"""
📈 **7-Day Performance**

🎯 **Overall:**
✅ Wins: {total_wins}
❌ Losses: {total_losses}
📊 Win Rate: {win_rate:.1f}%

**Daily Breakdown:**
"""
        for m in metrics[:5]:
            day_total = m.total_wins + m.total_losses
            day_rate = (m.total_wins / day_total * 100) if day_total > 0 else 0
            date_str = m.date.strftime("%m/%d")
            results_text += f"📅 {date_str}: {m.total_wins}-{m.total_losses} ({day_rate:.0f}%)\n"
        
        await update.message.reply_text(results_text, parse_mode="Markdown")
        
    finally:
        db.close()


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - show upgrade options."""
    db = get_db()
    try:
        user = get_or_create_user(
            db,
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        current_tier = plan.tier if plan else PlanTier.FREE
        
        plans = db.execute(
            select(Plan)
            .where(Plan.is_active == True)
            .order_by(Plan.price_cents)
        ).scalars().all()
        
        subscribe_text = f"""
💳 **Subscription Plans**

Your current plan: **{plan.name if plan else 'Free'}**

"""
        for p in plans:
            if p.tier == PlanTier.FREE:
                continue
            
            spots_text = ""
            if p.max_subscribers:
                remaining = p.max_subscribers - p.current_subscribers
                spots_text = f"⚡ Only {remaining} spots left!" if remaining < 20 else ""
            
            current_marker = " ← Current" if p.tier == current_tier else ""
            
            subscribe_text += f"""
**{p.name}** - ${p.price_cents / 100:.2f}/month{current_marker}
• {p.daily_signals if p.daily_signals != -1 else '∞'} signals/day
• {p.max_parlays if p.max_parlays != -1 else '∞'} parlays/day
• {'✅' if p.can_view_probabilities else '❌'} Probabilities
• {'✅' if p.can_view_ollama_notes else '❌'} AI Analysis
{spots_text}
"""
        
        # Payment link (replace with actual Stripe link)
        payment_url = os.getenv("STRIPE_PAYMENT_LINK", "https://buy.stripe.com/test")
        
        keyboard = [
            [InlineKeyboardButton("💳 Subscribe Now", url=payment_url)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            subscribe_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        
    finally:
        db.close()


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show user's stats."""
    db = get_db()
    try:
        user = get_or_create_user(
            db,
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        
        # Get usage stats
        _, signals_used, signals_limit = check_daily_limit(db, user, "signals")
        _, parlays_used, parlays_limit = check_daily_limit(db, user, "parlays")
        
        # Get view count
        view_count = db.execute(
            select(func.count(SignalView.id))
            .where(SignalView.user_id == user.id)
        ).scalar() or 0
        
        signals_remaining = "∞" if signals_limit == 999 else signals_limit - signals_used
        parlays_remaining = "∞" if parlays_limit == 999 else parlays_limit - parlays_used
        
        stats_text = f"""
📊 **Your Stats**

👤 **Account:**
• Plan: {plan.name if plan else 'Free'}
• Member since: {user.created_at.strftime('%b %d, %Y') if user.created_at else 'N/A'}

📈 **Today's Usage:**
• Signals: {signals_used}/{signals_limit} (Remaining: {signals_remaining})
• Parlays: {parlays_used}/{parlays_limit} (Remaining: {parlays_remaining})

📚 **All Time:**
• Total signals viewed: {view_count}
"""
        
        if sub and sub.expires_at:
            stats_text += f"\n⏰ Subscription renews: {sub.expires_at.strftime('%b %d, %Y')}"
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")
        
    finally:
        db.close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
📖 **Underdog Signals Help**

**What is this?**
I analyze sports props using Monte Carlo simulation (10,000 iterations) and AI to find high-probability plays for Underdog Pick'em.

**Tier System:**
🔥 SLAM (85%+) - Highest confidence
💪 STRONG (70-85%) - High confidence
📊 LEAN (60-70%) - Moderate confidence

**Commands:**
/menu - Show main menu
/signals - Get today's picks
/results - View recent performance
/subscribe - Upgrade options
/stats - Your usage stats
/help - This message

**Questions?**
Contact @YourSupportHandle

Good luck! 🍀
"""
    await update.message.reply_text(
        help_text, 
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command - show main menu."""
    await update.message.reply_text(
        "📱 **Main Menu**\n\nChoose an option below:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks from inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    # For callback queries, we need to edit the message instead of replying
    # Route to appropriate command handler based on callback data
    if query.data == "menu_signals":
        # Simulate a message update for the command handler
        # Create a minimal update object with the callback's message
        await query.edit_message_text(
            "📊 Loading signals...",
            parse_mode="Markdown"
        )
        # Call signals command with callback query context
        await signals_command_callback(update, context)
    elif query.data == "menu_results":
        await results_command_callback(update, context)
    elif query.data == "menu_subscribe":
        await subscribe_command_callback(update, context)
    elif query.data == "menu_stats":
        await stats_command_callback(update, context)
    elif query.data == "menu_help":
        await help_command_callback(update, context)


# Callback versions of commands that work with callback queries
async def signals_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle signals from callback query."""
    query = update.callback_query
    db = get_db()
    try:
        user = get_or_create_user(
            db,
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        
        # Check daily limit
        has_remaining, used, limit = check_daily_limit(db, user, "signals")
        
        if not has_remaining:
            upgrade_text = f"""
⚠️ **Daily Limit Reached**

You've used all {limit} signals for today.

🔓 **Upgrade for more access:**
• Starter ($19.99/mo): 5 signals/day
• Pro ($49.99/mo): 15 signals/day
• Whale ($199.99/mo): Unlimited

Use /subscribe to upgrade!
"""
            await query.message.reply_text(upgrade_text, parse_mode="Markdown")
            return
        
        # Load signals
        signals = load_latest_signals()
        
        if not signals:
            await query.message.reply_text(
                "📭 No signals available yet. Check back soon!",
                parse_mode="Markdown",
            )
            return
        
        # Get user's tier
        user_tier = plan.tier if plan else PlanTier.FREE
        
        # Filter and shape signals for user's tier
        shaped_signals, total_available = filter_and_shape_signals_for_telegram(
            signals,
            user_tier,
            limit=limit - used if limit != -1 else -1,
        )
        
        if not shaped_signals:
            await query.message.reply_text(
                "📭 No signals match your tier. Upgrade for more access!",
                parse_mode="Markdown",
            )
            return
        
        # Send signals
        await query.edit_message_text(
            f"📊 **Today's Top Picks** ({len(shaped_signals)} signals)",
            parse_mode="Markdown"
        )
        
        for sig in shaped_signals:
            await query.message.reply_text(sig, parse_mode="Markdown")
            await asyncio.sleep(0.2)
        
        # Increment usage
        increment_usage(db, user, "signals")
        
    finally:
        db.close()


async def results_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle results from callback query."""
    await update.callback_query.message.reply_text("📈 Results feature coming soon!", parse_mode="Markdown")


async def subscribe_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle subscribe from callback query."""
    query = update.callback_query
    db = get_db()
    try:
        user = get_or_create_user(
            db,
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        current_tier = plan.tier if plan else PlanTier.FREE
        
        plans = db.execute(
            select(Plan)
            .where(Plan.is_active == True)
            .order_by(Plan.price_cents)
        ).scalars().all()
        
        subscribe_text = f"""
💳 **Subscription Plans**

Your current plan: **{plan.name if plan else 'Free'}**

"""
        for p in plans:
            if p.tier == PlanTier.FREE:
                continue
            
            current_marker = " ← Current" if p.tier == current_tier else ""
            
            subscribe_text += f"""
**{p.name}** - ${p.price_cents / 100:.2f}/month{current_marker}
• {p.daily_signals if p.daily_signals != -1 else '∞'} signals/day
• {'✅' if p.can_view_probabilities else '❌'} Probabilities
• {'✅' if p.can_view_ollama_notes else '❌'} AI Analysis

"""
        
        payment_url = os.getenv("STRIPE_PAYMENT_LINK", "https://buy.stripe.com/test")
        
        keyboard = [
            [InlineKeyboardButton("💳 Subscribe Now", url=payment_url)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            subscribe_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )
        
    finally:
        db.close()


async def stats_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stats from callback query."""
    query = update.callback_query
    db = get_db()
    try:
        user = get_or_create_user(
            db,
            str(update.effective_user.id),
            update.effective_user.username,
        )
        plan, sub = get_user_plan(db, user)
        
        # Get usage stats
        _, signals_used, signals_limit = check_daily_limit(db, user, "signals")
        
        signals_remaining = "∞" if signals_limit == 999 else signals_limit - signals_used
        
        stats_text = f"""
📊 **Your Stats**

👤 **Account:**
• Plan: {plan.name if plan else 'Free'}

📈 **Today's Usage:**
• Signals: {signals_used}/{signals_limit if signals_limit != 999 else '∞'} ({signals_remaining} remaining)
"""
        
        await query.message.reply_text(stats_text, parse_mode="Markdown")
        
    finally:
        db.close()


async def help_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help from callback query."""
    help_text = """
📖 **Underdog Signals Help**

**What is this?**
I analyze sports props using Monte Carlo simulation (10,000 iterations) and AI to find high-probability plays for Underdog Pick'em.

**Tier System:**
🔥 SLAM (85%+) - Highest confidence
💪 STRONG (70-85%) - High confidence
📊 LEAN (60-70%) - Moderate confidence

**Commands:**
/menu - Show main menu
/signals - Get today's picks
/results - View recent performance
/subscribe - Upgrade options
/stats - Your usage stats
/help - This message

**Questions?**
Contact @YourSupportHandle

Good luck! 🍀
"""
    await update.callback_query.message.reply_text(
        help_text, 
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to broadcast message to all users."""
    if str(update.effective_user.id) not in ADMIN_TELEGRAM_IDS:
        await update.message.reply_text("⛔ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    db = get_db()
    
    try:
        users = db.execute(
            select(User).where(User.telegram_id.isnot(None))
        ).scalars().all()
        
        sent = 0
        failed = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"📢 **Announcement**\n\n{message}",
                    parse_mode="Markdown",
                )
                sent += 1
                await asyncio.sleep(0.1)  # Rate limit
            except Exception:
                failed += 1
        
        await update.message.reply_text(
            f"✅ Broadcast complete: {sent} sent, {failed} failed"
        )
        
    finally:
        db.close()


async def admin_push_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to push signals to all subscribers (Pro-level access for 3 days)."""
    if str(update.effective_user.id) not in ADMIN_TELEGRAM_IDS:
        await update.message.reply_text("⛔ Admin only command.")
        return
    
    db = get_db()
    
    try:
        # Load signals
        signals = load_latest_signals()
        if not signals:
            await update.message.reply_text("No signals to push.")
            return
        
        # Get ALL users (including free tier) - 3 DAY PRO PROMO
        subscribers = db.execute(
            select(User).where(User.telegram_id.isnot(None))
        ).scalars().all()
        
        sent = 0
        free_users = 0
        
        # Send ALL signals to each user (PRO LEVEL ACCESS - 3 DAY PROMO)
        top_signals = signals  # Send ALL signals instead of just top 3
        
        header = f"""🔔 **New Signals Alert!**
📅 {date.today().strftime('%B %d, %Y')}
🎁 **3-DAY PRO ACCESS** - Full probabilities & AI analysis!
📊 {len(top_signals)} Premium Picks
{"─" * 20}"""
        
        for user in subscribers:
            try:
                plan, _ = get_user_plan(db, user)
                is_free = plan.tier == PlanTier.FREE if plan else True
                
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=header,
                    parse_mode="Markdown",
                )
                
                for signal in top_signals:
                    # EVERYONE gets Pro-level access (probabilities + AI notes)
                    msg = format_signal(
                        signal,
                        show_probability=True,  # Force Pro access
                        show_notes=True,        # Force Pro access
                    )
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=msg,
                        parse_mode="Markdown",
                    )
                    await asyncio.sleep(0.3)
                
                sent += 1
                if is_free:
                    free_users += 1
                
            except Exception as e:
                logger.error(f"Failed to send to {user.telegram_id}: {e}")
        
        await update.message.reply_text(
            f"✅ Pushed {len(top_signals)} PRO signals to {sent} users ({free_users} free tier getting 3-day trial)"
        )
        
    finally:
        db.close()


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    
    # Initialize database
    Base.metadata.create_all(bind=engine)
    
    # Seed plans if needed
    db = get_db()
    try:
        from ufa.models.user import seed_plans
        seed_plans(db)
    finally:
        db.close()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("signals", signals_command))
    app.add_handler(CommandHandler("results", results_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Callback query handler for menu buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Admin commands
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("push", admin_push_signals))
    
    # Start bot
    logger.info("Starting Telegram bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
