from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import Integer, and_, cast, func
from sqlalchemy.orm import Session

from app.core.enums import EstadoAsignacion, EstadoResultado, EstadoSolicitud
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.resultado_servicio import ResultadoServicio
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller
from app.schemas.estadisticas_taller import (
    EstadisticaDemacruzada,
    EstadisticaDiagnostico,
    EstadisticaGeneralTaller,
    EstadisticaTiempoAtencion,
    EstadisticasTallerResponse,
    FiltroReporteAplicado,
    ReporteFiltradoTaller,
    ReporteGraficos,
    ReporteTablaItem,
)


class EstadisticasTallerService:
    """Servicio para calcular estadisticas del taller."""

    @staticmethod
    def obtener_estadisticas_taller(
        db: Session,
        id_taller: str,
        fecha_inicio: datetime | None = None,
        fecha_fin: datetime | None = None,
        agrupar_por: str = "dia",
        nivel_urgencia: str | None = None,
        categoria_incidente: str | None = None,
        estado_solicitud: str | None = None,
        estado_asignacion: str | None = None,
        estado_resultado: str | None = None,
    ) -> EstadisticasTallerResponse:
        if not fecha_fin:
            fecha_fin = datetime.utcnow()
        if not fecha_inicio:
            fecha_inicio = fecha_fin - timedelta(days=30)

        taller = db.query(Taller).filter(Taller.id_taller == id_taller).first()
        if not taller:
            return EstadisticasTallerResponse(
                id_taller=str(id_taller),
                nombre_taller="Desconocido",
                estadisticas=None,
                reporte=None,
                mensaje_vacio="Taller no encontrado",
            )

        asignaciones = (
            db.query(AsignacionAtencion)
            .filter(
                and_(
                    AsignacionAtencion.id_taller == id_taller,
                    AsignacionAtencion.fecha_asignacion >= fecha_inicio,
                    AsignacionAtencion.fecha_asignacion <= fecha_fin,
                )
            )
            .all()
        )

        filtros = {
            "nivel_urgencia": nivel_urgencia.strip().upper() if nivel_urgencia else None,
            "categoria_incidente": (
                categoria_incidente.strip().upper() if categoria_incidente else None
            ),
            "estado_solicitud": estado_solicitud.strip().upper() if estado_solicitud else None,
            "estado_asignacion": (
                estado_asignacion.strip().upper() if estado_asignacion else None
            ),
            "estado_resultado": estado_resultado.strip().upper() if estado_resultado else None,
        }

        asignaciones = EstadisticasTallerService._aplicar_filtros_asignaciones(
            db=db,
            asignaciones=asignaciones,
            nivel_urgencia=filtros["nivel_urgencia"],
            categoria_incidente=filtros["categoria_incidente"],
            estado_solicitud=filtros["estado_solicitud"],
            estado_asignacion=filtros["estado_asignacion"],
            estado_resultado=filtros["estado_resultado"],
        )

        reporte = EstadisticasTallerService._generar_reporte_filtrado(
            db=db,
            asignaciones=asignaciones,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            agrupar_por=agrupar_por,
            nivel_urgencia=filtros["nivel_urgencia"],
            categoria_incidente=filtros["categoria_incidente"],
            estado_solicitud=filtros["estado_solicitud"],
            estado_asignacion=filtros["estado_asignacion"],
            estado_resultado=filtros["estado_resultado"],
        )

        if not asignaciones:
            return EstadisticasTallerResponse(
                id_taller=str(id_taller),
                nombre_taller=taller.nombre_taller,
                estadisticas=None,
                reporte=reporte,
                mensaje_vacio="No existen datos suficientes para generar estadisticas en el rango seleccionado.",
            )

        diagnosticos, total_diag_seguimiento = EstadisticasTallerService._calcular_diagnosticos(
            db, asignaciones
        )
        dias_mayor_demanda = EstadisticasTallerService._calcular_dias_mayor_demanda(
            asignaciones
        )
        horas_mayor_demanda = EstadisticasTallerService._calcular_horas_mayor_demanda(
            asignaciones
        )
        tiempo_promedio = EstadisticasTallerService._calcular_tiempo_promedio_atencion(
            asignaciones
        )
        total_atendidas = len(asignaciones)
        total_canceladas = sum(
            1 for a in asignaciones if a.estado_asignacion == EstadoAsignacion.CANCELADA
        )
        servicios_completados = EstadisticasTallerService._contar_asignaciones_completadas(
            db, asignaciones
        )

        estadisticas = EstadisticaGeneralTaller(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            total_solicitudes_atendidas=total_atendidas,
            total_solicitudes_canceladas=total_canceladas,
            total_servicios_completados=servicios_completados,
            tasa_completacion=(
                (servicios_completados / total_atendidas * 100)
                if total_atendidas > 0
                else 0
            ),
            diagnosticos=diagnosticos,
            total_diagnosticos_con_seguimiento=total_diag_seguimiento,
            dias_mayor_demanda=dias_mayor_demanda,
            horas_mayor_demanda=horas_mayor_demanda,
            tiempo_promedio_atencion=tiempo_promedio,
        )

        return EstadisticasTallerResponse(
            id_taller=str(id_taller),
            nombre_taller=taller.nombre_taller,
            estadisticas=estadisticas,
            reporte=reporte,
        )

    @staticmethod
    def _aplicar_filtros_asignaciones(
        db: Session,
        asignaciones: list[AsignacionAtencion],
        nivel_urgencia: str | None,
        categoria_incidente: str | None,
        estado_solicitud: str | None,
        estado_asignacion: str | None,
        estado_resultado: str | None,
    ) -> list[AsignacionAtencion]:
        if not asignaciones:
            return []

        solicitud_ids = [a.id_solicitud for a in asignaciones]
        solicitud_map = {
            s.id_solicitud: s
            for s in db.query(SolicitudEmergencia)
            .filter(SolicitudEmergencia.id_solicitud.in_(solicitud_ids))
            .all()
        }

        resultados = (
            db.query(ResultadoServicio.id_asignacion, ResultadoServicio.estado_resultado)
            .filter(
                ResultadoServicio.id_asignacion.in_(
                    [a.id_asignacion for a in asignaciones]
                )
            )
            .all()
        )
        estados_resultado_por_asignacion: dict = defaultdict(set)
        for id_asignacion, estado in resultados:
            estados_resultado_por_asignacion[id_asignacion].add(
                estado.value if hasattr(estado, "value") else str(estado)
            )

        filtradas: list[AsignacionAtencion] = []
        for asignacion in asignaciones:
            solicitud = solicitud_map.get(asignacion.id_solicitud)
            if not solicitud:
                continue

            urgencia_actual = (
                solicitud.nivel_urgencia.value
                if hasattr(solicitud.nivel_urgencia, "value")
                else str(solicitud.nivel_urgencia)
            )
            categoria_actual = (solicitud.categoria_incidente or "").upper()
            estado_solicitud_actual = (
                solicitud.estado_actual.value
                if hasattr(solicitud.estado_actual, "value")
                else str(solicitud.estado_actual)
            )
            estado_asignacion_actual = (
                asignacion.estado_asignacion.value
                if hasattr(asignacion.estado_asignacion, "value")
                else str(asignacion.estado_asignacion)
            )
            estados_resultado_actual = estados_resultado_por_asignacion.get(
                asignacion.id_asignacion, set()
            )

            if nivel_urgencia and urgencia_actual != nivel_urgencia:
                continue
            if categoria_incidente and categoria_actual != categoria_incidente:
                continue
            if estado_solicitud and estado_solicitud_actual != estado_solicitud:
                continue
            if estado_asignacion and estado_asignacion_actual != estado_asignacion:
                continue
            if estado_resultado and estado_resultado not in estados_resultado_actual:
                continue

            filtradas.append(asignacion)

        return filtradas

    @staticmethod
    def _generar_reporte_filtrado(
        db: Session,
        asignaciones: list[AsignacionAtencion],
        fecha_inicio: datetime,
        fecha_fin: datetime,
        agrupar_por: str,
        nivel_urgencia: str | None,
        categoria_incidente: str | None,
        estado_solicitud: str | None,
        estado_asignacion: str | None,
        estado_resultado: str | None,
    ) -> ReporteFiltradoTaller:
        valid_groups = {
            "dia",
            "semana",
            "mes",
            "categoria",
            "urgencia",
            "estado_solicitud",
            "estado_asignacion",
            "estado_resultado",
        }
        group_mode = agrupar_por if agrupar_por in valid_groups else "dia"

        if not asignaciones:
            return ReporteFiltradoTaller(
                filtros_aplicados=FiltroReporteAplicado(
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    agrupar_por=group_mode,
                    nivel_urgencia=nivel_urgencia,
                    categoria_incidente=categoria_incidente,
                    estado_solicitud=estado_solicitud,
                    estado_asignacion=estado_asignacion,
                    estado_resultado=estado_resultado,
                ),
                tabla=[],
                graficos=ReporteGraficos(
                    categorias=[],
                    serie_total_solicitudes=[],
                    serie_solicitudes_atendidas=[],
                    serie_solicitudes_canceladas=[],
                    serie_servicios_completados=[],
                ),
            )

        solicitud_ids = [a.id_solicitud for a in asignaciones]
        solicitud_map = {
            s.id_solicitud: s
            for s in db.query(SolicitudEmergencia)
            .filter(SolicitudEmergencia.id_solicitud.in_(solicitud_ids))
            .all()
        }

        resultados = (
            db.query(ResultadoServicio.id_asignacion, ResultadoServicio.estado_resultado)
            .filter(
                ResultadoServicio.id_asignacion.in_(
                    [a.id_asignacion for a in asignaciones]
                )
            )
            .all()
        )
        estados_resultado_por_asignacion: dict = defaultdict(set)
        for id_asignacion, estado in resultados:
            estados_resultado_por_asignacion[id_asignacion].add(
                estado.value if hasattr(estado, "value") else str(estado)
            )

        grupos: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "total_solicitudes": 0,
                "solicitudes_atendidas": 0,
                "solicitudes_canceladas": 0,
                "servicios_completados": 0,
            }
        )

        for asignacion in asignaciones:
            solicitud = solicitud_map.get(asignacion.id_solicitud)
            if not solicitud:
                continue

            estados_resultado = estados_resultado_por_asignacion.get(
                asignacion.id_asignacion, set()
            )
            grupo = EstadisticasTallerService._obtener_grupo(
                asignacion=asignacion,
                solicitud=solicitud,
                estados_resultado=estados_resultado,
                agrupar_por=group_mode,
            )

            item = grupos[grupo]
            item["total_solicitudes"] += 1
            if solicitud.estado_actual == EstadoSolicitud.ATENDIDA:
                item["solicitudes_atendidas"] += 1
            if solicitud.estado_actual == EstadoSolicitud.CANCELADA:
                item["solicitudes_canceladas"] += 1
            if EstadoResultado.RESUELTO.value in estados_resultado:
                item["servicios_completados"] += 1

        tabla: list[ReporteTablaItem] = []
        for grupo, data in sorted(grupos.items(), key=lambda item: item[0]):
            total = data["total_solicitudes"]
            tabla.append(
                ReporteTablaItem(
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

        return ReporteFiltradoTaller(
            filtros_aplicados=FiltroReporteAplicado(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                agrupar_por=group_mode,
                nivel_urgencia=nivel_urgencia,
                categoria_incidente=categoria_incidente,
                estado_solicitud=estado_solicitud,
                estado_asignacion=estado_asignacion,
                estado_resultado=estado_resultado,
            ),
            tabla=tabla,
            graficos=ReporteGraficos(
                categorias=[item.grupo for item in tabla],
                serie_total_solicitudes=[item.total_solicitudes for item in tabla],
                serie_solicitudes_atendidas=[item.solicitudes_atendidas for item in tabla],
                serie_solicitudes_canceladas=[item.solicitudes_canceladas for item in tabla],
                serie_servicios_completados=[item.servicios_completados for item in tabla],
            ),
        )

    @staticmethod
    def _obtener_grupo(
        asignacion: AsignacionAtencion,
        solicitud: SolicitudEmergencia,
        estados_resultado: set[str],
        agrupar_por: str,
    ) -> str:
        fecha = asignacion.fecha_asignacion

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
        if agrupar_por == "estado_solicitud":
            return (
                solicitud.estado_actual.value
                if hasattr(solicitud.estado_actual, "value")
                else str(solicitud.estado_actual)
            )
        if agrupar_por == "estado_asignacion":
            return (
                asignacion.estado_asignacion.value
                if hasattr(asignacion.estado_asignacion, "value")
                else str(asignacion.estado_asignacion)
            )
        if agrupar_por == "estado_resultado":
            if not estados_resultado:
                return "SIN_RESULTADO"
            if EstadoResultado.RESUELTO.value in estados_resultado:
                return EstadoResultado.RESUELTO.value
            if EstadoResultado.PARCIAL.value in estados_resultado:
                return EstadoResultado.PARCIAL.value
            return EstadoResultado.PENDIENTE.value

        return fecha.strftime("%Y-%m-%d")

    @staticmethod
    def _calcular_diagnosticos(
        db: Session, asignaciones: list[AsignacionAtencion]
    ) -> tuple[list[EstadisticaDiagnostico], int]:
        asignacion_ids = [a.id_asignacion for a in asignaciones]

        if not asignacion_ids:
            return [], 0

        resultados = (
            db.query(
                ResultadoServicio.diagnostico,
                func.count(ResultadoServicio.id_resultado_servicio).label("cantidad"),
                func.sum(cast(ResultadoServicio.requiere_seguimiento, Integer)).label(
                    "con_seguimiento"
                ),
            )
            .filter(ResultadoServicio.id_asignacion.in_(asignacion_ids))
            .group_by(ResultadoServicio.diagnostico)
            .order_by(func.count(ResultadoServicio.id_resultado_servicio).desc())
            .limit(10)
            .all()
        )

        total_resultados = len(asignacion_ids)
        diagnosticos = []
        total_con_seguimiento = 0

        for diagnostico_text, cantidad, seguimiento_count in resultados:
            if diagnostico_text:
                seguimiento = int(seguimiento_count) if seguimiento_count else 0
                total_con_seguimiento += seguimiento
                porcentaje = (
                    (cantidad / total_resultados * 100) if total_resultados > 0 else 0
                )
                diagnosticos.append(
                    EstadisticaDiagnostico(
                        diagnostico=diagnostico_text[:50],
                        cantidad=cantidad,
                        porcentaje=round(porcentaje, 2),
                        requiere_seguimiento=seguimiento,
                    )
                )

        return diagnosticos, total_con_seguimiento

    @staticmethod
    def _calcular_dias_mayor_demanda(
        asignaciones: list[AsignacionAtencion],
    ) -> list[EstadisticaDemacruzada]:
        dias_count = {}

        for asignacion in asignaciones:
            dia = asignacion.fecha_asignacion.date()
            dia_str = dia.isoformat()
            dias_count[dia_str] = dias_count.get(dia_str, 0) + 1

        dias_ordenados = sorted(dias_count.items(), key=lambda x: x[1], reverse=True)[:10]

        return [
            EstadisticaDemacruzada(periodo=dia, cantidad=cantidad)
            for dia, cantidad in dias_ordenados
        ]

    @staticmethod
    def _calcular_horas_mayor_demanda(
        asignaciones: list[AsignacionAtencion],
    ) -> list[EstadisticaDemacruzada]:
        horas_count = {}

        for asignacion in asignaciones:
            hora = asignacion.fecha_asignacion.hour
            hora_str = f"{hora:02d}:00"
            horas_count[hora_str] = horas_count.get(hora_str, 0) + 1

        horas_ordenadas = sorted(horas_count.items(), key=lambda x: x[1], reverse=True)[:10]

        return [
            EstadisticaDemacruzada(periodo=hora, cantidad=cantidad)
            for hora, cantidad in horas_ordenadas
        ]

    @staticmethod
    def _calcular_tiempo_promedio_atencion(
        asignaciones: list[AsignacionAtencion],
    ) -> EstadisticaTiempoAtencion:
        tiempos = []

        for asignacion in asignaciones:
            if asignacion.fecha_inicio_atencion and asignacion.fecha_fin_atencion:
                duracion = asignacion.fecha_fin_atencion - asignacion.fecha_inicio_atencion
                tiempos.append(duracion.total_seconds() / 60)

        if not tiempos:
            return EstadisticaTiempoAtencion(
                tiempo_promedio_minutos=0,
                tiempo_minimo_minutos=0,
                tiempo_maximo_minutos=0,
            )

        return EstadisticaTiempoAtencion(
            tiempo_promedio_minutos=round(sum(tiempos) / len(tiempos), 2),
            tiempo_minimo_minutos=round(min(tiempos), 2),
            tiempo_maximo_minutos=round(max(tiempos), 2),
        )

    @staticmethod
    def _contar_asignaciones_completadas(
        db: Session, asignaciones: list[AsignacionAtencion]
    ) -> int:
        asignacion_ids = [a.id_asignacion for a in asignaciones]

        if not asignacion_ids:
            return 0

        completadas = (
            db.query(func.count(func.distinct(ResultadoServicio.id_asignacion)))
            .filter(
                and_(
                    ResultadoServicio.id_asignacion.in_(asignacion_ids),
                    ResultadoServicio.estado_resultado == EstadoResultado.RESUELTO,
                )
            )
            .scalar()
        )

        return completadas or 0
