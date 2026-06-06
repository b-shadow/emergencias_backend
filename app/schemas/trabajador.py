from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import EstadoOrdenRecojo


class TrabajadorCreateRequest(BaseModel):
    correo: str
    contrasena: str = Field(min_length=8, max_length=128)
    nombre_completo: str = Field(min_length=1, max_length=255)
    telefono: str | None = None
    licencia_conducir: str | None = None


class TrabajadorResponse(BaseModel):
    id_trabajador: UUID
    id_usuario: UUID
    id_taller: UUID
    nombre_completo: str | None = None
    correo: str | None = None
    telefono: str | None = None
    licencia_conducir: str | None = None
    es_activo: bool
    fecha_registro: datetime

    model_config = ConfigDict(from_attributes=True)


class TrabajadorUpdateRequest(BaseModel):
    nombre_completo: str = Field(min_length=1, max_length=255)
    telefono: str | None = None
    licencia_conducir: str | None = None


class TrabajadorEstadoRequest(BaseModel):
    es_activo: bool


class OrdenRecojoAsignarRequest(BaseModel):
    id_trabajador: UUID


class OrdenRecojoEstadoRequest(BaseModel):
    estado_orden: EstadoOrdenRecojo


class OrdenRecojoUbicacionRequest(BaseModel):
    latitud: float
    longitud: float
    profile: str = Field(default="foot")


class OrdenRecojoTrackingResponse(BaseModel):
    id_orden_recojo: UUID
    id_asignacion: UUID
    id_trabajador: UUID
    estado_orden: EstadoOrdenRecojo
    latitud_actual: float | None = None
    longitud_actual: float | None = None
    distancia_metros: float | None = None
    duracion_segundos: float | None = None
    ruta_geojson: dict | None = None
    ruta_recorrida_geojson: dict | None = None
    latitud_destino: float | None = None
    longitud_destino: float | None = None
    latitud_solicitud: float | None = None
    longitud_solicitud: float | None = None
    latitud_taller: float | None = None
    longitud_taller: float | None = None
    taller_nombre: str | None = None
    fecha_asignacion: datetime
    fecha_aceptacion: datetime | None = None
    fecha_llegada_auxilio: datetime | None = None
    fecha_inicio_regreso: datetime | None = None
    fecha_llegada_taller: datetime | None = None
    fecha_ultima_ubicacion: datetime | None = None
    duracion_total_segundos: float | None = None
