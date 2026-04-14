from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.enums import (
    RolUsuario,
    EstadoAprobacionTaller,
    EstadoOperativoTaller,
    TipoActor,
    ResultadoAuditoria,
)
from app.core.exceptions import not_found, forbidden, bad_request
from app.models.taller import Taller
from app.models.usuario import Usuario
from app.models.bitacora import Bitacora


class TallerService:
    @staticmethod
    def get_taller_by_usuario_id(db: Session, usuario_id: UUID) -> Taller | None:
        """
        Obtiene el taller asociado a un usuario_id.
        Retorna None si no existe.
        """
        return db.query(Taller).filter(Taller.id_usuario == usuario_id).first()

    @staticmethod
    def list_talleres(db: Session, current_user: Usuario):
        """
        Lista talleres.
        - ADMINISTRADOR: Ve todos
        - TALLER: Solo ve su propio perfil
        """
        if current_user.rol == RolUsuario.ADMINISTRADOR:
            return db.query(Taller).all()
        elif current_user.rol == RolUsuario.TALLER:
            # Un taller solo ve su propio perfil
            taller = TallerService.get_taller_by_usuario_id(db, current_user.id_usuario)
            if taller is None:
                raise not_found("Tu perfil de taller no existe")
            return [taller]
        else:
            # Otros roles (CLIENTE) no acceden a este endpoint
            return []

    @staticmethod
    def get_taller(db: Session, taller_id: UUID, current_user: Usuario):
        """
        Obtiene un taller.
        - Ownership: El usuario solo puede ver su propio taller
        - ADMINISTRADOR: Puede ver cualquier taller
        """
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if taller is None:
            raise not_found("Taller no encontrado")
        
        # Ownership check
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            if taller.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para acceder a este taller")
        
        return taller

    @staticmethod
    def create_taller(db: Session, data: dict, current_user: Usuario):
        """
        Crea un taller (uso interno/admin solamente).
        Los talleres normales se registran mediante auth.registrar_taller
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden crear talleres")
        
        taller = Taller(**data)
        db.add(taller)
        db.commit()
        db.refresh(taller)
        return taller

    @staticmethod
    def update_taller(db: Session, taller_id: UUID, data: dict, current_user: Usuario):
        """
        Actualiza un taller.
        - Ownership: Solo puede actualizar su propio taller
        - ADMINISTRADOR: Puede actualizar cualquier taller
        """
        taller = TallerService.get_taller(db, taller_id, current_user)
        
        # Ownership check (redundante pero explícito)
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            if taller.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para modificar este taller")
        
        payload = {k: v for k, v in data.items() if v is not None}
        for key, value in payload.items():
            setattr(taller, key, value)
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        TallerService._registrar_bitacora(
            db=db,
            accion="Edición de perfil de taller",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            tipo_actor=TipoActor.TALLER if current_user.rol == RolUsuario.TALLER else TipoActor.ADMINISTRADOR,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Campos actualizados: {', '.join(payload.keys())}",
        )
        
        return taller

    @staticmethod
    def delete_taller(db: Session, taller_id: UUID, current_user: Usuario) -> None:
        """
        Elimina un taller (solo ADMINISTRADOR).
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden eliminar talleres")
        
        taller = TallerService.get_taller(db, taller_id, current_user)
        db.delete(taller)
        db.commit()

    # ========================================================================
    # MÉTODOS ADMINISTRATIVOS CON BITÁCORA
    # ========================================================================

    @staticmethod
    def _registrar_bitacora(
        db: Session,
        accion: str,
        entidad_afectada: str,
        id_entidad_afectada: UUID,
        id_actor: UUID,
        resultado: ResultadoAuditoria,
        tipo_actor: TipoActor = TipoActor.ADMINISTRADOR,
        detalle: str | None = None,
    ) -> None:
        """
        Registra una acción en bitácora.
        
        Args:
            db: Sesión de base de datos
            accion: Descripción de la acción realizada
            entidad_afectada: Tipo de entidad afectada (e.g., "Taller")
            id_entidad_afectada: ID de la entidad afectada
            id_actor: ID del usuario que realizó la acción
            resultado: Resultado de la acción (EXITO, ERROR, ADVERTENCIA)
            tipo_actor: Tipo de actor que realiza la acción (por defecto ADMINISTRADOR)
            detalle: Detalle adicional de la acción
        """
        bitacora = Bitacora(
            tipo_actor=tipo_actor,
            id_actor=id_actor,
            accion=accion,
            modulo="Talleres",
            entidad_afectada=entidad_afectada,
            id_entidad_afectada=id_entidad_afectada,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()

    @staticmethod
    def list_talleres_admin(
        db: Session,
        current_user: Usuario,
        estado_aprobacion: EstadoAprobacionTaller | None = None,
        estado_operativo: EstadoOperativoTaller | None = None,
        es_activo: bool | None = None,
        nombre_taller: str | None = None,
        nit: str | None = None,
        correo: str | None = None,
    ) -> list[Taller]:
        """
        Lista talleres con filtros administrativos.
        Solo ADMINISTRADOR puede ejecutar.
        
        Args:
            db: Sesión de base de datos
            current_user: Usuario actual (debe ser ADMINISTRADOR)
            estado_aprobacion: Filtrar por estado de aprobación
            estado_operativo: Filtrar por estado operativo
            es_activo: Filtrar por actividad del usuario
            nombre_taller: Filtrar por nombre del taller (búsqueda parcial)
            nit: Filtrar por NIT
            correo: Filtrar por correo del usuario (búsqueda parcial)
        
        Returns:
            Lista de talleres que coinciden con los filtros
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden listar talleres")
        
        query = db.query(Taller)
        
        if estado_aprobacion:
            query = query.filter(Taller.estado_aprobacion == estado_aprobacion)
        if estado_operativo:
            query = query.filter(Taller.estado_operativo == estado_operativo)
        if nombre_taller:
            query = query.filter(Taller.nombre_taller.ilike(f"%{nombre_taller}%"))
        if nit:
            query = query.filter(Taller.nit == nit)
        
        if es_activo is not None or correo:
            # Si necesitamos filtrar por usuario, hacemos join
            query = query.join(Usuario, Taller.id_usuario == Usuario.id_usuario)
            if es_activo is not None:
                query = query.filter(Usuario.es_activo == es_activo)
            if correo:
                query = query.filter(Usuario.correo.ilike(f"%{correo}%"))
        
        return query.all()

    @staticmethod
    def get_taller_admin_detail(db: Session, taller_id: UUID, current_user: Usuario) -> Taller:
        """
        Obtiene el detalle administrativo de un taller.
        Solo ADMINISTRADOR puede ejecutar.
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden ver detalles administrativos")
        
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if taller is None:
            raise not_found("Taller no encontrado")
        
        return taller

    @staticmethod
    def update_taller_admin(
        db: Session, taller_id: UUID, data: dict, current_user: Usuario
    ) -> Taller:
        """
        Actualiza información administrativa de un taller.
        Only ADMINISTRADOR can execute.
        No permite cambiar estados de aprobación/operatividad desde aquí.
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden actualizar talleres")
        
        taller = TallerService.get_taller_admin_detail(db, taller_id, current_user)
        
        # Campos permitidos en actualización administrativa
        campos_permitidos = {
            "nombre_taller",
            "razon_social",
            "nit",
            "telefono",
            "direccion",
            "latitud",
            "longitud",
            "descripcion",
        }
        
        payload = {k: v for k, v in data.items() if k in campos_permitidos and v is not None}
        
        for key, value in payload.items():
            setattr(taller, key, value)
        
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        TallerService._registrar_bitacora(
            db=db,
            accion="Actualización de información administrativa",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Campos actualizados: {', '.join(payload.keys())}",
        )
        
        return taller

    @staticmethod
    def aprobar_taller(db: Session, taller_id: UUID, current_user: Usuario) -> dict:
        """
        Aprueba un taller pendiente.
        - Valida que el taller existe
        - Cambia estado_aprobacion a APROBADO
        - Actualiza fecha_aprobacion
        - Cambia estado_operativo a DISPONIBLE (para que pueda operar)
        - Activa al usuario asociado (es_activo = True)
        - Registra en bitácora
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden aprobar talleres")
        
        taller = TallerService.get_taller_admin_detail(db, taller_id, current_user)
        
        # Actualizar estados
        taller.estado_aprobacion = EstadoAprobacionTaller.APROBADO
        taller.fecha_aprobacion = datetime.now(timezone.utc).replace(tzinfo=None)  # Sin info de zona
        taller.estado_operativo = EstadoOperativoTaller.DISPONIBLE
        
        # Activar usuario
        usuario = db.query(Usuario).filter(Usuario.id_usuario == taller.id_usuario).first()
        if usuario:
            usuario.es_activo = True
        
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        TallerService._registrar_bitacora(
            db=db,
            accion="Aprobación de solicitud de taller",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller '{taller.nombre_taller}' aprobado. Usuario activado.",
        )
        
        # Notificar al taller de su aprobación
        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService
        
        if taller.id_usuario:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=taller.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="¡Tu taller ha sido aprobado!",
                mensaje=f"Felicidades {taller.nombre_taller}, tu solicitud de registro ha sido aprobada por el administrador. Ya puedes operar y recibir solicitudes de emergencia.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.CUENTA,
                referencia_entidad="Taller",
                referencia_id=taller.id_taller,
            )
        
        return {
            "mensaje": "Taller aprobado correctamente",
            "id_taller": taller.id_taller,
            "estado_aprobacion": taller.estado_aprobacion,
            "estado_operativo": taller.estado_operativo,
            "es_activo": usuario.es_activo if usuario else False,
        }

    @staticmethod
    def rechazar_taller(
        db: Session, taller_id: UUID, current_user: Usuario, motivo: str | None = None
    ) -> dict:
        """
        Rechaza una solicitud de taller.
        - Valida que el taller existe
        - Cambia estado_aprobacion a RECHAZADO
        - Desactiva al usuario asociado (es_activo = False)
        - Cambia estado_operativo a NO_DISPONIBLE
        - Registra motivo en bitácora si se proporciona
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden rechazar talleres")
        
        taller = TallerService.get_taller_admin_detail(db, taller_id, current_user)
        
        # Actualizar estados
        taller.estado_aprobacion = EstadoAprobacionTaller.RECHAZADO
        taller.estado_operativo = EstadoOperativoTaller.NO_DISPONIBLE
        
        # Desactivar usuario
        usuario = db.query(Usuario).filter(Usuario.id_usuario == taller.id_usuario).first()
        if usuario:
            usuario.es_activo = False
        
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        detalle_bitacora = f"Solicitud de taller '{taller.nombre_taller}' rechazada."
        if motivo:
            detalle_bitacora += f" Motivo: {motivo}"
        
        TallerService._registrar_bitacora(
            db=db,
            accion="Rechazo de solicitud de taller",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            detalle=detalle_bitacora,
        )
        
        # Notificar al taller del rechazo
        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService
        
        if usuario:
            mensaje = f"Tu solicitud de registro como taller ha sido rechazada."
            if motivo:
                mensaje += f" Motivo: {motivo}"
            
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=usuario.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="Solicitud de registro rechazada",
                mensaje=mensaje,
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.CUENTA,
                referencia_entidad="Taller",
                referencia_id=taller.id_taller,
            )
        
        return {
            "mensaje": "Solicitud de taller rechazada correctamente",
            "id_taller": taller.id_taller,
            "estado_aprobacion": taller.estado_aprobacion,
            "estado_operativo": taller.estado_operativo,
            "es_activo": usuario.es_activo if usuario else False,
        }

    @staticmethod
    def habilitar_taller(db: Session, taller_id: UUID, current_user: Usuario) -> dict:
        """
        Habilita un taller aprobado para que pueda operar.
        - Valida que el taller está aprobado
        - Cambia estado_operativo a DISPONIBLE
        - Activa al usuario (es_activo = True)
        - Registra en bitácora
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden habilitar talleres")
        
        taller = TallerService.get_taller_admin_detail(db, taller_id, current_user)
        
        # Validar que el taller está aprobado
        if taller.estado_aprobacion != EstadoAprobacionTaller.APROBADO:
            raise bad_request("El taller debe estar en estado APROBADO para habilitarlo")
        
        # Actualizar estados
        taller.estado_operativo = EstadoOperativoTaller.DISPONIBLE
        
        usuario = db.query(Usuario).filter(Usuario.id_usuario == taller.id_usuario).first()
        if usuario:
            usuario.es_activo = True
        
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        TallerService._registrar_bitacora(
            db=db,
            accion="Habilitación de taller",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller '{taller.nombre_taller}' habilitado para operar.",
        )
        
        # Notificar al taller del levantamiento de suspensión
        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService
        
        if usuario:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=usuario.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="Tu taller ha sido habilitado",
                mensaje=f"Tu taller {taller.nombre_taller} ha sido habilitado nuevamente y puede volver a recibir solicitudes de emergencia.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.CUENTA,
                referencia_entidad="Taller",
                referencia_id=taller.id_taller,
            )
        
        return {
            "mensaje": "Taller habilitado correctamente",
            "id_taller": taller.id_taller,
            "estado_aprobacion": taller.estado_aprobacion,
            "estado_operativo": taller.estado_operativo,
            "es_activo": usuario.es_activo if usuario else False,
        }

    @staticmethod
    def deshabilitar_taller(db: Session, taller_id: UUID, current_user: Usuario) -> dict:
        """
        Deshabilita un taller (sin eliminarlo).
        - Valida que el taller está aprobado
        - Cambia estado_operativo a SUSPENDIDO (inhabilitación administrativa)
        - No cambia es_activo del usuario (pueden reactivarse)
        - Registra en bitácora
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden deshabilitar talleres")
        
        taller = TallerService.get_taller_admin_detail(db, taller_id, current_user)
        
        # Validar que el taller está aprobado
        if taller.estado_aprobacion != EstadoAprobacionTaller.APROBADO:
            raise bad_request("El taller debe estar en estado APROBADO para deshabilitarlo")
        
        # Actualizar estado (usar SUSPENDIDO para indicar deshabilitación administrativa)
        taller.estado_operativo = EstadoOperativoTaller.SUSPENDIDO
        
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        TallerService._registrar_bitacora(
            db=db,
            accion="Deshabilitación de taller",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller '{taller.nombre_taller}' deshabilitado. Estado operativo: SUSPENDIDO.",
        )
        
        # Notificar al taller de la suspensión
        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService
        
        if taller.usuario and taller.usuario.id_usuario:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=taller.usuario.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="Tu taller ha sido suspendido",
                mensaje=f"Tu taller {taller.nombre_taller} ha sido suspendido y no puede recibir nuevas solicitudes de emergencia. Por favor contacta con el administrador.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.CUENTA,
                referencia_entidad="Taller",
                referencia_id=taller.id_taller,
            )
        
        return {
            "mensaje": "Taller deshabilitado correctamente",
            "id_taller": taller.id_taller,
            "estado_aprobacion": taller.estado_aprobacion,
            "estado_operativo": taller.estado_operativo,
            "es_activo": taller.usuario.es_activo if taller.usuario else False,
        }

    # ========================================================================
    # MÉTODOS DE PERFIL PROPIO DEL TALLER (CASO DE USO: GESTIONAR PERFIL)
    # ========================================================================

    @staticmethod
    def get_my_taller_profile(db: Session, current_user: Usuario) -> Taller:
        """
        Obtiene el perfil propio del taller autenticado.
        
        Args:
            db: Sesión de base de datos
            current_user: Usuario actual (debe tener rol TALLER)
        
        Returns:
            Objeto Taller asociado al usuario
        
        Raises:
            not_found: Si no existe taller asociado al usuario
        """
        # Validar que current_user tiene rol TALLER
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo usuarios con rol TALLER pueden acceder a esta información")
        
        # Buscar el taller asociado al usuario
        taller = TallerService.get_taller_by_usuario_id(db, current_user.id_usuario)
        if taller is None:
            raise not_found("Tu perfil de taller no existe en el sistema")
        
        return taller

    @staticmethod
    def update_my_taller_profile(
        db: Session,
        current_user: Usuario,
        data: dict,
    ) -> Taller:
        """
        Actualiza el perfil propio del taller autenticado.
        
        Validaciones:
        - current_user debe tener rol TALLER
        - El taller debe estar APROBADO (estado_aprobacion == APROBADO)
        - Solo permite editar campos no administrativos
        - No permite modificar: estado_aprobacion, estado_operativo, id_usuario, fecha_aprobacion
        
        Args:
            db: Sesión de base de datos
            current_user: Usuario actual (debe tener rol TALLER)
            data: Diccionario con los datos a actualizar
        
        Returns:
            Objeto Taller actualizado
        
        Raises:
            forbidden: Si current_user no tiene rol TALLER
            not_found: Si no existe taller asociado al usuario
            bad_request: Si el taller no está APROBADO
        """
        # Validar que current_user tiene rol TALLER
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo usuarios con rol TALLER pueden actualizar su perfil")
        
        # Obtener el taller asociado al usuario actual
        taller = TallerService.get_taller_by_usuario_id(db, current_user.id_usuario)
        if taller is None:
            raise not_found("Tu perfil de taller no existe en el sistema")
        
        # Validar que el taller está APROBADO
        if taller.estado_aprobacion != EstadoAprobacionTaller.APROBADO:
            raise bad_request(
                "No puedes editar tu perfil. Tu solicitud de taller aún está pendiente de aprobación "
                "o ha sido rechazada. Contacta al administrador para más información."
            )
        
        # Campos permitidos para editar perfil propio
        campos_permitidos = {
            "nombre_taller",
            "razon_social",
            "nit",
            "telefono",
            "direccion",
            "latitud",
            "longitud",
            "descripcion",
        }
        
        # Filtrar solo los campos permitidos que fueron modificados
        payload = {k: v for k, v in data.items() if k in campos_permitidos and v is not None}
        
        # Si no hay cambios, simplemente retornar el taller
        if not payload:
            return taller
        
        # Actualizar los campos del taller
        for key, value in payload.items():
            setattr(taller, key, value)
        
        db.commit()
        db.refresh(taller)
        
        # Registrar en bitácora
        TallerService._registrar_bitacora(
            db=db,
            accion="Actualización de perfil de taller",
            entidad_afectada="Taller",
            id_entidad_afectada=taller.id_taller,
            id_actor=current_user.id_usuario,
            resultado=ResultadoAuditoria.EXITO,
            tipo_actor=TipoActor.TALLER,
            detalle=f"Campos actualizados: {', '.join(payload.keys())}. Taller: '{taller.nombre_taller}'",
        )
        
        return taller
