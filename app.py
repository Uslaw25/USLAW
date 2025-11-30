from dotenv import load_dotenv
from typing import Dict, Optional
import chainlit as cl
import os
import jwt
import json
import httpx

from agent.chat_handler import LawAgent
from sql_data_layer import CustomSQLAlchemyDataLayer
from storage.storage_clients.digitalocean import DigitalOceanStorageClient

load_dotenv()

# Configuration
FREE_USER_MESSAGE_LIMIT = int(os.environ.get("FREE_USER_MESSAGE_LIMIT", "20"))

try:
    # Get configuration from environment variables
    bucket_name = os.environ.get("AWS_S3_BUCKET_NAME", "bot-lagen-law-test")
    region_name = os.environ.get("AWS_REGION_NAME", "ams3")
    access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    # Remove quotes if they exist in the environment variables
    if access_key_id and access_key_id.startswith('"') and access_key_id.endswith('"'):
        access_key_id = access_key_id[1:-1]
    if secret_access_key and secret_access_key.startswith('"') and secret_access_key.endswith('"'):
        secret_access_key = secret_access_key[1:-1]

    storage_client = DigitalOceanStorageClient(
        bucket=bucket_name,
        region_name=region_name,
        endpoint_url=f"https://{region_name}.digitaloceanspaces.com",
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )
    cl.logger.info(f"Digital Ocean Spaces client initialized for bucket: {bucket_name}")
except Exception as e:
    cl.logger.error(f"Error initializing Digital Ocean Spaces client: {e}")


# Configure data layer
@cl.data_layer
def get_data_layer():
    """
    Get the data layer for Chainlit

    This function returns a SQLAlchemyDataLayer instance configured with the
    connection string from the environment variables.
    """
    conninfo = os.environ.get("DATABASE_URL")
    cl.logger.info(f"Database connection string: {conninfo}")
    if not conninfo:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Make sure the connection string uses the asyncpg driver
    if "postgresql" in conninfo and "+asyncpg" not in conninfo:
        conninfo = conninfo.replace("postgresql://", "postgresql+asyncpg://")
    return CustomSQLAlchemyDataLayer(conninfo=conninfo, storage_provider=storage_client)

@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    """Authenticate user with email and password from database"""
    try:
        # Get data layer instance
        data_layer = get_data_layer()
        
        # Keep the hardcoded admin for backward compatibility
        if (username, password) == ("admin", "admin"):
            return cl.User(
                identifier="admin", metadata={"role": "ADMIN", "provider": "credentials"}
            )
        
        # Authenticate user from database
        user_data = await data_layer.authenticate_user(username, password)
        if user_data:
            # Parse metadata if it's a JSON string
            metadata = user_data.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except:
                    metadata = {"provider": "password"}
            
            # Ensure user has a role (preserve existing role)
            if "role" not in metadata:
                metadata["role"] = "USER"
            
            cl.logger.info(f"Password auth: User {username} logged in with role {metadata.get('role')}")
            
            return cl.User(
                identifier=user_data["identifier"],
                metadata=metadata
            )
        
        return None
        
    except Exception as e:
        cl.logger.error(f"Authentication error: {e}")
        return None


@cl.oauth_callback
async def oauth_callback(
  provider_id: str,
  token: str,
  raw_user_data: Dict[str, str],
  default_user: cl.User,
) -> Optional[cl.User]:
  try:
    if not default_user:
      return default_user
    
    # Get data layer instance
    data_layer = get_data_layer()
    
    # Check if user already exists in database
    existing_user = await data_layer.get_user(default_user.identifier)
    
    if existing_user:
      # User exists - preserve their role and other metadata
      existing_metadata = existing_user.metadata
      if isinstance(existing_metadata, str):
        import json
        try:
          existing_metadata = json.loads(existing_metadata)
        except:
          existing_metadata = {}
      
      # Preserve existing role, but update other OAuth metadata
      preserved_role = existing_metadata.get("role", "USER")
      
      # Merge metadata: keep role, update OAuth info
      updated_metadata = {
        "role": preserved_role,  # Keep existing role
        "provider": provider_id,
        "image": raw_user_data.get("picture", raw_user_data.get("avatar_url", "")),
        "email": raw_user_data.get("email", "")
      }
      
      default_user.metadata = updated_metadata
      cl.logger.info(f"OAuth: Preserved role '{preserved_role}' for existing user {default_user.identifier}")
    else:
      # New user - set default role
      if not default_user.metadata:
        default_user.metadata = {}
      default_user.metadata["role"] = "USER"
      default_user.metadata["provider"] = provider_id
      cl.logger.info(f"OAuth: New user {default_user.identifier} created with USER role")
    
    return default_user
    
  except Exception as e:
    cl.logger.error(f"OAuth callback error: {e}")
    # Fallback: just ensure user has a role
    if default_user and default_user.metadata:
      if "role" not in default_user.metadata:
        default_user.metadata["role"] = "USER"
    return default_user


chat_handler = LawAgent()


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session"""
    # Initialize chat history
    cl.user_session.set("chat_history", [])

    # Initialize vector store silently
    vector_store = chat_handler.setup_vector_store()
    if vector_store:
        cl.user_session.set("vector_store", vector_store)


@cl.on_message
async def on_message(message: cl.Message):
    """Handle user messages"""
    user_question = message.content
    
    # Get current user and check message limits for free users
    current_user = cl.user_session.get("user")
    if current_user:
        # Get user role to check if they're a free user
        user_metadata = current_user.metadata or {}
        user_role = user_metadata.get("role", "USER")
        
        # Skip limit check for admin users
        if user_role != "ADMIN":
            # Get data layer instance
            data_layer = get_data_layer()
            
            # Check message limit (configurable for free users)
            can_send, current_count = await data_layer.check_user_message_limit(current_user.identifier, FREE_USER_MESSAGE_LIMIT)
            
            if not can_send:
                # User has reached their message limit
                await cl.Message(
                    content=f"🚫 **Message limit reached!**\n\n"
                           f"You've used all {FREE_USER_MESSAGE_LIMIT} of your free messages. To continue chatting, please upgrade to our Pro plan.\n\n"
                           f"**Benefits of upgrading:**\n"
                           f"• Unlimited legal questions\n"
                           f"• Analyze and summarize PDFs\n"
                           f"• Priority AI responses\n"
                           f"• Cancel anytime\n\n"
                           f"[Upgrade to Pro Plan](/dashboard) to continue your legal research.",
                    author="System"
                ).send()
                return  # Stop processing the message
            
            # Show warning when approaching limit (75% of limit)
            warning_threshold = max(1, int(FREE_USER_MESSAGE_LIMIT * 0.75))
            if current_count >= warning_threshold:
                remaining = FREE_USER_MESSAGE_LIMIT - current_count
                await cl.Message(
                    content=f"⚠️ **{remaining} messages remaining** in your free plan. [Upgrade now](/dashboard) for unlimited messages.",
                    author="System"
                ).send()
    
    msg = cl.Message(content="")
    await msg.send()
    await msg.stream_token(" ")
    # Get chat history
    chat_history = cl.user_session.get("chat_history", [])

    # Process uploaded files if any
    additional_docs = []
    file_info = ""
    if message.elements:
        files = message.elements
        additional_docs, file_info = await chat_handler.process_uploaded_files(files)

        if additional_docs:
            # Handle unsupported file types in UI
            for file in files:
                file_extension = file.name.split(".")[-1].lower()
                if file_extension not in chat_handler.FILE_LOADERS:
                    await cl.Message(
                        content=f"⚠️ unsupported file .{file_extension}. 'supported formats are ({', '.join(chat_handler.FILE_LOADERS.keys())})",
                        author="System"
                    ).send()

    # Add user message to chat history
    chat_history.append({"role": "user", "content": user_question})

    # Regenerate question if there's history
    if len(chat_history) > 1:
        regenerated_question = chat_handler.regenerate_question(chat_history, user_question)

        # Add debug info if needed
        if os.environ.get("DEBUG_MODE") == "true":
            await cl.Message(
                content=f"🔍 **Original:** {user_question}\n\n🔄 **Regenerated:** {regenerated_question}",
                author="Debug",
                visible_to=["admin"]
            ).send()
    else:
        regenerated_question = user_question

    # Create a message for streaming
    # msg = cl.Message(content="")
    #
    # await msg.send()
    # await msg.stream_token(" ")
    # Get streaming response
    response_content, docs = await chat_handler.retrieve_and_generate_response(msg,
                                                                               regenerated_question,
                                                                               chat_history,
                                                                               additional_docs
                                                                               )
    chat_history.append({"role": "assistant", "content": response_content})
    cl.user_session.set("chat_history", chat_history)
    
    # Increment message count for non-admin users after successful message processing
    if current_user and user_role != "ADMIN":
        try:
            new_count = await data_layer.increment_user_message_count(current_user.identifier)
            cl.logger.info(f"Message count incremented to {new_count} for user {current_user.identifier}")
        except Exception as e:
            cl.logger.error(f"Failed to increment message count for user {current_user.identifier}: {e}")


@cl.on_chat_resume
async def on_chat_resume(thread):
    pass