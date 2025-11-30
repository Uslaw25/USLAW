-- Migration: Add message_count column to users table
-- Run this script on existing databases to add the new column

ALTER TABLE users ADD COLUMN IF NOT EXISTS "message_count" INTEGER DEFAULT 0;

-- Update existing users to have 0 message count
UPDATE users SET "message_count" = 0 WHERE "message_count" IS NULL;

-- Verify the migration
SELECT COUNT(*) as total_users, 
       COUNT("message_count") as users_with_count 
FROM users;