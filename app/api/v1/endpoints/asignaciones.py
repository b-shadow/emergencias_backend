from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.models.asignacion_atencion import AsignacionAtencion
from app.schemas.asignacion import (
    AsignacionEstadoUpdateRequest,
    AsignacionResponse,
    ServicioRealizadoRequest,
    ServicioTallerResponse,
    ServicioRealizadoResponse,
)
from app.schemas.common import MessageResponse
from app.services.asignacion_service import AsignacionService


router = APIRouter()


@router.get("/activas", response_model=list[dict])
def get_asignaciones_activas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene las asignaciones activas del taller actual CON TODA LA INFORMACIÓN necesaria.
    Retorna solicitud, cliente, vehículo, taller en una sola llamada.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"GET /asignaciones/activas - Usuario: {current_user.nombre_completo} ({current_user.rol})")
        
        from app.models.taller import Taller
        from app.core.enums import RolUsuario, EstadoAsignacion
        
        if current_user.rol == RolUsuario.TALLER:
            # Buscar el taller del usuario
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if not taller:
                logger.warning(f"Taller NO encontrado para usuario {current_user.id_usuario}")
                return []
            
            logger.info(f"Taller encontrado: {taller.nombre_taller}")
            
            # Query con carga lazy de relaciones
            asignaciones = db.query(AsignacionAtencion).filter(
                AsignacionAtencion.id_taller == taller.id_taller,
                AsignacionAtencion.estado_asignacion == EstadoAsignacion.ACTIVA
            ).all()
        else:
            logger.warning(f"Usuario no es TALLER, es {current_user.rol}")
            return []
        
        logger.info(f"Asignaciones encontradas: {len(asignaciones)}")
        
        # Convertir a dict con TODA la información incluida
        result = []
        for asignacion in asignaciones:
            asignacion_dict = {
                "id_asignacion": str(asignacion.id_asignacion),
                "id_solicitud": str(asignacion.id_solicitud),
                "id_taller": str(asignacion.id_taller),
                "estado_asignacion": asignacion.estado_asignacion.value,
                "fecha_asignacion": asignacion.fecha_asignacion.isoformat(),
                "fecha_inicio_atencion": asignacion.fecha_inicio_atencion.isoformat() if asignacion.fecha_inicio_atencion else None,
                "fecha_fin_atencion": asignacion.fecha_fin_atencion.isoformat() if asignacion.fecha_fin_atencion else None,
                "motivo_cancelacion": asignacion.motivo_cancelacion,
            }
            
            # Incluir TODA la información de solicitud (no hacer llamadas adicionales)
            if asignacion.solicitud:
                solicitud = asignacion.solicitud
                asignacion_dict["solicitud"] = {
                    "id_solicitud": str(solicitud.id_solicitud),
                    "codigo_solicitud": solicitud.codigo_solicitud,
                    "categoria_incidente": solicitud.categoria_incidente,
                    "nivel_urgencia": solicitud.nivel_urgencia.value,
                    "descripcion_texto": solicitud.descripcion_texto,
                    "estado_actual": solicitud.estado_actual.value,
                    "latitud": solicitud.latitud,
                    "longitud": solicitud.longitud,
                    "radio_busqueda_km": solicitud.radio_busqueda_km,
                    "cliente": {
                        "id_cliente": str(solicitud.cliente.id_cliente),
                        "nombre": solicitud.cliente.nombre,
                        "apellido": solicitud.cliente.apellido,
                        "telefono": solicitud.cliente.telefono,
                    } if solicitud.cliente else None,
                    "vehiculo": {
                        "id_vehiculo": str(solicitud.vehiculo.id_vehiculo),
                        "placa": solicitud.vehiculo.placa,
                        "marca": solicitud.vehiculo.marca,
                        "modelo": solicitud.vehiculo.modelo,
                        "color": solicitud.vehiculo.color,
                    } if solicitud.vehiculo else None,
                }
            
            # Incluir información de taller
            if asignacion.taller:
                taller_obj = asignacion.taller
                asignacion_dict["taller"] = {
                    "id_taller": str(taller_obj.id_taller),
                    "nombre_taller": taller_obj.nombre_taller,
                    "latitud": taller_obj.latitud,
                    "longitud": taller_obj.longitud,
                }
            
            result.append(asignacion_dict)
        
        logger.info(f"Retornando {len(result)} asignaciones con información completa")
        return result
    
    except Exception as e:
        logger.error(f"Error en GET /asignaciones/activas: {str(e)}", exc_info=True)
        raise


@router.get("/{asignacion_id}", response_model=dict)
def get_asignacion(
    asignacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene una asignación específica con información completa de solicitud.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        asignacion = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_asignacion == asignacion_id
        ).first()
        
        if not asignacion:
            from app.core.exceptions import not_found
            raise not_found("Asignación no encontrada")
        
        # Construir respuesta con datos completos
        asignacion_dict = {
            "id_asignacion": str(asignacion.id_asignacion),
            "id_solicitud": str(asignacion.id_solicitud),
            "id_taller": str(asignacion.id_taller),
            "estado_asignacion": asignacion.estado_asignacion.value,
            "fecha_asignacion": asignacion.fecha_asignacion.isoformat(),
            "fecha_inicio_atencion": asignacion.fecha_inicio_atencion.isoformat() if asignacion.fecha_inicio_atencion else None,
            "fecha_fin_atencion": asignacion.fecha_fin_atencion.isoformat() if asignacion.fecha_fin_atencion else None,
            "motivo_cancelacion": asignacion.motivo_cancelacion,
        }
        
        # Incluir información de solicitud si existe
        if asignacion.solicitud:
            solicitud = asignacion.solicitud
            asignacion_dict["solicitud"] = {
                "id_solicitud": str(solicitud.id_solicitud),
                "codigo_solicitud": solicitud.codigo_solicitud,
                "categoria_incidente": solicitud.categoria_incidente,
                "nivel_urgencia": solicitud.nivel_urgencia.value,
                "descripcion_texto": solicitud.descripcion_texto,
                "estado_actual": solicitud.estado_actual.value,
                "latitud": solicitud.latitud,
                "longitud": solicitud.longitud,
                "radio_busqueda_km": solicitud.radio_busqueda_km,
                "cliente": {
                    "id_cliente": str(solicitud.cliente.id_cliente),
                    "nombre": solicitud.cliente.nombre,
                    "apellido": solicitud.cliente.apellido,
                    "telefono": solicitud.cliente.telefono,
                } if solicitud.cliente else None,
                "vehiculo": {
                    "id_vehiculo": str(solicitud.vehiculo.id_vehiculo),
                    "placa": solicitud.vehiculo.placa,
                    "marca": solicitud.vehiculo.marca,
                    "modelo": solicitud.vehiculo.modelo,
                    "color": solicitud.vehiculo.color,
                } if solicitud.vehiculo else None,
            }
        
        # Incluir información de taller si existe
        if asignacion.taller:
            taller = asignacion.taller
            asignacion_dict["taller"] = {
                "id_taller": str(taller.id_taller),
                "nombre_taller": taller.nombre_taller,
                "latitud": taller.latitud,
                "longitud": taller.longitud,
            }
        
        return asignacion_dict
    
    except Exception as e:
        logger.error(f"Error en GET /asignaciones/{asignacion_id}: {str(e)}", exc_info=True)
        raise


@router.patch("/{asignacion_id}/estado", response_model=AsignacionResponse, status_code=status.HTTP_200_OK)
def update_estado_asignacion(
    asignacion_id: UUID,
    payload: AsignacionEstadoUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualiza el estado de una asignación (CU-20: Actualizar estado de atención).
    
    Flujo (Caso de Uso):
    1. Taller accede a detalle de solicitud asignada
    2. Sistema muestra información actual y estado registrado
    3. Taller selecciona opción de actualizar estado
    4. Sistema muestra estados disponibles
    5. Taller selecciona nuevo estado (En camino, En proceso, Atendida, Cancelada)
    6. Si corresponde, taller ingresa información adicional
    7. Taller confirma actualización
    8. Sistema valida transición de estado (paso 8)
    9. Sistema actualiza estado (paso 9)
    10. Sistema registra en historial (paso 10)
    11. Sistema notifica al cliente (paso 11)
    12. Sistema registra en bitácora (paso 12)
    13. Sistema muestra confirmación (paso 13)
    
    Estados válidos:
    - ASIGNADA -> EN_CAMINO | CANCELADA
    - EN_CAMINO -> EN_PROCESO | CANCELADA
    - EN_PROCESO -> COMPLETADA | CANCELADA
    - COMPLETADA -> (final)
    - CANCELADA -> (final)
    
    Excepciones:
    - E2: Solicitud no asignada al taller (validada por get_asignacion)
    """
    return AsignacionService.update_estado_asignacion(
        db,
        asignacion_id,
        payload.nuevo_estado,
        payload.comentario,
        current_user,
    )


@router.get("/{asignacion_id}/servicios", response_model=list[ServicioTallerResponse])
def get_servicios_taller(
    asignacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene los servicios disponibles del taller asignado a una solicitud.
    - Solo TALLER puede ver sus servicios
    - CLIENTE puede ver los servicios que realizará el taller
    """
    return AsignacionService.get_servicios_taller(db, asignacion_id, current_user)


@router.post("/{asignacion_id}/servicios-realizados", response_model=MessageResponse, status_code=status.HTTP_200_OK)
def guardar_servicios_realizados(
    asignacion_id: UUID,
    payload: list[ServicioRealizadoRequest],
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Guarda los servicios realizados en una asignación (durante ATENDIDA).
    - Solo TALLER puede registrar servicios de sus asignaciones
    """
    AsignacionService.guardar_servicios_realizados(db, asignacion_id, payload, current_user)
    return MessageResponse(message="Servicios realizados guardados exitosamente")


@router.get("/{asignacion_id}/servicios-realizados", response_model=list[dict])
def obtener_servicios_realizados(
    asignacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene los servicios ya realizados en una asignación.
    - Retorna lista de servicios con diagnostico, solución, observaciones, etc.
    """
    return AsignacionService.get_servicios_realizados(db, asignacion_id, current_user)

