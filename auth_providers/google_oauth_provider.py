import os
import httpx
from typing import Dict, Tuple
from fastapi import HTTPException

from chainlit.user import User
from chainlit.oauth_providers import OAuthProvider
from chainlit.logger import logger

class GoogleOAuthProvider(OAuthProvider):
    async def get_user_info_patched(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/userinfo/v2/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()

            google_user = response.json()
            logger.info(f"Google USER DATA: {google_user} END")
            user = User(
                display_name=google_user.get("name", ""),
                identifier=google_user["email"],
                metadata={"name":google_user.get("name", ""), "image": google_user["picture"], "provider": "google"},
            )
            logger.info(f"USER DATA: {user.to_dict()}")
            return (google_user, user)


