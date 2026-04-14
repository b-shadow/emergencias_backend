from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.core.security import get_password_hash
from app.core.enums import RolUsuario, TipoActor, ResultadoAuditoria, EstadoAprobacionTaller, EstadoOperativoTaller
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.taller import Taller
from app.models.bitacora import Bitacora


class UsuarioService:
    @staticmethod
    def list_usuarios(db: Session):
        """Lista todos los usuarios"""
        return db.query(Usuario).all()

    @staticmethod
    def get_usuario(db: Session, usuario_id: UUID):
        """Obtiene un usuario por su ID"""
        usuario = db.query(Usuario).filter(Usuario.id_usuario == usuario_id).first()
        if usuario is None:
            raise not_found("Usuario no encontrado")
        return usuario

    @staticmethod
    def create_usuario(db: Session, data: dict, current_user: Usuario = None):
        """Crea un nuevo usuario y registra en bitácora

        También crea el perfil correspondiente en Cliente o Taller según el rol
        """
        usuario = db.query(Usuario).filter(Usuario.correo == data["correo"]).first()
        if usuario:
            raise bad_request("Correo ya registrado")

        payload = {
            **data,
            "contrasena_hash": get_password_hash(data["contrasena"]),
        }
        payload.pop("contrasena", None)

        usuario = Usuario(**payload)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

        # Crear perfil en tabla derivada según el rol
        rol = usuario.rol
        if rol == RolUsuario.CLIENTE:
            cliente = Cliente(
                id_usuario=usuario.id_usuario,
                nombre="Usuario",  # Datos mínimos
                apellido=usuario.nombre_completo.split()[-1] if usuario.nombre_completo else "Cliente"
            )
            db.add(cliente)
            db.commit()

        elif rol == RolUsuario.TALLER:
            taller = Taller(
                id_usuario=usuario.id_usuario,
                nombre_taller=usuario.nombre_completo or "Taller",
                estado_aprobacion=EstadoAprobacionTaller.PENDIENTE,
                estado_operativo=EstadoOperativoTaller.DISPONIBLE
            )
            db.add(taller)
            db.commit()

        # ADMINISTRADOR no necesita tabla derivada

        # Registrar en bitácora si hay un actor
        if current_user:
            UsuarioService._registrar_bitacora(
                db=db,
                tipo_actor=TipoActor.ADMINISTRADOR,
                id_actor=current_user.id_usuario,
                accion="Crear usuario",
                modulo="Usuarios",
                entidad_afectada="Usuario",
                id_entidad_afectada=usuario.id_usuario,
                resultado=ResultadoAuditoria.EXITO,
                detalle=f"Usuario creado: {usuario.correo} con rol {usuario.rol} - Perfil {rol} creado",
            )

        return usuario

    @staticmethod
    def update_usuario(db: Session, usuario_id: UUID, data: dict):
        """Actualiza un usuario (mantener compatibilidad con actualización genérica)"""
        usuario = UsuarioService.get_usuario(db, usuario_id)
        payload = {k: v for k, v in data.items() if v is not None}
        if "contrasena" in payload:
            payload["contrasena_hash"] = get_password_hash(payload.pop("contrasena"))

        for key, value in payload.items():
            setattr(usuario, key, value)
        db.commit()
        db.refresh(usuario)
        return usuario

    @staticmethod
    def change_user_role(
        db: Session,
        usuario_id: UUID,
        nuevo_rol: RolUsuario,
        current_user: Usuario
    ):
        """
        Cambia el rol de un usuario. Solo ADMINISTRADOR puede hacer esto.
        También maneja los cambios en las tablas Cliente y Taller.

        Args:
            db: Sesión de BD
            usuario_id: ID del usuario a modificar
            nuevo_rol: Nuevo rol a asignar
            current_user: Usuario que hace el cambio (debe ser ADMINISTRADOR)

        Returns:
            Usuario actualizado

        Raises:
            HTTPException 403: Si el usuario no es administrador
            HTTPException 404: Si el usuario no existe
            HTTPException 400: Si el rol es igual al actual
        """

        # Validación 1 (capa de servicio): Verificar que el actor es ADMINISTRADOR
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden cambiar roles de usuarios")

        # Obtener usuario a modificar
        usuario = UsuarioService.get_usuario(db, usuario_id)

        # Validar que no sea el mismo rol
        if usuario.rol == nuevo_rol:
            raise bad_request(f"El usuario ya tiene asignado el mismo rol")

        # Guardar rol antiguo para bitácora
        rol_anterior = usuario.rol

        # Eliminar perfil del rol anterior
        if rol_anterior == RolUsuario.CLIENTE:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == usuario_id).first()
            if cliente:
                db.delete(cliente)
                db.commit()

        elif rol_anterior == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == usuario_id).first()
            if taller:
                db.delete(taller)
                db.commit()

        # Crear perfil para el nuevo rol
        if nuevo_rol == RolUsuario.CLIENTE:
            cliente = Cliente(
                id_usuario=usuario_id,
                nombre="Usuario",
                apellido=usuario.nombre_completo.split()[-1] if usuario.nombre_completo else "Cliente"
            )
            db.add(cliente)
            db.commit()

        elif nuevo_rol == RolUsuario.TALLER:
            taller = Taller(
                id_usuario=usuario_id,
                nombre_taller=usuario.nombre_completo or "Taller",
                estado_aprobacion=EstadoAprobacionTaller.PENDIENTE,
                estado_operativo=EstadoOperativoTaller.DISPONIBLE
            )
            db.add(taller)
            db.commit()

        # Actualizar rol en usuario
        usuario.rol = nuevo_rol
        db.commit()
        db.refresh(usuario)

        # Registrar en bitácora
        UsuarioService._registrar_bitacora(
            db=db,
            tipo_actor=TipoActor.ADMINISTRADOR,
            id_actor=current_user.id_usuario,
            accion="Cambiar rol de usuario",
            modulo="Usuarios",
            entidad_afectada="Usuario",
            id_entidad_afectada=usuario.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Rol changed from {rol_anterior} to {nuevo_rol} for user {usuario.correo} - Perfiles actualizados",
        )

        return usuario

    @staticmethod
    def delete_usuario(db: Session, usuario_id: UUID) -> None:
        """Elimina un usuario"""
        usuario = UsuarioService.get_usuario(db, usuario_id)
        db.delete(usuario)
        db.commit()

    @staticmethod
    def _registrar_bitacora(
        db: Session,
        tipo_actor: TipoActor,
        id_actor: UUID,
        accion: str,
        modulo: str,
        entidad_afectada: str,
        id_entidad_afectada: UUID,
        resultado: ResultadoAuditoria,
        detalle: str,
        ip_origen: str = None,
        user_agent: str = None,
    ) -> Bitacora:
        """Registra un evento en la bitácora"""
        evento = Bitacora(
            tipo_actor=tipo_actor,
            id_actor=id_actor,
            accion=accion,
            modulo=modulo,
            entidad_afectada=entidad_afectada,
            id_entidad_afectada=id_entidad_afectada,
            resultado=resultado,
            detalle=detalle,
            ip_origen=ip_origen,
            user_agent=user_agent,
        )
        db.add(evento)
        db.commit()
        db.refresh(evento)
        return evento
