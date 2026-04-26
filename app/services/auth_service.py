from jose import JWTError, jwt
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID

from fastapi import HTTPException

from app.core.config import settings
from app.core.enums import RolUsuario, TipoActor, ResultadoAuditoria, EstadoAprobacionTaller, EstadoOperativoTaller
from app.core.exceptions import unauthorized, forbidden, bad_request
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.core.email import EmailService
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.taller import Taller
from app.models.bitacora import Bitacora


class AuthService:
    # Mapeo de roles a TipoActor
    ROLE_TO_ACTOR = {
        RolUsuario.CLIENTE: TipoActor.CLIENTE,
        RolUsuario.TALLER: TipoActor.TALLER,
        RolUsuario.ADMINISTRADOR: TipoActor.ADMINISTRADOR,
    }

    @staticmethod
    def _registrar_bitacora(
        db: Session,
        usuario_id: str | UUID | None,
        accion: str,
        resultado: ResultadoAuditoria,
        detalle: str | None = None,
        tipo_actor: TipoActor = TipoActor.SISTEMA,
    ) -> None:
        """Registra eventos de autenticación en la bitácora"""
        # Convertir string a UUID si es necesario
        actor_id = None
        if usuario_id:
            if isinstance(usuario_id, str):
                try:
                    actor_id = UUID(usuario_id)
                except (ValueError, AttributeError):
                    actor_id = usuario_id
            else:
                actor_id = usuario_id
        
        bitacora = Bitacora(
            tipo_actor=tipo_actor,
            id_actor=actor_id,
            accion=accion,
            modulo="Autenticación",
            entidad_afectada="Usuario",
            id_entidad_afectada=actor_id,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()

    @staticmethod
    def _validar_entorno(rol: RolUsuario, client_type: str) -> None:
        """Valida que el rol pueda acceder desde el entorno especificado"""
        # Cliente solo desde mobile
        if rol == RolUsuario.CLIENTE and client_type != "mobile":
            raise forbidden("Los clientes deben acceder desde la aplicación móvil")
        
        # Taller y Admin solo desde web
        if rol in (RolUsuario.TALLER, RolUsuario.ADMINISTRADOR) and client_type != "web":
            raise forbidden(f"Los {rol.value} deben acceder desde la aplicación web")

    @staticmethod
    def registrar_cliente(
        db: Session,
        correo: str,
        contrasena: str,
        confirmar_contrasena: str,
        nombre_completo: str,
        nombre: str,
        apellido: str,
        telefono: str | None = None,
        ci: str | None = None,
        direccion: str | None = None,
    ) -> dict:
        """Registra un nuevo cliente en el sistema"""
        
        # Validar que las contraseñas coincidan
        if contrasena != confirmar_contrasena:
            raise bad_request("Las contraseñas no coinciden")
        
        # Validar que el correo no esté duplicado
        usuario_existente = db.query(Usuario).filter(Usuario.correo == correo).first()
        if usuario_existente:
            AuthService._registrar_bitacora(
                db=db,
                usuario_id=None,
                accion="Intento de registro fallido - Correo duplicado",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"Correo ya registrado: {correo}",
            )
            raise bad_request("El correo electrónico ya está registrado en el sistema")
        
        # Validar que el CI no sea duplicado (si se proporciona)
        if ci:
            cliente_existente = db.query(Cliente).filter(Cliente.ci == ci).first()
            if cliente_existente:
                AuthService._registrar_bitacora(
                    db=db,
                    usuario_id=None,
                    accion="Intento de registro fallido - CI duplicado",
                    resultado=ResultadoAuditoria.ADVERTENCIA,
                    detalle=f"CI ya registrado: {ci}",
                )
                raise bad_request("El CI ya está registrado en el sistema")
        
        # Crear usuario con rol CLIENTE
        nuevo_usuario = Usuario(
            correo=correo,
            contrasena_hash=get_password_hash(contrasena),
            nombre_completo=nombre_completo,
            rol=RolUsuario.CLIENTE,
            es_activo=True,
        )
        db.add(nuevo_usuario)
        db.flush()  # Para obtener el id_usuario sin hacer commit
        
        # Crear cliente asociado
        nuevo_cliente = Cliente(
            id_usuario=nuevo_usuario.id_usuario,
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
            ci=ci,
            direccion=direccion,
        )
        db.add(nuevo_cliente)
        db.commit()
        
        # Registrar en bitácora
        AuthService._registrar_bitacora(
            db=db,
            usuario_id=str(nuevo_usuario.id_usuario),
            accion="Registro de nuevo cliente",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Cliente registrado correctamente. Email: {correo}, CI: {ci if ci else 'No especificado'}",
            tipo_actor=TipoActor.CLIENTE,
        )
        
        # Enviar notificación de bienvenida al cliente
        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService
        
        NotificacionService.send_notification_to_user(
            db=db,
            id_usuario_destino=nuevo_usuario.id_usuario,
            tipo_usuario_destino="CLIENTE",
            titulo="¡Bienvenido a Asistencia Vehicular!",
            mensaje=f"Hola {nombre}, tu cuenta ha sido creada exitosamente. Ya puedes solicitar asistencia vehicular en caso de emergencia.",
            tipo_notificacion=TipoNotificacion.PUSH,
            categoria_evento=CategoriaNotificacion.SISTEMA,
            referencia_entidad="Usuario",
            referencia_id=nuevo_usuario.id_usuario,
        )
        
        return {
            "mensaje": "Registro completado exitosamente. Ya puedes iniciar sesión.",
            "correo": correo,
            "rol": RolUsuario.CLIENTE.value,
        }

    @staticmethod
    def registrar_taller(
        db: Session,
        correo: str,
        contrasena: str,
        confirmar_contrasena: str,
        nombre_taller: str,
        telefono: str,
        direccion: str,
        razon_social: str | None = None,
        nit: str | None = None,
        latitud: float | None = None,
        longitud: float | None = None,
        descripcion: str | None = None,
    ) -> dict:
        """Registra una solicitud de nuevo taller en el sistema (estado PENDIENTE)"""
        
        # Validar que las contraseñas coincidan
        if contrasena != confirmar_contrasena:
            raise bad_request("Las contraseñas no coinciden")
        
        # Validar que el correo no esté duplicado
        usuario_existente = db.query(Usuario).filter(Usuario.correo == correo).first()
        if usuario_existente:
            AuthService._registrar_bitacora(
                db=db,
                usuario_id=None,
                accion="Intento de solicitud de registro fallido - Correo duplicado",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"Correo ya registrado: {correo}",
            )
            raise bad_request("El correo electrónico ya está registrado en el sistema")
        
        # Validar que el NIT sea único (solo si se proporciona)
        if nit:
            nit_existente = db.query(Taller).filter(Taller.nit == nit).first()
            if nit_existente:
                AuthService._registrar_bitacora(
                    db=db,
                    usuario_id=None,
                    accion="Intento de solicitud de registro fallido - NIT duplicado",
                    resultado=ResultadoAuditoria.ADVERTENCIA,
                    detalle=f"NIT ya registrado: {nit}",
                )
                raise bad_request("El NIT ingresado ya está asociado a otro taller")
        
        # Crear usuario con rol TALLER (pero inactivo hasta aprobación)
        nuevo_usuario = Usuario(
            correo=correo,
            contrasena_hash=get_password_hash(contrasena),
            nombre_completo=nombre_taller,
            rol=RolUsuario.TALLER,
            es_activo=False,  # El taller solo se activa después de ser aprobado
        )
        db.add(nuevo_usuario)
        db.flush()  # Para obtener el id_usuario sin hacer commit
        
        # Crear taller con estado PENDIENTE
        nuevo_taller = Taller(
            id_usuario=nuevo_usuario.id_usuario,
            nombre_taller=nombre_taller,
            razon_social=razon_social,
            nit=nit,
            telefono=telefono,
            direccion=direccion,
            latitud=latitud,
            longitud=longitud,
            descripcion=descripcion,
            estado_aprobacion=EstadoAprobacionTaller.PENDIENTE,
            estado_operativo=EstadoOperativoTaller.NO_DISPONIBLE,
        )
        db.add(nuevo_taller)
        db.commit()
        
        # Registrar en bitácora
        AuthService._registrar_bitacora(
            db=db,
            usuario_id=str(nuevo_usuario.id_usuario),
            accion="Solicitud de registro de nuevo taller",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Solicitud registrada. Taller: {nombre_taller}, NIT: {nit}, Email: {correo}. Estado: PENDIENTE DE APROBACIÓN",
            tipo_actor=TipoActor.SISTEMA,
        )
        
        return {
            "mensaje": f"¡Bienvenido {nombre_taller}! Tu solicitud de registro ha sido recibida exitosamente. Nuestro equipo de validación está verificando tu información en este momento.",
            "correo": correo,
            "estado": "PENDIENTE_DE_APROBACION",
            "nota": f"Hemos enviado un correo de confirmación a {correo}. Te notificaremos tan pronto tu solicitud sea aprobada o si necesitamos información adicional.",
        }

    @staticmethod
    def login(db: Session, correo: str, contrasena: str, client_type: str = "web") -> dict:
        """Autentica usuario y retorna tokens con rol"""
        usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
        
        # Credenciales inválidas
        if usuario is None or not verify_password(contrasena, usuario.contrasena_hash):
            AuthService._registrar_bitacora(
                db=db,
                usuario_id=None,
                accion="Intento de login fallido - Credenciales inválidas",
                resultado=ResultadoAuditoria.ERROR,
                detalle=f"Credenciales inválidas para correo: {correo}",
            )
            raise unauthorized("Correo o contraseña inválidos")
        
        # Validar que el usuario esté activo
        if not usuario.es_activo:
            AuthService._registrar_bitacora(
                db=db,
                usuario_id=str(usuario.id_usuario),
                accion="Intento de login fallido - Usuario inactivo",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"Usuario inactivo ha intentado iniciar sesión",
            )
            raise unauthorized("Usuario inactivo o no existente")
        
        usuario_id_str = str(usuario.id_usuario)
        
        # Validar entorno permitido
        try:
            AuthService._validar_entorno(usuario.rol, client_type)
        except HTTPException as e:
            tipo_actor = AuthService.ROLE_TO_ACTOR.get(usuario.rol, TipoActor.SISTEMA)
            AuthService._registrar_bitacora(
                db=db,
                usuario_id=usuario_id_str,
                accion="Acceso denegado - Entorno no permitido",
                resultado=ResultadoAuditoria.ERROR,
                detalle=f"Intento desde {client_type}. Rol: {usuario.rol.value}",
                tipo_actor=tipo_actor,
            )
            raise e
        
        # Login exitoso
        tipo_actor = AuthService.ROLE_TO_ACTOR.get(usuario.rol, TipoActor.SISTEMA)
        AuthService._registrar_bitacora(
            db=db,
            usuario_id=usuario_id_str,
            accion="Inicio de sesión exitoso",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Login exitoso desde {client_type}. Rol: {usuario.rol.value}",
            tipo_actor=tipo_actor,
        )
        
        return {
            "access_token": create_access_token(subject=usuario_id_str),
            "refresh_token": create_refresh_token(subject=usuario_id_str),
            "rol": usuario.rol.value,
            "id_usuario": usuario_id_str,
            "nombre_completo": usuario.nombre_completo,
        }

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict[str, str]:
        try:
            payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
            if payload.get("type") != "refresh":
                raise unauthorized("Token de refresco inválido")
            subject = payload.get("sub")
            if subject is None:
                raise unauthorized("Carga útil de token inválida")
        except JWTError as exc:
            raise unauthorized("Token de refresco inválido") from exc

        return {
            "access_token": create_access_token(subject=subject),
            "refresh_token": create_refresh_token(subject=subject),
        }

    @staticmethod
    def logout(db: Session, usuario: Usuario) -> dict:
        """Registra el cierre de sesión en la bitácora"""
        tipo_actor = AuthService.ROLE_TO_ACTOR.get(usuario.rol, TipoActor.SISTEMA)
        
        AuthService._registrar_bitacora(
            db=db,
            usuario_id=str(usuario.id_usuario),
            accion="Cierre de sesión",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Usuario {usuario.rol.value} cerró sesión correctamente",
            tipo_actor=tipo_actor,
        )
        
        return {
            "mensaje": "Sesión cerrada correctamente. Has sido desconectado del sistema.",
            "estado": "logout_exitoso",
        }

    @staticmethod
    def forgot_password(db: Session, correo: str) -> dict:
        """
        Genera token de recuperación y envía correo al usuario
        
        Args:
            db: Sesión de BD
            correo: Correo del usuario
            
        Returns:
            dict: Mensaje confirmando envío de correo
        """
        usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
        
        if not usuario:
            # No revelar si el correo existe o no (seguridad)
            AuthService._registrar_bitacora(
                db=db,
                usuario_id=None,
                accion="Intento de recuperación con correo no registrado",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"Correo: {correo}",
            )
            # Devolver respuesta genérica
            return {
                "mensaje": "Si el correo está registrado, recibirás instrucciones de recuperación en tu bandeja de entrada.",
                "nota": "Revisa también tu carpeta de spam.",
            }
        
        # Generar token único
        reset_token = secrets.token_urlsafe(32)
        token_expiry = datetime.now(timezone.utc) + timedelta(
            minutes=settings.reset_token_expire_minutes
        )
        
        # Guardar token en BD
        usuario.reset_token = reset_token
        usuario.reset_token_expires = token_expiry
        db.commit()
        
        # Enviar correo
        correo_enviado = EmailService.enviar_recuperacion_contrasena(
            usuario.correo, reset_token
        )
        if not correo_enviado:
            raise HTTPException(
                status_code=503,
                detail=(
                    "No se pudo enviar el correo de recuperacion en este momento. "
                    "Intenta nuevamente en unos minutos."
                ),
            )
        
        # Registrar en bitácora
        AuthService._registrar_bitacora(
            db=db,
            usuario_id=str(usuario.id_usuario),
            accion="Solicitud de recuperación de contraseña",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Correo de recuperación enviado a: {correo}",
            tipo_actor=AuthService.ROLE_TO_ACTOR.get(usuario.rol, TipoActor.SISTEMA),
        )
        
        return {
            "mensaje": "Si el correo está registrado, recibirás instrucciones de recuperación en tu bandeja de entrada.",
            "nota": "Revisa también tu carpeta de spam.",
        }

    @staticmethod
    def reset_password(db: Session, token: str, nueva_contrasena: str, confirmar_contrasena: str) -> dict:
        """
        Valida token y actualiza contraseña del usuario
        
        Args:
            db: Sesión de BD
            token: Token de recuperación
            nueva_contrasena: Nueva contraseña
            confirmar_contrasena: Confirmación de nueva contraseña
            
        Returns:
            dict: Mensaje confirmando actualización
        """
        # Validar que las contraseñas coincidan
        if nueva_contrasena != confirmar_contrasena:
            raise bad_request("Las contraseñas no coinciden")
        
        # Buscar usuario por token
        usuario = db.query(Usuario).filter(Usuario.reset_token == token).first()
        
        if not usuario:
            raise bad_request("El enlace de recuperación es inválido. Por favor, solicita uno nuevo.")
        
        # Validar que el token no esté expirado
        now = AuthService._utc_now_matching(usuario.reset_token_expires)
        if usuario.reset_token_expires is None or now > usuario.reset_token_expires:
            usuario.reset_token = None
            usuario.reset_token_expires = None
            db.commit()
            raise bad_request("El enlace de recuperación ha expirado. Por favor, solicita uno nuevo.")
        
        # Actualizar contraseña
        usuario.contrasena_hash = get_password_hash(nueva_contrasena)
        usuario.reset_token = None
        usuario.reset_token_expires = None
        db.commit()
        
        # Registrar en bitácora
        AuthService._registrar_bitacora(
            db=db,
            usuario_id=str(usuario.id_usuario),
            accion="Contraseña actualizada mediante recuperación",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Usuario {usuario.rol.value} actualizó su contraseña",
            tipo_actor=AuthService.ROLE_TO_ACTOR.get(usuario.rol, TipoActor.SISTEMA),
        )
        
        return {
            "mensaje": "Contraseña actualizada correctamente. Ahora puedes iniciar sesión con tu nueva contraseña.",
            "estado": "contrasena_actualizada",
        }
    @staticmethod
    def _utc_now_matching(dt_value: datetime | None = None) -> datetime:
        """
        Devuelve 'ahora' con zona horaria compatible con dt_value para evitar
        comparaciones naive vs aware que pueden romper en producción.
        """
        if dt_value and dt_value.tzinfo is not None:
            return datetime.now(dt_value.tzinfo)
        return datetime.now(timezone.utc).replace(tzinfo=None)
