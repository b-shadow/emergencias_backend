import json
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.core.exceptions import bad_request


class GroqUrgencyService:
    """Clasifica nivel de urgencia de emergencia vehicular con Groq."""

    VALID_LEVELS = {"BAJO", "MEDIO", "ALTO"}

    def __init__(self) -> None:
        self.base_url = settings.groq_base_url.rstrip("/")
        self.model = settings.groq_model
        self.timeout = settings.groq_timeout_seconds
        self.api_key = settings.groq_api_key

    def _build_system_prompt(self) -> str:
        return (
            "Eres un asistente experto en emergencias vehiculares. "
            "Debes clasificar el nivel de urgencia SOLO como BAJO, MEDIO o ALTO. "
            "Usa estos criterios:\n"
            "- BAJO: falla leve/preventiva, el vehiculo puede moverse, usuario en lugar seguro, sin riesgo inmediato.\n"
            "- MEDIO: falla importante, puede quedar varado o empeorar, pero sin peligro directo inmediato.\n"
            "- ALTO: riesgo inmediato para personas/terceros/vehiculo, accidente, humo/fuego, fuga de gasolina, frenos/direccion sin respuesta, varado en via peligrosa.\n"
            "Tambien considera casos de carbonilla en gasolina segun contexto (leve=BAJO, varado sin riesgo=MEDIO, con humo/olor fuerte/inmovilizacion peligrosa=ALTO).\n"
            "Responde EXCLUSIVAMENTE en JSON valido con esta estructura exacta:\n"
            "{\n"
            '  "nivel_urgencia": "BAJO|MEDIO|ALTO",\n'
            '  "criterio_detectado": "texto breve",\n'
            '  "mensaje_chatbot": "mensaje para el usuario final en tono claro y empatico",\n'
            '  "accion_recomendada": "texto breve",\n'
            '  "confianza": 0.0\n'
            "}\n"
            "No incluyas markdown, ni explicaciones fuera del JSON."
        )

    async def classify_problem(self, descripcion: str) -> dict[str, Any]:
        descripcion = (descripcion or "").strip()
        if len(descripcion) < 8:
            raise bad_request("La descripcion del problema es muy corta para analizar")

        if not self.api_key or self.api_key.strip().lower() == "colocar api key aqui":
            raise bad_request("GROQ_API_KEY no configurada. Coloca tu API key en entorno")

        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {
                    "role": "user",
                    "content": (
                        "Analiza esta descripcion de emergencia vehicular y clasifica urgencia:\n"
                        f"{descripcion}"
                    ),
                },
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            logger.error("Groq error {}: {}", response.status_code, response.text)
            raise bad_request(f"No se pudo procesar el problema con IA (Groq): {response.status_code}")

        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        try:
            parsed = json.loads(content)
        except Exception as exc:
            logger.error("Respuesta Groq invalida: {}", content)
            raise bad_request("La IA devolvio una respuesta invalida") from exc

        nivel = str(parsed.get("nivel_urgencia", "")).upper().strip()
        if nivel not in self.VALID_LEVELS:
            raise bad_request("La IA no devolvio un nivel de urgencia valido")

        mensaje = str(parsed.get("mensaje_chatbot", "")).strip()
        criterio = str(parsed.get("criterio_detectado", "")).strip()
        accion = str(parsed.get("accion_recomendada", "")).strip()

        try:
            confianza = float(parsed.get("confianza", 0.7))
        except (TypeError, ValueError):
            confianza = 0.7

        confianza = max(0.0, min(1.0, confianza))

        if not mensaje:
            mensaje = (
                "Analizamos tu descripcion y recomendamos atencion "
                f"de urgencia {nivel.lower()}."
            )

        return {
            "nivel_urgencia": nivel,
            "criterio_detectado": criterio,
            "mensaje_chatbot": mensaje,
            "accion_recomendada": accion,
            "confianza": confianza,
            "proveedor": "groq",
            "modelo": self.model,
        }
