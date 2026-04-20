"""Tiny HTTP server that issues short-lived LiveKit JWTs to web clients.

The web frontend POSTs to /api/livekit-token and gets back { token, url }.
Each call gets a unique room so conversations are isolated.

Run:
    uvicorn agent.token_server:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from livekit import api

from agent.config import settings

app = FastAPI(title="PTSD-Ai Token Service")

# In production, restrict origins to your real domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [
        "https://yourdomain.example",
    ],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.post("/api/livekit-token")
async def issue_token() -> JSONResponse:
    """Issue a short-lived JWT for a fresh room."""
    room_name = f"call-{secrets.token_urlsafe(8)}"
    identity = f"caller-{secrets.token_urlsafe(6)}"

    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name("Caller")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_ttl(timedelta(minutes=30))
        .to_jwt()
    )

    return JSONResponse({"token": token, "url": settings.livekit_url})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
