from app.core.config import settings


class FCMService:
    def __init__(self) -> None:
        self.project_id = settings.fcm_project_id

    def send_push(self, token: str, title: str, body: str) -> dict[str, str]:
        return {
            "status": "queued",
            "project_id": self.project_id,
            "token": token,
            "title": title,
            "body": body,
        }
