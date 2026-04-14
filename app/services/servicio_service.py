from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import TipoActor, ResultadoAuditoria
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.models.bitacora import Bitacora
from app.models.servicio import Servicio
from app.models.taller import Taller
from app.models.taller_servicio import TallerServicio


class ServicioService:
    """Servicio para gestionar servicios de talleres."""

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
