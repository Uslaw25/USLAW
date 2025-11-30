# Stripe Subscription Setup

This document provides setup instructions for the Stripe subscription integration with your Chainlit application.

## Prerequisites

- PostgreSQL database
- Stripe account with test/live API keys
- Chainlit application with OAuth authentication

## Setup Instructions

### 1. Install Dependencies

```bash
pip install stripe fastapi[standard] sqlalchemy[asyncio] asyncpg
```

### 2. Environment Configuration

Copy the `.env.example` file to `.env` and update with your values:

```bash
cp .env.example .env
```

Required environment variables:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/dbname

# Stripe
STRIPE_SECRET_KEY=sk_test_...  # Your Stripe secret key
STRIPE_WEBHOOK_SECRET=whsec_...  # Webhook signing secret (optional for development)
STRIPE_MONTHLY_PRICE_ID=price_...  # Monthly subscription price ID
STRIPE_YEARLY_PRICE_ID=price_...  # Yearly subscription price ID
```

### 3. Database Migration

Run the database migration to create Stripe tables:

```bash
python migrations/init_stripe_schema.py
```

This will create the following tables:
- `stripe_customers`
- `stripe_products` 
- `stripe_prices`
- `stripe_subscriptions`
- `stripe_invoices`
- `stripe_payment_intents`
- `stripe_events`

### 4. Create Stripe Products

1. Log into your Stripe Dashboard
2. Go to Products → Create Product
3. Create a "Pro Plan" product
4. Create two prices for the product:
   - Monthly: $39.00/month
   - Yearly: $468.00/year (saves $100/year)
5. Copy the price IDs to your environment variables

### 5. Configure Webhooks (Production)

For production, set up Stripe webhooks:

1. Go to Stripe Dashboard → Webhooks
2. Add endpoint: `https://yourdomain.com/api/stripe/webhook`
3. Select events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy the webhook signing secret to `STRIPE_WEBHOOK_SECRET`

## API Endpoints

The following API endpoints are available:

### Subscription Management
- `GET /api/subscription/status` - Get user subscription status
- `POST /api/subscription/create-checkout-session` - Create Stripe checkout session
- `POST /api/subscription/cancel` - Cancel subscription
- `POST /api/subscription/customer-portal` - Create customer portal session
- `GET /api/subscription/billing-history` - Get billing history

### Webhook Handler
- `POST /api/stripe/webhook` - Handle Stripe webhook events

## React Frontend Integration

### 1. Install Dependencies

```bash
# In your frontend directory
npm install @chainlit/react-client
```

### 2. Environment Variables

Add to your frontend `.env` file:

```env
REACT_APP_STRIPE_MONTHLY_PRICE_ID=price_...
REACT_APP_STRIPE_YEARLY_PRICE_ID=price_...
```

### 3. Usage in Components

```typescript
import { useSubscription } from '@chainlit/react-client';

function MyComponent() {
  const {
    subscription,
    isLoading,
    hasActiveSubscription,
    isProUser,
    planInfo,
    createCheckoutSession,
    cancelSubscription,
    createCustomerPortal,
    billingHistory
  } = useSubscription();

  const handleUpgrade = async () => {
    const { checkout_url } = await createCheckoutSession(
      'price_monthly',
      'https://yoursite.com/success',
      'https://yoursite.com/cancel'
    );
    window.location.href = checkout_url;
  };

  // Component logic...
}
```

## Dashboard Integration

The dashboard automatically shows subscription status and provides upgrade flows:

1. **Free Users**: See upgrade tab with plan selection
2. **Pro Users**: See subscription management and billing history
3. **Billing History**: Automatic invoice download/view links
4. **Customer Portal**: Direct integration with Stripe's hosted portal

## Testing

### Test with Stripe Test Cards

Use Stripe's test cards for testing:

- Success: `4242 4242 4242 4242`
- Declined: `4000 0000 0000 0002`
- Requires 3D Secure: `4000 0025 0000 3155`

### Test Webhook Events

Use Stripe CLI to forward webhook events to localhost:

```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook
```

## Security Notes

1. **Environment Variables**: Never commit real API keys to version control
2. **Webhook Signatures**: Always verify webhook signatures in production
3. **HTTPS**: Use HTTPS in production for all Stripe interactions
4. **PCI Compliance**: Stripe handles PCI compliance for payment processing

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Check DATABASE_URL format: `postgresql+asyncpg://user:pass@host:port/db`

### Stripe API Errors
- Verify API keys are correct (test vs live)
- Check Stripe Dashboard for webhook delivery status
- Ensure webhook endpoint is accessible

### Frontend Integration Issues
- Check browser console for API errors
- Verify CORS settings in main.py
- Ensure user is authenticated when calling subscription endpoints

## Support

For issues specific to this integration:
1. Check Stripe Dashboard for webhook delivery logs
2. Review application logs for API errors
3. Verify database tables were created correctly
4. Test API endpoints directly with curl/Postman

For Stripe-specific issues, consult the [Stripe Documentation](https://stripe.com/docs).