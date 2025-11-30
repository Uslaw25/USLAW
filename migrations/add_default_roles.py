#!/usr/bin/env python3
"""
Migration script to add default USER role to existing users.

This script updates all existing users who don't have a role assigned
in their metadata to have the default 'USER' role.

Usage:
    python migrations/add_default_roles.py
"""

import os
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
from sql_data_layer import CustomSQLAlchemyDataLayer

# Load environment variables
load_dotenv()

async def add_default_roles():
    """Add default USER role to existing users without roles"""
    
    # Get database connection
    conninfo = os.environ.get("DATABASE_URL")
    if not conninfo:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Make sure the connection string uses the asyncpg driver
    if "postgresql" in conninfo and "+asyncpg" not in conninfo:
        conninfo = conninfo.replace("postgresql://", "postgresql+asyncpg://")
    
    data_layer = CustomSQLAlchemyDataLayer(conninfo=conninfo)
    
    print("🔍 Starting role migration for existing users...")
    print(f"⏰ Migration started at: {datetime.now().isoformat()}")
    
    try:
        # Get all users
        query = """SELECT "id", "identifier", "metadata" FROM users"""
        users = await data_layer.execute_sql(query, {})
        
        if not users or not isinstance(users, list):
            print("❌ No users found in database")
            return
        
        print(f"📊 Found {len(users)} users in database")
        
        users_updated = 0
        users_skipped = 0
        
        for user in users:
            user_id = user["id"]
            identifier = user["identifier"]
            metadata = user["metadata"]
            
            # Parse metadata
            if isinstance(metadata, str):
                try:
                    metadata_dict = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata_dict = {}
            else:
                metadata_dict = metadata or {}
            
            # Check if user already has a role
            current_role = metadata_dict.get("role")
            
            if current_role:
                print(f"⏭️  Skipping user {identifier} - already has role: {current_role}")
                users_skipped += 1
                continue
            
            # Add default USER role
            metadata_dict["role"] = "USER"
            
            # Update user in database
            update_query = """UPDATE users SET "metadata" = :metadata WHERE "id" = :user_id"""
            result = await data_layer.execute_sql(update_query, {
                "user_id": user_id,
                "metadata": json.dumps(metadata_dict)
            })
            
            if result is not None:
                print(f"✅ Updated user {identifier} with USER role")
                users_updated += 1
            else:
                print(f"❌ Failed to update user {identifier}")
        
        print("\n📈 Migration Summary:")
        print(f"   Total users processed: {len(users)}")
        print(f"   Users updated: {users_updated}")
        print(f"   Users skipped (already had role): {users_skipped}")
        print(f"⏰ Migration completed at: {datetime.now().isoformat()}")
        
        if users_updated > 0:
            print(f"\n🎉 Successfully added USER role to {users_updated} users!")
        else:
            print(f"\n✨ All users already have roles assigned. No changes needed.")
            
    except Exception as e:
        print(f"💥 Error during migration: {e}")
        raise

if __name__ == "__main__":
    print("🚀 Starting User Role Migration Script")
    print("=" * 50)
    
    try:
        asyncio.run(add_default_roles())
        print("=" * 50)
        print("✅ Migration completed successfully!")
    except Exception as e:
        print("=" * 50)
        print(f"❌ Migration failed: {e}")
        exit(1)