-- Migration to add default USER role to existing users
-- This script updates all users who don't have a role in their metadata

-- Update users where metadata doesn't contain 'role' key
UPDATE users 
SET "metadata" = jsonb_set(
    CASE 
        WHEN "metadata"::text = 'null' OR "metadata" IS NULL THEN '{}'::jsonb
        ELSE "metadata"::jsonb
    END,
    '{role}',
    '"USER"'
)
WHERE 
    -- Only update users who don't already have a role
    (
        "metadata" IS NULL 
        OR "metadata"::text = 'null'
        OR NOT ("metadata"::jsonb ? 'role')
    );

-- Display results
SELECT 
    COUNT(*) as total_users,
    COUNT(CASE WHEN "metadata"::jsonb ? 'role' THEN 1 END) as users_with_roles,
    COUNT(CASE WHEN "metadata"::jsonb->>'role' = 'USER' THEN 1 END) as users_with_user_role,
    COUNT(CASE WHEN "metadata"::jsonb->>'role' = 'ADMIN' THEN 1 END) as users_with_admin_role
FROM users;