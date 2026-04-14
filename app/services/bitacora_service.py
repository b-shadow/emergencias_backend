from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.core.enums import TipoActor, ResultadoAuditoria
from app.models.bitacora import Bitacora
from app.models.usuario import Usuario
from app.schemas.bitacora import BitacoraFiltro, BitacoraListResponse, BitacoraResponse


class BitacoraService:
    """Servicio para consultar y gestionar la bitácora del sistema"""

    @staticmethod
    def consultar_bitacora(db: Session, filtro: BitacoraFiltro) -> BitacoraListResponse:
        """
        Consulta la bitácora con filtros opcionales.
        
        Args:
            db: Sesión de base de datos
            filtro: Filtros a aplicar
            
        Returns:
            Lista paginada de eventos de bitácora
        """
        query = db.query(Bitacora)

        # Aplicar filtros
        conditions = []

        if filtro.tipo_actor:
            conditions.append(Bitacora.tipo_actor == filtro.tipo_actor)

        if filtro.id_actor:
            conditions.append(Bitacora.id_actor == filtro.id_actor)

        if filtro.accion:
            conditions.append(Bitacora.accion.ilike(f"%{filtro.accion}%"))

        if filtro.modulo:
            conditions.append(Bitacora.modulo.ilike(f"%{filtro.modulo}%"))

        if filtro.resultado:
            conditions.append(Bitacora.resultado == filtro.resultado)

        if filtro.fecha_inicio:
            conditions.append(Bitacora.fecha_evento >= filtro.fecha_inicio)

        if filtro.fecha_fin:
            conditions.append(Bitacora.fecha_evento <= filtro.fecha_fin)

        if conditions:
            query = query.filter(and_(*conditions))

        # Contar total
        total = query.count()

        # Aplicar paginación y ordenar por fecha descendente
        offset = (filtro.pagina - 1) * filtro.por_pagina
        registros = query.order_by(Bitacora.fecha_evento.desc()).offset(offset).limit(
            filtro.por_pagina
        ).all()

        # Convertir a respuesta con información del usuario
        registros_response = []
        for r in registros:
            respuesta = BitacoraResponse.from_orm(r)
            
            # Obtener información del usuario si existe id_actor
            if r.id_actor and r.tipo_actor != TipoActor.SISTEMA:
                usuario = db.query(Usuario).filter(Usuario.id_usuario == r.id_actor).first()
                if usuario:
                    respuesta.nombre_completo = usuario.nombre_completo
                    respuesta.correo = usuario.correo
            
            registros_response.append(respuesta)

        return BitacoraListResponse(
            total=total,
            pagina=filtro.pagina,
            por_pagina=filtro.por_pagina,
            registros=registros_response,
        )

    @staticmethod
    def obtener_acciones_disponibles(db: Session) -> list[str]:
        """Obtiene la lista de acciones registradas en la bitácora"""
        return [
            accion[0]
            for accion in db.query(Bitacora.accion.distinct()).order_by(Bitacora.accion).all()
        ]

    @staticmethod
    def obtener_modulos_disponibles(db: Session) -> list[str]:
        """Obtiene la lista de módulos registrados en la bitácora"""
        return [
            modulo[0]
            for modulo in db.query(Bitacora.modulo.distinct()).order_by(Bitacora.modulo).all()
        ]
