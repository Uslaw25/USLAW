from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from dotenv import load_dotenv
from typing import Dict, Optional
import chainlit as cl
import os
import jwt
import json
import httpx

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

@cl.on_message
async def main(message: cl.Message):
    # Your custom logic goes here...

    # Send a response back to the user

    message = await cl.Message(content="",).send()
    random_string = "some random story"
    import asyncio
    for s in random_string:
        await message.stream_token(s)
        await asyncio.sleep(0.3)
    await message.update()