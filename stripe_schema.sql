-- ===========================================================
--  USERS (Your app users)
-- ===========================================================
-- CREATE TABLE users (
--     id SERIAL PRIMARY KEY,
--     email VARCHAR(255) UNIQUE NOT NULL,
--     name VARCHAR(255),
--     created_at TIMESTAMP DEFAULT NOW()
-- );

-- ===========================================================
--  STRIPE CUSTOMERS (map users → stripe customers)
-- ===========================================================
CREATE TABLE stripe_customers (
    id SERIAL PRIMARY KEY,
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    stripe_customer_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);


-- ===========================================================
--  STRIPE PRODUCTS
-- ===========================================================
CREATE TABLE stripe_products (
    id SERIAL PRIMARY KEY,
    stripe_product_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE PRICES (Monthly, Yearly, etc.)
-- ===========================================================
CREATE TABLE stripe_prices (
    id SERIAL PRIMARY KEY,
    stripe_price_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_product_id VARCHAR(255) NOT NULL REFERENCES stripe_products(stripe_product_id) ON DELETE CASCADE,
    interval VARCHAR(50),                -- month / year
    unit_amount INTEGER NOT NULL,        -- cents
    currency VARCHAR(20) DEFAULT 'usd',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE SUBSCRIPTIONS
-- ===========================================================
CREATE TABLE stripe_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) NOT NULL REFERENCES stripe_customers(stripe_customer_id),
    stripe_price_id VARCHAR(255) NOT NULL REFERENCES stripe_prices(stripe_price_id),
    status VARCHAR(50) NOT NULL,                         -- active, past_due, canceled, trialing
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE INVOICES
-- ===========================================================
CREATE TABLE stripe_invoices (
    id SERIAL PRIMARY KEY,
    stripe_invoice_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) NOT NULL REFERENCES stripe_customers(stripe_customer_id),
    stripe_subscription_id VARCHAR(255) REFERENCES stripe_subscriptions(stripe_subscription_id),
    amount_due INTEGER NOT NULL,
    amount_paid INTEGER,
    currency VARCHAR(20) DEFAULT 'usd',
    status VARCHAR(50),                          -- paid, open, void
    invoice_pdf TEXT,
    hosted_invoice_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE PAYMENT INTENTS
-- ===========================================================
CREATE TABLE stripe_payment_intents (
    id SERIAL PRIMARY KEY,
    stripe_payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) REFERENCES stripe_customers(stripe_customer_id),
    amount INTEGER NOT NULL,
    currency VARCHAR(20) DEFAULT 'usd',
    status VARCHAR(50),                          -- succeeded, canceled, requires_payment_method
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================
--  STRIPE WEBHOOK EVENTS (For logs and debugging)
-- ===========================================================
CREATE TABLE stripe_events (
    id SERIAL PRIMARY KEY,
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(255) NOT NULL,                   -- invoice.payment_succeeded etc.
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
