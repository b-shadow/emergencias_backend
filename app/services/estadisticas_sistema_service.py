from datetime import datetime, timedelta
from sqlalchemy import and_, func, desc
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.resultado_servicio import ResultadoServicio
from app.models.taller import Taller
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.core.enums import EstadoSolicitud, EstadoAsignacion

from app.schemas.estadisticas_sistema import (
    EstadisticasGeneralesResponse,
    IncidenteFrequente,
    TallerActividad,
    ZonaEmergencia,
    TiempoRespuesta,
)


class EstadisticasSistemaService:
    """Servicio para calcular estadísticas generales del sistema"""

    @staticmethod
    def obtener_estadisticas_sistema(
        db: Session,
        fecha_inicio: Optional[datetime] = None,
        fecha_fin: Optional[datetime] = None,
    ) -> EstadisticasGeneralesResponse:
        """
        Calcula estadísticas generales del sistema en un rango de fechas.
        Si no se especifican fechas, usa los últimos 30 días.
        """

        # Valores por defecto: últimos 30 días
        if not fecha_fin:
            fecha_fin = datetime.utcnow()
        if not fecha_inicio:
            fecha_inicio = fecha_fin - timedelta(days=30)

        # 1. Obtener total de emergencias en el rango de fechas
        total_emergencias = db.query(func.count(SolicitudEmergencia.id_solicitud)).filter(
            and_(
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
            )
        ).scalar() or 0

        # 2. Obtener solicitudes atendidas
        solicitudes_atendidas = db.query(func.count(SolicitudEmergencia.id_solicitud)).filter(
            and_(
                SolicitudEmergencia.estado_actual == EstadoSolicitud.ATENDIDA,
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
            )
        ).scalar() or 0

        # 3. Obtener total de servicios realizados
        total_servicios = db.query(func.count(ResultadoServicio.id_resultado_servicio)).filter(
            and_(
                ResultadoServicio.fecha_registro >= fecha_inicio,
                ResultadoServicio.fecha_registro <= fecha_fin,
            )
        ).scalar() or 0

        # 4. Obtener talleres activos (que han atendido al menos una solicitud)
        talleres_activos = db.query(func.count(func.distinct(AsignacionAtencion.id_taller))).filter(
            and_(
                AsignacionAtencion.fecha_asignacion >= fecha_inicio,
                AsignacionAtencion.fecha_asignacion <= fecha_fin,
            )
        ).scalar() or 0

        # 5. Obtener clientes activos (que han hecho al menos una solicitud)
        clientes_activos = db.query(func.count(func.distinct(SolicitudEmergencia.id_cliente))).filter(
            and_(
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
            )
        ).scalar() or 0

        # 6. Obtener incidentes más frecuentes (top 5)
        incidentes_query = db.query(
            SolicitudEmergencia.categoria_incidente,
            func.count(SolicitudEmergencia.id_solicitud).label("cantidad")
        ).filter(
            and_(
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
                SolicitudEmergencia.categoria_incidente.isnot(None),
            )
        ).group_by(SolicitudEmergencia.categoria_incidente).order_by(
            desc("cantidad")
        ).limit(5).all()

        # Calcular porcentajes de incidentes
        incidentes_frecuentes = []
        if total_emergencias > 0:
            for tipo_incidente, cantidad in incidentes_query:
                porcentaje = (cantidad / total_emergencias) * 100
                incidentes_frecuentes.append(
                    IncidenteFrequente(
                        tipo_incidente=tipo_incidente or "Sin especificar",
                        cantidad=cantidad,
                        porcentaje=round(porcentaje, 2)
                    )
                )

        # 7. Obtener talleres con mayor actividad (top 5)
        talleres_query = db.query(
            Taller.id_taller,
            Taller.nombre_taller,
            func.count(func.distinct(AsignacionAtencion.id_asignacion)).label("solicitudes_atendidas"),
            func.count(func.distinct(ResultadoServicio.id_resultado_servicio)).label("servicios_realizados")
        ).outerjoin(
            AsignacionAtencion, and_(
                Taller.id_taller == AsignacionAtencion.id_taller,
                AsignacionAtencion.fecha_asignacion >= fecha_inicio,
                AsignacionAtencion.fecha_asignacion <= fecha_fin,
            )
        ).outerjoin(
            ResultadoServicio, and_(
                AsignacionAtencion.id_asignacion == ResultadoServicio.id_asignacion,
                ResultadoServicio.fecha_registro >= fecha_inicio,
                ResultadoServicio.fecha_registro <= fecha_fin,
            )
        ).group_by(
            Taller.id_taller,
            Taller.nombre_taller
        ).order_by(
            desc("solicitudes_atendidas")
        ).limit(5).all()

        talleres_top = [
            TallerActividad(
                nombre_taller=nombre,
                solicitudes_atendidas=solicitudes or 0,
                servicios_realizados=servicios or 0,
                calificacion_promedio=None
            )
            for _, nombre, solicitudes, servicios in talleres_query
        ]

        # 8. Obtener zonas con más emergencias (top 5)
        # Usando dirección del cliente como zona
        zonas_query = db.query(
            Cliente.direccion,
            func.count(SolicitudEmergencia.id_solicitud).label("cantidad_emergencias")
        ).join(
            Cliente, SolicitudEmergencia.id_cliente == Cliente.id_cliente
        ).filter(
            and_(
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
                Cliente.direccion.isnot(None),
            )
        ).group_by(Cliente.direccion).order_by(
            desc("cantidad_emergencias")
        ).limit(5).all()

        zonas_criticas = [
            ZonaEmergencia(
                zona=zona or "Sin especificar",
                cantidad_emergencias=cantidad,
                talleres_disponibles=0  # Puede mejorarse con cálculo geográfico
            )
            for zona, cantidad in zonas_query
        ]

        # 9. Obtener tiempo de respuesta (promedio entre solicitud y asignación)
        # SQLite no soporta func.extract, así que hacemos el cálculo en Python
        tiempos_query = db.query(
            SolicitudEmergencia.fecha_creacion,
            AsignacionAtencion.fecha_asignacion
        ).join(
            SolicitudEmergencia, AsignacionAtencion.id_solicitud == SolicitudEmergencia.id_solicitud
        ).filter(
            and_(
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
                AsignacionAtencion.fecha_asignacion.isnot(None),
            )
        ).all()

        tiempo_respuesta = None
        if tiempos_query:
            tiempos_minutos = []
            for fecha_solicitud, fecha_asignacion in tiempos_query:
                if fecha_solicitud and fecha_asignacion:
                    diferencia = (fecha_asignacion - fecha_solicitud).total_seconds() / 60
                    tiempos_minutos.append(diferencia)
            
            if tiempos_minutos:
                minimo = min(tiempos_minutos)
                maximo = max(tiempos_minutos)
                promedio = sum(tiempos_minutos) / len(tiempos_minutos)
                
                # Calcular mediana
                tiempos_minutos.sort()
                if len(tiempos_minutos) % 2 == 0:
                    mediana = (tiempos_minutos[len(tiempos_minutos) // 2 - 1] + tiempos_minutos[len(tiempos_minutos) // 2]) / 2
                else:
                    mediana = tiempos_minutos[len(tiempos_minutos) // 2]
                
                tiempo_respuesta = TiempoRespuesta(
                    minimo=round(minimo, 2),
                    maximo=round(maximo, 2),
                    promedio=round(promedio, 2),
                    mediana=round(mediana, 2)
                )

        # 10. Obtener estado de solicitudes
        solicitudes_completadas = db.query(func.count(SolicitudEmergencia.id_solicitud)).filter(
            and_(
                SolicitudEmergencia.estado_actual == EstadoSolicitud.ATENDIDA,
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
            )
        ).scalar() or 0

        solicitudes_pendientes = db.query(func.count(SolicitudEmergencia.id_solicitud)).filter(
            and_(
                SolicitudEmergencia.estado_actual == EstadoSolicitud.EN_PROCESO,
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
            )
        ).scalar() or 0

        solicitudes_canceladas = db.query(func.count(SolicitudEmergencia.id_solicitud)).filter(
            and_(
                SolicitudEmergencia.estado_actual == EstadoSolicitud.CANCELADA,
                SolicitudEmergencia.fecha_creacion >= fecha_inicio,
                SolicitudEmergencia.fecha_creacion <= fecha_fin,
            )
        ).scalar() or 0

        # Mensaje si no hay datos
        mensaje_vacio = None
        if total_emergencias == 0:
            mensaje_vacio = "No hay datos estadísticos disponibles para el período seleccionado"

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
            mensaje_vacio=mensaje_vacio,
        )
