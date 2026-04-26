import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings


class EmailService:
    """Servicio para envio de correos (SendGrid o SMTP)."""

    @staticmethod
    def enviar_recuperacion_contrasena(correo_destino: str, token: str) -> bool:
        """
        Envia correo con enlace de recuperacion de contrasena.
        """
        reset_link = f"{settings.frontend_url}/reset-password?token={token}"
        asunto = "Recupera tu contrasena - Plataforma de Emergencias Vehiculares"
        texto_plano = f"""
Hola,

Recibimos una solicitud para recuperar tu contrasena.
Si no fuiste tu, ignora este correo.

Para resetear tu contrasena, usa este enlace:
{reset_link}

Este enlace es valido por {settings.reset_token_expire_minutes} minutos.

Saludos,
Equipo de Atencion de Emergencias Vehiculares
        """.strip()
        html = f"""
<html>
  <body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #333;">Recuperar contrasena</h2>
      <p>Hola,</p>
      <p>Recibimos una solicitud para recuperar tu contrasena. Si no fuiste tu, <strong>ignora este correo</strong>.</p>
      <p style="margin-top: 24px;">
        <a href="{reset_link}"
           style="background-color: #007bff; color: white; padding: 12px 30px;
                  text-decoration: none; border-radius: 5px; display: inline-block;">
          Resetear contrasena
        </a>
      </p>
      <p style="color: #666; font-size: 12px;">
        Este enlace es valido por {settings.reset_token_expire_minutes} minutos.
      </p>
      <p style="color: #666; font-size: 12px; margin-top: 20px;">
        Si el boton no funciona, copia este enlace en tu navegador:<br>
        <code>{reset_link}</code>
      </p>
    </div>
  </body>
</html>
        """.strip()

        provider = (settings.email_provider or "smtp").strip().lower()
        if provider == "sendgrid":
            return EmailService._send_with_sendgrid(
                correo_destino=correo_destino,
                asunto=asunto,
                texto_plano=texto_plano,
                html=html,
            )

        return EmailService._send_with_smtp(
            correo_destino=correo_destino,
            asunto=asunto,
            texto_plano=texto_plano,
            html=html,
        )

    @staticmethod
    def _resolve_from_email() -> str:
        if settings.email_from and settings.email_from.strip():
            return settings.email_from.strip()
        if settings.smtp_user and settings.smtp_user.strip():
            return settings.smtp_user.strip()
        return "no-reply@localhost"

    @staticmethod
    def _send_with_sendgrid(
        correo_destino: str,
        asunto: str,
        texto_plano: str,
        html: str,
    ) -> bool:
        try:
            api_key = (settings.sendgrid_api_key or "").strip()
            if not api_key:
                print("SendGrid no configurado: falta SENDGRID_API_KEY")
                return False

            payload = {
                "personalizations": [{"to": [{"email": correo_destino}]}],
                "from": {"email": EmailService._resolve_from_email()},
                "subject": asunto,
                "content": [
                    {"type": "text/plain", "value": texto_plano},
                    {"type": "text/html", "value": html},
                ],
            }

            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )

            if response.status_code in (200, 202):
                return True

            print(
                f"Error SendGrid ({response.status_code}) enviando a {correo_destino}: "
                f"{response.text}"
            )
            return False
        except Exception as exc:
            print(f"Error SendGrid enviando a {correo_destino}: {str(exc)}")
            return False

    @staticmethod
    def _send_with_smtp(
        correo_destino: str,
        asunto: str,
        texto_plano: str,
        html: str,
    ) -> bool:
        try:
            remitente = EmailService._resolve_from_email()

            mensaje = MIMEMultipart("alternative")
            mensaje["Subject"] = asunto
            mensaje["From"] = remitente
            mensaje["To"] = correo_destino
            mensaje.attach(MIMEText(texto_plano, "plain"))
            mensaje.attach(MIMEText(html, "html"))

            with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as servidor:
                servidor.starttls()
                servidor.login(settings.smtp_user, settings.smtp_password)
                servidor.sendmail(remitente, correo_destino, mensaje.as_string())
            return True
        except Exception as exc:
            print(f"Error SMTP enviando a {correo_destino}: {str(exc)}")
            return False
