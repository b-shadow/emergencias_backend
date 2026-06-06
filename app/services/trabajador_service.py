import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.core.enums import EstadoOrdenRecojo, RolUsuario
from app.core.exceptions import bad_request, forbidden, not_found
from app.core.security import get_password_hash
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.cliente import Cliente
from app.models.orden_recojo import OrdenRecojo
from app.models.taller import Taller
from app.models.trabajador import Trabajador
from app.models.usuario import Usuario
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.services.route_eta_service import RouteEtaService
from app.services.tracking_ws_manager import tracking_ws_manager


class TrabajadorService:
    @staticmethod
    def _tracking_payload(orden: OrdenRecojo) -> dict:
        taller = orden.asignacion.taller if orden.asignacion else None
        solicitud = orden.asignacion.solicitud if orden.asignacion else None
        return {
            "id_orden_recojo": str(orden.id_orden_recojo),
            "id_asignacion": str(orden.id_asignacion),
            "id_trabajador": str(orden.id_trabajador),
            "estado_orden": orden.estado_orden.value if hasattr(orden.estado_orden, "value") else str(orden.estado_orden),
            "latitud_actual": orden.latitud_actual,
            "longitud_actual": orden.longitud_actual,
            "distancia_metros": orden.distancia_metros,
            "duracion_segundos": orden.duracion_segundos,
            "ruta_geojson": orden.ruta_geojson,
            "ruta_recorrida_geojson": orden.ruta_recorrida_geojson,
            "latitud_destino": orden.latitud_destino,
            "longitud_destino": orden.longitud_destino,
            "latitud_solicitud": solicitud.latitud if solicitud else None,
            "longitud_solicitud": solicitud.longitud if solicitud else None,
            "latitud_taller": taller.latitud if taller else None,
            "longitud_taller": taller.longitud if taller else None,
            "fecha_asignacion": orden.fecha_asignacion.isoformat() if orden.fecha_asignacion else None,
            "fecha_aceptacion": orden.fecha_aceptacion.isoformat() if orden.fecha_aceptacion else None,
            "fecha_llegada_auxilio": orden.fecha_llegada_auxilio.isoformat() if orden.fecha_llegada_auxilio else None,
            "fecha_inicio_regreso": orden.fecha_inicio_regreso.isoformat() if orden.fecha_inicio_regreso else None,
            "fecha_llegada_taller": orden.fecha_llegada_taller.isoformat() if orden.fecha_llegada_taller else None,
            "fecha_ultima_ubicacion": orden.fecha_ultima_ubicacion.isoformat() if orden.fecha_ultima_ubicacion else None,
            "duracion_total_segundos": orden.duracion_total_segundos,
            "taller_nombre": taller.nombre_taller if taller else None,
        }

    @staticmethod
    def _append_recorrido(orden: OrdenRecojo, latitud: float, longitud: float) -> None:
        coords: list[list[float]] = []
        if orden.ruta_recorrida_geojson:
            try:
                geo = json.loads(orden.ruta_recorrida_geojson)
                if isinstance(geo, dict) and geo.get("type") == "LineString":
                    coords = list(geo.get("coordinates") or [])
            except Exception:
                coords = []
        point = [float(longitud), float(latitud)]
        if not coords or coords[-1] != point:
            coords.append(point)
        orden.ruta_recorrida_geojson = json.dumps({"type": "LineString", "coordinates": coords})

    @staticmethod
    def _compute_destino(orden: OrdenRecojo) -> tuple[float | None, float | None]:
        if orden.estado_orden in (EstadoOrdenRecojo.EN_CAMINO_TALLER, EstadoOrdenRecojo.FINALIZADA):
            taller = orden.asignacion.taller
            if taller:
                return taller.latitud, taller.longitud
            return None, None
        solicitud = orden.asignacion.solicitud
        return solicitud.latitud, solicitud.longitud

    @staticmethod
    def _set_route_target(orden: OrdenRecojo) -> None:
        destino_lat, destino_lon = TrabajadorService._compute_destino(orden)
        orden.latitud_destino = destino_lat
        orden.longitud_destino = destino_lon

        if (
            orden.latitud_actual is not None
            and orden.longitud_actual is not None
            and destino_lat is not None
            and destino_lon is not None
        ):
            route = RouteEtaService.compute_route(
                origen_lat=orden.latitud_actual,
                origen_lon=orden.longitud_actual,
                destino_lat=destino_lat,
                destino_lon=destino_lon,
                profile="foot",
            )
            orden.distancia_metros = route["distance_meters"]
            orden.duracion_segundos = route["duration_seconds"]
            if route["route_geojson"] is not None:
                orden.ruta_geojson = json.dumps(route["route_geojson"])

    @staticmethod
    def _get_taller_from_user(db: Session, user: Usuario) -> Taller:
        taller = db.query(Taller).filter(Taller.id_usuario == user.id_usuario).first()
        if not taller:
            raise not_found("No se encontró perfil de taller")
        return taller

    @staticmethod
    def crear_trabajador(db: Session, payload: dict, current_user: Usuario) -> Trabajador:
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede crear trabajadores")
        taller = TrabajadorService._get_taller_from_user(db, current_user)
        exists = db.query(Usuario).filter(Usuario.correo == payload["correo"]).first()
        if exists:
            raise bad_request("El correo ya está registrado")
        usuario = Usuario(
            correo=payload["correo"],
            contrasena_hash=get_password_hash(payload["contrasena"]),
            nombre_completo=payload["nombre_completo"],
            rol=RolUsuario.TRABAJADOR,
            es_activo=True,
        )
        db.add(usuario)
        db.flush()
        trabajador = Trabajador(
            id_usuario=usuario.id_usuario,
            id_taller=taller.id_taller,
            telefono=payload.get("telefono"),
            licencia_conducir=payload.get("licencia_conducir"),
            es_activo=True,
        )
        db.add(trabajador)
        db.commit()
        db.refresh(trabajador)
        return trabajador

    @staticmethod
    def listar_mis_trabajadores(db: Session, current_user: Usuario) -> list[Trabajador]:
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede listar trabajadores")
        taller = TrabajadorService._get_taller_from_user(db, current_user)
        return (
            db.query(Trabajador)
            .options(joinedload(Trabajador.usuario))
            .filter(Trabajador.id_taller == taller.id_taller)
            .all()
        )

    @staticmethod
    def _get_trabajador_owned_by_taller(
        db: Session, id_trabajador: UUID, current_user: Usuario
    ) -> Trabajador:
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede gestionar trabajadores")
        taller = TrabajadorService._get_taller_from_user(db, current_user)
        trabajador = (
            db.query(Trabajador)
            .options(joinedload(Trabajador.usuario))
            .filter(Trabajador.id_trabajador == id_trabajador, Trabajador.id_taller == taller.id_taller)
            .first()
        )
        if not trabajador:
            raise not_found("Trabajador no encontrado para este taller")
        return trabajador

    @staticmethod
    def actualizar_trabajador(
        db: Session, id_trabajador: UUID, payload: dict, current_user: Usuario
    ) -> Trabajador:
        trabajador = TrabajadorService._get_trabajador_owned_by_taller(db, id_trabajador, current_user)
        trabajador.usuario.nombre_completo = payload["nombre_completo"].strip()
        trabajador.telefono = payload.get("telefono")
        trabajador.licencia_conducir = payload.get("licencia_conducir")
        db.commit()
        db.refresh(trabajador)
        return trabajador

    @staticmethod
    def cambiar_estado_trabajador(
        db: Session, id_trabajador: UUID, es_activo: bool, current_user: Usuario
    ) -> Trabajador:
        trabajador = TrabajadorService._get_trabajador_owned_by_taller(db, id_trabajador, current_user)
        trabajador.es_activo = es_activo
        if trabajador.usuario:
            trabajador.usuario.es_activo = es_activo
        db.commit()
        db.refresh(trabajador)
        return trabajador

    @staticmethod
    def asignar_trabajador_a_asignacion(
        db: Session, id_asignacion: UUID, id_trabajador: UUID, current_user: Usuario
    ) -> OrdenRecojo:
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede asignar trabajador")
        taller = TrabajadorService._get_taller_from_user(db, current_user)
        asignacion = db.query(AsignacionAtencion).filter(AsignacionAtencion.id_asignacion == id_asignacion).first()
        if not asignacion:
            raise not_found("Asignación no encontrada")
        if asignacion.id_taller != taller.id_taller:
            raise forbidden("La asignación no pertenece a tu taller")
        trabajador = db.query(Trabajador).filter(Trabajador.id_trabajador == id_trabajador).first()
        if not trabajador or trabajador.id_taller != taller.id_taller:
            raise bad_request("Trabajador inválido para este taller")

        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_asignacion == id_asignacion).first()
        if not orden:
            orden = OrdenRecojo(
                id_asignacion=id_asignacion,
                id_trabajador=id_trabajador,
                estado_orden=EstadoOrdenRecojo.PENDIENTE_ACEPTACION,
            )
            db.add(orden)
        else:
            orden.id_trabajador = id_trabajador
            orden.estado_orden = EstadoOrdenRecojo.PENDIENTE_ACEPTACION
            orden.fecha_aceptacion = None

        db.commit()
        db.refresh(orden)
        return orden

    @staticmethod
    def aceptar_orden_recojo(db: Session, id_orden_recojo: UUID, current_user: Usuario) -> OrdenRecojo:
        if current_user.rol != RolUsuario.TRABAJADOR:
            raise forbidden("Solo el trabajador puede aceptar la orden")
        trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
        if not trabajador:
            raise not_found("Perfil de trabajador no encontrado")
        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_orden_recojo == id_orden_recojo).first()
        if not orden:
            raise not_found("Orden de recojo no encontrada")
        if orden.id_trabajador != trabajador.id_trabajador:
            raise forbidden("Esta orden no te pertenece")
        orden.estado_orden = EstadoOrdenRecojo.ACEPTADA
        orden.fecha_aceptacion = datetime.now()
        orden.fecha_llegada_auxilio = None
        orden.fecha_inicio_regreso = None
        orden.fecha_llegada_taller = None
        orden.ruta_recorrida_geojson = json.dumps({"type": "LineString", "coordinates": []})
        TrabajadorService._set_route_target(orden)
        db.commit()
        db.refresh(orden)
        return orden

    @staticmethod
    def marcar_llegada_auxilio(db: Session, id_orden_recojo: UUID, current_user: Usuario) -> OrdenRecojo:
        if current_user.rol != RolUsuario.TRABAJADOR:
            raise forbidden("Solo el trabajador puede marcar llegada al auxilio")
        trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
        if not trabajador:
            raise not_found("Perfil de trabajador no encontrado")
        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_orden_recojo == id_orden_recojo).first()
        if not orden:
            raise not_found("Orden de recojo no encontrada")
        if orden.id_trabajador != trabajador.id_trabajador:
            raise forbidden("Esta orden no te pertenece")
        orden.estado_orden = EstadoOrdenRecojo.LLEGADA_AUXILIO
        orden.fecha_llegada_auxilio = datetime.now()
        orden.latitud_destino = orden.asignacion.solicitud.latitud if orden.asignacion and orden.asignacion.solicitud else None
        orden.longitud_destino = orden.asignacion.solicitud.longitud if orden.asignacion and orden.asignacion.solicitud else None
        db.commit()
        db.refresh(orden)
        return orden

    @staticmethod
    def iniciar_retorno_taller(db: Session, id_orden_recojo: UUID, current_user: Usuario) -> OrdenRecojo:
        if current_user.rol != RolUsuario.TRABAJADOR:
            raise forbidden("Solo el trabajador puede iniciar retorno")
        trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
        if not trabajador:
            raise not_found("Perfil de trabajador no encontrado")
        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_orden_recojo == id_orden_recojo).first()
        if not orden:
            raise not_found("Orden de recojo no encontrada")
        if orden.id_trabajador != trabajador.id_trabajador:
            raise forbidden("Esta orden no te pertenece")
        orden.estado_orden = EstadoOrdenRecojo.EN_CAMINO_TALLER
        orden.fecha_inicio_regreso = datetime.now()
        TrabajadorService._set_route_target(orden)
        if not orden.ruta_recorrida_geojson:
            orden.ruta_recorrida_geojson = json.dumps({"type": "LineString", "coordinates": []})
        db.commit()
        db.refresh(orden)
        return orden

    @staticmethod
    def marcar_llegada_taller(db: Session, id_orden_recojo: UUID, current_user: Usuario) -> OrdenRecojo:
        if current_user.rol != RolUsuario.TRABAJADOR:
            raise forbidden("Solo el trabajador puede marcar llegada al taller")
        trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
        if not trabajador:
            raise not_found("Perfil de trabajador no encontrado")
        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_orden_recojo == id_orden_recojo).first()
        if not orden:
            raise not_found("Orden de recojo no encontrada")
        if orden.id_trabajador != trabajador.id_trabajador:
            raise forbidden("Esta orden no te pertenece")
        orden.estado_orden = EstadoOrdenRecojo.FINALIZADA
        orden.fecha_llegada_taller = datetime.now()
        orden.duracion_total_segundos = (
            (orden.fecha_llegada_taller - orden.fecha_aceptacion).total_seconds()
            if orden.fecha_aceptacion and orden.fecha_llegada_taller
            else None
        )
        orden.latitud_destino = orden.asignacion.taller.latitud if orden.asignacion and orden.asignacion.taller else None
        orden.longitud_destino = orden.asignacion.taller.longitud if orden.asignacion and orden.asignacion.taller else None
        db.commit()
        db.refresh(orden)
        return orden

    @staticmethod
    def _can_view_orden(db: Session, orden: OrdenRecojo, current_user: Usuario) -> None:
        if current_user.rol == RolUsuario.ADMINISTRADOR:
            return
        if current_user.rol == RolUsuario.TRABAJADOR:
            trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
            if trabajador and trabajador.id_trabajador == orden.id_trabajador:
                return
        if current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if taller and orden.asignacion.id_taller == taller.id_taller:
                return
        if current_user.rol == RolUsuario.CLIENTE:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if cliente and orden.asignacion.solicitud.id_cliente == cliente.id_cliente:
                return
        raise forbidden("No tienes acceso a esta orden")

    @staticmethod
    def actualizar_ubicacion(db: Session, id_orden_recojo: UUID, payload: dict, current_user: Usuario) -> OrdenRecojo:
        if current_user.rol != RolUsuario.TRABAJADOR:
            raise forbidden("Solo el trabajador puede compartir ubicación")
        trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
        if not trabajador:
            raise not_found("Perfil de trabajador no encontrado")
        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_orden_recojo == id_orden_recojo).first()
        if not orden:
            raise not_found("Orden de recojo no encontrada")
        if orden.id_trabajador != trabajador.id_trabajador:
            raise forbidden("Esta orden no te pertenece")

        orden.latitud_actual = payload["latitud"]
        orden.longitud_actual = payload["longitud"]
        orden.fecha_ultima_ubicacion = datetime.now()
        if orden.estado_orden in (EstadoOrdenRecojo.ACEPTADA, EstadoOrdenRecojo.PENDIENTE_ACEPTACION):
            orden.estado_orden = EstadoOrdenRecojo.EN_CAMINO_RECOJO
        TrabajadorService._append_recorrido(orden, payload["latitud"], payload["longitud"])
        TrabajadorService._set_route_target(orden)
        db.commit()
        db.refresh(orden)
        return orden

    @staticmethod
    def get_tracking(db: Session, id_orden_recojo: UUID, current_user: Usuario) -> OrdenRecojo:
        orden = db.query(OrdenRecojo).filter(OrdenRecojo.id_orden_recojo == id_orden_recojo).first()
        if not orden:
            raise not_found("Orden de recojo no encontrada")
        TrabajadorService._can_view_orden(db, orden, current_user)
        return orden

    @staticmethod
    def listar_mis_ordenes(db: Session, current_user: Usuario) -> list[OrdenRecojo]:
        if current_user.rol != RolUsuario.TRABAJADOR:
            raise forbidden("Solo el trabajador puede listar sus órdenes")
        trabajador = db.query(Trabajador).filter(Trabajador.id_usuario == current_user.id_usuario).first()
        if not trabajador:
            raise not_found("Perfil de trabajador no encontrado")
        return (
            db.query(OrdenRecojo)
            .filter(
                OrdenRecojo.id_trabajador == trabajador.id_trabajador,
                OrdenRecojo.estado_orden.in_(
                    [
                        EstadoOrdenRecojo.PENDIENTE_ACEPTACION,
                        EstadoOrdenRecojo.ACEPTADA,
                        EstadoOrdenRecojo.EN_CAMINO_RECOJO,
                        EstadoOrdenRecojo.EN_CAMINO_TALLER,
                    ]
                ),
            )
            .all()
        )

    @staticmethod
    def get_tracking_by_solicitud(db: Session, id_solicitud: UUID, current_user: Usuario) -> OrdenRecojo:
        orden = (
            db.query(OrdenRecojo)
            .join(AsignacionAtencion, AsignacionAtencion.id_asignacion == OrdenRecojo.id_asignacion)
            .filter(AsignacionAtencion.id_solicitud == id_solicitud)
            .first()
        )
        if not orden:
            raise not_found("No existe orden de recojo para esta solicitud")
        TrabajadorService._can_view_orden(db, orden, current_user)
        return orden

    @staticmethod
    async def broadcast_tracking_event(orden: OrdenRecojo) -> None:
        payload = TrabajadorService._tracking_payload(orden)
        solicitud_id = orden.asignacion.id_solicitud
        await tracking_ws_manager.broadcast(orden.id_orden_recojo, solicitud_id, payload)
