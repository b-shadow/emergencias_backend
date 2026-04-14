from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.taller import Taller
from app.models.vehiculo import Vehiculo
from app.models.especialidad import Especialidad
from app.models.taller_especialidad import TallerEspecialidad
from app.models.servicio import Servicio
from app.models.taller_servicio import TallerServicio
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.evidencia import Evidencia
from app.models.clasificacion_incidente import ClasificacionIncidente
from app.models.postulacion_taller import PostulacionTaller
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.historial_estado_solicitud import HistorialEstadoSolicitud
from app.models.resultado_servicio import ResultadoServicio
from app.models.notificacion import Notificacion
from app.models.bitacora import Bitacora
from app.models.estadistica_resumen import EstadisticaResumen

__all__ = [
    "Usuario",
    "Cliente",
    "Taller",
    "Vehiculo",
    "Especialidad",
    "TallerEspecialidad",
    "Servicio",
    "TallerServicio",
    "SolicitudEmergencia",
    "Evidencia",
    "ClasificacionIncidente",
    "PostulacionTaller",
    "AsignacionAtencion",
    "HistorialEstadoSolicitud",
    "ResultadoServicio",
    "Notificacion",
    "Bitacora",
    "EstadisticaResumen",
]
