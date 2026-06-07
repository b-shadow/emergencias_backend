import json
from collections import defaultdict
from typing import Any

from app.services.cotizacion_service import CotizacionService


class ServicioEjecutadoService:
    META_PREFIX = "[[RSMETA]]"

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_uuid(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def get_cotizacion_items(asignacion) -> list[dict]:
        postulacion = getattr(asignacion, "postulacion", None)
        cotizacion = getattr(postulacion, "cotizacion", None) if postulacion else None
        if not cotizacion:
            return []
        return CotizacionService._parse_servicios_detalle(cotizacion.detalle)

    @staticmethod
    def build_cotizacion_index(asignacion) -> dict[str, list[dict]]:
        index: dict[str, list[dict]] = defaultdict(list)
        for item in ServicioEjecutadoService.get_cotizacion_items(asignacion):
            item_id = ServicioEjecutadoService._normalize_uuid(item.get("id_taller_servicio"))
            if not item_id:
                continue
            index[item_id].append(
                {
                    "precio_servicio": ServicioEjecutadoService._to_float(item.get("precio_servicio")),
                    "nombre_servicio": item.get("nombre_servicio"),
                    "incluido_en_solicitud": bool(item.get("incluido_en_solicitud", True)),
                }
            )
        return index

    @staticmethod
    def encode_observaciones(observaciones: str | None, meta: dict[str, Any]) -> str:
        payload = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
        clean_obs = (observaciones or "").strip()
        return f"{ServicioEjecutadoService.META_PREFIX}{payload}\n{clean_obs}".rstrip()

    @staticmethod
    def parse_observaciones(observaciones: str | None) -> tuple[str | None, dict[str, Any]]:
        if not observaciones:
            return None, {}
        if not observaciones.startswith(ServicioEjecutadoService.META_PREFIX):
            return observaciones, {}
        raw = observaciones[len(ServicioEjecutadoService.META_PREFIX):]
        meta_line, _, remainder = raw.partition("\n")
        try:
            meta = json.loads(meta_line) if meta_line else {}
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}
        clean = remainder.strip() or None
        return clean, meta

    @staticmethod
    def enrich_resultados(asignacion, resultados: list) -> list[dict]:
        cotizacion_index = ServicioEjecutadoService.build_cotizacion_index(asignacion)
        consumidos_cotizados: dict[str, int] = defaultdict(int)
        enriched: list[dict] = []

        ordered = sorted(
            resultados,
            key=lambda row: (
                getattr(row, "fecha_registro", None) or 0,
                str(getattr(row, "id_resultado_servicio", "")),
            ),
        )

        for resultado in ordered:
            service_id = ServicioEjecutadoService._normalize_uuid(resultado.id_taller_servicio)
            observaciones_clean, meta = ServicioEjecutadoService.parse_observaciones(resultado.observaciones)
            origen = str(meta.get("origen_item") or "").upper()
            precio_unitario = ServicioEjecutadoService._to_float(meta.get("precio_unitario"), default=-1)

            if origen not in {"COTIZADO", "EXTRA"}:
                quoted_rows = cotizacion_index.get(service_id or "", [])
                if consumidos_cotizados.get(service_id or "", 0) < len(quoted_rows):
                    origen = "COTIZADO"
                    precio_unitario = quoted_rows[consumidos_cotizados.get(service_id or "", 0)]["precio_servicio"]
                else:
                    origen = "EXTRA"
                    precio_unitario = ServicioEjecutadoService._to_float(
                        getattr(getattr(resultado, "taller_servicio", None), "precio_base", 0)
                    )
            elif origen == "COTIZADO" and precio_unitario < 0:
                quoted_rows = cotizacion_index.get(service_id or "", [])
                quote_idx = consumidos_cotizados.get(service_id or "", 0)
                if quote_idx < len(quoted_rows):
                    precio_unitario = quoted_rows[quote_idx]["precio_servicio"]
                else:
                    precio_unitario = 0.0
            elif origen == "EXTRA" and precio_unitario < 0:
                precio_unitario = ServicioEjecutadoService._to_float(
                    getattr(getattr(resultado, "taller_servicio", None), "precio_base", 0)
                )

            if origen == "COTIZADO":
                consumidos_cotizados[service_id or ""] += 1

            enriched.append(
                {
                    "resultado": resultado,
                    "id_taller_servicio": service_id,
                    "origen_item": origen,
                    "precio_unitario": round(precio_unitario, 2),
                    "observaciones_limpias": observaciones_clean,
                }
            )

        return enriched

    @staticmethod
    def build_servicios_catalogo(asignacion, servicios_taller: list, resultados: list) -> list[dict]:
        cotizacion_index = ServicioEjecutadoService.build_cotizacion_index(asignacion)
        enriched_results = ServicioEjecutadoService.enrich_resultados(asignacion, resultados)
        cotizados_realizados: dict[str, int] = defaultdict(int)
        extras_realizados: dict[str, int] = defaultdict(int)

        for item in enriched_results:
            service_id = item["id_taller_servicio"] or ""
            if item["origen_item"] == "COTIZADO":
                cotizados_realizados[service_id] += 1
            else:
                extras_realizados[service_id] += 1

        output: list[dict] = []
        for ts in servicios_taller:
            service_id = ServicioEjecutadoService._normalize_uuid(ts.id_taller_servicio)
            cotizados = cotizacion_index.get(service_id or "", [])
            cantidad_cotizada = len(cotizados)
            cantidad_realizada_cotizada = cotizados_realizados.get(service_id or "", 0)
            precio_cotizado = cotizados[0]["precio_servicio"] if cotizados else None
            output.append(
                {
                    "id_taller_servicio": str(ts.id_taller_servicio),
                    "id_servicio": str(ts.servicio.id_servicio),
                    "nombre_servicio": ts.servicio.nombre_servicio,
                    "descripcion": ts.servicio.descripcion,
                    "realizado": False,
                    "precio_base": round(ServicioEjecutadoService._to_float(ts.precio_base), 2),
                    "es_cotizado": cantidad_cotizada > 0,
                    "cantidad_cotizada": cantidad_cotizada,
                    "cantidad_realizada_cotizada": cantidad_realizada_cotizada,
                    "cantidad_pendiente_cotizada": max(cantidad_cotizada - cantidad_realizada_cotizada, 0),
                    "cantidad_extras_realizados": extras_realizados.get(service_id or "", 0),
                    "precio_cotizado": round(precio_cotizado, 2) if precio_cotizado is not None else None,
                }
            )
        return output

    @staticmethod
    def calculate_extras_total(asignacion, resultados: list) -> float:
        total = 0.0
        for item in ServicioEjecutadoService.enrich_resultados(asignacion, resultados):
            if item["origen_item"] == "EXTRA":
                total += ServicioEjecutadoService._to_float(item["precio_unitario"])
        return round(total, 2)

    @staticmethod
    def pendientes_cotizados(asignacion, resultados: list) -> list[dict]:
        cotizacion_index = ServicioEjecutadoService.build_cotizacion_index(asignacion)
        enriched_results = ServicioEjecutadoService.enrich_resultados(asignacion, resultados)
        cotizados_realizados: dict[str, int] = defaultdict(int)
        for item in enriched_results:
            if item["origen_item"] == "COTIZADO":
                cotizados_realizados[item["id_taller_servicio"] or ""] += 1

        pendientes: list[dict] = []
        for id_taller_servicio, rows in cotizacion_index.items():
            faltantes = len(rows) - cotizados_realizados.get(id_taller_servicio, 0)
            if faltantes > 0:
                pendientes.append(
                    {
                        "id_taller_servicio": id_taller_servicio,
                        "nombre_servicio": rows[0].get("nombre_servicio"),
                        "faltantes": faltantes,
                    }
                )
        return pendientes
