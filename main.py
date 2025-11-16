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
from chainlit.oauth_providers import GoogleOAuthProvider

from auth_providers.google_oauth_provider import GoogleOAuthProvider as CustomGoogleOAuthProvider
from chainlit.utils import mount_chainlit
from chainlit.server import _authenticate_user

GoogleOAuthProvider.get_user_info = CustomGoogleOAuthProvider.get_user_info_patched
app = FastAPI(title="Chainlit with Google OAuth")

# Add CORS middleware for React app communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
mount_chainlit(app=app, target="app.py", path="/chat")

@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/chat")

# Debug: Print all routes after mounting
@app.on_event("startup")
async def startup_event():
    print("Available routes:")
    for route in app.routes:
        print(f"  {route.methods if hasattr(route, 'methods') else 'N/A'} {route.path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)