from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import TipoActor, ResultadoAuditoria


class BitacoraResponse(BaseModel):
    """Respuesta para un registro de bitácora"""
    id_bitacora: UUID
    tipo_actor: TipoActor
    id_actor: UUID | None
    nombre_completo: str | None = None
    correo: str | None = None
    accion: str
    modulo: str
    entidad_afectada: str
    id_entidad_afectada: UUID | None
    resultado: ResultadoAuditoria
    detalle: str | None
    ip_origen: str | None
    fecha_evento: datetime

    class Config:
        from_attributes = True


class BitacoraListResponse(BaseModel):
    """Respuesta con lista paginada de eventos"""
    total: int
    pagina: int
    por_pagina: int
    registros: list[BitacoraResponse]


class BitacoraFiltro(BaseModel):
    """Filtros para consultar bitácora"""
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=20, ge=1, le=100)
    tipo_actor: TipoActor | None = None
    accion: str | None = None
    modulo: str | None = None
    resultado: ResultadoAuditoria | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    id_actor: UUID | None = None
