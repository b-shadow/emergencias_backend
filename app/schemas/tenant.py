from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TenantTallerResponse(BaseModel):
    id_tenant: UUID
    nombre_tenant: str
    slug_tenant: str
    es_activo: bool
    fecha_creacion: datetime

    model_config = {"from_attributes": True}
