-- Migration to add password authentication support
-- Add password_hash column to users table for email/password authentication

ALTER TABLE users ADD COLUMN IF NOT EXISTS "password_hash" TEXT;

-- Add index on identifier for faster lookups during authentication
CREATE INDEX IF NOT EXISTS idx_users_identifier ON users("identifier");

-- Optional: Add email constraint validation (identifier should be email for password auth)
-- This is handled in application logic instead of database constraints