"""Feishu Open Platform API client for tenant token and messaging."""

from __future__ import annotations

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("evolux.gateway.feishu_api")

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
HttpPost = Callable[[str, dict[str, str], bytes], dict[str, Any]]
HttpGet = Callable[[str, dict[str, str]], dict[str, Any]]


@dataclass
class FeishuCredentials:
    app_id: str
    app_secret: str


@dataclass
class FeishuAPIClient:
    credentials: FeishuCredentials
    base_url: str = FEISHU_API_BASE
    _token: str | None = field(default=None, init=False, repr=False)
    _token_expires_at: float = field(default=0.0, init=False, repr=False)
    _http_post: HttpPost | None = field(default=None, init=False, repr=False)
    _http_get: HttpGet | None = field(default=None, init=False, repr=False)

    def send_text(self, chat_id: str, text: str) -> dict[str, Any]:
        token = self.get_tenant_access_token()
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        url = f"{self.base_url}/im/v1/messages?receive_id_type=chat_id"
        body = self._post(url, token, payload)
        logger.info("Feishu message sent to chat_id=%s", chat_id)
        return body

    def read_doc_raw(self, document_id: str) -> dict[str, Any]:
        token = self.get_tenant_access_token()
        url = f"{self.base_url}/docx/v1/documents/{document_id}/raw_content"
        return self._get(url, token)

    def create_doc(self, title: str, *, folder_token: str | None = None) -> dict[str, Any]:
        token = self.get_tenant_access_token()
        payload: dict[str, Any] = {"title": title}
        if folder_token:
            payload["folder_token"] = folder_token
        url = f"{self.base_url}/docx/v1/documents"
        return self._post(url, token, payload)

    def get_tenant_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token

        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        response = self._post(url, None, {"app_id": self.credentials.app_id, "app_secret": self.credentials.app_secret})
        token = str(response.get("tenant_access_token") or "")
        if not token:
            raise RuntimeError(f"Feishu auth failed: {response}")
        expire = int(response.get("expire", 7200))
        self._token = token
        self._token_expires_at = now + expire
        return token

    def _post(self, url: str, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if self._http_post:
            return self._http_post(url, headers, data)

        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with _urlopen(request, timeout=30.0) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Feishu API error {exc.code}: {detail}") from exc

        if body.get("code") not in (0, None):
            raise RuntimeError(f"Feishu API returned code={body.get('code')}: {body.get('msg')}")
        return body

    def _get(self, url: str, token: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"}
        if self._http_get:
            return self._http_get(url, headers)

        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with _urlopen(request, timeout=30.0) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Feishu API error {exc.code}: {detail}") from exc

        if body.get("code") not in (0, None):
            raise RuntimeError(f"Feishu API returned code={body.get('code')}: {body.get('msg')}")
        return body


def _ssl_context() -> ssl.SSLContext:
    if os.environ.get("EVOLUX_SSL_INSECURE", "").lower() in {"1", "true", "yes"}:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _urlopen(request: urllib.request.Request, timeout: float):
    if os.environ.get("EVOLUX_USE_SYSTEM_PROXY", "").lower() in {"1", "true", "yes"}:
        return urllib.request.urlopen(request, timeout=timeout)
    https_handler = urllib.request.HTTPSHandler(context=_ssl_context())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), https_handler)
    return opener.open(request, timeout=timeout)


def build_feishu_client(platform_config: dict[str, Any]) -> FeishuAPIClient | None:
    app_id = str(platform_config.get("app_id") or "")
    app_secret = str(platform_config.get("app_secret") or "")
    if not app_id or not app_secret:
        return None
    return FeishuAPIClient(credentials=FeishuCredentials(app_id=app_id, app_secret=app_secret))
