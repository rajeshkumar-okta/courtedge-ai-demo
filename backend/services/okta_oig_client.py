"""Async HTTP wrapper around Okta OIG Access Requests API.

Endpoints used (verify against current Okta docs at
https://developer.okta.com/docs/reference/api/governance/ before
going to production):

- POST   /governance/api/v1/requests
- GET    /governance/api/v1/requests/{id}
- GET    /governance/api/v1/requests?requestTypeId=...&status=...
- POST   /governance/api/v1/requests/{id}/comments
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OIGAuthError(RuntimeError):
    """Raised when Okta returns 401 — API token expired/invalid."""


class OIGUnavailable(RuntimeError):
    """Raised when Okta returns 5xx or times out."""


class OktaOIGClient:
    def __init__(self, base_url: str, api_token: str, http: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._http = http or httpx.AsyncClient(timeout=10.0)
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"SSWS {self._api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base_url}/governance/api/v1{path}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = self._url(path)
        try:
            resp = await self._http.request(method, url, headers=self._headers(), **kwargs)
        except httpx.RequestError as exc:
            logger.warning("OIG transport error on %s %s: %s", method, url, exc)
            raise OIGUnavailable(f"OIG unreachable: {exc}") from exc

        if resp.status_code == 401:
            raise OIGAuthError(f"OIG auth failed on {method} {url}")
        if resp.status_code >= 500:
            raise OIGUnavailable(f"OIG {resp.status_code} on {method} {url}")
        if resp.status_code >= 400:
            # 4xx other than 401: surface as ValueError with body for caller visibility
            raise ValueError(f"OIG {resp.status_code} on {method} {url}: {resp.text}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def create_request(
        self,
        *,
        request_type_id: str,
        requester_id: str,
        subject: str,
        justification: str,
    ) -> dict[str, Any]:
        payload = {
            "requestTypeId": request_type_id,
            "requesterId": requester_id,
            "subject": subject,
            "justification": justification,
        }
        return await self._request("POST", "/requests", json=payload)

    async def get_request(self, request_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/requests/{request_id}")

    async def list_requests(
        self, *, request_type_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"requestTypeId": request_type_id}
        if status:
            params["status"] = status
        data = await self._request("GET", "/requests", params=params)
        # Okta list endpoints typically return {"items": [...]} or a bare list
        if isinstance(data, list):
            return data
        return data.get("items", []) or data.get("requests", [])

    async def add_comment(self, request_id: str, text: str) -> None:
        await self._request("POST", f"/requests/{request_id}/comments", json={"text": text})
