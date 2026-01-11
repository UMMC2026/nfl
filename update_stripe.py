"""Update plans with Stripe Price IDs."""
from dotenv import load_dotenv
load_dotenv()

from ufa.db import SessionLocal
from ufa.models.user import seed_plans

db = SessionLocal()
seed_plans(db)
print("✓ Plans updated with Stripe Price IDs!")

# Verify
from sqlalchemy import select
from ufa.models.user import Plan

plans = db.execute(select(Plan)).scalars().all()
for p in plans:
    print(f"  {p.name}: ${p.price_cents/100:.2f} → {p.stripe_price_id or 'N/A'}")

db.close()
