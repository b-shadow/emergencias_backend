from fastapi import APIRouter

from app.api.v1.endpoints import (
    asignaciones,
    auth,
    bitacora,
    clientes,
    especialidades_servicios,
    administrador_especialidades,
    administrador_servicios,
    estadisticas_taller,
    notificaciones,
    postulaciones,
    push,
    solicitudes_emergencia,
    talleres,
    usuarios,
    vehiculos,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(bitacora.router, prefix="/bitacora", tags=["Bitácora"])
api_router.include_router(usuarios.router, prefix="/usuarios", tags=["Usuarios"])
api_router.include_router(clientes.router, prefix="/clientes", tags=["Clientes"])
api_router.include_router(talleres.router, prefix="/talleres", tags=["Talleres"])
api_router.include_router(especialidades_servicios.router)
api_router.include_router(administrador_especialidades.router, prefix="/admin/especialidades", tags=["Admin"])
api_router.include_router(administrador_servicios.router, prefix="/admin/servicios", tags=["Admin"])
api_router.include_router(estadisticas_taller.router, prefix="/estadisticas-taller", tags=["Estadísticas Taller"])
api_router.include_router(vehiculos.router, prefix="/vehiculos", tags=["Vehículos"])
api_router.include_router(solicitudes_emergencia.router, prefix="/solicitudes_emergencia", tags=["Solicitudes de Emergencia"])
api_router.include_router(postulaciones.router, prefix="/postulaciones", tags=["Postulaciones"])
api_router.include_router(asignaciones.router, prefix="/asignaciones", tags=["Asignaciones"])
api_router.include_router(notificaciones.router, prefix="/notificaciones", tags=["Notificaciones"])
api_router.include_router(push.router, prefix="/push", tags=["Push Notifications"])
