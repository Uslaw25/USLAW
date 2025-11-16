from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from dotenv import load_dotenv
from typing import Dict, Optional
import chainlit as cl
import os
import jwt
import json
import httpx

from agent.chat_handler import LawAgent
from storage.storage_clients.digitalocean import DigitalOceanStorageClient

load_dotenv()

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
    return SQLAlchemyDataLayer(conninfo=conninfo, storage_provider=storage_client)

@cl.oauth_callback
def oauth_callback(
  provider_id: str,
  token: str,
  raw_user_data: Dict[str, str],
  default_user: cl.User,
) -> Optional[cl.User]:
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


@cl.on_chat_resume
async def on_chat_resume(thread):
    pass