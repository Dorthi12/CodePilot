import logging
from typing import Any, Dict, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AIService:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.AI_SERVICES_URL).rstrip("/")

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
        except httpx.RequestError as exc:
            logger.error("AI services unavailable at %s: %s", self.base_url, exc)
            raise AIServiceError("AI services are unavailable.", status_code=503)

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            message = detail.get("detail") if isinstance(detail, dict) else response.text
            if isinstance(message, dict):
                message = message.get("message") or str(message)
            raise AIServiceError(str(message or "AI services request failed."), status_code=response.status_code)
        return response.json()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}{path}", params=params)
        except httpx.RequestError as exc:
            logger.error("AI services unavailable at %s: %s", self.base_url, exc)
            raise AIServiceError("AI services are unavailable.", status_code=503)

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            message = detail.get("detail") if isinstance(detail, dict) else response.text
            if isinstance(message, dict):
                message = message.get("message") or str(message)
            raise AIServiceError(str(message or "AI services request failed."), status_code=response.status_code)
        return response.json()

    async def index_repository(
        self,
        repo_id: str,
        snapshot_id: str,
        files: Dict[str, str],
    ) -> Dict[str, Any]:
        return await self._post("/index", {
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "files": files,
        })

    async def search(
        self,
        repo_id: str,
        snapshot_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> Dict[str, Any]:
        return await self._post("/search", {
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "query": query,
            "filters": filters,
            "top_k": top_k,
        })

    async def explain(
        self,
        repo_id: str,
        snapshot_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        body = {"repo_id": repo_id, "snapshot_id": snapshot_id, **payload}
        return await self._post("/explain", body)

    async def get_summary(
        self,
        repo_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        return await self._get(f"/summary/{repo_id}/{snapshot_id}")

    async def get_files(
        self,
        repo_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        return await self._get(f"/files/{repo_id}/{snapshot_id}")

    async def get_file_content(
        self,
        repo_id: str,
        snapshot_id: str,
        path: str,
    ) -> Dict[str, Any]:
        return await self._get(f"/file-content/{repo_id}/{snapshot_id}", params={"path": path})
