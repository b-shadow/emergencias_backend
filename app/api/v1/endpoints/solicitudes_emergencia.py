from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.solicitud import (
    SolicitudCreateRequest,
    SolicitudUpdateRequest,
    SolicitudResponse,
    SolicitudCancelRequest,
    SolicitudEstadoDetailResponse,
    SolicitudHistorialListResponse,
    SolicitudHistorialDetalleResponse,
    ListadoSolicitudesDisponiblesResponse,
    SolicitudDisponibleDetalleResponse,
    PostulacionCreateRequest,
    PostulacionResponse,
)
from app.schemas.incident_analysis import (
    AudioTranscriptionRequest,
    AudioTranscriptionResponse,
    TextClassificationRequest,
    TextClassificationResponse,
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    TranscribeAudioToolRequest,
    TranscribeAudioToolResponse,
    ClassifyTextToolRequest,
    ClassifyTextToolResponse,
    AnalyzeIncidentToolResponse,
    ProblemUrgencyRequest,
    ProblemUrgencyResponse,
    ProcessProblemToolResponse,
)
from app.schemas.common import MessageResponse
from app.services.solicitud_service import SolicitudService
from app.integrations.ai_text_audio import AITextAudioService
from app.services.groq_urgency_service import GroqUrgencyService
from loguru import logger


router = APIRouter()


@router.get("", response_model=list[SolicitudResponse])
def list_solicitudes(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista solicitudes de emergencia.
    - ADMINISTRADOR: Ve todas las solicitudes
    - CLIENTE: Solo ve sus propias solicitudes
    """
    solicitudes = SolicitudService.list_solicitudes(db, current_user)
    return [SolicitudResponse.from_orm_with_relations(s) for s in solicitudes]


@router.get("/historial", response_model=SolicitudHistorialListResponse)
def get_historial_solicitudes(
    orden_por: str = "fecha",
    descendente: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene el historial de solicitudes de emergencia (Caso de Uso: Consultar historial).
    
    Flujo:
    1. Cliente accede a sección de historial
    2. Sistema consulta sus solicitudes
    3. Sistema muestra listado ordenado por fecha/estado (paso 3)
    
    Excepciones:
    - E1: Historial vacío -> devuelve lista vacía con estadísticas
    
    La consulta es registrada en bitácora (paso 8).
    
    Query Parameters:
    - orden_por: "fecha" o "estado" (default: "fecha")
    - descendente: true (más recientes) o false (más antiguos, default: true)
    - skip: Paginación offset (default: 0)
    - limit: Paginación limit (default: 100)
    
    Permisos:
    - CLIENTE: Solo su propia solicitudes
    - ADMINISTRADOR: Todas las solicitudes
    """
    result = SolicitudService.get_historial_solicitudes(
        db,
        current_user,
        orden_por=orden_por,
        descendente=descendente,
        skip=skip,
        limit=limit,
    )
    
    # Serializar solicitudes a respuesta
    historial_items = []
    for sol in result["solicitudes"]:
        taller_nombre = None
        vehiculo_placa = None
        
        if sol.id_vehiculo:
            from app.models.vehiculo import Vehiculo
            veh = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == sol.id_vehiculo).first()
            if veh:
                vehiculo_placa = veh.placa
        
        from app.models.asignacion_atencion import AsignacionAtencion
        asignacion = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_solicitud == sol.id_solicitud
        ).first()
        if asignacion and asignacion.taller:
            taller_nombre = asignacion.taller.nombre_taller
        
        historial_items.append({
            "id_solicitud": sol.id_solicitud,
            "codigo_solicitud": sol.codigo_solicitud,
            "estado_actual": sol.estado_actual,
            "nivel_urgencia": sol.nivel_urgencia,
            "fecha_creacion": sol.fecha_creacion,
            "fecha_cierre": sol.fecha_cierre,
            "vehículo_placa": vehiculo_placa,
            "taller_nombre": taller_nombre,
            "categoria_incidente": sol.categoria_incidente,
        })
    
    return SolicitudHistorialListResponse(
        total_solicitudes=result["total_solicitudes"],
        total_finalizadas=result["total_finalizadas"],
        total_activas=result["total_activas"],
        historial=historial_items,
    )


# ==================== Endpoints de Herramientas de Análisis ====================



@router.get("/disponibles", response_model=ListadoSolicitudesDisponiblesResponse)
def get_solicitudes_disponibles_para_taller(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene listado de solicitudes disponibles para que un taller se postule
    (Caso de Uso: Visualizar solicitudes de emergencia - Perspectiva TALLER).
    
    Flujo:
    1. Taller accede a ver solicitudes disponibles
    2. Sistema valida que taller está aprobado, habilitado y tiene especialidades (E3)
    3. Sistema consulta solicitudes compatibles
    4. Sistema calcula distancia para cada solicitud
    5. Sistema agrupa por especialidad para estadísticas
    6. Taller revisa listado
    7. Sistema registra consulta en bitácora
    
    Excepciones:
    - E1: No hay solicitudes disponibles -> devuelve lista vacía con estadísticas
    - E3: Taller sin especialidades o no aprobado -> 400 Bad Request
    
    Permisos:
    - TALLER: Solo puede ver solicitudes disponibles para sus especialidades
    
    Query Parameters:
    - skip: Paginación offset (default: 0)
    - limit: Paginación limit (default: 100)
    """
    from loguru import logger
    
    logger.info(f"[DEBUG] Endpoint /disponibles llamado")
    logger.info(f"[DEBUG] current_user: {current_user}")
    logger.info(f"[DEBUG] current_user.rol: {current_user.rol if current_user else 'None'}")
    
    try:
        result = SolicitudService.get_solicitudes_disponibles_para_taller(
            db,
            current_user,
            skip=skip,
            limit=limit,
        )
        
        # Serializar solicitudes a respuesta
        solicitudes_items = []
        for item in result["solicitudes"]:
            solicitud = item["solicitud"]
            
            # Obtener información del vehículo
            vehiculo_marca_modelo = None
            if solicitud.id_vehiculo:
                vehiculo = db.query(Vehiculo).filter(
                    Vehiculo.id_vehiculo == solicitud.id_vehiculo
                ).first()
                if vehiculo:
                    vehiculo_marca_modelo = f"{vehiculo.marca} {vehiculo.modelo}".strip()
            
            list_item = {
                "id_solicitud": solicitud.id_solicitud,
                "codigo_solicitud": solicitud.codigo_solicitud,
                "estado_actual": solicitud.estado_actual,
                "nivel_urgencia": solicitud.nivel_urgencia,
                "categoria_incidente": solicitud.categoria_incidente,
                "latitud": solicitud.latitud,
                "longitud": solicitud.longitud,
                "fecha_creacion": solicitud.fecha_creacion,
                "distancia_km": item["distancia_km"],
                "vehiculo_marca_modelo": vehiculo_marca_modelo,
                "descripcion_texto": solicitud.descripcion_texto,
            }
            solicitudes_items.append(list_item)
        
        return ListadoSolicitudesDisponiblesResponse(
            total_disponibles=result["total_disponibles"],
            cantidad_por_especialidad=result["cantidad_por_especialidad"],
            solicitudes=solicitudes_items,
        )
    except Exception as e:
        logger.error(f"[ERROR] Exception in /disponibles: {str(e)}", exc_info=True)
        raise


@router.get("/disponibles/{solicitud_id}", response_model=SolicitudDisponibleDetalleResponse)
def get_solicitud_disponible_detalle(
    solicitud_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene el detalle completo de una solicitud disponible para un taller
    (Caso de Uso: Visualizar solicitudes - Vista detallada del taller).
    
    Flujo:
    9. Taller selecciona una solicitud del listado
    10. Sistema valida que taller sigue siendo compatible (E2)
    11. Sistema muestra detalle completo:
        - Información de la solicitud
        - Evidencias adjuntas
        - Categoría/especialidad requerida
        - Ubicación y distancia
    12. Sistema registra consulta en bitácora
    
    Excepciones:
    - E2: Solicitud no disponible anymore (estado cambió, radio expiró, etc.)
    - E3: Taller sin especialidades
    
    Permisos:
    - TALLER: Solo puede ver detalles de solicitudes compatibles con sus especialidades
    """
    result = SolicitudService.get_solicitud_disponible_detalle(
        db,
        solicitud_id,
        current_user,
    )
    
    solicitud = result["solicitud"]
    
    # Obtener datos del cliente
    from app.models.cliente import Cliente
    from app.models.usuario import Usuario
    cliente = db.query(Cliente).filter(Cliente.id_cliente == solicitud.id_cliente).first()
    cliente_nombre = f"{cliente.nombre} {cliente.apellido}".strip() if cliente else "Cliente"
    cliente_telefono = cliente.telefono if cliente and cliente.telefono else "No disponible"
    
    # Obtener email del usuario del cliente
    cliente_email = "No disponible"
    if cliente:
        usuario = db.query(Usuario).filter(Usuario.id_usuario == cliente.id_usuario).first()
        if usuario and hasattr(usuario, 'correo_electronico') and usuario.correo_electronico:
            cliente_email = usuario.correo_electronico
    
    # Obtener datos del vehículo si existe
    vehiculo_marca = None
    vehiculo_modelo = None
    vehiculo_color = None
    vehiculo_placa = None
    if solicitud.id_vehiculo:
        vehiculo = db.query(Vehiculo).filter(
            Vehiculo.id_vehiculo == solicitud.id_vehiculo
        ).first()
        if vehiculo:
            vehiculo_marca = vehiculo.marca
            vehiculo_modelo = vehiculo.modelo
            vehiculo_color = vehiculo.color
            vehiculo_placa = vehiculo.placa
    
    # Serializar evidencias
    evidencias_list = []
    for evidencia in result["evidencias"]:
        evidencia_item = {
            "tipo_evidencia": evidencia.tipo_evidencia,
            "url_archivo": evidencia.url_archivo,
            "nombre_archivo": evidencia.nombre_archivo,
            "descripcion": evidencia.descripcion,
            "fecha_subida": evidencia.fecha_subida,
        }
        evidencias_list.append(evidencia_item)
    
    # Obtener especialidades desde especialidad_solicitud_emergencia
    from app.models.solicitud_emergencia import EspecialidadSolicitudEmergencia, ServicioSolicitudEmergencia
    especialidades_rel = db.query(EspecialidadSolicitudEmergencia).filter(
        EspecialidadSolicitudEmergencia.id_solicitud == solicitud_id
    ).all()
    especialidades_list = [rel.especialidad.nombre_especialidad for rel in especialidades_rel]
    
    # Obtener servicios desde servicio_solicitud_emergencia
    servicios_rel = db.query(ServicioSolicitudEmergencia).filter(
        ServicioSolicitudEmergencia.id_solicitud == solicitud_id
    ).all()
    servicios_list = [rel.servicio.nombre_servicio for rel in servicios_rel]
    
    return SolicitudDisponibleDetalleResponse(
        id_solicitud=solicitud.id_solicitud,
        codigo_solicitud=solicitud.codigo_solicitud,
        estado_actual=solicitud.estado_actual,
        nivel_urgencia=solicitud.nivel_urgencia,
        categoria_incidente=solicitud.categoria_incidente,
        descripcion_texto=solicitud.descripcion_texto,
        descripcion_audio_url=solicitud.descripcion_audio_url,
        latitud=solicitud.latitud,
        longitud=solicitud.longitud,
        direccion_referencial=solicitud.direccion_referencial,
        radio_busqueda_km=solicitud.radio_busqueda_km,
        vehiculo_placa=vehiculo_placa,
        vehiculo_marca=vehiculo_marca,
        vehiculo_modelo=vehiculo_modelo,
        vehiculo_color=vehiculo_color,
        fecha_creacion=solicitud.fecha_creacion,
        distancia_km=result["distancia_km"],
        evidencias=evidencias_list,
        especialidades_requeridas=especialidades_list,
        servicios_requeridos=servicios_list,
        cliente_nombre=cliente_nombre,
        cliente_email=cliente_email,
        cliente_telefono=cliente_telefono,
    )


@router.get("/{solicitud_id}", response_model=SolicitudResponse)
def get_solicitud(
    solicitud_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene una solicitud específica.
    - CLIENTE: Solo puede ver sus propias solicitudes
    - ADMINISTRADOR/TALLER: Pueden ver cualquiera
    """
    solicitud = SolicitudService.get_solicitud(db, solicitud_id, current_user)
    return SolicitudResponse.from_orm_with_relations(solicitud)


@router.get("/{solicitud_id}/estado/detalle", response_model=SolicitudEstadoDetailResponse)
def get_solicitud_estado_detalle(
    solicitud_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene estado detallado de una solicitud (Caso de Uso: Consultar estado).
    
    Incluye:
    - Estado actual y detalles básicos (paso 3)
    - Historial de cambios de estado (paso 4)
    - Información del taller asignado si existe (paso 5, E2)
    
    Excepciones:
    - E1: Solicitud no encontrada -> 404
    - E2: Sin taller seleccionado -> asignacion_actual será None
    
    La consulta es registrada en bitácora (paso 8).
    
    Permisos:
    - CLIENTE: Solo puede consultar sus propias solicitudes
    - ADMINISTRADOR/TALLER: Pueden consultar cualquiera
    """
    return SolicitudService.get_solicitud_estado_detalle(db, solicitud_id, current_user)


@router.get("/{solicitud_id}/historial/detalle", response_model=SolicitudHistorialDetalleResponse)
def get_solicitud_historial_detalle(
    solicitud_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene el detalle completo de una solicitud del historial (Caso de Uso: Consultar historial).
    
    Flujo:
    4. Cliente selecciona una solicitud del historial
    5. Sistema muestra detalle completo (paso 5)
    6. Incluye: vehículo, descripción, ubicación, estado, taller que atendió (paso 6)
    7. Cliente revisa información (paso 7)
    
    El detalle incluye:
    - Información completa de la solicitud
    - Vehículo asociado si existe
    - Taller que la atendió si existe
    - Resultado del servicio si existe
    - Historial completo de cambios de estado
    
    Excepciones:
    - E2: Solicitud no encontrada -> 404
    
    La consulta es registrada en bitácora (paso 8).
    
    Permisos:
    - CLIENTE: Solo puede ver sus propias solicitudes
    - ADMINISTRADOR: Puede ver cualquiera
    """
    result = SolicitudService.get_solicitud_historial_detalle(db, solicitud_id, current_user)
    
    # Serializar vehículo
    vehiculo_response = None
    if result["vehiculo"]:
        veh = result["vehiculo"]
        vehiculo_response = {
            "id_vehiculo": veh.id_vehiculo,
            "placa": veh.placa,
            "marca": veh.marca,
            "modelo": veh.modelo,
            "anio": veh.anio,
            "color": veh.color,
        }
    
    # Serializar taller
    taller_response = None
    if result["taller_asignado"]:
        taller = result["taller_asignado"]
        taller_response = {
            "id_taller": taller.id_taller,
            "nombre_taller": taller.nombre_taller,
            "telefono": taller.telefono,
            "email": taller.usuario.correo if taller.usuario else None,
            "direccion": taller.direccion,
            "calificacion_promedio": None,  # Se puede agregar cálculo si existe
        }
    
    # Serializar resultado
    resultado_response = None
    if result["resultado_servicio"]:
        res = result["resultado_servicio"]
        resultado_response = {
            "id_resultado_servicio": res.id_resultado_servicio,
            "diagnostico": res.diagnostico,
            "solucion_aplicada": res.solucion_aplicada,
            "estado_resultado": res.estado_resultado.value if hasattr(res.estado_resultado, 'value') else str(res.estado_resultado),
            "requiere_seguimiento": res.requiere_seguimiento,
            "observaciones": res.observaciones,
            "fecha_registro": res.fecha_registro,
        }
    
    # Serializar historial
    historial_response = [
        {
            "id_historial_estado": h.id_historial_estado,
            "estado_anterior": h.estado_anterior,
            "estado_nuevo": h.estado_nuevo,
            "comentario": h.comentario,
            "actualizado_por_tipo": h.actualizado_por_tipo,
            "actualizado_por_id": h.actualizado_por_id,
            "fecha_cambio": h.fecha_cambio,
        }
        for h in result["historial_estado"]
    ]
    
    solicitud = result["solicitud"]
    return SolicitudHistorialDetalleResponse(
        id_solicitud=solicitud.id_solicitud,
        codigo_solicitud=solicitud.codigo_solicitud,
        estado_actual=solicitud.estado_actual,
        nivel_urgencia=solicitud.nivel_urgencia,
        categoria_incidente=solicitud.categoria_incidente,
        descripcion_texto=solicitud.descripcion_texto,
        descripcion_audio_url=solicitud.descripcion_audio_url,
        latitud=solicitud.latitud,
        longitud=solicitud.longitud,
        direccion_referencial=solicitud.direccion_referencial,
        fecha_creacion=solicitud.fecha_creacion,
        fecha_actualizacion=solicitud.fecha_actualizacion,
        fecha_cierre=solicitud.fecha_cierre,
        vehiculo=vehiculo_response,
        taller_asignado=taller_response,
        resultado_servicio=resultado_response,
        historial_estado=historial_response,
    )


@router.post("", response_model=SolicitudResponse, status_code=status.HTTP_201_CREATED)
def create_solicitud(
    payload: SolicitudCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea una nueva solicitud de emergencia con especialidades y servicios.
    - Solo CLIENTE puede crear solicitudes
    - Acepta listas de IDs de especialidades y servicios requeridos
    """
    solicitud = SolicitudService.create_solicitud(db, payload.model_dump(), current_user)
    db.refresh(solicitud)  # Recargar para obtener las relaciones
    return SolicitudResponse.from_orm_with_relations(solicitud)


@router.put("/{solicitud_id}", response_model=SolicitudResponse)
def update_solicitud(
    solicitud_id: UUID,
    payload: SolicitudUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualiza una solicitud.
    - CLIENTE: Solo puede actualizar sus propias solicitudes (campos limitados)
    - ADMINISTRADOR: Puede actualizar cualquier solicitud
    """
    return SolicitudService.update_solicitud(db, solicitud_id, payload.model_dump(), current_user)


@router.post("/{solicitud_id}/cancel", response_model=MessageResponse)
def cancel_solicitud(
    solicitud_id: UUID,
    payload: SolicitudCancelRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Cancela una solicitud de emergencia.
    - CLIENTE: Solo puede cancelar sus propias solicitudes
    - ADMINISTRADOR: Puede cancelar cualquiera
    """
    SolicitudService.cancel_solicitud(db, solicitud_id, current_user, payload.razon)
    return MessageResponse(message="Solicitud cancelada correctamente")


@router.post("/{solicitud_id}/postulaciones", response_model=PostulacionResponse)
def create_postulacion(
    solicitud_id: UUID,
    payload: PostulacionCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea una postulación de taller para atender una solicitud
    (Caso de Uso: Solicitar atención de emergencia).
    
    Flujo:
    1. Taller accede a listado de solicitudes disponibles
    2. Taller selecciona una solicitud compatible
    3. Sistema muestra información completa
    4. Taller decide postularse
    5. Taller selecciona opción de solicitar atención
    6. Sistema confirma disponibilidad
    7. Taller ingresa tiempo estimado de llegada
    8. Taller confirma envío
    9. Sistema valida que solicitud sigue disponible (E1)
    10. Sistema registra postulación
    11. Sistema notifica al cliente
    12. Sistema registra evento en bitácora
    13. Sistema muestra confirmación
    
    Excepciones:
    - E1: Solicitud no disponible (CANCELADA, ATENDIDA)
    - E2: Taller ya postulado a esta solicitud
    - E3: Taller no aprobado o no habilitado
    - E4: Taller sin especialidades compatibles
    
    Permisos:
    - Solo TALLER puede postularse
    - CLIENTE y ADMIN no tienen acceso
    
    Request body:
    - tiempo_estimado_llegada_min: int (1-1440 minutos, opcional)
    - mensaje_propuesta: str (hasta 1000 caracteres, opcional)
    """
    postulacion = SolicitudService.create_postulacion(
        db,
        solicitud_id,
        current_user,
        payload.dict(exclude_unset=True),
    )
    
    return PostulacionResponse(
        id_postulacion=postulacion.id_postulacion,
        id_solicitud=postulacion.id_solicitud,
        id_taller=postulacion.id_taller,
        tiempo_estimado_llegada_min=postulacion.tiempo_estimado_llegada_min,
        mensaje_propuesta=postulacion.mensaje_propuesta,
        estado_postulacion=postulacion.estado_postulacion.value,
        fecha_postulacion=postulacion.fecha_postulacion,
        fecha_respuesta=postulacion.fecha_respuesta,
    )


@router.post("/tools/transcribir-audio", response_model=TranscribeAudioToolResponse)
async def transcribe_audio_tool(
    payload: TranscribeAudioToolRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Herramienta de transcripción: descarga audio desde URL y lo transcribe
    
    Útil para:
    - Probar transcripción antes de crear solicitud
    - Transcribir audio adicional
    - Debugging y análisis
    """
    try:
        ai_service = AITextAudioService()
        result = await ai_service.transcribe_audio(payload.audio_url)
        return TranscribeAudioToolResponse(success=True, data=AudioTranscriptionResponse(**result))
    except Exception as e:
        logger.error(f"Error en transcribe_audio_tool: {e}")
        return TranscribeAudioToolResponse(
            success=False,
            error=f"Error al transcribir audio: {str(e)}"
        )


@router.post("/tools/clasificar-texto", response_model=ClassifyTextToolResponse)
def classify_text_tool(
    payload: ClassifyTextToolRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Herramienta de clasificación: analiza texto y clasifica el incidente
    
    Útil para:
    - Probar clasificación antes de crear solicitud
    - Validar categorización manual
    - Debugging y análisis
    """
    try:
        ai_service = AITextAudioService()
        result = ai_service.classify_incident(payload.texto, payload.min_confidence)
        return ClassifyTextToolResponse(
            success=True,
            data=TextClassificationResponse(**result)
        )
    except Exception as e:
        logger.error(f"Error en classify_text_tool: {e}")
        return ClassifyTextToolResponse(
            success=False,
            error=f"Error al clasificar texto: {str(e)}"
        )


@router.post("/tools/procesar-problema", response_model=ProcessProblemToolResponse)
async def process_problem_tool(
    payload: ProblemUrgencyRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Procesa la descripción del problema con IA (Groq) para:
    - Detectar nivel de urgencia (BAJO|MEDIO|ALTO)
    - Generar mensaje tipo chatbot para el usuario
    - Recomendar acción en app
    """
    try:
        _ = db
        _ = current_user
        urgency_service = GroqUrgencyService()
        result = await urgency_service.classify_problem(payload.texto)
        return ProcessProblemToolResponse(
            success=True,
            data=ProblemUrgencyResponse(**result),
        )
    except Exception as e:
        logger.error(f"Error en process_problem_tool: {e}")
        return ProcessProblemToolResponse(
            success=False,
            error=f"Error al procesar problema: {str(e)}",
        )


@router.post("/{solicitud_id}/analizar-incidente", response_model=AnalyzeIncidentToolResponse)
async def analyze_incident(
    solicitud_id: UUID,
    payload: IncidentAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Análisis completo del incidente:
    1. Transcribe audio si existe
    2. Clasifica el incidente
    3. Resuelve especialidad y servicio
    4. Persiste clasificación
    5. Actualiza solicitud
    
    Requiere:
    - Solicitud existente
    - CLIENTE: debe ser su propia solicitud
    - ADMINISTRADOR: cualquier solicitud
    """
    try:
        # Validar acceso a la solicitud
        SolicitudService.get_solicitud(db, solicitud_id, current_user)
        
        ai_service = AITextAudioService()
        result = await ai_service.analyze_incident(
            db,
            solicitud_id,
            payload.force_reanalysis
        )
        
        return AnalyzeIncidentToolResponse(
            success=True,
            data=IncidentAnalysisResponse(**result)
        )
    except Exception as e:
        logger.error(f"Error en analyze_incident: {e}")
        return AnalyzeIncidentToolResponse(
            success=False,
            error=f"Error al analizar incidente: {str(e)}"
        )
