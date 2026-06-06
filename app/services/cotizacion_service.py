from datetime import datetime
import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EstadoCotizacion, RolUsuario
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.cotizacion_atencion import CotizacionAtencion
from app.models.postulacion_taller import PostulacionTaller
from app.models.taller import Taller


class CotizacionService:
    @staticmethod
    def _build_servicios_detalle(servicios: list[dict]) -> str:
        return json.dumps({"servicios": servicios}, ensure_ascii=False)

    @staticmethod
    def _parse_servicios_detalle(detalle: str | None) -> list[dict]:
        if not detalle:
            return []
        try:
            payload = json.loads(detalle)
            if isinstance(payload, dict) and isinstance(payload.get("servicios"), list):
                return payload["servicios"]
        except Exception:
            return []
        return []

    @staticmethod
    def _to_response(cotizacion: CotizacionAtencion, postulacion: PostulacionTaller | None = None):
        servicios = CotizacionService._parse_servicios_detalle(cotizacion.detalle)
        setattr(cotizacion, "servicios", servicios)
        if postulacion is not None:
            setattr(cotizacion, "tiempo_estimado_llegada_min", postulacion.tiempo_estimado_llegada_min)
        return cotizacion

    @staticmethod
    def _get_postulacion_with_access(db: Session, postulacion_id: UUID, current_user):
        postulacion = (
            db.query(PostulacionTaller)
            .filter(PostulacionTaller.id_postulacion == postulacion_id)
            .first()
        )
        if not postulacion:
            raise not_found("Postulacion no encontrada")

        if current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if not taller or taller.id_taller != postulacion.id_taller:
                raise forbidden("No tienes acceso a esta postulacion")
        elif current_user.rol == RolUsuario.CLIENTE:
            from app.models.cliente import Cliente

            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or postulacion.solicitud.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes acceso a esta postulacion")

        return postulacion

    @staticmethod
    def upsert_cotizacion(db: Session, postulacion_id: UUID, data: dict, current_user):
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede crear/actualizar cotizaciones")

        postulacion = CotizacionService._get_postulacion_with_access(db, postulacion_id, current_user)
        if postulacion.estado_postulacion.value != "POSTULADA":
            raise bad_request("Solo se puede cotizar una postulacion en estado POSTULADA")

        from app.models.taller_servicio import TallerServicio

        servicios_input = data.get("servicios") or []
        if not isinstance(servicios_input, list) or len(servicios_input) == 0:
            raise bad_request("Debes enviar al menos un servicio en la cotizacion")

        ids = [item["id_taller_servicio"] for item in servicios_input]
        servicios_taller = (
            db.query(TallerServicio)
            .filter(
                TallerServicio.id_taller_servicio.in_(ids),
                TallerServicio.id_taller == postulacion.id_taller,
            )
            .all()
        )
        if len(servicios_taller) != len(set(ids)):
            raise bad_request("Todos los servicios cotizados deben pertenecer al taller postulado")

        servicios_map = {serv.id_taller_servicio: serv for serv in servicios_taller}
        servicios_detalle = []
        subtotal = 0.0

        for item in servicios_input:
            precio_item = float(item["precio_servicio"])
            subtotal += precio_item
            servicio = servicios_map.get(item["id_taller_servicio"])
            servicios_detalle.append(
                {
                    "id_taller_servicio": str(item["id_taller_servicio"]),
                    "precio_servicio": precio_item,
                    "nombre_servicio": item.get("nombre_servicio") or (servicio.nombre_servicio if servicio else None),
                    "categoria_tarifa": item.get("categoria_tarifa") or (servicio.categoria_tarifa if servicio else None),
                    "incluido_en_solicitud": bool(item.get("incluido_en_solicitud", True)),
                }
            )

        precio_servicio = subtotal
        costo_ida = float(data.get("costo_ida", 0))
        precio_total = precio_servicio + costo_ida
        servicio_principal_id = servicios_input[0]["id_taller_servicio"]

        cotizacion = (
            db.query(CotizacionAtencion)
            .filter(CotizacionAtencion.id_postulacion == postulacion_id)
            .first()
        )

        if cotizacion:
            if cotizacion.estado_cotizacion == EstadoCotizacion.ACEPTADA_CLIENTE:
                raise bad_request("La cotizacion ya fue aceptada por el cliente y no puede editarse")
            cotizacion.id_taller_servicio = servicio_principal_id
            cotizacion.precio_servicio = precio_servicio
            cotizacion.costo_ida = costo_ida
            cotizacion.precio_total_estimado = precio_total
            cotizacion.tipo_pintura = data.get("tipo_pintura")
            cotizacion.detalle = CotizacionService._build_servicios_detalle(servicios_detalle)
            cotizacion.estado_cotizacion = EstadoCotizacion.PENDIENTE
            cotizacion.fecha_respuesta_cliente = None
        else:
            cotizacion = CotizacionAtencion(
                id_postulacion=postulacion_id,
                id_taller_servicio=servicio_principal_id,
                precio_servicio=precio_servicio,
                costo_ida=costo_ida,
                precio_total_estimado=precio_total,
                estado_cotizacion=EstadoCotizacion.PENDIENTE,
                tipo_pintura=data.get("tipo_pintura"),
                detalle=CotizacionService._build_servicios_detalle(servicios_detalle),
            )
            db.add(cotizacion)

        db.commit()
        db.refresh(cotizacion)
        return CotizacionService._to_response(cotizacion, postulacion)

    @staticmethod
    def get_cotizacion(db: Session, postulacion_id: UUID, current_user):
        postulacion = CotizacionService._get_postulacion_with_access(db, postulacion_id, current_user)
        cotizacion = (
            db.query(CotizacionAtencion)
            .filter(CotizacionAtencion.id_postulacion == postulacion_id)
            .first()
        )
        if not cotizacion:
            raise not_found("Cotizacion no encontrada para la postulacion")
        return CotizacionService._to_response(cotizacion, postulacion)

    @staticmethod
    def decidir_cotizacion(db: Session, postulacion_id: UUID, aceptar: bool, current_user):
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo el cliente puede aceptar/rechazar cotizaciones")
        CotizacionService._get_postulacion_with_access(db, postulacion_id, current_user)
        cotizacion = (
            db.query(CotizacionAtencion)
            .filter(CotizacionAtencion.id_postulacion == postulacion_id)
            .first()
        )
        if not cotizacion:
            raise not_found("Cotizacion no encontrada para la postulacion")
        if cotizacion.estado_cotizacion != EstadoCotizacion.PENDIENTE:
            raise bad_request("La cotizacion ya fue respondida previamente")

        cotizacion.estado_cotizacion = (
            EstadoCotizacion.ACEPTADA_CLIENTE if aceptar else EstadoCotizacion.RECHAZADA_CLIENTE
        )
        cotizacion.fecha_respuesta_cliente = datetime.now()
        db.commit()
        db.refresh(cotizacion)
        return cotizacion
