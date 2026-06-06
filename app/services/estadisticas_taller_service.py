from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import Integer, and_, cast, func
from sqlalchemy.orm import Session

from app.core.enums import EstadoAsignacion, EstadoResultado, EstadoSolicitud, NivelUrgencia
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.calificacion_atencion import CalificacionAtencion
from app.models.resultado_servicio import ResultadoServicio
from app.models.pago_atencion import PagoAtencion
from app.models.servicio import Servicio
from app.models.postulacion_taller import PostulacionTaller
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller
from app.models.taller_servicio import TallerServicio
from app.schemas.estadisticas_taller import (
    EstadisticaDemacruzada,
    EstadisticaDiagnostico,
    EstadisticaGeneralTaller,
    EstadisticaTiempoAtencion,
    EstadisticasTallerResponse,
    FiltroReporteAplicado,
    KPICancelacionTipo,
    KPIEficienciaServicio,
    KPIIncidenteTipo,
    KPIFrecuente,
    OpcionesFiltrosTaller,
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
                opciones_filtros=OpcionesFiltrosTaller(
                    urgencias=[item.value for item in NivelUrgencia],
                    categorias_incidente=[],
                    estados_solicitud=[item.value for item in EstadoSolicitud],
                    estados_asignacion=[item.value for item in EstadoAsignacion],
                    estados_resultado=[item.value for item in EstadoResultado],
                ),
                mensaje_vacio="Taller no encontrado",
            )

        base_asignaciones = (
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

        base_postulaciones = (
            db.query(PostulacionTaller)
            .filter(
                and_(
                    PostulacionTaller.id_taller == id_taller,
                    PostulacionTaller.fecha_postulacion >= fecha_inicio,
                    PostulacionTaller.fecha_postulacion <= fecha_fin,
                )
            )
            .all()
        )

        opciones_filtros = EstadisticasTallerService._build_filter_options(
            db=db,
            asignaciones=base_asignaciones,
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
            asignaciones=base_asignaciones,
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
                opciones_filtros=opciones_filtros,
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
        tiempo_promedio_asignacion = EstadisticasTallerService._calcular_tiempo_promedio_asignacion(
            asignaciones
        )
        tiempo_promedio_llegada = EstadisticasTallerService._calcular_tiempo_promedio_llegada(
            asignaciones
        )
        calificacion_promedio = EstadisticasTallerService._calcular_calificacion_promedio(db, asignaciones)
        pagos_confirmados, monto_total_pagado, monto_promedio_pago = EstadisticasTallerService._calcular_pagos(
            db, asignaciones
        )
        solicitudes_recibidas = len({p.id_solicitud for p in base_postulaciones})
        solicitudes_aceptadas = len({a.id_solicitud for a in asignaciones})
        tasa_aceptacion = round((solicitudes_aceptadas / solicitudes_recibidas) * 100, 2) if solicitudes_recibidas else 0
        cumplimiento_eta_pct = EstadisticasTallerService._calcular_cumplimiento_eta(db, asignaciones)
        servicios_mas_realizados = EstadisticasTallerService._calcular_servicios_mas_realizados(db, asignaciones)
        incidentes_por_tipo = EstadisticasTallerService._calcular_incidentes_por_tipo(
            db, asignaciones
        )
        zona_mas_incidentes = EstadisticasTallerService._calcular_zona_mas_incidentes(
            db, asignaciones
        )
        cancelaciones_por_tipo = EstadisticasTallerService._calcular_cancelaciones_por_tipo(
            asignaciones
        )
        eficiencia_por_servicio = EstadisticasTallerService._calcular_eficiencia_por_servicio(
            db, asignaciones
        )

        estadisticas = EstadisticaGeneralTaller(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            total_solicitudes_atendidas=total_atendidas,
            total_solicitudes_canceladas=total_canceladas,
            solicitudes_recibidas=solicitudes_recibidas,
            solicitudes_aceptadas=solicitudes_aceptadas,
            tasa_aceptacion=tasa_aceptacion,
            total_servicios_completados=servicios_completados,
            tasa_completacion=(
                (servicios_completados / total_atendidas * 100)
                if total_atendidas > 0
                else 0
            ),
            calificacion_promedio=calificacion_promedio,
            total_pagos_confirmados=pagos_confirmados["cantidad"],
            monto_total_pagado=pagos_confirmados["monto_total"],
            monto_promedio_pago=monto_promedio_pago,
            cumplimiento_eta_pct=cumplimiento_eta_pct,
            diagnosticos=diagnosticos,
            total_diagnosticos_con_seguimiento=total_diag_seguimiento,
            dias_mayor_demanda=dias_mayor_demanda,
            horas_mayor_demanda=horas_mayor_demanda,
            tiempo_promedio_atencion=tiempo_promedio,
            tiempo_promedio_asignacion_minutos=tiempo_promedio_asignacion,
            tiempo_promedio_llegada_minutos=tiempo_promedio_llegada,
            incidentes_por_tipo=incidentes_por_tipo,
            zona_mas_incidentes=zona_mas_incidentes,
            cancelaciones_por_tipo=cancelaciones_por_tipo,
            eficiencia_por_servicio=eficiencia_por_servicio,
            servicios_mas_realizados=servicios_mas_realizados,
        )

        return EstadisticasTallerResponse(
            id_taller=str(id_taller),
            nombre_taller=taller.nombre_taller,
            estadisticas=estadisticas,
            reporte=reporte,
            opciones_filtros=opciones_filtros,
        )

    @staticmethod
    def _build_filter_options(
        db: Session,
        asignaciones: list[AsignacionAtencion],
    ) -> OpcionesFiltrosTaller:
        if not asignaciones:
            return OpcionesFiltrosTaller(
                urgencias=[item.value for item in NivelUrgencia],
                categorias_incidente=[],
                estados_solicitud=[item.value for item in EstadoSolicitud],
                estados_asignacion=[item.value for item in EstadoAsignacion],
                estados_resultado=[item.value for item in EstadoResultado],
            )

        solicitud_ids = [a.id_solicitud for a in asignaciones]
        solicitud_map = {
            s.id_solicitud: s
            for s in db.query(SolicitudEmergencia)
            .filter(SolicitudEmergencia.id_solicitud.in_(solicitud_ids))
            .all()
        }

        urgencias = sorted(
            {
                solicitud.nivel_urgencia.value
                if hasattr(solicitud.nivel_urgencia, "value")
                else str(solicitud.nivel_urgencia)
                for solicitud in solicitud_map.values()
                if solicitud.nivel_urgencia
            }
        )
        if not urgencias:
            urgencias = [item.value for item in NivelUrgencia]

        categorias = sorted(
            {
                (solicitud.categoria_incidente or "").upper()
                for solicitud in solicitud_map.values()
                if solicitud.categoria_incidente
            }
        )

        estados_solicitud = sorted(
            {
                solicitud.estado_actual.value
                if hasattr(solicitud.estado_actual, "value")
                else str(solicitud.estado_actual)
                for solicitud in solicitud_map.values()
                if solicitud.estado_actual
            }
        )

        estados_asignacion = sorted(
            {
                asignacion.estado_asignacion.value
                if hasattr(asignacion.estado_asignacion, "value")
                else str(asignacion.estado_asignacion)
                for asignacion in asignaciones
                if asignacion.estado_asignacion
            }
        )

        resultados = (
            db.query(ResultadoServicio.estado_resultado)
            .filter(ResultadoServicio.id_asignacion.in_([a.id_asignacion for a in asignaciones]))
            .all()
        )
        estados_resultado = sorted(
            {
                estado.value if hasattr(estado, "value") else str(estado)
                for (estado,) in resultados
                if estado
            }
        )

        return OpcionesFiltrosTaller(
            urgencias=urgencias,
            categorias_incidente=categorias,
            estados_solicitud=estados_solicitud,
            estados_asignacion=estados_asignacion,
            estados_resultado=estados_resultado,
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
                ResultadoServicio.id_asignacion.in_([a.id_asignacion for a in asignaciones])
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
                ResultadoServicio.id_asignacion.in_([a.id_asignacion for a in asignaciones])
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

    @staticmethod
    def _calcular_tiempo_promedio_asignacion(asignaciones: list[AsignacionAtencion]) -> float:
        tiempos = []
        for asignacion in asignaciones:
            if asignacion.solicitud and asignacion.solicitud.fecha_creacion and asignacion.fecha_asignacion:
                delta = asignacion.fecha_asignacion - asignacion.solicitud.fecha_creacion
                tiempos.append(max(delta.total_seconds() / 60, 0))
        if not tiempos:
            return 0
        return round(sum(tiempos) / len(tiempos), 2)

    @staticmethod
    def _calcular_tiempo_promedio_llegada(asignaciones: list[AsignacionAtencion]) -> float:
        tiempos = []
        for asignacion in asignaciones:
            if asignacion.fecha_inicio_atencion and asignacion.fecha_asignacion:
                delta = asignacion.fecha_inicio_atencion - asignacion.fecha_asignacion
                tiempos.append(max(delta.total_seconds() / 60, 0))
        if not tiempos:
            return 0
        return round(sum(tiempos) / len(tiempos), 2)

    @staticmethod
    def _calcular_calificacion_promedio(
        db: Session, asignaciones: list[AsignacionAtencion]
    ) -> float | None:
        if not asignaciones:
            return None
        solicitud_ids = [a.id_solicitud for a in asignaciones]
        try:
            promedio = (
                db.query(func.avg(CalificacionAtencion.estrellas))
                .filter(CalificacionAtencion.id_solicitud.in_(solicitud_ids))
                .scalar()
            )
        except Exception:
            db.rollback()
            return None
        return round(float(promedio), 2) if promedio is not None else None

    @staticmethod
    def _calcular_pagos(
        db: Session, asignaciones: list[AsignacionAtencion]
    ) -> tuple[dict, float, float]:
        if not asignaciones:
            return {"cantidad": 0, "monto_total": 0}, 0, 0
        solicitud_ids = [a.id_solicitud for a in asignaciones]
        try:
            pagos = (
                db.query(PagoAtencion)
                .filter(PagoAtencion.id_solicitud.in_(solicitud_ids))
                .all()
            )
        except Exception:
            db.rollback()
            return {"cantidad": 0, "monto_total": 0}, 0, 0
        confirmados = [p for p in pagos if str(p.estado_pago).upper() == "CONFIRMADO"]
        monto_total = round(sum(float(p.monto) for p in confirmados), 2) if confirmados else 0
        monto_promedio = round(monto_total / len(confirmados), 2) if confirmados else 0
        return {"cantidad": len(confirmados), "monto_total": monto_total}, monto_total, monto_promedio

    @staticmethod
    def _calcular_cumplimiento_eta(
        db: Session,
        asignaciones: list[AsignacionAtencion],
    ) -> float:
        if not asignaciones:
            return 0
        try:
            postulaciones = (
                db.query(PostulacionTaller.id_postulacion, PostulacionTaller.tiempo_estimado_llegada_min)
                .filter(PostulacionTaller.id_postulacion.in_([a.id_postulacion for a in asignaciones]))
                .all()
            )
        except Exception:
            db.rollback()
            return 0
        eta_map = {str(pid): eta for pid, eta in postulaciones}
        cumplidas = 0
        total = 0
        for asignacion in asignaciones:
            eta = eta_map.get(str(asignacion.id_postulacion))
            if not eta or not asignacion.fecha_asignacion or not asignacion.fecha_inicio_atencion:
                continue
            total += 1
            minutos = max((asignacion.fecha_inicio_atencion - asignacion.fecha_asignacion).total_seconds() / 60, 0)
            if minutos <= float(eta):
                cumplidas += 1
        return round((cumplidas / total) * 100, 2) if total else 0

    @staticmethod
    def _calcular_servicios_mas_realizados(
        db: Session,
        asignaciones: list[AsignacionAtencion],
    ) -> list[KPIFrecuente]:
        if not asignaciones:
            return []
        asignacion_ids = [a.id_asignacion for a in asignaciones]
        try:
            rows = (
                db.query(Servicio.nombre_servicio, func.count(ResultadoServicio.id_resultado_servicio))
                .select_from(ResultadoServicio)
                .join(TallerServicio, TallerServicio.id_taller_servicio == ResultadoServicio.id_taller_servicio)
                .join(Servicio, Servicio.id_servicio == TallerServicio.id_servicio)
                .filter(ResultadoServicio.id_asignacion.in_(asignacion_ids))
                .group_by(Servicio.nombre_servicio)
                .order_by(func.count(ResultadoServicio.id_resultado_servicio).desc())
                .limit(10)
                .all()
            )
        except Exception:
            db.rollback()
            return []
        total = len(asignacion_ids)
        return [
            KPIFrecuente(
                nombre=nombre or "SIN_NOMBRE",
                cantidad=cantidad,
                porcentaje=round((cantidad / total) * 100, 2) if total else 0,
            )
            for nombre, cantidad in rows
        ]

    @staticmethod
    def _calcular_incidentes_por_tipo(
        db: Session,
        asignaciones: list[AsignacionAtencion],
    ) -> list[KPIIncidenteTipo]:
        if not asignaciones:
            return []
        solicitud_ids = [a.id_solicitud for a in asignaciones]
        rows = (
            db.query(
                SolicitudEmergencia.categoria_incidente,
                func.count(SolicitudEmergencia.id_solicitud).label("cantidad"),
            )
            .filter(SolicitudEmergencia.id_solicitud.in_(solicitud_ids))
            .group_by(SolicitudEmergencia.categoria_incidente)
            .order_by(func.count(SolicitudEmergencia.id_solicitud).desc())
            .all()
        )
        return [
            KPIIncidenteTipo(tipo=(categoria or "SIN_CATEGORIA"), cantidad=cantidad)
            for categoria, cantidad in rows
        ]

    @staticmethod
    def _calcular_zona_mas_incidentes(
        db: Session,
        asignaciones: list[AsignacionAtencion],
    ) -> str | None:
        if not asignaciones:
            return None
        solicitud_ids = [a.id_solicitud for a in asignaciones]
        solicitudes = (
            db.query(SolicitudEmergencia.direccion_referencial)
            .filter(SolicitudEmergencia.id_solicitud.in_(solicitud_ids))
            .all()
        )
        zonas: dict[str, int] = defaultdict(int)
        for (direccion,) in solicitudes:
            if not direccion:
                continue
            zona = " ".join(direccion.strip().upper().split()[:3])
            if zona:
                zonas[zona] += 1
        if not zonas:
            return None
        return sorted(zonas.items(), key=lambda x: x[1], reverse=True)[0][0]

    @staticmethod
    def _calcular_cancelaciones_por_tipo(
        asignaciones: list[AsignacionAtencion],
    ) -> list[KPICancelacionTipo]:
        conteo: dict[str, int] = defaultdict(int)
        for asignacion in asignaciones:
            if asignacion.estado_asignacion == EstadoAsignacion.CANCELADA:
                motivo = (asignacion.motivo_cancelacion or "SIN_MOTIVO").upper()
                conteo[motivo] += 1
        return [
            KPICancelacionTipo(motivo=motivo, cantidad=cantidad)
            for motivo, cantidad in sorted(conteo.items(), key=lambda x: x[1], reverse=True)
        ]

    @staticmethod
    def _calcular_eficiencia_por_servicio(
        db: Session,
        asignaciones: list[AsignacionAtencion],
    ) -> list[KPIEficienciaServicio]:
        if not asignaciones:
            return []
        asignacion_ids = [a.id_asignacion for a in asignaciones]
        resultados = (
            db.query(
                ResultadoServicio.id_taller_servicio,
                ResultadoServicio.estado_resultado,
            )
            .filter(ResultadoServicio.id_asignacion.in_(asignacion_ids))
            .all()
        )
        if not resultados:
            return []

        by_service: dict = defaultdict(lambda: {"total": 0, "completados": 0})
        for id_taller_servicio, estado in resultados:
            if not id_taller_servicio:
                continue
            by_service[id_taller_servicio]["total"] += 1
            estado_str = estado.value if hasattr(estado, "value") else str(estado)
            if estado_str == EstadoResultado.RESUELTO.value:
                by_service[id_taller_servicio]["completados"] += 1

        servicios = (
            db.query(TallerServicio, Servicio)
            .join(Servicio, Servicio.id_servicio == TallerServicio.id_servicio)
            .filter(TallerServicio.id_taller_servicio.in_(list(by_service.keys())))
            .all()
        )
        respuesta: list[KPIEficienciaServicio] = []
        for taller_servicio, servicio in servicios:
            data = by_service.get(taller_servicio.id_taller_servicio)
            if not data or data["total"] == 0:
                continue
            tasa = round((data["completados"] / data["total"]) * 100, 2)
            respuesta.append(
                KPIEficienciaServicio(
                    servicio=servicio.nombre_servicio,
                    categoria_tarifa=taller_servicio.categoria_tarifa.value
                    if hasattr(taller_servicio.categoria_tarifa, "value")
                    else str(taller_servicio.categoria_tarifa),
                    total=data["total"],
                    completados=data["completados"],
                    tasa_completacion=tasa,
                )
            )
        return sorted(respuesta, key=lambda x: x.tasa_completacion, reverse=True)
