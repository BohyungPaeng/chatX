import os
import requests
import aiohttp
import json
import asyncio
from typing import List, Dict, Optional, Any, Union, AsyncGenerator
# Django 환경에서 .env 로드용
# import environ

from .config import LITELLM_URL, LITELLM_KEY

class PwcLLMClient:
    """
    동기/비동기/스트리밍/헬스체크를 모두 제공하는 퍼사드 클래스
    """
    def __init__(
        self,
        default_model_name: str,
        logger: Optional[Any] = None
    ):
        self.default_model = default_model_name

        # 기본: config.py 에 정의된 상수 사용
        self.base_url = LITELLM_URL
        self.api_key  = LITELLM_KEY
        self.logger   = logger

        # Django 환경에서 .env 사용하고 싶다면 아래 주석 해제
        # env = environ.Env(DEBUG=(bool, False))
        # project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        # env.read_env(os.path.join(project_root, '.env'))
        # self.base_url = env("LITELLM_URL", default=self.base_url)
        # self.api_key  = env("LITELLM_KEY", default=self.api_key)

        # 역할별 헬퍼 인스턴스
        self._sync   = SyncHelper(self)
        self._async  = AsyncHelper(self)
        self._stream = StreamHelper(self)

    # 동기 퍼사드
    def run(self, messages: Union[Dict, List[Dict]], **opts) -> str:
        return self._sync.run(messages, **opts)

    def health_check(self) -> int:
        return self._sync.health_check()

    # 비동기 퍼사드
    async def run_async(self, messages: Union[Dict, List[Dict]], **opts) -> str:
        return await self._async.run(messages, **opts)

    async def health_check_async(self) -> int:
        return await self._async.health_check()

    async def run_stream(self, messages: Union[Dict, List[Dict]], **opts) -> AsyncGenerator:
        return self._stream.run(messages, **opts)

    @staticmethod
    def _prepare_request(
        self_ref,
        messages: Union[Dict, List[Dict]],
        **opts
    ) -> Dict[str, Any]:
        # 공통 전처리: 메시지 정규화, 헤더/바디 구성
        if isinstance(messages, dict):
            messages = [messages]
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self_ref.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self_ref.default_model,
            "messages": messages,
            **opts
        }
        return {
            "url":    f"{self_ref.base_url}/chat/completions",
            "headers": headers,
            "json":   body
        }

class SyncHelper:
    def __init__(self, parent: PwcLLMClient):
        self.p = parent

    def run(self, messages: Union[Dict, List[Dict]], **opts) -> str:
        req = PwcLLMClient._prepare_request(self.p, messages, **opts)
        resp = requests.post(**req, verify=False)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def health_check(self) -> int:
        if self.p.logger:
            self.p.logger.info("PWC Sync Health Check")
        url = self.p.base_url + "/models"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.p.api_key}"
        }
        # v1 archive 방식 주석
        # url = self.p.base_url + "/healthz"
        # headers = { ... }
        resp = requests.get(url, headers=headers, verify=False)
        if self.p.logger:
            self.p.logger.info(f"Health Check Status code: {resp.status_code}")
        print(f"[Sync] Health Check Status code: {resp.status_code}")
        return resp.status_code

class AsyncHelper:
    def __init__(self, parent: PwcLLMClient):
        self.p = parent

    async def run(self, messages: Union[Dict, List[Dict]], **opts) -> str:
        req = PwcLLMClient._prepare_request(self.p, messages, **opts)
        async with aiohttp.ClientSession() as sess:
            async with sess.post(req["url"], headers=req["headers"], json=req["json"], ssl=False) as r:
                r.raise_for_status()
                data = await r.json()
                return data["choices"][0]["message"]["content"]

    async def health_check(self) -> int:
        if self.p.logger:
            self.p.logger.info("PWC Async Health Check")
        url = self.p.base_url + "/models"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.p.api_key}"
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=headers, ssl=False) as resp:
                status = resp.status
                if self.p.logger:
                    self.p.logger.info(f"Health Check Status code: {status}")
                print(f"[Async] Health Check Status code: {status}")
                return status

class StreamHelper:
    def __init__(self, parent: PwcLLMClient):
        self.p = parent

    async def run(self, messages: Union[Dict, List[Dict]], **opts) -> AsyncGenerator:
        opts.setdefault("stream", True)
        req = PwcLLMClient._prepare_request(self.p, messages, **opts)
        async with aiohttp.ClientSession() as sess:
            async with sess.post(req["url"], headers=req["headers"], json=req["json"], ssl=False) as r:
                r.raise_for_status()
                async for line in r.content:
                    line = line.decode().strip()
                    if not line.startswith("data: "):
                        continue
                    chunk = line[len("data: "):]
                    if chunk == "[DONE]":
                        break
                    yield json.loads(chunk)
