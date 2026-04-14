import httpx

from app.core.config import settings


class AIImageClient:
    def __init__(self) -> None:
        self.base_url = settings.ai_image_service_url.rstrip("/")
        self.api_key = settings.ai_image_service_api_key

    async def analyze_image_url(self, image_url: str) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/analyze",
                json={"image_url": image_url},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
