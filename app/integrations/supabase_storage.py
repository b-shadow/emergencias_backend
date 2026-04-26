from __future__ import annotations

from urllib.parse import quote

import httpx

from app.core.config import settings


class SupabaseStorageAdapter:
    """Adapter mínimo para subir archivos a Supabase Storage."""

    def __init__(self) -> None:
        self.base_url = settings.supabase_url.rstrip("/")
        self.service_role_key = settings.supabase_service_role_key
        self.bucket = settings.supabase_storage_bucket

    def is_configured(self) -> bool:
        return bool(self.base_url and self.service_role_key and self.bucket)

    def _validate_config(self) -> None:
        if not self.is_configured():
            raise RuntimeError(
                "Supabase Storage no está configurado. "
                "Define SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y SUPABASE_STORAGE_BUCKET."
            )

    def upload_bytes(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
        upsert: bool = True,
    ) -> str:
        """
        Sube bytes al bucket y retorna URL pública.
        """
        self._validate_config()

        encoded_path = quote(object_path.lstrip("/"), safe="/")
        upload_url = f"{self.base_url}/storage/v1/object/{self.bucket}/{encoded_path}"

        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": content_type,
            "x-upsert": "true" if upsert else "false",
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(upload_url, headers=headers, content=content)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Error subiendo archivo a Supabase ({response.status_code}): {response.text}"
                )

        public_base = f"{self.base_url}/storage/v1/object/public/{self.bucket}"
        return f"{public_base}/{encoded_path}"
