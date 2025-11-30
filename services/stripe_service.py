"""
Stripe Service for subscription management.

This service handles all Stripe API interactions including:
- Creating customers and checkout sessions
- Managing subscriptions and invoices
- Processing webhook events
- Syncing data with local database
"""

import os
import stripe
from typing import Dict, Optional, List, Any
from datetime import datetime
from fastapi import HTTPException
from chainlit.logger import logger

# Initialize Stripe with secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class StripeService:
    def __init__(self, data_layer):
        """Initialize Stripe service with data layer for database operations"""
        self.data_layer = data_layer
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        # Product and price configuration
        self.MONTHLY_PRICE_ID = os.getenv("STRIPE_MONTHLY_PRICE_ID", "price_1SWMauSBcaUtv6fpCztlUeM3")
        self.YEARLY_PRICE_ID = os.getenv("STRIPE_YEARLY_PRICE_ID", "price_1SWMauSBcaUtv6fpDXIFPJ4T")
        
    async def create_or_get_customer(self, user_id: str, email: str, name: str = None) -> str:
        """Create a new Stripe customer or get existing one"""
        try:
            # Check if customer already exists in our database
            existing_customer_id = await self.data_layer.get_stripe_customer(user_id)
            if existing_customer_id:
                # Verify customer exists in Stripe
                try:
                    stripe.Customer.retrieve(existing_customer_id)
                    return existing_customer_id
                except stripe.error.InvalidRequestError:
                    logger.warning(f"Stripe customer {existing_customer_id} not found in Stripe, creating new one")
            
            # Create new Stripe customer
            customer_data = {"email": email}
            if name:
                customer_data["name"] = name
                
            stripe_customer = stripe.Customer.create(**customer_data)
            
            # Store in our database
            await self.data_layer.create_stripe_customer(user_id, stripe_customer.id)
            
            logger.info(f"Created Stripe customer {stripe_customer.id} for user {user_id}")
            return stripe_customer.id
            
        except Exception as e:
            logger.error(f"Error creating Stripe customer for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create customer")

    async def create_checkout_session(
        self, 
        user_id: str, 
        email: str, 
        price_id: str,
        success_url: str,
        cancel_url: str,
        name: str = None,
        apply_discount: bool = False
    ) -> str:
        """Create a Stripe checkout session for subscription"""
        try:
            # Ensure customer exists
            customer_id = await self.create_or_get_customer(user_id, email, name)
            
            # Prepare checkout session parameters
            session_params = {
                "mode": "subscription",
                "customer": customer_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "billing_address_collection": "required",
                "line_items": [{
                    "price": price_id,
                    "quantity": 1,
                }],
                "metadata": {
                    "user_id": user_id
                }
            }
            
            # Apply 20% discount for yearly plans
            if apply_discount:
                try:
                    # Create a coupon for first year 20% discount
                    coupon = stripe.Coupon.create(
                        percent_off=20,
                        duration="once",
                        name="20% off first year",
                        metadata={
                            "description": "Save 20% on your first year of Pro subscription"
                        }
                    )
                    session_params["discounts"] = [{"coupon": coupon.id}]
                    logger.info(f"Applied 20% first-year discount coupon {coupon.id} to checkout session")
                except Exception as e:
                    logger.warning(f"Failed to apply discount to checkout: {e}")
            else:
                # Only allow promotion codes if we're not applying a discount
                session_params["allow_promotion_codes"] = True
            
            # Create checkout session
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created checkout session {session.id} for user {user_id}")
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating checkout session for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create checkout session")

    async def create_customer_portal_session(self, user_id: str, return_url: str) -> str:
        """Create a Stripe customer portal session for subscription management"""
        try:
            customer_id = await self.data_layer.get_stripe_customer(user_id)
            if not customer_id:
                raise HTTPException(status_code=404, detail="Customer not found")
            
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            
            logger.info(f"Created customer portal session for user {user_id}")
            return session.url
            
        except Exception as e:
            logger.error(f"Error creating customer portal session for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create customer portal session")

    async def get_subscription_status(self, user_id: str) -> Dict[str, Any]:
        """Get current subscription status for a user"""
        try:
            subscription = await self.data_layer.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    "status": "free",
                    "plan": "Free",
                    "billing_cycle": None,
                    "current_period_end": None,
                    "cancel_at_period_end": False
                }
            
            return {
                "status": subscription["status"],
                "plan": subscription["product_name"],
                "billing_cycle": subscription["billing_cycle"],
                "current_period_end": subscription["current_period_end"].isoformat() if subscription["current_period_end"] else None,
                "cancel_at_period_end": subscription["cancel_at_period_end"],
                "amount": subscription["amount_cents"] / 100,  # Convert cents to dollars
                "currency": subscription["currency"]
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription status for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to get subscription status")

    async def sync_subscription_from_stripe(self, user_id: str) -> bool:
        """Manually sync subscription status from Stripe (for debugging)"""
        try:
            # Get user's subscription from database
            subscription = await self.data_layer.get_user_subscription(user_id)
            if not subscription:
                logger.info(f"No subscription found for user {user_id}")
                return False
            
            stripe_subscription_id = subscription["stripe_subscription_id"]
            
            # Fetch current status from Stripe
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            
            cancel_at = getattr(stripe_subscription, 'cancel_at', None)
            cancel_at_period_end = getattr(stripe_subscription, 'cancel_at_period_end', False)
            
            # If subscription has a cancel_at date, it should be considered as cancelled
            if cancel_at and not cancel_at_period_end:
                cancel_at_period_end = True
                logger.info(f"Subscription {stripe_subscription_id} has cancel_at date {cancel_at}, treating as cancel_at_period_end=True")
            
            logger.info(f"Stripe subscription {stripe_subscription_id} current status: {stripe_subscription.status}")
            logger.info(f"Cancel at period end: {cancel_at_period_end}")
            logger.info(f"Cancel at: {cancel_at}")
            logger.info(f"Current period start: {getattr(stripe_subscription, 'current_period_start', None)}")
            logger.info(f"Current period end: {getattr(stripe_subscription, 'current_period_end', None)}")
            
            # Safely convert timestamps
            period_start = None
            period_end = None
            
            if hasattr(stripe_subscription, 'current_period_start') and stripe_subscription.current_period_start:
                period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
                
            if hasattr(stripe_subscription, 'current_period_end') and stripe_subscription.current_period_end:
                period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            
            # Update local database
            await self.data_layer.update_subscription_status(
                stripe_subscription_id,
                stripe_subscription.status,
                period_start,
                period_end,
                cancel_at_period_end,
                None  # Don't update price_id in sync operations
            )
            
            logger.info(f"Updated local subscription {stripe_subscription_id} to match Stripe")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing subscription from Stripe: {e}")
            return False

    async def cancel_subscription(self, user_id: str, cancel_immediately: bool = False) -> bool:
        """Cancel user subscription"""
        try:
            subscription = await self.data_layer.get_user_subscription(user_id)
            if not subscription:
                raise HTTPException(status_code=404, detail="No active subscription found")
            
            stripe_subscription_id = subscription["stripe_subscription_id"]
            
            if cancel_immediately:
                # Cancel immediately
                stripe.Subscription.delete(stripe_subscription_id)
                await self.data_layer.update_subscription_status(
                    stripe_subscription_id, 
                    "canceled",
                    cancel_at_period_end=False
                )
            else:
                # Cancel at period end
                stripe.Subscription.modify(
                    stripe_subscription_id,
                    cancel_at_period_end=True
                )
                await self.data_layer.cancel_subscription(user_id, cancel_at_period_end=True)
            
            logger.info(f"Cancelled subscription {stripe_subscription_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling subscription for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to cancel subscription")

    async def modify_subscription(self, user_id: str, new_price_id: str, apply_discount: bool = False) -> Dict[str, Any]:
        """Modify existing subscription with automatic proration and optional discount"""
        try:
            # Get current subscription
            subscription = await self.data_layer.get_user_subscription(user_id)
            if not subscription:
                # No existing subscription, create new checkout session instead
                return await self._create_new_subscription(user_id, new_price_id, apply_discount)
            
            stripe_subscription_id = subscription["stripe_subscription_id"]
            current_price_id = subscription["stripe_price_id"]
            
            # Check if this is actually a change
            if current_price_id == new_price_id:
                return {"success": True, "message": "Already on the selected plan"}
            
            logger.info(f"Modifying subscription {stripe_subscription_id} from {current_price_id} to {new_price_id}")
            
            # Get the subscription from Stripe with expanded items
            stripe_subscription = stripe.Subscription.retrieve(
                stripe_subscription_id,
                expand=['items']
            )
            
            # Get the current subscription item
            # Access items from the expanded subscription
            if 'items' not in stripe_subscription:
                raise HTTPException(status_code=400, detail="Subscription items not found")
            
            items = stripe_subscription['items']
            if not items or not items.data:
                raise HTTPException(status_code=400, detail="No subscription items data found")
            
            subscription_item_id = items.data[0].id
            logger.info(f"Found subscription item: {subscription_item_id}")
            
            # Get current and new price details to check interval change
            current_price = stripe.Price.retrieve(current_price_id)
            new_price = stripe.Price.retrieve(new_price_id)
            
            # Create modification parameters with automatic proration
            modification_params = {
                "items": [{
                    "id": subscription_item_id,
                    "price": new_price_id,
                }],
                "proration_behavior": "always_invoice",  # This handles automatic proration
            }
            
            # Only set billing_cycle_anchor to unchanged if intervals are the same
            if current_price.recurring.interval == new_price.recurring.interval:
                modification_params["billing_cycle_anchor"] = "unchanged"
                logger.info(f"Keeping billing cycle unchanged (same interval: {current_price.recurring.interval})")
            else:
                logger.info(f"Changing billing interval from {current_price.recurring.interval} to {new_price.recurring.interval}")
                # For interval changes, let Stripe handle the billing cycle automatically
            
            # For flexible billing mode, we can't apply coupons directly to subscription modifications
            # Instead, we'll apply a discount as a separate invoice item after the modification
            discount_to_apply = None
            if apply_discount:
                logger.info("20% discount will be applied as a separate credit after subscription modification")
                discount_to_apply = 0.20  # 20% discount
            
            # Modify the subscription
            updated_subscription = stripe.Subscription.modify(
                stripe_subscription_id,
                **modification_params
            )
            
            # Apply discount as a separate invoice item if requested
            if discount_to_apply:
                try:
                    # Get the new price amount to calculate discount
                    new_price = stripe.Price.retrieve(new_price_id)
                    discount_amount = int(new_price.unit_amount * discount_to_apply)  # 20% of the new price
                    
                    # Create a credit invoice item for the discount
                    stripe.InvoiceItem.create(
                        customer=updated_subscription.customer,
                        amount=-discount_amount,  # Negative amount for credit
                        currency=new_price.currency,
                        description="20% discount for yearly subscription upgrade"
                    )
                    logger.info(f"Applied ${discount_amount/100:.2f} credit as 20% yearly discount")
                except Exception as e:
                    logger.warning(f"Failed to apply discount credit: {e}")
                    # Don't fail the whole operation if discount fails
            
            logger.info(f"Successfully modified subscription {stripe_subscription_id}")
            logger.info(f"New status: {updated_subscription.status}")
            
            # Update local database
            await self._update_local_subscription_from_stripe(updated_subscription)
            
            return {
                "success": True,
                "message": "Subscription updated successfully",
                "subscription_id": stripe_subscription_id
            }
            
        except Exception as e:
            logger.error(f"Error modifying subscription for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to modify subscription: {str(e)}")

    async def _create_new_subscription(self, user_id: str, price_id: str, apply_discount: bool = False) -> Dict[str, Any]:
        """Create a new subscription for users without existing subscription"""
        # For new subscriptions, redirect to checkout session
        # This could be enhanced to create the subscription directly, but checkout provides better UX
        return {
            "success": False,
            "message": "Please use the checkout flow for new subscriptions",
            "requires_checkout": True
        }
    
    async def _update_local_subscription_from_stripe(self, stripe_subscription) -> None:
        """Update local database from a Stripe subscription object"""
        try:
            subscription_id = stripe_subscription.id
            status = stripe_subscription.status
            
            # Get pricing details
            try:
                items = stripe_subscription.items()  # Call the method to get items
                if items and items.data:
                    price_id = items.data[0].price.id
                else:
                    logger.warning(f"No subscription items found for {subscription_id}")
                    price_id = None
            except Exception as e:
                logger.warning(f"Cannot get price_id from subscription {subscription_id}: {e}")
                price_id = None
            
            # Handle period dates
            period_start = None
            period_end = None
            
            if hasattr(stripe_subscription, 'current_period_start') and stripe_subscription.current_period_start:
                period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
                
            if hasattr(stripe_subscription, 'current_period_end') and stripe_subscription.current_period_end:
                period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            
            # Handle cancellation
            cancel_at_period_end = getattr(stripe_subscription, 'cancel_at_period_end', False)
            cancel_at = getattr(stripe_subscription, 'cancel_at', None)
            
            if cancel_at and not cancel_at_period_end:
                cancel_at_period_end = True
            
            # Update database
            await self.data_layer.update_subscription_status(
                subscription_id,
                status,
                period_start,
                period_end,
                cancel_at_period_end,
                None  # Don't update price_id here
            )
            
            logger.info(f"Updated local database for subscription {subscription_id}")
            
        except Exception as e:
            logger.error(f"Error updating local subscription data: {e}")
            raise

    async def get_billing_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get billing history for a user"""
        try:
            invoices = await self.data_layer.get_billing_history(user_id, limit)
            
            formatted_invoices = []
            for invoice in invoices:
                formatted_invoices.append({
                    "id": invoice["stripe_invoice_id"],
                    "amount": invoice["amount_due"] / 100,  # Convert cents to dollars
                    "currency": invoice["currency"],
                    "status": invoice["status"],
                    "date": invoice["created_at"],
                    "invoice_pdf": invoice["invoice_pdf"],
                    "hosted_invoice_url": invoice["hosted_invoice_url"]
                })
            
            return formatted_invoices
            
        except Exception as e:
            logger.error(f"Error getting billing history for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to get billing history")

    async def handle_webhook_event(self, event_data: Dict) -> bool:
        """Process Stripe webhook events"""
        try:
            event_type = event_data.get("type")
            event_id = event_data.get("id")
            
            # Store event for debugging - convert to JSON string for database storage
            import json
            payload_json = json.dumps(event_data, default=str)
            await self.data_layer.store_stripe_event(event_id, event_type, payload_json)
            
            # Process specific event types
            if event_type == "customer.subscription.created":
                await self._handle_subscription_created(event_data)
            elif event_type == "customer.subscription.updated":
                await self._handle_subscription_updated(event_data)
            elif event_type == "customer.subscription.deleted":
                await self._handle_subscription_deleted(event_data)
            elif event_type == "invoice.payment_succeeded":
                await self._handle_invoice_payment_succeeded(event_data)
            elif event_type == "invoice.payment_failed":
                await self._handle_invoice_payment_failed(event_data)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling webhook event {event_data.get('id')}: {e}")
            return False

    async def _handle_subscription_created(self, event_data: Dict):
        """Handle subscription.created webhook"""
        try:
            subscription = event_data["data"]["object"]
            customer_id = subscription["customer"]
            
            logger.info(f"Processing subscription.created webhook for subscription {subscription['id']}")
            
            # Get user_id from customer
            user_id = await self._get_user_id_from_customer(customer_id)
            if not user_id:
                logger.error(f"Could not find user for customer {customer_id}")
                return
            
            # Get price and product info
            price_id = subscription["items"]["data"][0]["price"]["id"]
            price_info = await self._get_price_info(price_id)
            
            # If price info is not found in database, create it from webhook data
            if not price_info:
                logger.info(f"Price {price_id} not found in database, creating from webhook data")
                await self._create_price_from_webhook_data(subscription["items"]["data"][0]["price"])
                price_info = await self._get_price_info(price_id)
            
            # Convert timestamps to datetime objects - use subscription item periods if subscription doesn't have them
            current_period_start = None
            current_period_end = None
            
            if "current_period_start" in subscription:
                current_period_start = datetime.fromtimestamp(subscription["current_period_start"])
            elif subscription["items"]["data"]:
                # Fall back to subscription item periods
                item = subscription["items"]["data"][0]
                if "current_period_start" in item:
                    current_period_start = datetime.fromtimestamp(item["current_period_start"])
            
            if "current_period_end" in subscription:
                current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
            elif subscription["items"]["data"]:
                # Fall back to subscription item periods
                item = subscription["items"]["data"][0]
                if "current_period_end" in item:
                    current_period_end = datetime.fromtimestamp(item["current_period_end"])
                    
            # Use start_date as fallback if periods are missing
            if not current_period_start and "start_date" in subscription:
                current_period_start = datetime.fromtimestamp(subscription["start_date"])
                
            logger.info(f"Subscription periods: start={current_period_start}, end={current_period_end}")
            
            logger.info(f"Creating subscription record for user {user_id} with subscription {subscription['id']}")
            
            await self.data_layer.create_subscription(
                user_id=user_id,
                stripe_subscription_id=subscription["id"],
                stripe_customer_id=customer_id,
                stripe_price_id=price_id,
                status=subscription["status"],
                plan_name=price_info.get("product_name", "Pro"),
                billing_cycle=price_info.get("interval", "month"),
                current_period_start=current_period_start,
                current_period_end=current_period_end
            )
            
            logger.info(f"Successfully created subscription {subscription['id']} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in _handle_subscription_created: {e}")
            raise

    async def _handle_subscription_updated(self, event_data: Dict):
        """Handle subscription.updated webhook"""
        try:
            subscription = event_data["data"]["object"]
            subscription_id = subscription["id"]
            new_status = subscription["status"]
            cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            cancel_at = subscription.get("cancel_at")
            
            # If subscription has a cancel_at date, it should be considered as cancelled
            if cancel_at and not cancel_at_period_end:
                cancel_at_period_end = True
                logger.info(f"Subscription {subscription_id} has cancel_at date {cancel_at}, treating as cancel_at_period_end=True")
            
            logger.info(f"Processing subscription.updated webhook for subscription {subscription_id}")
            logger.info(f"New status: {new_status}, cancel_at_period_end: {cancel_at_period_end}, cancel_at: {cancel_at}")
            
            # Get the new price_id from subscription items
            new_price_id = None
            if subscription.get("items", {}).get("data"):
                new_price_id = subscription["items"]["data"][0]["price"]["id"]
                logger.info(f"New price_id from webhook: {new_price_id}")
            
            # Convert timestamps to datetime objects with safe defaults
            current_period_start = None
            current_period_end = None
            
            if "current_period_start" in subscription:
                current_period_start = datetime.fromtimestamp(subscription["current_period_start"])
            elif subscription.get("items", {}).get("data"):
                # Fall back to subscription item periods
                item = subscription["items"]["data"][0]
                if "current_period_start" in item:
                    current_period_start = datetime.fromtimestamp(item["current_period_start"])
            
            if "current_period_end" in subscription:
                current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
            elif subscription.get("items", {}).get("data"):
                # Fall back to subscription item periods
                item = subscription["items"]["data"][0]
                if "current_period_end" in item:
                    current_period_end = datetime.fromtimestamp(item["current_period_end"])
            
            logger.info(f"Updating subscription {subscription_id}: status={new_status}, periods: {current_period_start} to {current_period_end}")
            
            await self.data_layer.update_subscription_status(
                subscription_id,
                new_status,
                current_period_start,
                current_period_end,
                cancel_at_period_end,
                new_price_id
            )
            
            logger.info(f"Successfully updated subscription {subscription_id} to status {new_status}")
            
        except Exception as e:
            logger.error(f"Error in _handle_subscription_updated: {e}")
            raise

    async def _handle_subscription_deleted(self, event_data: Dict):
        """Handle subscription.deleted webhook"""
        try:
            subscription = event_data["data"]["object"]
            
            logger.info(f"Processing subscription.deleted webhook for subscription {subscription['id']}")
            
            await self.data_layer.update_subscription_status(
                subscription["id"],
                "canceled"
            )
            
            logger.info(f"Successfully canceled subscription {subscription['id']}")
            
        except Exception as e:
            logger.error(f"Error in _handle_subscription_deleted: {e}")
            raise

    async def _handle_invoice_payment_succeeded(self, event_data: Dict):
        """Handle invoice.payment_succeeded webhook"""
        invoice = event_data["data"]["object"]
        
        await self.data_layer.create_invoice(
            stripe_invoice_id=invoice["id"],
            stripe_customer_id=invoice["customer"],
            stripe_subscription_id=invoice.get("subscription"),
            amount_due=invoice["amount_due"],
            amount_paid=invoice["amount_paid"],
            currency=invoice["currency"],
            status=invoice["status"],
            invoice_pdf=invoice.get("invoice_pdf"),
            hosted_invoice_url=invoice.get("hosted_invoice_url")
        )
        
        logger.info(f"Processed successful payment for invoice {invoice['id']}")

    async def _handle_invoice_payment_failed(self, event_data: Dict):
        """Handle invoice.payment_failed webhook"""
        invoice = event_data["data"]["object"]
        
        await self.data_layer.create_invoice(
            stripe_invoice_id=invoice["id"],
            stripe_customer_id=invoice["customer"],
            stripe_subscription_id=invoice.get("subscription"),
            amount_due=invoice["amount_due"],
            amount_paid=invoice.get("amount_paid", 0),
            currency=invoice["currency"],
            status=invoice["status"],
            invoice_pdf=invoice.get("invoice_pdf"),
            hosted_invoice_url=invoice.get("hosted_invoice_url")
        )
        
        logger.warning(f"Payment failed for invoice {invoice['id']}")

    async def _get_user_id_from_customer(self, stripe_customer_id: str) -> Optional[str]:
        """Get user_id from Stripe customer ID"""
        query = "SELECT user_id FROM stripe_customers WHERE stripe_customer_id = :customer_id"
        result = await self.data_layer.execute_sql(query, {"customer_id": stripe_customer_id})
        return result[0]["user_id"] if result and isinstance(result, list) else None

    async def _get_price_info(self, price_id: str) -> Dict[str, Any]:
        """Get price and product information"""
        query = """
            SELECT p.name as product_name, pr.interval
            FROM stripe_prices pr
            JOIN stripe_products p ON pr.stripe_product_id = p.stripe_product_id
            WHERE pr.stripe_price_id = :price_id
        """
        result = await self.data_layer.execute_sql(query, {"price_id": price_id})
        return result[0] if result and isinstance(result, list) else {}

    async def _create_price_from_webhook_data(self, price_data: Dict[str, Any]):
        """Create product and price records from webhook data"""
        try:
            product_id = price_data["product"]
            price_id = price_data["id"]
            
            # First, create or update the product
            product_query = """
                INSERT INTO stripe_products (stripe_product_id, name, created_at)
                VALUES (:product_id, :name, :created_at)
                ON CONFLICT (stripe_product_id) DO NOTHING
            """
            
            # Get product details from Stripe if needed
            product_name = "Pro Plan"  # Default name
            try:
                stripe_product = stripe.Product.retrieve(product_id)
                product_name = stripe_product.name
            except Exception as e:
                logger.warning(f"Could not retrieve product details for {product_id}: {e}")
            
            product_result = await self.data_layer.execute_sql(product_query, {
                "product_id": product_id,
                "name": product_name,
                "created_at": datetime.now()
            })
            
            logger.info(f"Product creation result for {product_id}: {product_result}")
            
            # Verify product was created by checking if it exists
            check_product_query = "SELECT stripe_product_id FROM stripe_products WHERE stripe_product_id = :product_id"
            product_check = await self.data_layer.execute_sql(check_product_query, {"product_id": product_id})
            
            if not product_check:
                raise Exception(f"Failed to create or find product {product_id}")
                
            logger.info(f"Confirmed product {product_id} exists in database")
            
            # Then create the price
            price_query = """
                INSERT INTO stripe_prices (stripe_price_id, stripe_product_id, unit_amount, currency, interval, created_at)
                VALUES (:price_id, :product_id, :unit_amount, :currency, :interval, :created_at)
                ON CONFLICT (stripe_price_id) DO NOTHING
            """
            
            price_result = await self.data_layer.execute_sql(price_query, {
                "price_id": price_id,
                "product_id": product_id,
                "unit_amount": price_data.get("unit_amount", 0),
                "currency": price_data.get("currency", "usd"),
                "interval": price_data.get("recurring", {}).get("interval", "month"),
                "created_at": datetime.now()
            })
            
            logger.info(f"Price creation result for {price_id}: {price_result}")
            
            # Verify price was created
            check_price_query = "SELECT stripe_price_id FROM stripe_prices WHERE stripe_price_id = :price_id"
            price_check = await self.data_layer.execute_sql(check_price_query, {"price_id": price_id})
            
            if not price_check:
                raise Exception(f"Failed to create or find price {price_id}")
                
            logger.info(f"Successfully created product {product_id} and price {price_id} from webhook data")
            
        except Exception as e:
            logger.error(f"Error creating price from webhook data: {e}")
            raise