from chainlit.data.sql_alchemy import SQLAlchemyDataLayer as ChainlitSQLAlchemyDataLayer
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime
import bcrypt
import os
import re
from chainlit.user import User


class CustomSQLAlchemyDataLayer(ChainlitSQLAlchemyDataLayer):
    
    # ========== Password Authentication Methods ==========
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt with CHAINLIT_AUTH_SECRET as salt"""
        # Get the secret from environment variable
        secret = os.environ.get("CHAINLIT_AUTH_SECRET", "").encode('utf-8')
        if not secret:
            raise ValueError("CHAINLIT_AUTH_SECRET environment variable is required for password hashing")
        
        # Generate salt with the secret (pepper)
        salt = bcrypt.gensalt()
        
        # Combine password with secret for additional security
        password_with_secret = (password + secret.decode('utf-8')).encode('utf-8')
        
        # Hash the password
        hashed = bcrypt.hashpw(password_with_secret, salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            # Get the secret from environment variable
            secret = os.environ.get("CHAINLIT_AUTH_SECRET", "").encode('utf-8')
            if not secret:
                return False
            
            # Combine password with secret (same as during hashing)
            password_with_secret = (password + secret.decode('utf-8')).encode('utf-8')
            
            # Verify the password
            return bcrypt.checkpw(password_with_secret, hashed_password.encode('utf-8'))
        except Exception:
            return False
    
    def _validate_password_strength(self, password: str) -> tuple[bool, str]:
        """Validate password meets security requirements"""
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, "Password is strong"
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None
    
    async def create_user_with_password(self, email: str, password: str, metadata: Optional[Dict[str, Any]] = None, role: str = "USER") -> Optional[Dict[str, Any]]:
        """Create a new user with email and password authentication"""
        # Validate email format
        if not self._validate_email(email):
            raise ValueError("Invalid email format")
        
        # Validate password strength
        is_strong, message = self._validate_password_strength(password)
        if not is_strong:
            raise ValueError(message)
        
        # Validate role
        if role not in ["USER", "ADMIN"]:
            raise ValueError("Invalid role. Must be USER or ADMIN")
        
        # Check if user already exists
        existing_user = await self.get_user(email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Hash the password
        password_hash = self._hash_password(password)
        
        # Create user metadata with role
        user_metadata = metadata or {"provider": "password"}
        user_metadata["role"] = role
        
        # Create user record
        user_dict = {
            "id": str(uuid.uuid4()),
            "identifier": email,
            "metadata": user_metadata,
            "createdAt": datetime.now().isoformat(),
            "password_hash": password_hash
        }
        
        query = """
            INSERT INTO users ("id", "identifier", "metadata", "createdAt", "password_hash", "message_count") 
            VALUES (:id, :identifier, :metadata, :createdAt, :password_hash, 0)
        """
        
        # Convert metadata to JSON string if it's a dict
        if isinstance(user_dict["metadata"], dict):
            import json
            user_dict["metadata"] = json.dumps(user_dict["metadata"])
        
        result = await self.execute_sql(query, user_dict)
        if result is not None:
            return {"id": user_dict["id"], "identifier": email}
        return None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password"""
        # Validate email format
        if not self._validate_email(email):
            return None
        
        # Get user from database
        query = """
            SELECT "id", "identifier", "metadata", "password_hash" 
            FROM users 
            WHERE "identifier" = :identifier AND "password_hash" IS NOT NULL
        """
        
        result = await self.execute_sql(query, {"identifier": email})
        if not result or not isinstance(result, list) or len(result) == 0:
            return None
        
        user_data = result[0]
        password_hash = user_data.get("password_hash")
        
        if not password_hash:
            return None
        
        # Verify password
        if self._verify_password(password, password_hash):
            return {
                "id": user_data["id"],
                "identifier": user_data["identifier"],
                "metadata": user_data["metadata"]
            }
        
        return None
    
    async def update_user_role(self, user_id: str, role: str) -> bool:
        """Update user role (admin only)"""
        if role not in ["USER", "ADMIN"]:
            raise ValueError("Invalid role. Must be USER or ADMIN")
        
        # Get current user metadata
        query = """SELECT "metadata" FROM users WHERE "id" = :user_id"""
        result = await self.execute_sql(query, {"user_id": user_id})
        
        if not result or not isinstance(result, list) or len(result) == 0:
            return False
        
        # Update metadata with new role
        import json
        current_metadata = result[0]["metadata"]
        if isinstance(current_metadata, str):
            metadata = json.loads(current_metadata)
        else:
            metadata = current_metadata or {}
        
        metadata["role"] = role
        
        # Update user record
        update_query = """UPDATE users SET "metadata" = :metadata WHERE "id" = :user_id"""
        update_result = await self.execute_sql(update_query, {
            "user_id": user_id,
            "metadata": json.dumps(metadata)
        })
        
        return update_result is not None
    
    async def get_all_users(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all users with pagination (admin only)"""
        query = """
            SELECT "id", "identifier", "metadata", "createdAt"
            FROM users 
            ORDER BY "createdAt" DESC
            LIMIT :limit OFFSET :offset
        """
        
        result = await self.execute_sql(query, {"limit": limit, "offset": offset})
        return result if isinstance(result, list) else []
    
    async def get_users_count(self) -> int:
        """Get total number of users (admin only)"""
        query = """SELECT COUNT(*) as count FROM users"""
        result = await self.execute_sql(query, {})
        
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]["count"]
        return 0
    
    async def get_all_subscriptions_admin(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all subscriptions for admin view"""
        query = """
            SELECT 
                s.*, 
                u.identifier as user_email,
                p.name as product_name,
                pr.interval as billing_interval,
                pr.unit_amount as amount_cents,
                pr.currency
            FROM stripe_subscriptions s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN stripe_prices pr ON s.stripe_price_id = pr.stripe_price_id
            LEFT JOIN stripe_products p ON pr.stripe_product_id = p.stripe_product_id
            ORDER BY s.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        result = await self.execute_sql(query, {"limit": limit, "offset": offset})
        return result if isinstance(result, list) else []
    
    async def get_global_billing_history_admin(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get global billing history for admin view"""
        query = """
            SELECT 
                i.*,
                u.identifier as user_email
            FROM stripe_invoices i
            LEFT JOIN stripe_customers c ON i.stripe_customer_id = c.stripe_customer_id
            LEFT JOIN users u ON c.user_id = u.id
            ORDER BY i.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        result = await self.execute_sql(query, {"limit": limit, "offset": offset})
        return result if isinstance(result, list) else []
    
    # Override Chainlit's create_user to preserve roles
    async def create_user(self, user) -> Optional[dict]:
        """Override Chainlit's create_user to preserve existing user roles"""
        from chainlit.logger import logger
        import json
        
        if self.show_logger:
            logger.info(f"CustomSQLAlchemy: create_user, user_identifier={user.identifier}")
        
        existing_user = await self.get_user(user.identifier)
        
        if not existing_user:  # Create new user
            if self.show_logger:
                logger.info("CustomSQLAlchemy: Creating new user")
            
            user_dict = {
                "id": str(uuid.uuid4()),
                "identifier": str(user.identifier),
                "metadata": json.dumps(user.metadata) if user.metadata else "{}",
                "createdAt": datetime.now().isoformat(),
                "message_count": 0
            }
            
            query = """INSERT INTO users ("id", "identifier", "createdAt", "metadata", "message_count") VALUES (:id, :identifier, :createdAt, :metadata, :message_count)"""
            await self.execute_sql(query=query, parameters=user_dict)
            logger.info(f"CustomSQLAlchemy: Created new user {user.identifier} with role {user.metadata.get('role', 'No role') if user.metadata else 'No metadata'}")
            
        else:  # Update existing user but preserve role
            if self.show_logger:
                logger.info("CustomSQLAlchemy: Updating existing user metadata (preserving role)")
            
            # Get existing metadata
            existing_metadata = existing_user.metadata
            if isinstance(existing_metadata, str):
                try:
                    existing_metadata = json.loads(existing_metadata)
                except:
                    existing_metadata = {}
            
            # Preserve existing role if it exists
            new_metadata = user.metadata or {}
            if existing_metadata.get("role"):
                new_metadata["role"] = existing_metadata["role"]
                logger.info(f"CustomSQLAlchemy: Preserved role '{existing_metadata['role']}' for user {user.identifier}")
            
            user_dict = {
                "identifier": str(user.identifier),
                "metadata": json.dumps(new_metadata)
            }
            
            query = """UPDATE users SET "metadata" = :metadata WHERE "identifier" = :identifier"""
            await self.execute_sql(query=query, parameters=user_dict)
        
        return await self.get_user(user.identifier)
    
    # ========== Message Count Management Methods ==========
    
    async def get_user_message_count(self, user_identifier: str) -> int:
        """Get current message count for a user"""
        query = """
            SELECT "message_count" 
            FROM users 
            WHERE "identifier" = :identifier
        """
        
        result = await self.execute_sql(query, {"identifier": user_identifier})
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("message_count", 0) or 0
        return 0
    
    async def increment_user_message_count(self, user_identifier: str) -> int:
        """Increment message count for a user and return new count"""
        query = """
            UPDATE users 
            SET "message_count" = COALESCE("message_count", 0) + 1 
            WHERE "identifier" = :identifier
            RETURNING "message_count"
        """
        
        result = await self.execute_sql(query, {"identifier": user_identifier})
        if result and isinstance(result, list) and len(result) > 0:
            return result[0].get("message_count", 1)
        return 1
    
    async def reset_user_message_count(self, user_identifier: str) -> bool:
        """Reset message count for a user (used when upgrading to paid plan)"""
        query = """
            UPDATE users 
            SET "message_count" = 0 
            WHERE "identifier" = :identifier
        """
        
        result = await self.execute_sql(query, {"identifier": user_identifier})
        return result is not None
    
    async def check_user_message_limit(self, user_identifier: str, limit: int = 20) -> tuple[bool, int]:
        """
        Check if user has reached message limit
        Returns (can_send_message: bool, current_count: int)
        """
        current_count = await self.get_user_message_count(user_identifier)
        can_send = current_count < limit
        return can_send, current_count

    # ========== Subscription Management Methods ==========
    
    async def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get current active subscription for a user"""
        query = """
            SELECT 
                s.*, 
                p.name as product_name,
                pr.interval as billing_interval,
                pr.unit_amount as amount_cents,
                pr.currency
            FROM stripe_subscriptions s
            JOIN stripe_prices pr ON s.stripe_price_id = pr.stripe_price_id
            JOIN stripe_products p ON pr.stripe_product_id = p.stripe_product_id
            WHERE s.user_id = :user_id 
            AND s.status IN ('active', 'trialing', 'past_due')
            ORDER BY s.created_at DESC
            LIMIT 1
        """
        result = await self.execute_sql(query, {"user_id": user_id})
        return result[0] if result and isinstance(result, list) else None

    async def create_stripe_customer(self, user_id: str, stripe_customer_id: str) -> bool:
        """Create a new Stripe customer record"""
        query = """
            INSERT INTO stripe_customers (user_id, stripe_customer_id, created_at)
            VALUES (:user_id, :stripe_customer_id, :created_at)
            ON CONFLICT (user_id) DO UPDATE SET
                stripe_customer_id = EXCLUDED.stripe_customer_id
        """
        parameters = {
            "user_id": user_id,
            "stripe_customer_id": stripe_customer_id,
            "created_at": datetime.now()
        }
        result = await self.execute_sql(query, parameters)
        return result is not None

    async def get_stripe_customer(self, user_id: str) -> Optional[str]:
        """Get Stripe customer ID for a user"""
        query = "SELECT stripe_customer_id FROM stripe_customers WHERE user_id = :user_id"
        result = await self.execute_sql(query, {"user_id": user_id})
        return result[0]["stripe_customer_id"] if result and isinstance(result, list) else None

    async def create_subscription(
        self, 
        user_id: str, 
        stripe_subscription_id: str, 
        stripe_customer_id: str,
        stripe_price_id: str, 
        status: str,
        plan_name: str,
        billing_cycle: str,
        current_period_start: datetime,
        current_period_end: datetime
    ) -> bool:
        """Create a new subscription record"""
        query = """
            INSERT INTO stripe_subscriptions (
                user_id, stripe_subscription_id, stripe_customer_id, stripe_price_id,
                status, plan_name, billing_cycle, current_period_start, current_period_end,
                cancel_at_period_end, created_at, updated_at
            )
            VALUES (
                :user_id, :stripe_subscription_id, :stripe_customer_id, :stripe_price_id,
                :status, :plan_name, :billing_cycle, :current_period_start, :current_period_end,
                FALSE, :created_at, :updated_at
            )
            ON CONFLICT (stripe_subscription_id) DO UPDATE SET
                status = EXCLUDED.status,
                plan_name = EXCLUDED.plan_name,
                billing_cycle = EXCLUDED.billing_cycle,
                current_period_start = EXCLUDED.current_period_start,
                current_period_end = EXCLUDED.current_period_end,
                updated_at = EXCLUDED.updated_at
        """
        now = datetime.now()
        parameters = {
            "user_id": user_id,
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_customer_id": stripe_customer_id,
            "stripe_price_id": stripe_price_id,
            "status": status,
            "plan_name": plan_name,
            "billing_cycle": billing_cycle,
            "current_period_start": current_period_start,
            "current_period_end": current_period_end,
            "created_at": now,
            "updated_at": now
        }
        result = await self.execute_sql(query, parameters)
        return result is not None

    async def update_subscription_status(
        self, 
        stripe_subscription_id: str, 
        status: str,
        current_period_start: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
        cancel_at_period_end: Optional[bool] = None,
        stripe_price_id: Optional[str] = None
    ) -> bool:
        """Update subscription status and period information"""
        updates = ["status = :status", "updated_at = :updated_at"]
        parameters = {
            "stripe_subscription_id": stripe_subscription_id,
            "status": status,
            "updated_at": datetime.now()
        }
        
        if current_period_start:
            updates.append("current_period_start = :current_period_start")
            parameters["current_period_start"] = current_period_start
            
        if current_period_end:
            updates.append("current_period_end = :current_period_end") 
            parameters["current_period_end"] = current_period_end
            
        if cancel_at_period_end is not None:
            updates.append("cancel_at_period_end = :cancel_at_period_end")
            parameters["cancel_at_period_end"] = cancel_at_period_end
            
        if stripe_price_id:
            updates.append("stripe_price_id = :stripe_price_id")
            parameters["stripe_price_id"] = stripe_price_id

        query = f"""
            UPDATE stripe_subscriptions 
            SET {', '.join(updates)}
            WHERE stripe_subscription_id = :stripe_subscription_id
        """
        result = await self.execute_sql(query, parameters)
        return result is not None

    async def get_billing_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get billing history/invoices for a user"""
        # First get the stripe customer ID
        stripe_customer_id = await self.get_stripe_customer(user_id)
        if not stripe_customer_id:
            return []

        query = """
            SELECT 
                stripe_invoice_id,
                amount_due,
                amount_paid,
                currency,
                status,
                invoice_pdf,
                hosted_invoice_url,
                created_at
            FROM stripe_invoices
            WHERE stripe_customer_id = :stripe_customer_id
            ORDER BY created_at DESC
            LIMIT :limit
        """
        result = await self.execute_sql(query, {
            "stripe_customer_id": stripe_customer_id,
            "limit": limit
        })
        return result if isinstance(result, list) else []

    async def cancel_subscription(self, user_id: str, cancel_at_period_end: bool = True) -> bool:
        """Mark subscription for cancellation"""
        query = """
            UPDATE stripe_subscriptions 
            SET cancel_at_period_end = :cancel_at_period_end,
                updated_at = :updated_at
            WHERE user_id = :user_id 
            AND status IN ('active', 'trialing')
        """
        parameters = {
            "user_id": user_id,
            "cancel_at_period_end": cancel_at_period_end,
            "updated_at": datetime.now()
        }
        result = await self.execute_sql(query, parameters)
        return result is not None

    async def create_invoice(
        self,
        stripe_invoice_id: str,
        stripe_customer_id: str,
        stripe_subscription_id: Optional[str],
        amount_due: int,
        amount_paid: Optional[int],
        currency: str,
        status: str,
        invoice_pdf: Optional[str] = None,
        hosted_invoice_url: Optional[str] = None
    ) -> bool:
        """Create or update an invoice record"""
        query = """
            INSERT INTO stripe_invoices (
                stripe_invoice_id, stripe_customer_id, stripe_subscription_id,
                amount_due, amount_paid, currency, status, invoice_pdf, 
                hosted_invoice_url, created_at
            )
            VALUES (
                :stripe_invoice_id, :stripe_customer_id, :stripe_subscription_id,
                :amount_due, :amount_paid, :currency, :status, :invoice_pdf,
                :hosted_invoice_url, :created_at
            )
            ON CONFLICT (stripe_invoice_id) DO UPDATE SET
                amount_paid = EXCLUDED.amount_paid,
                status = EXCLUDED.status,
                invoice_pdf = EXCLUDED.invoice_pdf,
                hosted_invoice_url = EXCLUDED.hosted_invoice_url
        """
        parameters = {
            "stripe_invoice_id": stripe_invoice_id,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "amount_due": amount_due,
            "amount_paid": amount_paid,
            "currency": currency,
            "status": status,
            "invoice_pdf": invoice_pdf,
            "hosted_invoice_url": hosted_invoice_url,
            "created_at": datetime.now()
        }
        result = await self.execute_sql(query, parameters)
        return result is not None

    async def store_stripe_event(self, stripe_event_id: str, event_type: str, payload: Dict) -> bool:
        """Store Stripe webhook event for debugging/auditing"""
        query = """
            INSERT INTO stripe_events (stripe_event_id, type, payload, created_at)
            VALUES (:stripe_event_id, :type, :payload, :created_at)
            ON CONFLICT (stripe_event_id) DO NOTHING
        """
        parameters = {
            "stripe_event_id": stripe_event_id,
            "type": event_type,
            "payload": payload,
            "created_at": datetime.now()
        }
        result = await self.execute_sql(query, parameters)
        return result is not None