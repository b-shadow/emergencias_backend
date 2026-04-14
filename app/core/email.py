import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings


class EmailService:
    """Servicio para envío de correos mediante Gmail SMTP"""

    @staticmethod
    def enviar_recuperacion_contrasena(correo_destino: str, token: str) -> bool:
        """
        Envía correo con enlace de recuperación de contraseña
        
        Args:
            correo_destino: Email del usuario
            token: Token de recuperación
            
        Returns:
            bool: True si se envió exitosamente, False en caso contrario
        """
        try:
            # Generar enlace de recuperación
            reset_link = f"{settings.frontend_url}/reset-password?token={token}"
            
            # Crear mensaje
            mensaje = MIMEMultipart("alternative")
            mensaje["Subject"] = "Recupera tu contraseña - Plataforma de Emergencias Vehiculares"
            mensaje["From"] = settings.smtp_user
            mensaje["To"] = correo_destino
            
            # Cuerpo en texto plano
            texto_plano = f"""
Hola,

Recibimos una solicitud para recuperar tu contraseña. 
Si no fuiste tú, ignora este correo.

Para resetear tu contraseña, haz clic en el siguiente enlace:
{reset_link}

Este enlace es válido por 15 minutos.

Si el enlace no funciona, copia y pega esto en tu navegador:
{reset_link}

Si tienes problemas, contacta a nuestro equipo de soporte.

Saludos,
Equipo de Atención de Emergencias Vehiculares
            """
            
            # Cuerpo en HTML
            html = f"""
<html>
  <body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #333;">Recuperar Contraseña</h2>
      <p>Hola,</p>
      <p>Recibimos una solicitud para recuperar tu contraseña. Si no fuiste tú, <strong>ignora este correo</strong>.</p>
      
      <p style="margin-top: 30px;">
        <a href="{reset_link}" 
           style="background-color: #007bff; color: white; padding: 12px 30px; 
                  text-decoration: none; border-radius: 5px; display: inline-block;">
          Resetear Contraseña
        </a>
      </p>
      
      <p style="color: #666; font-size: 12px;">
        Este enlace es válido por 15 minutos.
      </p>
      
      <p style="color: #666; font-size: 12px; margin-top: 30px;">
        Si el botón no funciona, copia este enlace en tu navegador:<br>
        <code>{reset_link}</code>
      </p>
      
      <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
      <p style="color: #999; font-size: 12px; text-align: center;">
        Equipo de Atención de Emergencias Vehiculares
      </p>
    </div>
  </body>
</html>
            """
            
            # Adjuntar ambas versiones
            parte_texto = MIMEText(texto_plano, "plain")
            parte_html = MIMEText(html, "html")
            mensaje.attach(parte_texto)
            mensaje.attach(parte_html)
            
            # Enviar correo
            with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as servidor:
                servidor.starttls()  # Iniciar TLS
                servidor.login(settings.smtp_user, settings.smtp_password)
                servidor.sendmail(settings.smtp_user, correo_destino, mensaje.as_string())
            
            return True
            
        except Exception as e:
            print(f"Error al enviar correo a {correo_destino}: {str(e)}")
            return False

    @staticmethod
    def enviar_confirmacion_registro(correo_destino: str, nombre: str) -> bool:
        """
        Envía correo de confirmación de registro
        
        Args:
            correo_destino: Email del usuario
            nombre: Nombre del usuario
            
        Returns:
            bool: True si se envió exitosamente
        """
        try:
            mensaje = MIMEMultipart("alternative")
            mensaje["Subject"] = "Bienvenido a la Plataforma - Confirmación de Registro"
            mensaje["From"] = settings.smtp_user
            mensaje["To"] = correo_destino
            
            texto_plano = f"""
Hola {nombre},

¡Bienvenido a la Plataforma de Atención de Emergencias Vehiculares!

Tu cuenta ha sido registrada exitosamente. Ahora puedes iniciar sesión con tus credenciales.

Puedes acceder a la plataforma en:
{settings.frontend_url}

Si tienes preguntas, no dudes en contactarnos.

Saludos,
Equipo de Emergencias Vehiculares
            """
            
            html = f"""
<html>
  <body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #333;">¡Bienvenido!</h2>
      <p>Hola <strong>{nombre}</strong>,</p>
      <p>¡Bienvenido a la <strong>Plataforma de Atención de Emergencias Vehiculares</strong>!</p>
      
      <p>Tu cuenta ha sido registrada exitosamente. Ahora puedes iniciar sesión con tus credenciales.</p>
      
      <p style="margin-top: 30px;">
        <a href="{settings.frontend_url}" 
           style="background-color: #28a745; color: white; padding: 12px 30px; 
                  text-decoration: none; border-radius: 5px; display: inline-block;">
          Ir a la Plataforma
        </a>
      </p>
      
      <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
      <p style="color: #999; font-size: 12px; text-align: center;">
        Si tienes preguntas, contáctanos.
      </p>
    </div>
  </body>
</html>
            """
            
            parte_texto = MIMEText(texto_plano, "plain")
            parte_html = MIMEText(html, "html")
            mensaje.attach(parte_texto)
            mensaje.attach(parte_html)
            
            with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as servidor:
                servidor.starttls()
                servidor.login(settings.smtp_user, settings.smtp_password)
                servidor.sendmail(settings.smtp_user, correo_destino, mensaje.as_string())
            
            return True
            
        except Exception as e:
            print(f"Error al enviar confirmación a {correo_destino}: {str(e)}")
            return False
