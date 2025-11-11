import os
import httpx
from typing import Dict, Tuple
from fastapi import HTTPException

from chainlit.user import User
from chainlit.oauth_providers import OAuthProvider


class GoogleOAuthProvider(OAuthProvider):
    """
    Google OAuth provider for Chainlit authentication.
    Follows the same pattern as WordPressJWTProvider.
    """
    id = "google-oauth"
    env = ["GOOGLE_CLIENT_ID"]
    authorize_url = ""

    def __init__(self):
        self.id = "google-oauth"
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.authorize_params = {}  # Not used in this flow

    def is_configured(self):
        return bool(self.google_client_id)

    async def get_user_info(self, credential: str) -> Tuple[Dict[str, str], User]:
        """
        Verify Google JWT credential and extract user information.
        
        Args:
            credential: Google JWT ID token from React app
            
        Returns:
            Tuple of (raw_user_data, User object)
        """
        try:
            # Verify Google JWT token with Google's tokeninfo endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400, 
                        detail="Invalid Google token"
                    )
                
                google_user_data = response.json()
                
                # Verify the audience (client_id) matches our app
                if google_user_data.get("aud") != self.google_client_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Token audience does not match"
                    )
                
                # Extract user information
                user_id = google_user_data.get("sub", "")
                email = google_user_data.get("email", "")
                name = google_user_data.get("name", "")
                picture = google_user_data.get("picture", "")
                
                # Create Chainlit User object (following WordPress pattern)
                user = User(
                    identifier=email,  # Use email as unique identifier
                    display_name=name,
                    metadata={
                        "email": email,
                        "name": name,
                        "image": picture,
                        "google_id": user_id,
                        "provider": "google",
                        "token": credential,  # Store original token
                    }
                )
                
                return (google_user_data, user)
                
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to verify Google token: {str(e)}"
            )
        except KeyError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field in Google token: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Google authentication failed: {str(e)}"
            )