import enum


class RolUsuario(str, enum.Enum):
    CLIENTE = "CLIENTE"
    TALLER = "TALLER"
    ADMINISTRADOR = "ADMINISTRADOR"


class EstadoSolicitud(str, enum.Enum):
    REGISTRADA = "REGISTRADA"
    EN_BUSQUEDA = "EN_BUSQUEDA"
    EN_ESPERA_RESPUESTAS = "EN_ESPERA_RESPUESTAS"
    TALLER_SELECCIONADO = "TALLER_SELECCIONADO"
    EN_CAMINO = "EN_CAMINO"
    EN_PROCESO = "EN_PROCESO"
    ATENDIDA = "ATENDIDA"
    CANCELADA = "CANCELADA"


class NivelUrgencia(str, enum.Enum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class EstadoAprobacionTaller(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class EstadoOperativoTaller(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    NO_DISPONIBLE = "NO_DISPONIBLE"
    SUSPENDIDO = "SUSPENDIDO"


class EstadoRegistroVehiculo(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class EstadoEspecialidad(str, enum.Enum):
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"


class EstadoServicio(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class EstadoTallerEspecialidad(str, enum.Enum):
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"


class EstadoPostulacion(str, enum.Enum):
    POSTULADA = "POSTULADA"
    RETIRADA = "RETIRADA"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"
    EXPIRADA = "EXPIRADA"


class EstadoAsignacion(str, enum.Enum):
    ACTIVA = "ACTIVA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"


class EstadoResultado(str, enum.Enum):
    RESUELTO = "RESUELTO"
    PARCIAL = "PARCIAL"
    PENDIENTE = "PENDIENTE"


class TipoActor(str, enum.Enum):
    CLIENTE = "CLIENTE"
    TALLER = "TALLER"
    ADMINISTRADOR = "ADMINISTRADOR"
    SISTEMA = "SISTEMA"


class TipoEvidencia(str, enum.Enum):
    IMAGEN = "IMAGEN"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    DOCUMENTO = "DOCUMENTO"


class OrigenEvidencia(str, enum.Enum):
    CLIENTE = "CLIENTE"
    TALLER = "TALLER"
    SISTEMA = "SISTEMA"


class TipoNotificacion(str, enum.Enum):
    PUSH = "PUSH"
    INTERNA = "INTERNA"
    EMAIL = "EMAIL"


class CategoriaNotificacion(str, enum.Enum):
    SOLICITUD = "SOLICITUD"
    POSTULACION = "POSTULACION"
    ASIGNACION = "ASIGNACION"
    ESTADO = "ESTADO"
    SISTEMA = "SISTEMA"


class EstadoLecturaNotificacion(str, enum.Enum):
    LEIDA = "LEIDA"
    NO_LEIDA = "NO_LEIDA"


class EstadoEnvioNotificacion(str, enum.Enum):
    ENVIADA = "ENVIADA"
    FALLIDA = "FALLIDA"
    PENDIENTE = "PENDIENTE"


class ResultadoAuditoria(str, enum.Enum):
    EXITO = "EXITO"
    ERROR = "ERROR"
    ADVERTENCIA = "ADVERTENCIA"


class TipoEstadistica(str, enum.Enum):
    TALLER = "TALLER"
    GENERAL = "GENERAL"


class PeriodoEstadistica(str, enum.Enum):
    DIA = "DIA"
    SEMANA = "SEMANA"
    MES = "MES"


# ==================== Audio & Text Analysis Enums ====================

class EstadoComprensionAudio(str, enum.Enum):
    """Estado de comprensión de audio transcrito"""
    COMPRENDIDO = "COMPRENDIDO"
    PARCIALMENTE_COMPRENDIDO = "PARCIALMENTE_COMPRENDIDO"
    NO_ENTENDIBLE = "NO_ENTENDIBLE"


class CategoriaIncidenteAuto(str, enum.Enum):
    """Categorías base de incidente vehicular - para clasificación automática"""
    BATERIA_DESCARGADA = "BATERIA_DESCARGADA"
    COLISION = "COLISION"
    PINCHAZO_LLANTA = "PINCHAZO_LLANTA"
    SOBRECALENTAMIENTO = "SOBRECALENTAMIENTO"
    VEHICULO_INMOVILIZADO = "VEHICULO_INMOVILIZADO"
    FALLA_ELECTRICA = "FALLA_ELECTRICA"
    FALLA_MECANICA = "FALLA_MECANICA"
    NO_ENTENDIBLE = "NO_ENTENDIBLE"
    SIN_CLASIFICACION_CLARA = "SIN_CLASIFICACION_CLARA"


class PlataformaPush(str, enum.Enum):
    """Plataformas soportadas para notificaciones push"""
    WEB = "WEB"
    ANDROID = "ANDROID"
    IOS = "IOS"


class CategoriaIncidente(str, enum.Enum):
    """Categorías principales de incidentes para clasificación manual por especialidad"""
    MECANICA = "MECANICA"
    ELECTRICIDAD = "ELECTRICIDAD"
    HIDRAULICA = "HIDRAULICA"
    CLIMATIZACION = "CLIMATIZACION"
    SISTEMA_FRENOS = "SISTEMA_FRENOS"
    SISTEMA_COMBUSTIBLE = "SISTEMA_COMBUSTIBLE"
    TRANSMISION = "TRANSMISION"
    SUSPENSION = "SUSPENSION"
    CARROCERIA = "CARROCERIA"
    OTRO = "OTRO"


class SeveridadIncidente(str, enum.Enum):
    """Nivel de severidad del incidente"""
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class FuenteAnalisisIncidente(str, enum.Enum):
    """Origen de los datos usados para análisis"""
    TEXTO_MANUAL = "TEXTO_MANUAL"
    TRANSCRIPCION_AUDIO = "TRANSCRIPCION_AUDIO"
    COMBINADO = "COMBINADO"
