"""SQLite database models for user subscriptions and tier access."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/subscribers.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    """Initialize database tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            stripe_customer_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Subscriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            stripe_subscription_id TEXT UNIQUE,
            tier TEXT NOT NULL,
            status TEXT NOT NULL,
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            cancel_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Access log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            resource TEXT NOT NULL,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    conn.close()


class User:
    @staticmethod
    def create(email: str, stripe_customer_id: str) -> str:
        """Create new user."""
        import uuid
        user_id = str(uuid.uuid4())
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO users (id, email, stripe_customer_id) VALUES (?, ?, ?)",
                (user_id, email, stripe_customer_id)
            )
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            # User already exists
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email: str) -> Optional[dict]:
        """Get user by email."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, stripe_customer_id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"id": row[0], "email": row[1], "stripe_customer_id": row[2]}
        return None

    @staticmethod
    def get_by_id(user_id: str) -> Optional[dict]:
        """Get user by ID."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, stripe_customer_id FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"id": row[0], "email": row[1], "stripe_customer_id": row[2]}
        return None


class Subscription:
    @staticmethod
    def create(
        user_id: str,
        stripe_subscription_id: str,
        tier: str,
        current_period_start: datetime,
        current_period_end: datetime,
    ) -> str:
        """Create subscription."""
        import uuid
        sub_id = str(uuid.uuid4())
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO subscriptions 
               (id, user_id, stripe_subscription_id, tier, status, current_period_start, current_period_end)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, user_id, stripe_subscription_id, tier, "active", current_period_start, current_period_end)
        )
        conn.commit()
        conn.close()
        return sub_id

    @staticmethod
    def get_active_by_user(user_id: str) -> Optional[dict]:
        """Get active subscription for user."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, user_id, stripe_subscription_id, tier, status, current_period_end 
               FROM subscriptions WHERE user_id = ? AND status = 'active'
               ORDER BY current_period_end DESC LIMIT 1""",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "stripe_subscription_id": row[2],
                "tier": row[3],
                "status": row[4],
                "current_period_end": row[5],
            }
        return None

    @staticmethod
    def update_status(stripe_subscription_id: str, status: str, cancel_at: Optional[datetime] = None):
        """Update subscription status."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if cancel_at:
            cursor.execute(
                "UPDATE subscriptions SET status = ?, cancel_at = ? WHERE stripe_subscription_id = ?",
                (status, cancel_at, stripe_subscription_id)
            )
        else:
            cursor.execute(
                "UPDATE subscriptions SET status = ? WHERE stripe_subscription_id = ?",
                (status, stripe_subscription_id)
            )
        
        conn.commit()
        conn.close()

    @staticmethod
    def get_tier(user_id: str) -> Optional[str]:
        """Get user's current tier (None if no active subscription)."""
        sub = Subscription.get_active_by_user(user_id)
        return sub["tier"] if sub else None


class AccessLog:
    @staticmethod
    def record(user_id: str, resource: str):
        """Record resource access."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO access_logs (user_id, resource) VALUES (?, ?)",
            (user_id, resource)
        )
        conn.commit()
        conn.close()


# Initialize on import
init_db()
