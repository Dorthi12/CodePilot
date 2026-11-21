from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GitHubStatusResponse(BaseModel):
    connected: bool
    provider: str = "github"
    username: Optional[str] = None
    scopes: Optional[str] = None
    connected_at: Optional[datetime] = None


class GitHubAuthUrlResponse(BaseModel):
    authorization_url: str
    state: str


class MessageResponse(BaseModel):
    message: str
