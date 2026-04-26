import json
import logging
import base64
import os
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class FCMService:
    """
    Servicio para enviar notificaciones push via Firebase Cloud Messaging (FCM).
    
    Este servicio maneja la inicialización de Firebase Admin SDK y el envío
    de notificaciones a dispositivos específicos.
    """
    
    _firebase_app = None
    _initialized = False

    @classmethod
    def initialize(cls) -> None:
        """
        Inicializa Firebase Admin una sola vez.
        
        Soporta dos modos:
        1. Credenciales JSON en variable de entorno (json string)
        2. Credenciales desde archivo
        """
        if cls._initialized:
            logger.debug("[FCM] Ya fue inicializado anteriormente")
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
        except ImportError:
            logger.warning("[FCM] ❌ firebase-admin no está instalado. FCM está deshabilitado.")
            cls._initialized = True
            return

        # Si FCM no está habilitado, salir
        if not settings.FCM_ENABLED:
            logger.warning("[FCM] ⚠️  FCM está deshabilitado en settings.FCM_ENABLED = False")
            cls._initialized = True
            return

        logger.info("[FCM] 🚀 Iniciando Firebase Admin SDK...")

        try:
            # Intenta cargar credenciales desde JSON string o archivo
            if settings.FIREBASE_CREDENTIALS_JSON:
                logger.debug("[FCM] 📋 FIREBASE_CREDENTIALS_JSON detectada (primeros 50 chars): " + 
                           settings.FIREBASE_CREDENTIALS_JSON[:50] + "...")
                
                try:
                    # Primero intenta decodificar como base64
                    try:
                        logger.debug("[FCM] Intentando decodificar como base64...")
                        decoded = base64.b64decode(
                            settings.FIREBASE_CREDENTIALS_JSON, 
                            validate=True
                        ).decode('utf-8')
                        creds_dict = json.loads(decoded)
                        logger.info("[FCM] ✅ Credenciales decodificadas correctamente desde base64")
                    except (base64.binascii.Error, UnicodeDecodeError) as e:
                        logger.debug(f"[FCM] Base64 decode falló ({type(e).__name__}), intentando como JSON directo...")
                        creds_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                        logger.info("[FCM] ✅ Credenciales cargadas como JSON directo")
                    except json.JSONDecodeError as e:
                        logger.debug(f"[FCM] Base64 JSON parse falló: {e}")
                        raise
                    
                    logger.debug(f"[FCM] 🔑 Credenciales contienen project_id: {creds_dict.get('project_id', 'N/A')}")
                    cred = credentials.Certificate(creds_dict)
                    logger.info("[FCM] ✅ Credencial Certificate creado exitosamente")
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"[FCM] ⚠️  JSON parse falló ({type(e).__name__}: {e}). Intentando como ruta a archivo...")
                    try:
                        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_JSON)
                        logger.info("[FCM] ✅ Credenciales cargadas desde archivo")
                    except FileNotFoundError:
                        logger.error("[FCM] ❌ Archivo no encontrado: " + settings.FIREBASE_CREDENTIALS_JSON)
                        raise
                    except Exception as file_e:
                        logger.error(f"[FCM] ❌ Error cargando archivo: {file_e}")
                        raise
            elif settings.fcm_project_id and settings.fcm_client_email and settings.fcm_private_key:
                logger.info("[FCM] 📋 Usando credenciales legacy (FCM_PROJECT_ID/FCM_CLIENT_EMAIL/FCM_PRIVATE_KEY)")
                private_key = settings.fcm_private_key.replace("\\n", "\n")
                creds_dict = {
                    "type": "service_account",
                    "project_id": settings.fcm_project_id,
                    "private_key": private_key,
                    "client_email": settings.fcm_client_email,
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
                cred = credentials.Certificate(creds_dict)
                logger.info("[FCM] ✅ Credenciales legacy convertidas correctamente")
            elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                logger.info(f"[FCM] 📋 Usando GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
                cred = credentials.Certificate(creds_path)
                logger.info("[FCM] ✅ Credenciales cargadas desde GOOGLE_APPLICATION_CREDENTIALS")
            else:
                logger.warning("[FCM] ❌ FIREBASE_CREDENTIALS_JSON NO ESTÁ CONFIGURADA")
                cls._initialized = True
                return

            logger.info("[FCM] 🔧 Inicializando firebase_admin.initialize_app()...")
            cls._firebase_app = firebase_admin.initialize_app(cred)
            logger.info("[FCM] ✅ Firebase Admin inicializado CORRECTAMENTE")
            cls._initialized = True

        except Exception as e:
            logger.exception(f"[FCM] ❌ EXCEPCIÓN inicializando Firebase Admin: {type(e).__name__}: {e}")
            logger.error(f"[FCM] Stack trace completo arriba ⬆️")
            cls._initialized = True
            # No levantamos excepción, permitimos que el app siga funcionando sin FCM

    @classmethod
    def _get_fcm_unavailable_reason(cls) -> str:
        """
        Diagnostica por qué FCM no está disponible.
        
        Returns:
            String con la razón específica del problema
        """
        if not settings.FCM_ENABLED:
            return "FCM_ENABLED es False en settings"
        
        if not settings.FIREBASE_CREDENTIALS_JSON:
            has_legacy = bool(settings.fcm_project_id and settings.fcm_client_email and settings.fcm_private_key)
            has_google_app_creds = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
            if not has_legacy and not has_google_app_creds:
                return "No hay credenciales FCM configuradas (FIREBASE_CREDENTIALS_JSON / legacy / GOOGLE_APPLICATION_CREDENTIALS)"
        
        try:
            import firebase_admin
        except ImportError:
            return "firebase-admin no instalado"
        
        if cls._firebase_app is None:
            try:
                if firebase_admin._apps.get(None) is None:
                    return "firebase_admin.initialize_app() falló en init (ver logs arriba)"
            except:
                pass
        
        return "motivo desconocido (ver logs)"

    @classmethod
    def is_available(cls) -> bool:
        """
        Verifica si FCM está disponible y habilitado.
        
        Intenta inicializar Firebase si aún no se ha hecho (lazy init).
        
        Returns:
            True si se puede enviar notificaciones push, False en caso contrario
        """
        if not settings.FCM_ENABLED:
            logger.debug("[FCM] ⚠️  FCM_ENABLED es False")
            return False
        
        # Lazy init: si no se ha inicializado, intentar ahora
        if not cls._initialized:
            logger.debug("[FCM] Lazy init: inicializando Firebase en primer uso...")
            cls.initialize()
        
        try:
            import firebase_admin
            app_available = cls._firebase_app is not None or firebase_admin._apps.get(None) is not None
            
            if not app_available:
                logger.debug(f"[FCM] ⚠️  Firebase app no está inicializado (_firebase_app={cls._firebase_app})")
            
            return app_available
        except ImportError:
            logger.debug("[FCM] ⚠️  firebase_admin no puede importarse")
            return False
        except AttributeError as e:
            logger.debug(f"[FCM] ⚠️  Error accediendo firebase_admin._apps: {e}")
            return False

    @classmethod
    def send_to_token(
        cls,
        token: str,
        title: str,
        body: str,
        data: Optional[dict[str, str]] = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Envía una notificación push a un token FCM específico.
        
        Args:
            token: Token FCM del dispositivo
            title: Título de la notificación
            body: Cuerpo/mensaje de la notificación
            data: Datos adicionales (diccionario de strings)
            **kwargs: Opciones adicionales (android, webpush, apns, etc)
            
        Returns:
            Diccionario con resultado del envío:
            {
                'success': bool,
                'message_id': str | None,
                'error': str | None,
                'token_invalid': bool
            }
        """
        # Lazy init: asegurar que Firebase esté inicializado
        if not cls._initialized:
            logger.debug("[FCM] Lazy init en send_to_token()...")
            cls.initialize()
        
        if not cls.is_available():
            reason = cls._get_fcm_unavailable_reason()
            logger.warning(f"[FCM] ❌ FCM NO DISPONIBLE ({reason}). Token {token[:20]}... NO será enviado a dispositivo.")
            return {
                'success': False,
                'message_id': None,
                'error': 'FCM not available',
                'token_invalid': False
            }

        try:
            from firebase_admin import messaging

            # Construir el mensaje
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=token,
                **kwargs
            )

            # Enviar
            message_id = messaging.send(message)
            logger.info(f"Notificación enviada correctamente. Message ID: {message_id}")
            
            return {
                'success': True,
                'message_id': message_id,
                'error': None,
                'token_invalid': False
            }

        except Exception as e:
            error_str = str(e).lower()
            is_invalid_token = (
                "invalid registration token" in error_str or
                "registration token is invalid" in error_str or
                "the registration token is not a valid fcm token" in error_str or
                "no matching credential found for the provided token" in error_str
            )

            log_level = logging.WARNING if is_invalid_token else logging.ERROR
            logger.log(
                log_level,
                f"Error enviando notificación a token {token[:20]}...: {e}"
            )

            return {
                'success': False,
                'message_id': None,
                'error': str(e),
                'token_invalid': is_invalid_token
            }

    @classmethod
    def send_to_tokens(
        cls,
        tokens: list[str],
        title: str,
        body: str,
        data: Optional[dict[str, str]] = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Envía una notificación push a múltiples tokens (multicast).
        
        Args:
            tokens: Lista de tokens FCM
            title: Título de la notificación
            body: Cuerpo/mensaje de la notificación
            data: Datos adicionales (diccionario de strings)
            **kwargs: Opciones adicionales
            
        Returns:
            Diccionario con resultado:
            {
                'success_count': int,
                'failure_count': int,
                'results': list[dict],  # Resultado por cada token
                'message_ids': list[str]
            }
        """
        # Lazy init: asegurar que Firebase esté inicializado
        if not cls._initialized:
            logger.debug("[FCM] Lazy init en send_to_tokens()...")
            cls.initialize()
        
        if not cls.is_available() or not tokens:
            return {
                'success_count': 0,
                'failure_count': len(tokens),
                'results': [
                    {'token': t, 'success': False, 'error': 'FCM not available'}
                    for t in tokens
                ],
                'message_ids': []
            }

        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=tokens,
                **kwargs
            )

            # send_multicast depende de /batch (puede fallar con 404 en algunos entornos).
            # Preferir send_each_for_multicast cuando exista.
            if hasattr(messaging, "send_each_for_multicast"):
                response = messaging.send_each_for_multicast(message)

                results = []
                message_ids = []
                success_count = 0
                failure_count = 0

                for idx, send_response in enumerate(response.responses):
                    if send_response.exception is None:
                        success_count += 1
                        results.append({
                            'token': tokens[idx],
                            'success': True,
                            'message_id': send_response.message_id,
                            'token_invalid': False
                        })
                        message_ids.append(send_response.message_id)
                    else:
                        failure_count += 1
                        error_str = str(send_response.exception).lower()
                        is_invalid_token = (
                            "invalid registration token" in error_str or
                            "registration token is invalid" in error_str or
                            "the registration token is not a valid fcm token" in error_str or
                            "no matching credential found" in error_str
                        )
                        results.append({
                            'token': tokens[idx],
                            'success': False,
                            'error': str(send_response.exception),
                            'token_invalid': is_invalid_token
                        })

                logger.info(
                    f"Multicast (send_each_for_multicast) enviado. Éxito: {success_count}, "
                    f"Fallos: {failure_count}"
                )

                return {
                    'success_count': success_count,
                    'failure_count': failure_count,
                    'results': results,
                    'message_ids': message_ids
                }

            # Fallback seguro: enviar token por token usando send(message)
            logger.warning(
                "[FCM] send_each_for_multicast no disponible; usando fallback por token"
            )
            results = []
            message_ids = []
            success_count = 0
            failure_count = 0

            for token in tokens:
                one = cls.send_to_token(
                    token=token,
                    title=title,
                    body=body,
                    data=data,
                    **kwargs
                )
                if one.get("success"):
                    success_count += 1
                    message_ids.append(one.get("message_id"))
                    results.append({
                        "token": token,
                        "success": True,
                        "message_id": one.get("message_id"),
                        "token_invalid": False,
                    })
                else:
                    failure_count += 1
                    results.append({
                        "token": token,
                        "success": False,
                        "error": one.get("error"),
                        "token_invalid": one.get("token_invalid", False),
                    })

            logger.info(
                f"Multicast (fallback por token) enviado. Éxito: {success_count}, "
                f"Fallos: {failure_count}"
            )

            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "results": results,
                "message_ids": message_ids,
            }

        except Exception as e:
            logger.error(f"Error en multicast: {e}")
            return {
                'success_count': 0,
                'failure_count': len(tokens),
                'results': [
                    {'token': t, 'success': False, 'error': str(e)}
                    for t in tokens
                ],
                'message_ids': []
            }

    @classmethod
    def build_message(
        cls,
        title: str,
        body: str,
        data: Optional[dict[str, str]] = None,
        android_priority: str = "high",
        webpush_ttl: int = 3600,
    ) -> dict[str, Any]:
        """
        Construye un payload de mensaje con opciones platform-specific.
        
        Args:
            title: Título
            body: Cuerpo
            data: Variable de datos
            android_priority: Prioridad en Android (high, normal)
            webpush_ttl: TTL en segundos para web
            
        Returns:
            Diccionario con configuración completa
        """
        return {
            'title': title,
            'body': body,
            'data': data or {},
            'android_priority': android_priority,
            'webpush_ttl': webpush_ttl
        }
