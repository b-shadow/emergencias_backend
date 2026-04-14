from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import TipoActor, ResultadoAuditoria
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.models.bitacora import Bitacora
from app.models.especialidad import Especialidad
from app.models.taller import Taller
from app.models.taller_especialidad import TallerEspecialidad


class EspecialidadService:
    """Servicio para gestionar especialidades de talleres."""

    @staticmethod
    def get_all_especialidades(db: Session) -> list[Especialidad]:
        """
        Obtener todas las especialidades disponibles (master data).
        
        Args:
            db: Sesión de base de datos
            
        Returns:
            Lista de especialidades activas
        """
        return db.query(Especialidad).all()

    @staticmethod
    def get_taller_especialidades(db: Session, taller_id: UUID) -> list[TallerEspecialidad]:
        """
        Obtener especialidades asociadas a un taller.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            
        Returns:
            Lista de especialidades del taller
            
        Raises:
            NotFoundException: Si el taller no existe
        """
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        return db.query(TallerEspecialidad).filter(
            TallerEspecialidad.id_taller == taller_id
        ).all()

    @staticmethod
    def add_especialidad_to_taller(
        db: Session,
        taller_id: UUID,
        especialidad_id: UUID,
        usuario_id: UUID,
        rol: str,
    ) -> TallerEspecialidad:
        """
        Agregar una especialidad a un taller.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            especialidad_id: ID de la especialidad
            usuario_id: ID del usuario que realiza la acción
            rol: Rol del usuario (debe ser TALLER)
            
        Returns:
            La relación TallerEspecialidad creada
            
        Raises:
            NotFoundException: Si taller o especialidad no existen
            ForbiddenException: Si el usuario no es dueño del taller
            ConflictException: Si la especialidad ya está ligada al taller
        """
        # Verificar que el taller existe y pertenece al usuario
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        if rol == "TALLER" and taller.id_usuario != usuario_id:
            raise ForbiddenException("No tienes permiso para modificar este taller")

        # Verificar que la especialidad existe
        especialidad = db.query(Especialidad).filter(
            Especialidad.id_especialidad == especialidad_id
        ).first()
        if not especialidad:
            raise NotFoundException("Especialidad no encontrada")

        # Verificar que no exista ya esta relación
        existing = db.query(TallerEspecialidad).filter(
            TallerEspecialidad.id_taller == taller_id,
            TallerEspecialidad.id_especialidad == especialidad_id,
        ).first()
        if existing:
            raise ConflictException("Esta especialidad ya está ligada al taller")

        # Crear la relación
        taller_especialidad = TallerEspecialidad(
            id_taller=taller_id,
            id_especialidad=especialidad_id,
            estado="ACTIVA",
        )
        db.add(taller_especialidad)
        db.flush()

        # Registrar en bitácora
        bitacora = Bitacora(
            tipo_actor=TipoActor.TALLER,
            id_actor=usuario_id,
            accion="AGREGAR_ESPECIALIDAD",
            modulo="Especialidades",
            entidad_afectada="TallerEspecialidad",
            id_entidad_afectada=taller_especialidad.id_taller_especialidad,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Se agregó la especialidad '{especialidad.nombre_especialidad}' al taller",
        )
        db.add(bitacora)
        db.commit()

        return taller_especialidad

    @staticmethod
    def remove_especialidad_from_taller(
        db: Session,
        taller_id: UUID,
        especialidad_id: UUID,
        usuario_id: UUID,
        rol: str,
    ) -> None:
        """
        Remover una especialidad de un taller.
        
        Args:
            db: Sesión de base de datos
            taller_id: ID del taller
            especialidad_id: ID de la especialidad
            usuario_id: ID del usuario que realiza la acción
            rol: Rol del usuario (debe ser TALLER)
            
        Raises:
            NotFoundException: Si taller, especialidad o relación no existen
            ForbiddenException: Si el usuario no es dueño del taller
        """
        # Verificar que el taller existe y pertenece al usuario
        taller = db.query(Taller).filter(Taller.id_taller == taller_id).first()
        if not taller:
            raise NotFoundException("Taller no encontrado")

        if rol == "TALLER" and taller.id_usuario != usuario_id:
            raise ForbiddenException("No tienes permiso para modificar este taller")

        # Obtener la especialidad para el nombre en bitácora
        especialidad = db.query(Especialidad).filter(
            Especialidad.id_especialidad == especialidad_id
        ).first()

        # Verificar y eliminar la relación
        taller_especialidad = db.query(TallerEspecialidad).filter(
            TallerEspecialidad.id_taller == taller_id,
            TallerEspecialidad.id_especialidad == especialidad_id,
        ).first()
        if not taller_especialidad:
            raise NotFoundException(
                "Esta especialidad no está ligada al taller"
            )

        db.delete(taller_especialidad)
        db.flush()

        # Registrar en bitácora
        bitacora = Bitacora(
            tipo_actor=TipoActor.TALLER,
            id_actor=usuario_id,
            accion="REMOVER_ESPECIALIDAD",
            modulo="Especialidades",
            entidad_afectada="TallerEspecialidad",
            id_entidad_afectada=taller_especialidad.id_taller_especialidad,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Se removió la especialidad '{especialidad.nombre_especialidad if especialidad else 'desconocida'}' del taller",
        )
        db.add(bitacora)
        db.commit()
