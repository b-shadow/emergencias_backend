from datetime import datetime, timedelta
from sqlalchemy import and_, func, cast, Integer
from sqlalchemy.orm import Session

from app.core.enums import EstadoAsignacion, EstadoResultado
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.resultado_servicio import ResultadoServicio
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller
from app.schemas.estadisticas_taller import (
    EstadisticaDemacruzada,
    EstadisticaGeneralTaller,
    EstadisticaDiagnostico,
    EstadisticaTiempoAtencion,
    EstadisticasTallerResponse,
)


class EstadisticasTallerService:
    """Servicio para calcular estadísticas del taller"""

    @staticmethod
    def obtener_estadisticas_taller(
        db: Session,
        id_taller: str,
        fecha_inicio: datetime | None = None,
        fecha_fin: datetime | None = None,
    ) -> EstadisticasTallerResponse:
        """
        Calcula estadísticas del taller en un rango de fechas.
        Si no se especifican fechas, usa los últimos 30 días.
        """

        # Valores por defecto: últimos 30 días
        if not fecha_fin:
            fecha_fin = datetime.utcnow()
        if not fecha_inicio:
            fecha_inicio = fecha_fin - timedelta(days=30)

        # Validar que el taller existe
        taller = db.query(Taller).filter(Taller.id_taller == id_taller).first()
        if not taller:
            return EstadisticasTallerResponse(
                id_taller=str(id_taller),
                nombre_taller="Desconocido",
                estadisticas=None,
                mensaje_vacio="Taller no encontrado",
            )

        # Obtener todas las asignaciones del taller en el rango de fechas
        asignaciones = db.query(AsignacionAtencion).filter(
            and_(
                AsignacionAtencion.id_taller == id_taller,
                AsignacionAtencion.fecha_asignacion >= fecha_inicio,
                AsignacionAtencion.fecha_asignacion <= fecha_fin,
            )
        ).all()

        if not asignaciones:
            return EstadisticasTallerResponse(
                id_taller=str(id_taller),
                nombre_taller=taller.nombre_taller,
                estadisticas=None,
                mensaje_vacio="No existen datos suficientes para generar estadísticas en el rango seleccionado.",
            )

        # Calcular métricas
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
        )

    @staticmethod
    def _calcular_diagnosticos(
        db: Session, asignaciones: list[AsignacionAtencion]
    ) -> tuple[list[EstadisticaDiagnostico], int]:
        """Calcula los diagnósticos más frecuentes y cuántos requieren seguimiento"""
        asignacion_ids = [a.id_asignacion for a in asignaciones]

        if not asignacion_ids:
            return [], 0

        # Agrupar por diagnóstico en ResultadoServicio
        resultados = (
            db.query(
                ResultadoServicio.diagnostico,
                func.count(ResultadoServicio.id_resultado_servicio).label("cantidad"),
                func.sum(
                    cast(ResultadoServicio.requiere_seguimiento, Integer)
                ).label("con_seguimiento"),
            )
            .filter(ResultadoServicio.id_asignacion.in_(asignacion_ids))
            .group_by(ResultadoServicio.diagnostico)
            .order_by(func.count(ResultadoServicio.id_resultado_servicio).desc())
            .limit(10)  # Top 10
            .all()
        )

        total_resultados = len(asignacion_ids)  # Aproximación: número de asignaciones
        diagnosticos = []
        total_con_seguimiento = 0

        for diagnostico_text, cantidad, seguimiento_count in resultados:
            if diagnostico_text:  # Solo si hay diagnóstico
                seguimiento = int(seguimiento_count) if seguimiento_count else 0
                total_con_seguimiento += seguimiento
                porcentaje = (cantidad / total_resultados * 100) if total_resultados > 0 else 0
                diagnosticos.append(
                    EstadisticaDiagnostico(
                        diagnostico=diagnostico_text[:50],  # Limitar a 50 caracteres para UI
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
        """Calcula los días con mayor demanda"""
        dias_count = {}

        for asignacion in asignaciones:
            dia = asignacion.fecha_asignacion.date()
            dia_str = dia.isoformat()
            dias_count[dia_str] = dias_count.get(dia_str, 0) + 1

        # Ordenar por cantidad descendente y tomar top 10
        dias_ordenados = sorted(dias_count.items(), key=lambda x: x[1], reverse=True)[:10]

        return [
            EstadisticaDemacruzada(periodo=dia, cantidad=cantidad)
            for dia, cantidad in dias_ordenados
        ]

    @staticmethod
    def _calcular_horas_mayor_demanda(
        asignaciones: list[AsignacionAtencion],
    ) -> list[EstadisticaDemacruzada]:
        """Calcula las horas con mayor demanda"""
        horas_count = {}

        for asignacion in asignaciones:
            hora = asignacion.fecha_asignacion.hour
            hora_str = f"{hora:02d}:00"
            horas_count[hora_str] = horas_count.get(hora_str, 0) + 1

        # Ordenar por cantidad descendente y tomar top 10
        horas_ordenadas = sorted(horas_count.items(), key=lambda x: x[1], reverse=True)[:10]

        return [
            EstadisticaDemacruzada(periodo=hora, cantidad=cantidad)
            for hora, cantidad in horas_ordenadas
        ]

    @staticmethod
    def _calcular_tiempo_promedio_atencion(
        asignaciones: list[AsignacionAtencion],
    ) -> EstadisticaTiempoAtencion:
        """Calcula el tiempo promedio de atención"""
        tiempos = []

        for asignacion in asignaciones:
            if asignacion.fecha_inicio_atencion and asignacion.fecha_fin_atencion:
                duracion = asignacion.fecha_fin_atencion - asignacion.fecha_inicio_atencion
                tiempos.append(duracion.total_seconds() / 60)  # Convertir a minutos

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
        """Cuenta las asignaciones que tienen al menos un resultado resuelto"""
        asignacion_ids = [a.id_asignacion for a in asignaciones]

        if not asignacion_ids:
            return 0

        # Contar asignaciones únicas que tienen al menos un resultado RESUELTO
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
