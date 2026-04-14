from app.core.config import settings


class R2StorageAdapter:
    def __init__(self) -> None:
        self.bucket_name = settings.r2_bucket_name
        self.public_base_url = settings.r2_public_base_url

    def build_public_url(self, object_key: str) -> str:
        if not self.public_base_url:
            return object_key
        return f"{self.public_base_url.rstrip('/')}/{object_key.lstrip('/')}"
