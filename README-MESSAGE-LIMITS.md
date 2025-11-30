# Message Limits for Free Users

This feature implements a 20-message limit for free users across all chat threads to encourage upgrades to paid plans.

## Overview

Free users are limited to 20 messages total across all chat threads. When they reach this limit, they're prompted to upgrade to continue using the service.

## Architecture

### Backend Implementation

1. **Database Schema** (`default_schema.sql`, `migration_add_message_count.sql`)
   - Added `message_count` column to users table
   - Defaults to 0 for all users

2. **Data Layer** (`sql_data_layer.py`)
   - `get_user_message_count()` - Get current count
   - `increment_user_message_count()` - Increment after message
   - `reset_user_message_count()` - Reset to 0 on upgrade
   - `check_user_message_limit()` - Check if user can send more messages

3. **Message Handler** (`app.py`)
   - Pre-message: Check if user has remaining messages
   - Post-message: Increment count for non-admin users
   - Block messages at 20 limit with upgrade prompt

4. **API Endpoints** (`main.py`)
   - `GET /chat/api/usage/status` - Get current usage status
   - `POST /chat/api/subscription/reset-message-count` - Reset count on upgrade

### Frontend Implementation

1. **MessageUsageCounter** (`MessageUsageCounter.tsx`)
   - Shows "X/20 messages used" for free users
   - Warning state at 15+ messages
   - Auto-refreshes every 5 seconds
   - Hidden for pro users

2. **UpgradeRequiredModal** (`UpgradeRequiredModal.tsx`)
   - Triggered when limit is reached
   - Shows upgrade benefits and pricing
   - Direct link to upgrade flow

3. **Integration** (`chat/index.tsx`, `header/index.tsx`)
   - Usage counter in header center area
   - Modal integrated into chat component
   - Auto-triggers on limit reached

## User Experience Flow

### Free User Journey
1. **Messages 1-14**: Silent counting, usage counter visible in header
2. **Messages 15-19**: Warning indicators, upgrade suggestions appear
3. **Message 20**: Final message processed, then usage limit enforced
4. **Limit Reached**: Modal blocks further messages with clear upgrade path

### Admin Users
- No message limits applied
- All limiting logic is bypassed

### Subscription Integration
- Pro users: No limits, counter hidden
- On upgrade: Message count automatically reset to 0
- Subscription status checked in real-time

## Key Features

✅ **Cross-thread counting**: Counts messages across all chat conversations  
✅ **Real-time updates**: Counter updates immediately after each message  
✅ **Graceful degradation**: Clear upgrade path when limit reached  
✅ **Admin bypass**: No restrictions for admin users  
✅ **Automatic reset**: Count resets to 0 when user upgrades  
✅ **Visual feedback**: Progress bar and warning states  

## Database Migration

For existing deployments, run the migration:

```sql
-- Run this on your database
\i migration_add_message_count.sql
```

Or manually:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS "message_count" INTEGER DEFAULT 0;
UPDATE users SET "message_count" = 0 WHERE "message_count" IS NULL;
```

## Configuration

The message limit is configurable via environment variable:

### Environment Variable
```bash
# Set in your .env file
FREE_USER_MESSAGE_LIMIT=20  # Default: 20 messages
```

### Examples
```bash
# For development with higher limits
FREE_USER_MESSAGE_LIMIT=50

# For production with strict limits  
FREE_USER_MESSAGE_LIMIT=10

# Default behavior (if not set)
# Defaults to 20 messages
```

### Dynamic Behavior
- **Warning Threshold**: Automatically calculated at 75% of limit
- **Frontend**: UI components adapt to any limit value
- **Backend**: All endpoints use the configured limit
- **No Code Changes**: Just update environment variable and restart

## Testing

Test the flow:

1. Create a free user account
2. Send 15+ messages to see warnings
3. Send 20+ messages to trigger modal
4. Upgrade to pro plan
5. Verify count resets and limits are removed

## Error Handling

- Database errors are logged but don't block chat
- Failed count increments are logged for monitoring  
- Network errors in frontend gracefully degrade
- Missing usage data defaults to allowing messages

## Monitoring

Monitor these metrics:
- Message count distribution across users
- Upgrade conversion rate from limit-reached state
- Failed message count operations
- Usage API response times