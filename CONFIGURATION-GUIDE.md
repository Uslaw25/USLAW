# Message Limit Configuration Guide

## Overview

The message limit system is now fully configurable via environment variables, making it easy to adjust limits for different environments without code changes.

## Quick Setup

Add this to your `.env` file:

```bash
# Message limit for free users (default: 20)
FREE_USER_MESSAGE_LIMIT=20
```

## Configuration Examples

### Development Environment
```bash
# Higher limit for testing
FREE_USER_MESSAGE_LIMIT=100
```

### Staging Environment  
```bash
# Medium limit for pre-production testing
FREE_USER_MESSAGE_LIMIT=30
```

### Production Environment
```bash
# Standard limit to drive conversions
FREE_USER_MESSAGE_LIMIT=20
```

### Strict Production
```bash
# Lower limit for aggressive conversion targeting
FREE_USER_MESSAGE_LIMIT=10
```

## How It Works

### Backend Components

1. **Configuration Loading** (`app.py`, `main.py`):
   ```python
   FREE_USER_MESSAGE_LIMIT = int(os.environ.get("FREE_USER_MESSAGE_LIMIT", "20"))
   ```

2. **Dynamic Thresholds**:
   - **Warning**: Shows at 75% of limit (e.g., 15/20 messages)
   - **Blocking**: Enforced at 100% of limit
   - **Messages**: All text uses dynamic limit values

### Frontend Components

1. **MessageUsageCounter**: 
   - Gets limit from API dynamically
   - Calculates warning threshold automatically (75% of limit)
   - Progress bar adapts to any limit value

2. **UpgradeRequiredModal**:
   - Shows actual message count from API
   - No hardcoded values

## Benefits

✅ **No Code Deployment**: Change limits by updating env var and restarting  
✅ **Environment-Specific**: Different limits for dev/staging/prod  
✅ **A/B Testing**: Easy to test different conversion thresholds  
✅ **Automatic Scaling**: All UI components adapt to new limits  
✅ **Backward Compatible**: Defaults to 20 if not set  

## Testing Different Limits

### Test with 5 Messages
```bash
FREE_USER_MESSAGE_LIMIT=5
```
- Warning at message 4 (75% = 3.75, rounded up to 4)
- Blocked at message 5

### Test with 10 Messages  
```bash
FREE_USER_MESSAGE_LIMIT=10
```
- Warning at message 8 (75% = 7.5, rounded up to 8)
- Blocked at message 10

### Test with 50 Messages
```bash
FREE_USER_MESSAGE_LIMIT=50  
```
- Warning at message 38 (75% = 37.5, rounded up to 38)
- Blocked at message 50

## Deployment

1. **Update Environment Variable**:
   ```bash
   echo "FREE_USER_MESSAGE_LIMIT=30" >> .env
   ```

2. **Restart Services**:
   ```bash
   # Restart your application
   docker-compose restart  # or equivalent
   ```

3. **Verify Configuration**:
   - Check application logs for loaded config
   - Test with a free user account
   - Verify warning and blocking thresholds

## Monitoring

Track these metrics after changing limits:
- Conversion rate at different thresholds
- User engagement vs. limit strictness  
- Support requests related to limits
- Revenue impact from limit changes

## Rollback

If needed, quickly rollback by:
1. Changing environment variable back
2. Restarting application
3. No code deployment required