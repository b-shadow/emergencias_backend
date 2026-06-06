from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.enums import (
    CategoriaNotificacion,
    EstadoServicio,
    EstadoSolicitudServicio,
    ResultadoAuditoria,
    RolUsuario,
    TipoActor,
    TipoNotificacion,
)
from app.models.bitacora import Bitacora
from app.models.servicio import Servicio
from app.models.solicitud_servicio_taller import SolicitudServicioTaller
from app.models.taller import Taller
from app.models.taller_servicio import TallerServicio
from app.models.usuario import Usuario
from app.services.notificacion_service import NotificacionService


class ServicioService:
    """Servicio para gestionar servicios de talleres."""

    @staticmethod
    def crear_servicio_global(db: Session, nombre_servicio: str, descripcion: str | None = None) -> Servicio:
        existente = db.query(Servicio).filter(Servicio.nombre_servicio == nombre_servicio).first()
        if existente:
            raise ConflictException("Ya existe un servicio con ese nombre")

        servicio = Servicio(nombre_servicio=nombre_servicio, descripcion=descripcion, estado=EstadoServicio.ACTIVO)
        db.add(servicio)
        db.flush()
        return servicio

    @staticmethod
    def get_all_servicios(db: Session) -> list[Servicio]:
        """
        Obtener todos los servicios disponibles (master data).
        
        Args:
            db: Sesión de base de datos
            
        Returns:
            Lista de servicios
        """
        return db.query(Servicio).all()

    @staticmethod
    def get_taller_servicios(db: Session, taller_id: UUID) -> list[TallerServicio]:
        """
        Obtener servicios asociados a un taller.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            
        Returns:
            Lista de servicios del taller
            
        Raises:
            NotFoundException: Si el taller no existe
        """
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        return db.query(TallerServicio).filter(
            TallerServicio.id_taller == taller_id
        ).all()

    @staticmethod
    def add_servicio_to_taller(
        db: Session,
        taller_id: UUID,
        servicio_id: UUID,
        usuario_id: UUID,
        rol: str,
        disponible: bool = True,
        observaciones: str | None = None,
        categoria_tarifa: str = "MECANICO",
        precio_base: float = 0,
        tipo_pintura_chaperio: str | None = None,
    ) -> TallerServicio:
        """
        Agregar un servicio a un taller.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            servicio_id: ID del servicio
            usuario_id: ID del usuario que realiza la acción
            rol: Rol del usuario (debe ser TALLER)
            disponible: Si el servicio está disponible
            observaciones: Observaciones sobre el servicio
            
        Returns:
            La relación TallerServicio creada
            
        Raises:
            NotFoundException: Si taller o servicio no existen
            ForbiddenException: Si el usuario no es dueño del taller
            ConflictException: Si el servicio ya está ligado al taller
        """
        # Verificar que el taller existe y pertenece al usuario
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        if rol == "TALLER" and taller.id_usuario != usuario_id:
            raise ForbiddenException("No tienes permiso para modificar este taller")

        # Verificar que el servicio existe
        servicio = db.query(Servicio).filter(
            Servicio.id_servicio == servicio_id
        ).first()
        if not servicio:
            raise NotFoundException("Servicio no encontrado")

        # Verificar que no exista ya esta relación
        existing = db.query(TallerServicio).filter(
            TallerServicio.id_taller == taller_id,
            TallerServicio.id_servicio == servicio_id,
        ).first()
        if existing:
            raise ConflictException("Este servicio ya está ligado al taller")

        # Crear la relación
        taller_servicio = TallerServicio(
            id_taller=taller_id,
            id_servicio=servicio_id,
            disponible=disponible,
            observaciones=observaciones,
            categoria_tarifa=categoria_tarifa,
            precio_base=precio_base,
            tipo_pintura_chaperio=tipo_pintura_chaperio,
        )
        db.add(taller_servicio)
        db.flush()

        # Registrar en bitácora
        bitacora = Bitacora(
            tipo_actor=TipoActor.TALLER,
            id_actor=usuario_id,
            accion="AGREGAR_SERVICIO",
            modulo="Servicios",
            entidad_afectada="TallerServicio",
            id_entidad_afectada=taller_servicio.id_taller_servicio,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Se agregó el servicio '{servicio.nombre_servicio}' al taller",
        )
        db.add(bitacora)
        db.commit()

        return taller_servicio

    @staticmethod
    def solicitar_nuevo_servicio_taller(
        db: Session,
        taller_id: UUID,
        usuario_id: UUID,
        nombre_servicio: str,
        descripcion: str | None = None,
    ) -> SolicitudServicioTaller:
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        solicitud = SolicitudServicioTaller(
            id_taller=taller_id,
            nombre_servicio=nombre_servicio.strip(),
            descripcion=descripcion.strip() if descripcion else None,
            estado=EstadoSolicitudServicio.EN_ESPERA,
            id_usuario_solicitante=usuario_id,
        )
        db.add(solicitud)
        db.flush()

        db.add(
            Bitacora(
                tipo_actor=TipoActor.TALLER,
                id_actor=usuario_id,
                accion="SOLICITAR_SERVICIO",
                modulo="Servicios",
                entidad_afectada="SolicitudServicioTaller",
                id_entidad_afectada=solicitud.id_solicitud_servicio_taller,
                resultado=ResultadoAuditoria.EXITO,
                detalle=f"Se solicitó el servicio '{solicitud.nombre_servicio}'",
            )
        )
        administradores = db.query(Usuario).filter(
            Usuario.rol == RolUsuario.ADMINISTRADOR,
            Usuario.es_activo.is_(True),
        ).all()
        for admin in administradores:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=admin.id_usuario,
                tipo_usuario_destino="ADMINISTRADOR",
                titulo="Nueva solicitud de servicio",
                mensaje=f"El taller '{taller.nombre_taller}' solicitó crear el servicio '{solicitud.nombre_servicio}'.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.SOLICITUD,
                referencia_entidad="SolicitudServicioTaller",
                referencia_id=solicitud.id_solicitud_servicio_taller,
                actor_id=usuario_id,
                actor_tipo=TipoActor.TALLER,
            )
        db.commit()
        return solicitud

    @staticmethod
    def listar_solicitudes_servicio(
        db: Session,
        taller_id: UUID | None = None,
    ) -> list[SolicitudServicioTaller]:
        query = db.query(SolicitudServicioTaller).order_by(SolicitudServicioTaller.fecha_solicitud.desc())
        if taller_id:
            query = query.filter(SolicitudServicioTaller.id_taller == taller_id)
        return query.all()

    @staticmethod
    def aprobar_solicitud_servicio(
        db: Session,
        solicitud_id: UUID,
        usuario_id: UUID,
    ) -> tuple[SolicitudServicioTaller, Servicio]:
        solicitud = db.query(SolicitudServicioTaller).filter(
            SolicitudServicioTaller.id_solicitud_servicio_taller == solicitud_id
        ).first()
        if not solicitud:
            raise NotFoundException("Solicitud no encontrada")
        if solicitud.estado != EstadoSolicitudServicio.EN_ESPERA:
            raise ConflictException("La solicitud ya fue resuelta")

        servicio = ServicioService.crear_servicio_global(db, solicitud.nombre_servicio, solicitud.descripcion)
        solicitud.estado = EstadoSolicitudServicio.APROBADO
        solicitud.id_servicio_creado = servicio.id_servicio
        solicitud.id_usuario_resolutor = usuario_id
        solicitud.fecha_resolucion = datetime.utcnow()
        db.add(
            Bitacora(
                tipo_actor=TipoActor.ADMINISTRADOR,
                id_actor=usuario_id,
                accion="APROBAR_SOLICITUD_SERVICIO",
                modulo="Servicios",
                entidad_afectada="SolicitudServicioTaller",
                id_entidad_afectada=solicitud.id_solicitud_servicio_taller,
                resultado=ResultadoAuditoria.EXITO,
                detalle=f"Se aprobó la solicitud de servicio '{solicitud.nombre_servicio}'",
            )
        )
        if solicitud.taller and solicitud.taller.id_usuario:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=solicitud.taller.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="Solicitud de servicio aprobada",
                mensaje=f"Tu solicitud para crear '{solicitud.nombre_servicio}' fue aprobada.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.SOLICITUD,
                referencia_entidad="SolicitudServicioTaller",
                referencia_id=solicitud.id_solicitud_servicio_taller,
                actor_id=usuario_id,
                actor_tipo=TipoActor.ADMINISTRADOR,
            )
        db.commit()
        return solicitud, servicio

    @staticmethod
    def rechazar_solicitud_servicio(
        db: Session,
        solicitud_id: UUID,
        usuario_id: UUID,
        motivo: str | None = None,
    ) -> SolicitudServicioTaller:
        solicitud = db.query(SolicitudServicioTaller).filter(
            SolicitudServicioTaller.id_solicitud_servicio_taller == solicitud_id
        ).first()
        if not solicitud:
            raise NotFoundException("Solicitud no encontrada")
        if solicitud.estado != EstadoSolicitudServicio.EN_ESPERA:
            raise ConflictException("La solicitud ya fue resuelta")

        solicitud.estado = EstadoSolicitudServicio.RECHAZADO
        solicitud.motivo_rechazo = motivo
        solicitud.id_usuario_resolutor = usuario_id
        solicitud.fecha_resolucion = datetime.utcnow()
        db.add(
            Bitacora(
                tipo_actor=TipoActor.ADMINISTRADOR,
                id_actor=usuario_id,
                accion="RECHAZAR_SOLICITUD_SERVICIO",
                modulo="Servicios",
                entidad_afectada="SolicitudServicioTaller",
                id_entidad_afectada=solicitud.id_solicitud_servicio_taller,
                resultado=ResultadoAuditoria.EXITO,
                detalle=f"Se rechazó la solicitud de servicio '{solicitud.nombre_servicio}'",
            )
        )
        if solicitud.taller and solicitud.taller.id_usuario:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=solicitud.taller.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="Solicitud de servicio rechazada",
                mensaje=f"Tu solicitud para crear '{solicitud.nombre_servicio}' fue rechazada.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.SOLICITUD,
                referencia_entidad="SolicitudServicioTaller",
                referencia_id=solicitud.id_solicitud_servicio_taller,
                actor_id=usuario_id,
                actor_tipo=TipoActor.ADMINISTRADOR,
            )
        db.commit()
        return solicitud

    @staticmethod
    def remove_servicio_from_taller(
        db: Session,
        taller_id: UUID,
        servicio_id: UUID,
        usuario_id: UUID,
        rol: str,
    ) -> None:
        """
        Remover un servicio de un taller.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            servicio_id: ID del servicio
            usuario_id: ID del usuario que realiza la acción
            rol: Rol del usuario (debe ser TALLER)
            
        Raises:
            NotFoundException: Si taller, servicio o relación no existen
            ForbiddenException: Si el usuario no es dueño del taller
        """
        # Verificar que el taller existe y pertenece al usuario
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        if rol == "TALLER" and taller.id_usuario != usuario_id:
            raise ForbiddenException("No tienes permiso para modificar este taller")

        # Obtener el servicio para el nombre en bitácora
        servicio = db.query(Servicio).filter(
            Servicio.id_servicio == servicio_id
        ).first()

        # Verificar y eliminar la relación
        taller_servicio = db.query(TallerServicio).filter(
            TallerServicio.id_taller == taller_id,
            TallerServicio.id_servicio == servicio_id,
        ).first()
        if not taller_servicio:
            raise NotFoundException(
                "Este servicio no está ligado al taller"
            )

        db.delete(taller_servicio)
        db.flush()

        # Registrar en bitácora
        bitacora = Bitacora(
            tipo_actor=TipoActor.TALLER,
            id_actor=usuario_id,
            accion="REMOVER_SERVICIO",
            modulo="Servicios",
            entidad_afectada="TallerServicio",
            id_entidad_afectada=taller_servicio.id_taller_servicio,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Se removió el servicio '{servicio.nombre_servicio if servicio else 'desconocido'}' del taller",
        )
        db.add(bitacora)
        db.commit()

    @staticmethod
    def update_servicio_disponibilidad(
        db: Session,
        taller_id: UUID,
        servicio_id: UUID,
        usuario_id: UUID,
        rol: str,
        disponible: bool,
        observaciones: str | None = None,
        categoria_tarifa: str = "MECANICO",
        precio_base: float = 0,
        tipo_pintura_chaperio: str | None = None,
    ) -> TallerServicio:
        """
        Actualizar la disponibilidad y observaciones de un servicio.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            servicio_id: ID del servicio
            usuario_id: ID del usuario que realiza la acción
            rol: Rol del usuario (debe ser TALLER)
            disponible: Nueva disponibilidad
            observaciones: Nuevas observaciones
            
        Returns:
            La relación TallerServicio actualizada
            
        Raises:
            NotFoundException: Si taller, servicio o relación no existen
            ForbiddenException: Si el usuario no es dueño del taller
        """
        # Verificar que el taller existe y pertenece al usuario
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        if rol == "TALLER" and taller.id_usuario != usuario_id:
            raise ForbiddenException("No tienes permiso para modificar este taller")

        # Obtener la relación
        taller_servicio = db.query(TallerServicio).filter(
            TallerServicio.id_taller == taller_id,
            TallerServicio.id_servicio == servicio_id,
        ).first()
        if not taller_servicio:
            raise NotFoundException(
                "Este servicio no está ligado al taller"
            )

        # Obtener servicio para bitácora
        servicio = db.query(Servicio).filter(
            Servicio.id_servicio == servicio_id
        ).first()

        # Actualizar
        taller_servicio.disponible = disponible
        taller_servicio.observaciones = observaciones
        taller_servicio.categoria_tarifa = categoria_tarifa
        taller_servicio.precio_base = precio_base
        taller_servicio.tipo_pintura_chaperio = tipo_pintura_chaperio
        db.flush()

        # Registrar en bitácora
        estado = "disponible" if disponible else "no disponible"
        bitacora = Bitacora(
            tipo_actor=TipoActor.TALLER,
            id_actor=usuario_id,
            accion="ACTUALIZAR_SERVICIO",
            modulo="Servicios",
            entidad_afectada="TallerServicio",
            id_entidad_afectada=taller_servicio.id_taller_servicio,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Se actualizó el servicio '{servicio.nombre_servicio if servicio else 'desconocido'}' a {estado}",
        )
        db.add(bitacora)
        db.commit()

        return taller_servicio
