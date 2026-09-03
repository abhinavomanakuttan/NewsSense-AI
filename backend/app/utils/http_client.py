import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class HttpClient:
    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        kwargs: dict = {"timeout": self.timeout, "follow_redirects": True}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = httpx.AsyncClient(**kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get(self, url: str, **kwargs) -> httpx.Response:
        if not self.client:
            self.client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def post(self, url: str, **kwargs) -> httpx.Response:
        if not self.client:
            self.client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return response
