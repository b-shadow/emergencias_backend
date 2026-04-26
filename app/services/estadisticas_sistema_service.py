from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session, selectinload

from app.core.enums import EstadoResultado, EstadoSolicitud, NivelUrgencia
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller
from app.schemas.estadisticas_sistema import (
    EstadisticasGeneralesResponse,
    FiltroReporteSistemaAplicado,
    IncidenteFrequente,
    OpcionesFiltrosSistema,
    ReporteFiltradoSistema,
    ReporteGraficosSistema,
    ReporteTablaSistemaItem,
    TallerActividad,
    TiempoRespuesta,
    ZonaEmergencia,
)


class EstadisticasSistemaService:
    """Servicio para calcular estadisticas generales del sistema."""

    @staticmethod
    def obtener_estadisticas_sistema(
        db: Session,
        fecha_inicio: Optional[datetime] = None,
        fecha_fin: Optional[datetime] = None,
        agrupar_por: str = "dia",
        nivel_urgencia: Optional[str] = None,
        categoria_incidente: Optional[str] = None,
        estado_solicitud: Optional[str] = None,
        id_taller: Optional[str] = None,
    ) -> EstadisticasGeneralesResponse:
        if not fecha_fin:
            fecha_fin = datetime.utcnow()
        if not fecha_inicio:
            fecha_inicio = fecha_fin - timedelta(days=30)

        filtros = {
            "nivel_urgencia": nivel_urgencia.strip().upper() if nivel_urgencia else None,
            "categoria_incidente": (
                categoria_incidente.strip().upper() if categoria_incidente else None
            ),
            "estado_solicitud": estado_solicitud.strip().upper() if estado_solicitud else None,
            "id_taller": id_taller.strip() if id_taller else None,
        }

        base_solicitudes = (
            db.query(SolicitudEmergencia)
            .options(
                selectinload(SolicitudEmergencia.asignaciones).selectinload(
                    AsignacionAtencion.resultados
                ),
                selectinload(SolicitudEmergencia.cliente),
            )
            .filter(
                and_(
                    SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                    SolicitudEmergencia.fecha_creacion <= fecha_fin,
                )
            )
            .all()
        )

        talleres_catalogo = {
            str(t.id_taller): t.nombre_taller
            for t in db.query(Taller.id_taller, Taller.nombre_taller).all()
        }

        opciones_filtros = EstadisticasSistemaService._build_filter_options(
            base_solicitudes=base_solicitudes,
            talleres_catalogo=talleres_catalogo,
        )

        solicitudes = EstadisticasSistemaService._aplicar_filtros_solicitudes(
            solicitudes=base_solicitudes,
            nivel_urgencia=filtros["nivel_urgencia"],
            categoria_incidente=filtros["categoria_incidente"],
            estado_solicitud=filtros["estado_solicitud"],
            id_taller=filtros["id_taller"],
        )

        reporte = EstadisticasSistemaService._generar_reporte_filtrado(
            solicitudes=solicitudes,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            agrupar_por=agrupar_por,
            nivel_urgencia=filtros["nivel_urgencia"],
            categoria_incidente=filtros["categoria_incidente"],
            estado_solicitud=filtros["estado_solicitud"],
            id_taller=filtros["id_taller"],
            talleres_catalogo=talleres_catalogo,
        )

        total_emergencias = len(solicitudes)
        solicitudes_atendidas = sum(
            1 for s in solicitudes if s.estado_actual == EstadoSolicitud.ATENDIDA
        )

        total_servicios = sum(
            len([r for a in s.asignaciones for r in a.resultados]) for s in solicitudes
        )

        talleres_activos = len(
            {
                str(a.id_taller)
                for s in solicitudes
                for a in s.asignaciones
            }
        )

        clientes_activos = len({str(s.id_cliente) for s in solicitudes})

        incidentes_count: dict[str, int] = defaultdict(int)
        for solicitud in solicitudes:
            key = (solicitud.categoria_incidente or "SIN_CATEGORIA").upper()
            incidentes_count[key] += 1

        incidentes_frecuentes = []
        for tipo_incidente, cantidad in sorted(
            incidentes_count.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            porcentaje = (cantidad / total_emergencias * 100) if total_emergencias else 0
            incidentes_frecuentes.append(
                IncidenteFrequente(
                    tipo_incidente=tipo_incidente,
                    cantidad=cantidad,
                    porcentaje=round(porcentaje, 2),
                )
            )

        taller_metricas: dict[str, dict[str, int]] = defaultdict(
            lambda: {"solicitudes": 0, "servicios": 0}
        )
        for solicitud in solicitudes:
            for asignacion in solicitud.asignaciones:
                key = str(asignacion.id_taller)
                taller_metricas[key]["solicitudes"] += 1
                taller_metricas[key]["servicios"] += len(asignacion.resultados)

        talleres_top = [
            TallerActividad(
                nombre_taller=talleres_catalogo.get(taller_id, "Taller"),
                solicitudes_atendidas=data["solicitudes"],
                servicios_realizados=data["servicios"],
                calificacion_promedio=None,
            )
            for taller_id, data in sorted(
                taller_metricas.items(), key=lambda item: item[1]["solicitudes"], reverse=True
            )[:5]
        ]

        zonas_count: dict[str, int] = defaultdict(int)
        for solicitud in solicitudes:
            zona = solicitud.cliente.direccion if solicitud.cliente and solicitud.cliente.direccion else "Sin especificar"
            zonas_count[zona] += 1

        zonas_criticas = [
            ZonaEmergencia(
                zona=zona,
                cantidad_emergencias=cantidad,
                talleres_disponibles=0,
            )
            for zona, cantidad in sorted(
                zonas_count.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        tiempos_minutos: list[float] = []
        for solicitud in solicitudes:
            for asignacion in solicitud.asignaciones:
                if solicitud.fecha_creacion and asignacion.fecha_asignacion:
                    inicio = EstadisticasSistemaService._normalize_dt(solicitud.fecha_creacion)
                    asignada = EstadisticasSistemaService._normalize_dt(asignacion.fecha_asignacion)
                    minutos = (asignada - inicio).total_seconds() / 60
                    if minutos >= 0:
                        tiempos_minutos.append(minutos)

        tiempo_respuesta = None
        if tiempos_minutos:
            tiempos_minutos.sort()
            minimo = min(tiempos_minutos)
            maximo = max(tiempos_minutos)
            promedio = sum(tiempos_minutos) / len(tiempos_minutos)
            if len(tiempos_minutos) % 2 == 0:
                mid = len(tiempos_minutos) // 2
                mediana = (tiempos_minutos[mid - 1] + tiempos_minutos[mid]) / 2
            else:
                mediana = tiempos_minutos[len(tiempos_minutos) // 2]

            tiempo_respuesta = TiempoRespuesta(
                minimo=round(minimo, 2),
                maximo=round(maximo, 2),
                promedio=round(promedio, 2),
                mediana=round(mediana, 2),
            )

        solicitudes_completadas = solicitudes_atendidas
        solicitudes_pendientes = sum(
            1 for s in solicitudes if s.estado_actual == EstadoSolicitud.EN_PROCESO
        )
        solicitudes_canceladas = sum(
            1 for s in solicitudes if s.estado_actual == EstadoSolicitud.CANCELADA
        )

        mensaje_vacio = None
        if total_emergencias == 0:
            mensaje_vacio = "No hay datos estadisticos disponibles para el periodo seleccionado"

        return EstadisticasGeneralesResponse(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            total_emergencias=total_emergencias,
            total_solicitudes_atendidas=solicitudes_atendidas,
            total_servicios_realizados=total_servicios,
            talleres_activos=talleres_activos,
            clientes_activos=clientes_activos,
            incidentes_frecuentes=incidentes_frecuentes,
            talleres_top=talleres_top,
            zonas_criticas=zonas_criticas,
            tiempo_respuesta=tiempo_respuesta,
            solicitudes_completadas=solicitudes_completadas,
            solicitudes_pendientes=solicitudes_pendientes,
            solicitudes_canceladas=solicitudes_canceladas,
            reporte=reporte,
            opciones_filtros=opciones_filtros,
            mensaje_vacio=mensaje_vacio,
        )

    @staticmethod
    def _normalize_dt(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value

    @staticmethod
    def _build_filter_options(
        base_solicitudes: list[SolicitudEmergencia],
        talleres_catalogo: dict[str, str],
    ) -> OpcionesFiltrosSistema:
        urgencias = sorted(
            {
                s.nivel_urgencia.value if hasattr(s.nivel_urgencia, "value") else str(s.nivel_urgencia)
                for s in base_solicitudes
                if s.nivel_urgencia
            }
        )
        if not urgencias:
            urgencias = [item.value for item in NivelUrgencia]

        categorias = sorted(
            {
                (s.categoria_incidente or "").upper()
                for s in base_solicitudes
                if s.categoria_incidente
            }
        )

        estados_solicitud = sorted(
            {
                s.estado_actual.value if hasattr(s.estado_actual, "value") else str(s.estado_actual)
                for s in base_solicitudes
                if s.estado_actual
            }
        )

        taller_ids = {
            str(a.id_taller)
            for s in base_solicitudes
            for a in s.asignaciones
            if a.id_taller
        }
        talleres = [
            {"id_taller": tid, "nombre_taller": talleres_catalogo.get(tid, "Taller")}
            for tid in sorted(taller_ids)
        ]

        return OpcionesFiltrosSistema(
            urgencias=urgencias,
            categorias_incidente=categorias,
            estados_solicitud=estados_solicitud,
            talleres=talleres,
        )

    @staticmethod
    def _aplicar_filtros_solicitudes(
        solicitudes: list[SolicitudEmergencia],
        nivel_urgencia: Optional[str],
        categoria_incidente: Optional[str],
        estado_solicitud: Optional[str],
        id_taller: Optional[str],
    ) -> list[SolicitudEmergencia]:
        filtradas = []
        for solicitud in solicitudes:
            urgencia_actual = (
                solicitud.nivel_urgencia.value
                if hasattr(solicitud.nivel_urgencia, "value")
                else str(solicitud.nivel_urgencia)
            )
            categoria_actual = (solicitud.categoria_incidente or "").upper()
            estado_actual = (
                solicitud.estado_actual.value
                if hasattr(solicitud.estado_actual, "value")
                else str(solicitud.estado_actual)
            )

            if nivel_urgencia and urgencia_actual != nivel_urgencia:
                continue
            if categoria_incidente and categoria_actual != categoria_incidente:
                continue
            if estado_solicitud and estado_actual != estado_solicitud:
                continue
            if id_taller and not any(str(a.id_taller) == id_taller for a in solicitud.asignaciones):
                continue

            filtradas.append(solicitud)

        return filtradas

    @staticmethod
    def _generar_reporte_filtrado(
        solicitudes: list[SolicitudEmergencia],
        fecha_inicio: datetime,
        fecha_fin: datetime,
        agrupar_por: str,
        nivel_urgencia: Optional[str],
        categoria_incidente: Optional[str],
        estado_solicitud: Optional[str],
        id_taller: Optional[str],
        talleres_catalogo: dict[str, str],
    ) -> ReporteFiltradoSistema:
        valid_groups = {"dia", "semana", "mes", "categoria", "urgencia", "estado", "taller"}
        group_mode = agrupar_por if agrupar_por in valid_groups else "dia"

        grupos: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "total_solicitudes": 0,
                "solicitudes_atendidas": 0,
                "solicitudes_canceladas": 0,
                "servicios_completados": 0,
            }
        )

        for solicitud in solicitudes:
            grupo = EstadisticasSistemaService._obtener_grupo_sistema(
                solicitud=solicitud,
                agrupar_por=group_mode,
                talleres_catalogo=talleres_catalogo,
            )
            item = grupos[grupo]
            item["total_solicitudes"] += 1
            if solicitud.estado_actual == EstadoSolicitud.ATENDIDA:
                item["solicitudes_atendidas"] += 1
            if solicitud.estado_actual == EstadoSolicitud.CANCELADA:
                item["solicitudes_canceladas"] += 1

            tiene_resuelto = any(
                r.estado_resultado == EstadoResultado.RESUELTO
                for a in solicitud.asignaciones
                for r in a.resultados
            )
            if tiene_resuelto:
                item["servicios_completados"] += 1

        tabla = []
        for grupo, data in sorted(grupos.items(), key=lambda item: item[0]):
            total = data["total_solicitudes"]
            tabla.append(
                ReporteTablaSistemaItem(
                    grupo=grupo,
                    total_solicitudes=total,
                    solicitudes_atendidas=data["solicitudes_atendidas"],
                    solicitudes_canceladas=data["solicitudes_canceladas"],
                    servicios_completados=data["servicios_completados"],
                    tasa_completacion=(
                        round((data["servicios_completados"] / total) * 100, 2)
                        if total > 0
                        else 0
                    ),
                )
            )

        return ReporteFiltradoSistema(
            filtros_aplicados=FiltroReporteSistemaAplicado(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                agrupar_por=group_mode,
                nivel_urgencia=nivel_urgencia,
                categoria_incidente=categoria_incidente,
                estado_solicitud=estado_solicitud,
                id_taller=id_taller,
            ),
            tabla=tabla,
            graficos=ReporteGraficosSistema(
                categorias=[item.grupo for item in tabla],
                serie_total_solicitudes=[item.total_solicitudes for item in tabla],
                serie_solicitudes_atendidas=[item.solicitudes_atendidas for item in tabla],
                serie_solicitudes_canceladas=[item.solicitudes_canceladas for item in tabla],
                serie_servicios_completados=[item.servicios_completados for item in tabla],
            ),
        )

    @staticmethod
    def _obtener_grupo_sistema(
        solicitud: SolicitudEmergencia,
        agrupar_por: str,
        talleres_catalogo: dict[str, str],
    ) -> str:
        fecha = EstadisticasSistemaService._normalize_dt(solicitud.fecha_creacion)

        if agrupar_por == "semana":
            iso_year, iso_week, _ = fecha.isocalendar()
            return f"{iso_year}-W{iso_week:02d}"
        if agrupar_por == "mes":
            return fecha.strftime("%Y-%m")
        if agrupar_por == "categoria":
            return (solicitud.categoria_incidente or "SIN_CATEGORIA").upper()
        if agrupar_por == "urgencia":
            return (
                solicitud.nivel_urgencia.value
                if hasattr(solicitud.nivel_urgencia, "value")
                else str(solicitud.nivel_urgencia)
            )
        if agrupar_por == "estado":
            return (
                solicitud.estado_actual.value
                if hasattr(solicitud.estado_actual, "value")
                else str(solicitud.estado_actual)
            )
        if agrupar_por == "taller":
            if not solicitud.asignaciones:
                return "SIN_TALLER"
            taller_id = str(solicitud.asignaciones[0].id_taller)
            return talleres_catalogo.get(taller_id, taller_id)

        return fecha.strftime("%Y-%m-%d")
