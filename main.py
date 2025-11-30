"""
Main FastAPI application that mounts Chainlit as a sub-application.

This file serves as the entry point for the FastAPI application.
It mounts the Chainlit application and registers additional routes
for Google OAuth authentication and Stripe subscription management.
"""

import os
import stripe
from chainlit import User, PersistedUser
from chainlit.auth import get_current_user
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Union, Annotated, List
from chainlit.oauth_providers import GoogleOAuthProvider

from auth_providers.google_oauth_provider import GoogleOAuthProvider as CustomGoogleOAuthProvider
from chainlit.utils import mount_chainlit
from chainlit.server import _authenticate_user
from services.stripe_service import StripeService
from sql_data_layer import CustomSQLAlchemyDataLayer

# Configuration
FREE_USER_MESSAGE_LIMIT = int(os.environ.get("FREE_USER_MESSAGE_LIMIT", "20"))

GenericUser = Union[User, PersistedUser, None]
UserParam = Annotated[GenericUser, Depends(get_current_user)]

# Admin middleware for role-based access control
async def get_admin_user(current_user: UserParam) -> GenericUser:
    """Ensure current user is an admin"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check if user has admin role
    user_role = None
    if hasattr(current_user, 'metadata') and current_user.metadata:
        user_role = current_user.metadata.get('role')
    
    if user_role != 'ADMIN':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return current_user

AdminUserParam = Annotated[GenericUser, Depends(get_admin_user)]

GoogleOAuthProvider.get_user_info = CustomGoogleOAuthProvider.get_user_info_patched
app = FastAPI(title="Chainlit with Google OAuth")

# Add CORS middleware for React app communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize data layer and Stripe service
data_layer = None
stripe_service = None

@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    global data_layer, stripe_service
    
    conninfo = os.environ.get("DATABASE_URL")
    if conninfo and "postgresql" in conninfo and "+asyncpg" not in conninfo:
        conninfo = conninfo.replace("postgresql://", "postgresql+asyncpg://")
    
    data_layer = CustomSQLAlchemyDataLayer(conninfo=conninfo)
    stripe_service = StripeService(data_layer)

# Pydantic models for request/response
class CreateCheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    apply_discount: Optional[bool] = False

class SubscriptionResponse(BaseModel):
    status: str
    plan: str
    billing_cycle: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    amount: Optional[float] = None
    currency: Optional[str] = None

class CancelSubscriptionRequest(BaseModel):
    cancel_immediately: bool = False

class ModifySubscriptionRequest(BaseModel):
    new_price_id: str
    apply_discount: Optional[bool] = False

class SignupRequest(BaseModel):
    email: str
    password: str

class SignupResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None

# Admin API Models
class AdminUserResponse(BaseModel):
    id: str
    identifier: str
    role: str
    provider: str
    created_at: str
    subscription_status: Optional[str] = None

class AdminUsersResponse(BaseModel):
    users: List[AdminUserResponse]
    total: int
    page: int
    limit: int

class UpdateRoleRequest(BaseModel):
    role: str

class AdminSubscriptionResponse(BaseModel):
    id: str
    user_email: str
    plan_name: str
    status: str
    billing_cycle: str
    amount_cents: int
    currency: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    created_at: str

class AdminBillingResponse(BaseModel):
    invoice_id: str
    user_email: str
    amount_due: int
    amount_paid: Optional[int]
    currency: str
    status: str
    created_at: str
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None

# # Helper function to get user from JWT token
# async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
#     """Extract user ID from Authorization header"""
#     if not authorization or not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
#     
#     token = authorization.replace("Bearer ", "")
#     try:
#         # Use Chainlit's authentication to verify the token and get user info
#         user = await _authenticate_user(token)
#         if not user:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return user.identifier
#     except Exception as e:
#         raise HTTPException(status_code=401, detail="Token verification failed")

# ========== Subscription API Endpoints ==========

@app.post("/chat/api/subscription/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: UserParam
):
    """Create a Stripe checkout session for subscription"""
    try:
        # Get user info for customer creation (you may need to adjust this based on your user system)
        checkout_url = await stripe_service.create_checkout_session(
            user_id=current_user.id,
            email=current_user.identifier,  # You'll want to get real email from user system
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            apply_discount=request.apply_discount
        )
        print("Checkout URL:", checkout_url)
        return {"checkout_url": checkout_url}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/subscription/status", response_model=SubscriptionResponse)
async def get_subscription_status(current_user: UserParam):
    """Get current subscription status for user"""
    try:
        status = await stripe_service.get_subscription_status(current_user.id)
        return SubscriptionResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/api/subscription/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: UserParam
):
    """Cancel user subscription"""
    try:
        result = await stripe_service.cancel_subscription(
            user_id=current_user.id,
            cancel_immediately=request.cancel_immediately
        )
        
        return {"success": result, "message": "Subscription cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CustomerPortalRequest(BaseModel):
    return_url: str

@app.post("/chat/api/subscription/customer-portal")
async def create_customer_portal_session(
    request: CustomerPortalRequest,
    current_user: UserParam
):
    """Create Stripe customer portal session"""
    try:
        portal_url = await stripe_service.create_customer_portal_session(
            user_id=current_user.id,
            return_url=request.return_url
        )
        
        return {"portal_url": portal_url}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/subscription/billing-history")
async def get_billing_history(
    current_user: UserParam,
    limit: int = 20,
):
    """Get billing history for user"""
    try:
        history = await stripe_service.get_billing_history(current_user.id, limit)
        return {"invoices": history}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/subscription/plans")
async def get_subscription_plans():
    """Get available subscription plans and pricing"""
    try:
        # Get price IDs from environment
        monthly_price_id = os.getenv("STRIPE_MONTHLY_PRICE_ID", "price_1SWMauSBcaUtv6fpCztlUeM3")
        yearly_price_id = os.getenv("STRIPE_YEARLY_PRICE_ID", "price_1SWMauSBcaUtv6fpDXIFPJ4T")
        
        plans = [
            {
                "id": "monthly",
                "name": "Pro Monthly",
                "price": 39,
                "interval": "month",
                "priceId": monthly_price_id,
                "description": "Perfect for getting started with pro features",
                "features": [
                    "Unlimited conversations",
                    "Advanced AI models",
                    "Priority support",
                    "Custom integrations",
                    "Team collaboration",
                    "Advanced analytics"
                ]
            },
            {
                "id": "yearly",
                "name": "Pro Yearly",
                "price": 374,
                "interval": "year",
                "priceId": yearly_price_id,
                "description": "Best value - save 20% per year",
                "features": [
                    "Unlimited conversations",
                    "Advanced AI models", 
                    "Priority support",
                    "Custom integrations",
                    "Team collaboration",
                    "Advanced analytics",
                    "20% discount"
                ],
                "popular": True
            }
        ]
        
        return {"plans": plans}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/api/subscription/modify")
async def modify_subscription(
    request: ModifySubscriptionRequest,
    current_user: UserParam
):
    """Modify existing subscription with automatic proration"""
    try:
        result = await stripe_service.modify_subscription(
            current_user.id,
            request.new_price_id,
            apply_discount=request.apply_discount
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/api/subscription/sync")
async def sync_subscription_status(current_user: UserParam):
    """Manually sync subscription status from Stripe (for debugging)"""
    try:
        result = await stripe_service.sync_subscription_from_stripe(current_user.id)
        return {"success": result, "message": "Subscription status synced from Stripe"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/api/subscription/reset-message-count")
async def reset_message_count(current_user: UserParam):
    """Reset user message count (typically called after upgrading to paid plan)"""
    try:
        # Get user subscription status to verify they have an active subscription
        subscription_status = await stripe_service.get_subscription_status(current_user.id)
        
        # Only reset count if user has active subscription or is admin
        user_role = "USER"
        if hasattr(current_user, 'metadata') and current_user.metadata:
            user_role = current_user.metadata.get('role', 'USER')
        
        if subscription_status.status != 'active' and user_role != 'ADMIN':
            raise HTTPException(
                status_code=403, 
                detail="Message count reset is only available for users with active subscriptions"
            )
        
        # Reset the message count
        success = await data_layer.reset_user_message_count(current_user.identifier)
        
        if success:
            return {"success": True, "message": "Message count reset successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset message count")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting message count: {str(e)}")

@app.get("/chat/api/usage/status")
async def get_usage_status(current_user: UserParam):
    """Get current message usage status for the user"""
    try:
        # Get current message count
        message_count = await data_layer.get_user_message_count(current_user.identifier)
        
        # Check if user can send more messages
        can_send, current_count = await data_layer.check_user_message_limit(current_user.identifier, FREE_USER_MESSAGE_LIMIT)
        
        return {
            "messageCount": current_count,
            "limit": FREE_USER_MESSAGE_LIMIT,
            "canSend": can_send,
            "remaining": FREE_USER_MESSAGE_LIMIT - current_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting usage status: {str(e)}")

# ========== Authentication API Endpoints ==========

@app.post("/chat/api/auth/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    """Create a new user account with email and password"""
    try:
        result = await data_layer.create_user_with_password(
            email=request.email,
            password=request.password,
            metadata={"provider": "password"},
            role="USER"  # Default role for signup
        )
        
        if result:
            return SignupResponse(
                success=True,
                message="Account created successfully",
                user_id=result["id"]
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create user account")
            
    except ValueError as e:
        # Handle validation errors (email format, password strength, duplicate email)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error during signup")

# ========== Admin API Endpoints ==========

@app.get("/chat/api/admin/users", response_model=AdminUsersResponse)
async def get_all_users(
    admin_user: AdminUserParam,
    page: int = 1,
    limit: int = 50
):
    """Get all users (admin only)"""
    try:
        offset = (page - 1) * limit
        users = await data_layer.get_all_users(limit=limit, offset=offset)
        total = await data_layer.get_users_count()
        
        # Format users for response
        formatted_users = []
        for user in users:
            # Parse metadata
            metadata = user["metadata"]
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            # Get subscription status for this user
            subscription = await data_layer.get_user_subscription(user["id"])
            subscription_status = subscription.get("status") if subscription else None
            
            formatted_users.append(AdminUserResponse(
                id=user["id"],
                identifier=user["identifier"],
                role=metadata.get("role", "USER"),
                provider=metadata.get("provider", "unknown"),
                created_at=user["createdAt"],
                subscription_status=subscription_status
            ))
        
        return AdminUsersResponse(
            users=formatted_users,
            total=total,
            page=page,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/chat/api/admin/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateRoleRequest,
    admin_user: AdminUserParam
):
    """Update user role (admin only)"""
    try:
        success = await data_layer.update_user_role(user_id, request.role)
        
        if success:
            return {"success": True, "message": f"User role updated to {request.role}"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/admin/subscriptions")
async def get_all_subscriptions(
    admin_user: AdminUserParam,
    page: int = 1,
    limit: int = 50
):
    """Get all subscriptions (admin only)"""
    try:
        offset = (page - 1) * limit
        subscriptions = await data_layer.get_all_subscriptions_admin(limit=limit, offset=offset)
        
        formatted_subscriptions = []
        for sub in subscriptions:
            formatted_subscriptions.append(AdminSubscriptionResponse(
                id=sub.get("stripe_subscription_id", ""),
                user_email=sub.get("user_email", ""),
                plan_name=sub.get("product_name", "Unknown"),
                status=sub.get("status", ""),
                billing_cycle=sub.get("billing_interval", ""),
                amount_cents=sub.get("amount_cents", 0),
                currency=sub.get("currency", "usd"),
                current_period_start=sub.get("current_period_start", ""),
                current_period_end=sub.get("current_period_end", ""),
                cancel_at_period_end=sub.get("cancel_at_period_end", False),
                created_at=sub.get("created_at", "")
            ))
        
        return {"subscriptions": formatted_subscriptions}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/api/admin/subscriptions/{subscription_id}/cancel")
async def admin_cancel_subscription(
    subscription_id: str,
    admin_user: AdminUserParam,
    cancel_immediately: bool = False
):
    """Admin cancel user subscription"""
    try:
        # Get subscription details
        query = "SELECT user_id FROM stripe_subscriptions WHERE stripe_subscription_id = :subscription_id"
        result = await data_layer.execute_sql(query, {"subscription_id": subscription_id})
        
        if not result:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        user_id = result[0]["user_id"]
        
        # Use existing cancel subscription method
        success = await stripe_service.cancel_subscription(
            user_id=user_id,
            cancel_immediately=cancel_immediately
        )
        
        if success:
            return {"success": True, "message": "Subscription cancelled successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to cancel subscription")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/admin/billing/global")
async def get_global_billing_history(
    admin_user: AdminUserParam,
    page: int = 1,
    limit: int = 100
):
    """Get global billing history (admin only)"""
    try:
        offset = (page - 1) * limit
        billing_history = await data_layer.get_global_billing_history_admin(limit=limit, offset=offset)
        
        formatted_billing = []
        for bill in billing_history:
            formatted_billing.append(AdminBillingResponse(
                invoice_id=bill.get("stripe_invoice_id", ""),
                user_email=bill.get("user_email", ""),
                amount_due=bill.get("amount_due", 0),
                amount_paid=bill.get("amount_paid"),
                currency=bill.get("currency", "usd"),
                status=bill.get("status", ""),
                created_at=bill.get("created_at", ""),
                invoice_pdf=bill.get("invoice_pdf"),
                hosted_invoice_url=bill.get("hosted_invoice_url")
            ))
        
        return {"billing_history": formatted_billing}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/admin/users/{user_id}/subscription")
async def get_user_subscription_admin(
    user_id: str,
    admin_user: AdminUserParam
):
    """Get specific user's subscription details (admin only)"""
    try:
        subscription = await data_layer.get_user_subscription(user_id)
        
        if subscription:
            # Format subscription data
            formatted_subscription = {
                "id": subscription.get("stripe_subscription_id", ""),
                "plan_name": subscription.get("product_name", "Unknown"),
                "status": subscription.get("status", ""),
                "billing_cycle": subscription.get("billing_interval", ""),
                "amount_cents": subscription.get("amount_cents", 0),
                "currency": subscription.get("currency", "usd"),
                "current_period_start": subscription.get("current_period_start", ""),
                "current_period_end": subscription.get("current_period_end", ""),
                "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
                "created_at": subscription.get("created_at", "")
            }
            return {"subscription": formatted_subscription}
        else:
            return {"subscription": None}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/api/admin/users/{user_id}/billing")
async def get_user_billing_admin(
    user_id: str,
    admin_user: AdminUserParam,
    limit: int = 50
):
    """Get specific user's billing history (admin only)"""
    try:
        # Get billing history for specific user
        query = """
            SELECT 
                i.*
            FROM stripe_invoices i
            LEFT JOIN stripe_customers c ON i.stripe_customer_id = c.stripe_customer_id
            WHERE c.user_id = :user_id
            ORDER BY i.created_at DESC
            LIMIT :limit
        """
        
        result = await data_layer.execute_sql(query, {"user_id": user_id, "limit": limit})
        billing_history = result if isinstance(result, list) else []
        
        formatted_billing = []
        for bill in billing_history:
            formatted_billing.append({
                "invoice_id": bill.get("stripe_invoice_id", ""),
                "amount_due": bill.get("amount_due", 0),
                "amount_paid": bill.get("amount_paid"),
                "currency": bill.get("currency", "usd"),
                "status": bill.get("status", ""),
                "created_at": bill.get("created_at", ""),
                "invoice_pdf": bill.get("invoice_pdf"),
                "hosted_invoice_url": bill.get("hosted_invoice_url")
            })
        
        return {"billing_history": formatted_billing}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== Stripe Webhook Handler ==========

@app.post("/chat/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        #
        # if not sig_header:
        #     raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        # Verify webhook signature
        # webhook_secret = stripe_service.webhook_secret
        webhook_secret = "whsec_ADYI2devLuzYLy04cLC6HODGUOvYIeQi"
        if webhook_secret:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, webhook_secret
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid payload")
            except stripe.error.SignatureVerificationError:
                raise HTTPException(status_code=400, detail="Invalid signature")
        else:
            # If no webhook secret is configured, parse the payload directly (not recommended for production)
            import json
            event = json.loads(payload.decode('utf-8'))
        
        # Process the webhook event
        success = await stripe_service.handle_webhook_event(event)
        
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Failed to process webhook event")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@app.get("/chat/hello")
async def hello():
    return {"message": "Hello World"}

mount_chainlit(app=app, target="app.py", path='/chat')

# @app.get("/")
# async def root():
#     from fastapi.responses import RedirectResponse
#     return RedirectResponse(url="/chat")

# Debug: Print all routes after mounting
# @app.on_event("startup")
# async def startup_event():
#     print("Available routes:")
#     for route in app.routes:
#         print(f"  {route.methods if hasattr(route, 'methods') else 'N/A'} {route.path}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)