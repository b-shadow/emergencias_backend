import json
from uuid import UUID

from fastapi import APIRouter, Depends, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.schemas.trabajador import (
    OrdenRecojoAsignarRequest,
    OrdenRecojoTrackingResponse,
    OrdenRecojoUbicacionRequest,
    TrabajadorEstadoRequest,
    TrabajadorCreateRequest,
    TrabajadorUpdateRequest,
    TrabajadorResponse,
)
from app.schemas.tenant import TenantTallerResponse
from app.services.tenant_service import TenantService
from app.services.trabajador_service import TrabajadorService
from app.services.tracking_ws_manager import tracking_ws_manager

router = APIRouter()


def _to_trabajador_response(trabajador) -> TrabajadorResponse:
    return TrabajadorResponse(
        id_trabajador=trabajador.id_trabajador,
        id_usuario=trabajador.id_usuario,
        id_taller=trabajador.id_taller,
        nombre_completo=getattr(trabajador.usuario, "nombre_completo", None),
        correo=getattr(trabajador.usuario, "correo", None),
        telefono=trabajador.telefono,
        licencia_conducir=trabajador.licencia_conducir,
        es_activo=trabajador.es_activo,
        fecha_registro=trabajador.fecha_registro,
    )


def _to_tracking_response(orden) -> OrdenRecojoTrackingResponse:
    cliente = orden.asignacion.solicitud.cliente if orden.asignacion and orden.asignacion.solicitud else None
    cliente_nombre = None
    if cliente:
        nombre = getattr(cliente, "nombre", None)
        apellido = getattr(cliente, "apellido", None)
        nombre_completo = " ".join(part for part in [nombre, apellido] if part)
        cliente_nombre = nombre_completo or getattr(cliente, "nombre_completo", None)

    return OrdenRecojoTrackingResponse(
        id_orden_recojo=orden.id_orden_recojo,
        id_asignacion=orden.id_asignacion,
        id_trabajador=orden.id_trabajador,
        estado_orden=orden.estado_orden,
        codigo_solicitud=orden.asignacion.solicitud.codigo_solicitud if orden.asignacion and orden.asignacion.solicitud else None,
        cliente_nombre=cliente_nombre,
        latitud_actual=orden.latitud_actual,
        longitud_actual=orden.longitud_actual,
        distancia_metros=orden.distancia_metros,
        duracion_segundos=orden.duracion_segundos,
        ruta_geojson=json.loads(orden.ruta_geojson) if orden.ruta_geojson else None,
        ruta_recorrida_geojson=json.loads(orden.ruta_recorrida_geojson) if orden.ruta_recorrida_geojson else None,
        latitud_destino=orden.latitud_destino,
        longitud_destino=orden.longitud_destino,
        latitud_solicitud=orden.asignacion.solicitud.latitud if orden.asignacion and orden.asignacion.solicitud else None,
        longitud_solicitud=orden.asignacion.solicitud.longitud if orden.asignacion and orden.asignacion.solicitud else None,
        latitud_taller=orden.asignacion.taller.latitud if orden.asignacion and orden.asignacion.taller else None,
        longitud_taller=orden.asignacion.taller.longitud if orden.asignacion and orden.asignacion.taller else None,
        taller_nombre=orden.asignacion.taller.nombre_taller if orden.asignacion and orden.asignacion.taller else None,
        fecha_asignacion=orden.fecha_asignacion,
        fecha_aceptacion=orden.fecha_aceptacion,
        fecha_llegada_auxilio=orden.fecha_llegada_auxilio,
        fecha_inicio_regreso=orden.fecha_inicio_regreso,
        fecha_llegada_taller=orden.fecha_llegada_taller,
        fecha_ultima_ubicacion=orden.fecha_ultima_ubicacion,
        duracion_total_segundos=orden.duracion_total_segundos,
    )


@router.get("/me/tenant", response_model=TenantTallerResponse)
def get_tenant_context_trabajador(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return TenantService.get_tenant_for_user(db, current_user)


@router.post("", response_model=TrabajadorResponse, status_code=status.HTTP_201_CREATED)
def crear_trabajador(
    payload: TrabajadorCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    trabajador = TrabajadorService.crear_trabajador(db, payload.model_dump(), current_user)
    return _to_trabajador_response(trabajador)


@router.get("", response_model=list[TrabajadorResponse])
def listar_trabajadores(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    trabajadores = TrabajadorService.listar_mis_trabajadores(db, current_user)
    return [_to_trabajador_response(t) for t in trabajadores]


@router.patch("/{id_trabajador}", response_model=TrabajadorResponse)
def actualizar_trabajador(
    id_trabajador: UUID,
    payload: TrabajadorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    trabajador = TrabajadorService.actualizar_trabajador(db, id_trabajador, payload.model_dump(), current_user)
    return _to_trabajador_response(trabajador)


@router.patch("/{id_trabajador}/estado", response_model=TrabajadorResponse)
def actualizar_estado_trabajador(
    id_trabajador: UUID,
    payload: TrabajadorEstadoRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    trabajador = TrabajadorService.cambiar_estado_trabajador(
        db, id_trabajador, payload.es_activo, current_user
    )
    return _to_trabajador_response(trabajador)


@router.post("/asignaciones/{id_asignacion}/orden-recojo", response_model=OrdenRecojoTrackingResponse)
def asignar_orden_recojo(
    id_asignacion: UUID,
    payload: OrdenRecojoAsignarRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.asignar_trabajador_a_asignacion(
        db, id_asignacion, payload.id_trabajador, current_user
    )
    return _to_tracking_response(orden)


@router.post("/ordenes-recojo/{id_orden_recojo}/accept", response_model=OrdenRecojoTrackingResponse)
async def aceptar_orden_recojo(
    id_orden_recojo: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.aceptar_orden_recojo(db, id_orden_recojo, current_user)
    await TrabajadorService.broadcast_tracking_event(orden)
    return _to_tracking_response(orden)


@router.post("/ordenes-recojo/{id_orden_recojo}/llegada-auxilio", response_model=OrdenRecojoTrackingResponse)
async def marcar_llegada_auxilio(
    id_orden_recojo: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.marcar_llegada_auxilio(db, id_orden_recojo, current_user)
    await TrabajadorService.broadcast_tracking_event(orden)
    return _to_tracking_response(orden)


@router.post("/ordenes-recojo/{id_orden_recojo}/iniciar-retorno", response_model=OrdenRecojoTrackingResponse)
async def iniciar_retorno(
    id_orden_recojo: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.iniciar_retorno_taller(db, id_orden_recojo, current_user)
    await TrabajadorService.broadcast_tracking_event(orden)
    return _to_tracking_response(orden)


@router.post("/ordenes-recojo/{id_orden_recojo}/llegada-taller", response_model=OrdenRecojoTrackingResponse)
async def marcar_llegada_taller(
    id_orden_recojo: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.marcar_llegada_taller(db, id_orden_recojo, current_user)
    await TrabajadorService.broadcast_tracking_event(orden)
    return _to_tracking_response(orden)


@router.post("/ordenes-recojo/{id_orden_recojo}/ubicacion", response_model=OrdenRecojoTrackingResponse)
async def actualizar_ubicacion(
    id_orden_recojo: UUID,
    payload: OrdenRecojoUbicacionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.actualizar_ubicacion(db, id_orden_recojo, payload.model_dump(), current_user)
    await TrabajadorService.broadcast_tracking_event(orden)
    return _to_tracking_response(orden)


@router.get("/ordenes-recojo/{id_orden_recojo}/tracking", response_model=OrdenRecojoTrackingResponse)
def get_tracking(
    id_orden_recojo: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.get_tracking(db, id_orden_recojo, current_user)
    return _to_tracking_response(orden)


@router.get("/mis-ordenes", response_model=list[OrdenRecojoTrackingResponse])
def listar_mis_ordenes(
    incluir_historial: bool = False,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ordenes = TrabajadorService.listar_mis_ordenes(db, current_user, incluir_historial=incluir_historial)
    return [_to_tracking_response(orden) for orden in ordenes]


@router.get("/solicitudes/{id_solicitud}/tracking", response_model=OrdenRecojoTrackingResponse)
def get_tracking_by_solicitud(
    id_solicitud: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    orden = TrabajadorService.get_tracking_by_solicitud(db, id_solicitud, current_user)
    return _to_tracking_response(orden)


@router.websocket("/ws/ordenes-recojo/{id_orden_recojo}")
async def ws_tracking_orden(id_orden_recojo: UUID, websocket: WebSocket):
    await tracking_ws_manager.connect_order(id_orden_recojo, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        tracking_ws_manager.disconnect(websocket)


@router.websocket("/ws/solicitudes/{id_solicitud}")
async def ws_tracking_solicitud(id_solicitud: UUID, websocket: WebSocket):
    await tracking_ws_manager.connect_solicitud(id_solicitud, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        tracking_ws_manager.disconnect(websocket)
