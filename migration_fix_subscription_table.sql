-- Migration: Fix stripe_subscriptions table to add missing columns
-- Run this script to add plan_name and billing_cycle columns

-- Add plan_name column
ALTER TABLE stripe_subscriptions ADD COLUMN IF NOT EXISTS plan_name VARCHAR(50);

-- Add billing_cycle column  
ALTER TABLE stripe_subscriptions ADD COLUMN IF NOT EXISTS billing_cycle VARCHAR(20);

-- Update user_id column type to match users table
ALTER TABLE stripe_subscriptions ALTER COLUMN user_id TYPE VARCHAR(255);

-- Verify the migration
\d stripe_subscriptions;