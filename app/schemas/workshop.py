from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller


class TallerBase(BaseModel):
    id_usuario: UUID
    nombre_taller: str = Field(min_length=2, max_length=255)
    razon_social: str = Field(min_length=2, max_length=255)
    nit: str = Field(min_length=5, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=255)
    latitud: float | None = None
    longitud: float | None = None
    descripcion: str | None = Field(default=None, max_length=1000)


class TallerCreate(TallerBase):
    pass


class TallerUpdate(BaseModel):
    nombre_taller: str | None = Field(default=None, min_length=2, max_length=255)
    razon_social: str | None = Field(default=None, min_length=2, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=255)
    latitud: float | None = None
    longitud: float | None = None
    descripcion: str | None = Field(default=None, max_length=1000)
    estado_aprobacion: EstadoAprobacionTaller | None = None
    estado_operativo: EstadoOperativoTaller | None = None


class TallerRead(TallerBase):
    id_taller: UUID
    estado_aprobacion: EstadoAprobacionTaller
    estado_operativo: EstadoOperativoTaller
    fecha_registro: datetime
    fecha_aprobacion: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================================
# SCHEMAS DE PERFIL PROPIO DEL TALLER (CASO DE USO: GESTIONAR PERFIL)
# ============================================================================


class TallerPerfilUpdate(BaseModel):
    """
    Schema para actualizar el perfil propio del taller.
    Solo permite editar campos NO administrativos.
    
    NO incluye:
    - estado_aprobacion
    - estado_operativo
    - id_usuario
    - fecha_aprobacion
    - campos administrativos
    """
    nombre_taller: str | None = Field(default=None, min_length=2, max_length=255)
    razon_social: str | None = Field(default=None, min_length=2, max_length=255)
    nit: str | None = Field(default=None, min_length=5, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=500)
    latitud: float | None = None
    longitud: float | None = None
    descripcion: str | None = Field(default=None, max_length=1000)


class TallerPerfilResponse(BaseModel):
    """
    Schema de respuesta para obtener/actualizar el perfil propio del taller.
    Incluye información completa del taller y del usuario asociado.
    """
    id_taller: UUID
    id_usuario: UUID
    nombre_taller: str
    razon_social: str | None
    nit: str | None
    telefono: str | None
    direccion: str | None
    latitud: float | None
    longitud: float | None
    descripcion: str | None
    estado_aprobacion: EstadoAprobacionTaller
    estado_operativo: EstadoOperativoTaller
    fecha_registro: datetime
    fecha_aprobacion: datetime | None = None
    correo: str | None = None  # Del usuario relacionado

    model_config = {"from_attributes": True}


# ============================================================================
# SCHEMAS ADMINISTRATIVOS PARA GESTIÓN DE TALLERES
# ============================================================================


class TallerAdminListItem(BaseModel):
    """Schema para listar talleres en vista administrativa."""
    id_taller: UUID
    id_usuario: UUID
    nombre_taller: str
    razon_social: str | None
    nit: str | None
    telefono: str | None
    correo: str  # Del usuario relacionado
    estado_aprobacion: EstadoAprobacionTaller
    estado_operativo: EstadoOperativoTaller
    es_activo: bool  # Estado del usuario
    fecha_registro: datetime
    fecha_aprobacion: datetime | None = None

    model_config = {"from_attributes": True}


class TallerAdminDetail(BaseModel):
    """Schema para detalle administrativo completo de un taller."""
    id_taller: UUID
    id_usuario: UUID
    nombre_taller: str
    razon_social: str | None
    nit: str | None
    telefono: str | None
    direccion: str | None
    latitud: float | None
    longitud: float | None
    descripcion: str | None
    estado_aprobacion: EstadoAprobacionTaller
    estado_operativo: EstadoOperativoTaller
    fecha_registro: datetime
    fecha_aprobacion: datetime | None = None
    # Información del usuario relacionado
    correo: str
    es_activo: bool

    model_config = {"from_attributes": True}


class TallerAdminUpdate(BaseModel):
    """Schema para actualizar información administrativa del taller."""
    nombre_taller: str | None = Field(default=None, min_length=2, max_length=255)
    razon_social: str | None = Field(default=None, min_length=2, max_length=255)
    nit: str | None = Field(default=None, min_length=5, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=500)
    latitud: float | None = None
    longitud: float | None = None
    descripcion: str | None = Field(default=None, max_length=1000)


class TallerDecisionRequest(BaseModel):
    """Schema para rechazo de solicitud de taller con motivo opcional."""
    motivo: str | None = Field(default=None, max_length=1000)


class TallerEstadoResponse(BaseModel):
    """Schema de respuesta estándar para acciones administrativas."""
    mensaje: str
    id_taller: UUID
    estado_aprobacion: EstadoAprobacionTaller
    estado_operativo: EstadoOperativoTaller
    es_activo: bool

    model_config = {"from_attributes": True}
