"""
Database migration script to initialize Stripe subscription schema.
This script ensures all required Stripe tables exist with proper indexes and constraints.
"""

import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from chainlit.logger import logger

load_dotenv()

STRIPE_SCHEMA_SQL = """
-- ===========================================================
--  STRIPE CUSTOMERS (map users → stripe customers)
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_customers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE PRODUCTS
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_products (
    id SERIAL PRIMARY KEY,
    stripe_product_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE PRICES (Monthly, Yearly, etc.)
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_prices (
    id SERIAL PRIMARY KEY,
    stripe_price_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_product_id VARCHAR(255) NOT NULL,
    interval VARCHAR(50),                -- month / year
    unit_amount INTEGER NOT NULL,        -- cents
    currency VARCHAR(20) DEFAULT 'usd',
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (stripe_product_id) REFERENCES stripe_products(stripe_product_id) ON DELETE CASCADE
);

-- ===========================================================
--  STRIPE SUBSCRIPTIONS
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) NOT NULL,
    stripe_price_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,                         -- active, past_due, canceled, trialing
    plan_name VARCHAR(50),                               -- Pro, Premium, etc.
    billing_cycle VARCHAR(20),                           -- monthly, yearly
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (stripe_customer_id) REFERENCES stripe_customers(stripe_customer_id) ON DELETE CASCADE,
    FOREIGN KEY (stripe_price_id) REFERENCES stripe_prices(stripe_price_id) ON DELETE CASCADE
);

-- ===========================================================
--  STRIPE INVOICES
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_invoices (
    id SERIAL PRIMARY KEY,
    stripe_invoice_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) NOT NULL,
    stripe_subscription_id VARCHAR(255),
    amount_due INTEGER NOT NULL,
    amount_paid INTEGER,
    currency VARCHAR(20) DEFAULT 'usd',
    status VARCHAR(50),                          -- paid, open, void
    invoice_pdf TEXT,
    hosted_invoice_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (stripe_customer_id) REFERENCES stripe_customers(stripe_customer_id) ON DELETE CASCADE,
    FOREIGN KEY (stripe_subscription_id) REFERENCES stripe_subscriptions(stripe_subscription_id) ON DELETE SET NULL
);

-- ===========================================================
--  STRIPE PAYMENT INTENTS
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_payment_intents (
    id SERIAL PRIMARY KEY,
    stripe_payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255),
    amount INTEGER NOT NULL,
    currency VARCHAR(20) DEFAULT 'usd',
    status VARCHAR(50),                          -- succeeded, canceled, requires_payment_method
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (stripe_customer_id) REFERENCES stripe_customers(stripe_customer_id) ON DELETE SET NULL
);

-- ===========================================================
--  STRIPE WEBHOOK EVENTS (For logs and debugging)
-- ===========================================================
CREATE TABLE IF NOT EXISTS stripe_events (
    id SERIAL PRIMARY KEY,
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(255) NOT NULL,                   -- invoice.payment_succeeded etc.
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

INDEXES_SQL = """
-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_stripe_customers_user_id ON stripe_customers(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_customers_stripe_id ON stripe_customers(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_user_id ON stripe_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_customer_id ON stripe_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_status ON stripe_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_stripe_id ON stripe_subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_stripe_invoices_customer_id ON stripe_invoices(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_stripe_invoices_subscription_id ON stripe_invoices(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_stripe_events_type ON stripe_events(type);
CREATE INDEX IF NOT EXISTS idx_stripe_events_created_at ON stripe_events(created_at);
"""

SAMPLE_DATA_SQL = """
-- Insert sample Stripe products (Pro Plan)
INSERT INTO stripe_products (stripe_product_id, name, created_at) 
VALUES ('prod_sample_pro', 'Pro Plan', NOW())
ON CONFLICT (stripe_product_id) DO NOTHING;

-- Insert sample prices for Pro Plan
INSERT INTO stripe_prices (stripe_price_id, stripe_product_id, interval, unit_amount, currency, created_at)
VALUES 
    ('price_sample_monthly', 'prod_sample_pro', 'month', 3900, 'usd', NOW()),
    ('price_sample_yearly', 'prod_sample_pro', 'year', 46800, 'usd', NOW())
ON CONFLICT (stripe_price_id) DO NOTHING;
"""


async def run_migration():
    """Run the Stripe schema migration"""
    conninfo = os.environ.get("DATABASE_URL")
    if not conninfo:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Ensure asyncpg driver is used
    if "postgresql" in conninfo and "+asyncpg" not in conninfo:
        conninfo = conninfo.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(conninfo)
    
    try:
        async with engine.begin() as conn:
            logger.info("Creating Stripe tables...")
            await conn.execute(text(STRIPE_SCHEMA_SQL))
            
            logger.info("Creating performance indexes...")
            await conn.execute(text(INDEXES_SQL))
            
            logger.info("Inserting sample data...")
            await conn.execute(text(SAMPLE_DATA_SQL))
            
            logger.info("✅ Stripe schema migration completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())