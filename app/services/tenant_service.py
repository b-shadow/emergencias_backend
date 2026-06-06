from sqlalchemy.orm import Session

from app.core.enums import RolUsuario
from app.core.exceptions import forbidden, not_found
from app.models.taller import Taller
from app.models.trabajador import Trabajador
from app.models.usuario import Usuario


class TenantService:
    @staticmethod
    def get_tenant_for_user(db: Session, current_user: Usuario):
        if current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if not taller or not taller.tenant:
                raise not_found("Tenant no encontrado para el taller")
            return taller.tenant

        if current_user.rol == RolUsuario.TRABAJADOR:
            trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
            if not trabajador:
                raise not_found("Perfil de trabajador no encontrado")
            taller = db.query(Taller).filter(Taller.id_taller == trabajador.id_taller).first()
            if not taller or not taller.tenant:
                raise not_found("Tenant no encontrado para el trabajador")
            return taller.tenant

        raise forbidden("Solo TALLER y TRABAJADOR tienen contexto tenant")
