"""
Main FastAPI application that mounts Chainlit as a sub-application.

This file serves as the entry point for the FastAPI application.
It mounts the Chainlit application and registers additional routes
for Google OAuth authentication from React app.
"""

import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chainlit.utils import mount_chainlit
from chainlit.server import _authenticate_user

app = FastAPI(title="Chainlit with Google OAuth")

# Add CORS middleware for React app communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GoogleAuthRequest(BaseModel):
    credential: str

@app.post("/auth/google")
async def google_auth(request: Request, auth_request: GoogleAuthRequest):
    """
    Handle Google OAuth authentication from React app.
    This endpoint receives the Google JWT credential and authenticates the user.
    Following the exact pattern from WordPress OAuth implementation.
    """
    try:
        from auth_providers.google_oauth_provider import GoogleOAuthProvider
        from chainlit.auth import create_jwt, set_auth_cookie
        from chainlit.data import get_data_layer
        
        provider = GoogleOAuthProvider()
        raw_user_data, default_user = await provider.get_user_info(auth_request.credential)
        
        # Create user in database using existing data layer
        data_layer = get_data_layer()
        if data_layer:
            try:
                await data_layer.create_user(default_user)
            except Exception as e:
                print(f"Error creating user: {e}")
        
        # Create JWT token manually to ensure compatibility
        access_token = create_jwt(default_user)
        
        # Create response
        response = JSONResponse(
            content={
                "success": True,
                "user": default_user.metadata
            },
            status_code=200
        )
        
        # Set authentication cookie using Chainlit's function
        set_auth_cookie(request, response, access_token)
        
        # Debug: Print response headers to see what cookies are being set
        print(f"Response cookies being set: {response.headers.get('set-cookie', 'None')}")
        print(f"Access token created: {access_token[:50]}...")
        
        return response
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to authenticate: {str(e)}")

@app.get("/auth/validate")
async def validate_session(request: Request):
    """
    Validate existing session for React app.
    Checks if the user has valid Chainlit session cookies.
    """
    try:
        from chainlit.auth import get_token_from_cookies
        import jwt
        import os
        
        # Debug: Print all cookies
        print(f"Cookies received: {dict(request.cookies)}")
        
        # Get token from cookies using Chainlit's function
        token = get_token_from_cookies(request.cookies)
        print(f"Token from cookies: {token[:50] if token else 'None'}...")
        
        if not token:
            print("No token found in cookies")
            return JSONResponse(content={"valid": False, "reason": "no_token"}, status_code=200)
        
        # Verify the JWT token manually
        try:
            secret_key = os.environ.get("CHAINLIT_AUTH_SECRET")
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            print(f"Token verification successful: {payload.get('identifier')}")
            
            return JSONResponse(
                content={"valid": True, "user_id": payload.get("identifier")},
                status_code=200
            )
        except jwt.ExpiredSignatureError:
            print("Token has expired")
            return JSONResponse(content={"valid": False, "reason": "expired"}, status_code=200)
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {e}")
            return JSONResponse(content={"valid": False, "reason": "invalid_token"}, status_code=200)
            
    except Exception as e:
        print(f"Validation error: {e}")
        return JSONResponse(content={"valid": False, "reason": "error"}, status_code=200)

@app.post("/auth/logout")
async def logout(request: Request):
    """
    Logout endpoint that clears all authentication cookies.
    """
    try:
        from chainlit.auth import clear_auth_cookie
        
        response = JSONResponse(
            content={"success": True, "message": "Logged out successfully"},
            status_code=200
        )
        
        # Clear authentication cookies using Chainlit's function
        clear_auth_cookie(request, response)
        
        print("Logout successful - cookies cleared")
        return response
        
    except Exception as e:
        print(f"Logout error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

# Add a simple test route to verify FastAPI is working
@app.get("/test")
async def test_route():
    return {"message": "FastAPI is working"}

# Mount Chainlit app (exactly like WordPress example)
mount_chainlit(app=app, target="app.py", path="/chat")

# Debug: Print all routes after mounting
@app.on_event("startup")
async def startup_event():
    print("Available routes:")
    for route in app.routes:
        print(f"  {route.methods if hasattr(route, 'methods') else 'N/A'} {route.path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)