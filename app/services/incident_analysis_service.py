"""
Incident Analysis Orchestrator Service
Orchesta el flujo completo de análisis de incidentes:
1. Transcripción de audio (si aplica)
2. Clasificación de texto
3. Persistencia del análisis
"""

import json
from typing import Optional
from uuid import UUID
from loguru import logger
from sqlalchemy.orm import Session

from app.core.enums import (
    CategoriaIncidenteAuto,
    NivelUrgencia,
    EstadoComprensionAudio,
    FuenteAnalisisIncidente,
    ResultadoAuditoria,
    TipoActor,
)
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.clasificacion_incidente import ClasificacionIncidente
from app.models.especialidad import Especialidad
from app.models.servicio import Servicio
from app.models.bitacora import Bitacora
from app.core.exceptions import not_found, bad_request
from app.services.speech_to_text_service import SpeechToTextService
from app.services.text_incident_classifier import TextIncidentClassifier


class IncidentAnalysisResult:
    """Resultado del análisis completo de un incidente"""
    def __init__(
        self,
        solicitud_id: Optional[UUID] = None,
        descripcion_texto: Optional[str] = None,
        transcripcion_audio: Optional[str] = None,
        estado_comprension: Optional[EstadoComprensionAudio] = None,
        categoria_predicha: Optional[CategoriaIncidenteAuto] = None,
        subcategoria_predicha: Optional[str] = None,
        especialidad_sugerida: Optional[str] = None,
        id_especialidad_requerida: Optional[UUID] = None,
        servicio_sugerido: Optional[str] = None,
        id_servicio_sugerido: Optional[UUID] = None,
        nivel_urgencia_predicho: Optional[NivelUrgencia] = None,
        confianza_modelo: float = 0.0,
        fuente_entrada: Optional[FuenteAnalisisIncidente] = None,
        observaciones: Optional[str] = None,
    ):
        self.solicitud_id = solicitud_id
        self.descripcion_texto = descripcion_texto
        self.transcripcion_audio = transcripcion_audio
        self.estado_comprension = estado_comprension
        self.categoria_predicha = categoria_predicha
        self.subcategoria_predicha = subcategoria_predicha
        self.especialidad_sugerida = especialidad_sugerida
        self.id_especialidad_requerida = id_especialidad_requerida
        self.servicio_sugerido = servicio_sugerido
        self.id_servicio_sugerido = id_servicio_sugerido
        self.nivel_urgencia_predicho = nivel_urgencia_predicho
        self.confianza_modelo = confianza_modelo
        self.fuente_entrada = fuente_entrada
        self.observaciones = observaciones
    
    def to_dict(self) -> dict:
        return {
            "solicitud_id": str(self.solicitud_id) if self.solicitud_id else None,
            "descripcion_texto": self.descripcion_texto,
            "transcripcion_audio": self.transcripcion_audio,
            "estado_comprension": self.estado_comprension.value if self.estado_comprension else None,
            "categoria_predicha": self.categoria_predicha.value if self.categoria_predicha else None,
            "subcategoria_predicha": self.subcategoria_predicha,
            "especialidad_sugerida": self.especialidad_sugerida,
            "id_especialidad_requerida": str(self.id_especialidad_requerida) if self.id_especialidad_requerida else None,
            "servicio_sugerido": self.servicio_sugerido,
            "id_servicio_sugerido": str(self.id_servicio_sugerido) if self.id_servicio_sugerido else None,
            "nivel_urgencia_predicho": self.nivel_urgencia_predicho.value if self.nivel_urgencia_predicho else None,
            "confianza_modelo": self.confianza_modelo,
            "fuente_entrada": self.fuente_entrada.value if self.fuente_entrada else None,
            "observaciones": self.observaciones,
        }


class IncidentAnalysisService:
    """Servicio orquestador para análisis completo de incidentes"""
    
    def __init__(self):
        self.stt_service = SpeechToTextService()
        self.classifier = TextIncidentClassifier()
        self.logger = logger
    
    @staticmethod
    def _registrar_bitacora(
        db: Session,
        solicitud_id: UUID,
        accion: str,
        resultado: ResultadoAuditoria,
        detalle: str | None = None,
    ) -> None:
        """
        Registra eventos de análisis de incidentes en la bitácora.
        
        Args:
            db: Sesión de base de datos
            solicitud_id: ID de la solicitud analizada
            accion: Descripción de la acción realizada
            resultado: Resultado de la acción (EXITO, ADVERTENCIA, ERROR)
            detalle: Detalles adicionales del evento
        """
        bitacora = Bitacora(
            tipo_actor=TipoActor.SISTEMA,
            id_actor=None,
            accion=accion,
            modulo="AnalisisIncidente",
            entidad_afectada="SolicitudEmergencia",
            id_entidad_afectada=solicitud_id,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()
    
    async def analyze_solicitud(
        self,
        db: Session,
        solicitud_id: UUID,
        force_reanalysis: bool = False,
    ) -> IncidentAnalysisResult:
        """
        Analiza una solicitud completamente:
        1. Obtiene la solicitud
        2. Transcribe audio si existe
        3. Clasifica el texto/transcripción
        4. Resuelve IDs de especialidad y servicio
        5. Guarda clasificación en BD
        6. Actualiza solicitud si aplica
        
        Args:
            db: Sesión de base de datos
            solicitud_id: ID de la solicitud a analizar
            force_reanalysis: Si True, reprocesa incluso si ya existe clasificación
            
        Returns:
            IncidentAnalysisResult con todos los detalles del análisis
        """
        # Obtener solicitud
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        
        if not solicitud:
            self.logger.error(f"Solicitud no encontrada: {solicitud_id}")
            raise not_found(f"Solicitud con ID {solicitud_id} no encontrada")
        
        # Verificar si ya existe clasificación reciente
        if not force_reanalysis:
            existing = db.query(ClasificacionIncidente).filter(
                ClasificacionIncidente.id_solicitud == solicitud_id
            ).first()
            if existing:
                self.logger.info(f"Clasificación existente para solicitud {solicitud_id}")
                return self._result_from_db_classification(db, existing)
        
        self.logger.info(f"Iniciando análisis de solicitud {solicitud_id}")
        
        # FASE 1: Transcripción de audio si existe
        transcripcion_audio = solicitud.transcripcion_audio
        estado_comprension = EstadoComprensionAudio.COMPRENDIDO
        
        if solicitud.descripcion_audio_url and not transcripcion_audio:
            self.logger.info(f"Transcribiendo audio: {solicitud.descripcion_audio_url}")
            try:
                transcription_result = await self.stt_service.transcribe_from_url(
                    solicitud.descripcion_audio_url
                )
                
                transcripcion_audio = transcription_result.texto
                estado_comprension = transcription_result.estado_comprension
                
                # Si el audio no fue entendible, registrar advertencia
                if estado_comprension == EstadoComprensionAudio.NO_ENTENDIBLE:
                    self.logger.warning(f"Audio no entendible en solicitud {solicitud_id}")
                    self._registrar_bitacora(
                        db=db,
                        solicitud_id=solicitud_id,
                        accion="Audio no entendible",
                        resultado=ResultadoAuditoria.ADVERTENCIA,
                        detalle="La transcripción de audio no fue posible o no fue claramente comprensible",
                    )
                elif estado_comprension == EstadoComprensionAudio.PARCIALMENTE_COMPRENDIDO:
                    self.logger.warning(f"Audio parcialmente comprendido en solicitud {solicitud_id}")
                    self._registrar_bitacora(
                        db=db,
                        solicitud_id=solicitud_id,
                        accion="Audio parcialmente comprendido",
                        resultado=ResultadoAuditoria.ADVERTENCIA,
                        detalle="La transcripción de audio se completó pero con comprensión parcial",
                    )
                
                # Actualizar solicitud con transcripción
                if transcripcion_audio:
                    solicitud.transcripcion_audio = transcripcion_audio
                    self.logger.info(f"Transcripción guardada: {len(transcripcion_audio)} caracteres")
            except Exception as e:
                self.logger.error(f"Error durante transcripción: {str(e)}")
                self._registrar_bitacora(
                    db=db,
                    solicitud_id=solicitud_id,
                    accion="Error en transcripción de audio",
                    resultado=ResultadoAuditoria.ERROR,
                    detalle=f"Error durante transcripción: {str(e)}",
                )
                raise
        elif solicitud.transcripcion_audio:
            # Si ya existe, usarla
            transcripcion_audio = solicitud.transcripcion_audio
        
        # FASE 2: Preparar texto para clasificación
        texto_para_clasificar = ""
        fuente_entrada = FuenteAnalisisIncidente.TEXTO_MANUAL
        
        # Priorizar texto manual, luego transcripción
        if solicitud.descripcion_texto and solicitud.descripcion_texto.strip():
            texto_para_clasificar = solicitud.descripcion_texto
            fuente_entrada = FuenteAnalisisIncidente.TEXTO_MANUAL
            
            if transcripcion_audio and transcripcion_audio.strip():
                # Si hay ambos, combinarlos
                texto_para_clasificar = f"{solicitud.descripcion_texto} {transcripcion_audio}"
                fuente_entrada = FuenteAnalisisIncidente.COMBINADO
                
        elif transcripcion_audio and transcripcion_audio.strip():
            texto_para_clasificar = transcripcion_audio
            fuente_entrada = FuenteAnalisisIncidente.TRANSCRIPCION_AUDIO
        
        # Validar que hay texto para clasificar
        if not texto_para_clasificar.strip():
            self.logger.warning(f"Sin texto para clasificar en solicitud {solicitud_id}")
            # Registrar advertencia en bitácora
            self._registrar_bitacora(
                db=db,
                solicitud_id=solicitud_id,
                accion="Análisis sin texto",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle="No hay descripción de texto ni transcripción de audio disponibles",
            )
            return IncidentAnalysisResult(
                solicitud_id=solicitud_id,
                descripcion_texto=solicitud.descripcion_texto,
                transcripcion_audio=transcripcion_audio,
                estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
                categoria_predicha=CategoriaIncidenteAuto.NO_ENTENDIBLE,
                fuente_entrada=fuente_entrada,
            )
        
        # FASE 3: Clasificar el incidente
        self.logger.info(f"Clasificando texto de solicitud {solicitud_id}")
        classification_result = self.classifier.classify(texto_para_clasificar)
        
        # FASE 4: Resolver IDs de especialidad y servicio
        id_especialidad = None
        id_servicio = None
        
        if classification_result.especialidad_sugerida:
            especialidad = db.query(Especialidad).filter(
                Especialidad.nombre_especialidad == classification_result.especialidad_sugerida
            ).first()
            if especialidad:
                id_especialidad = especialidad.id_especialidad
                self.logger.info(f"Especialidad encontrada: {classification_result.especialidad_sugerida}")
            else:
                self.logger.warning(
                    f"Especialidad no encontrada en BD: {classification_result.especialidad_sugerida}"
                )
        
        if classification_result.servicio_sugerido:
            servicio = db.query(Servicio).filter(
                Servicio.nombre_servicio == classification_result.servicio_sugerido
            ).first()
            if servicio:
                id_servicio = servicio.id_servicio
                self.logger.info(f"Servicio encontrado: {classification_result.servicio_sugerido}")
            else:
                self.logger.warning(
                    f"Servicio no encontrado en BD: {classification_result.servicio_sugerido}"
                )
        
        # FASE 5: Persistir clasificación en BD
        resultado_json = classification_result.to_dict()
        resultado_json["estado_comprension_audio"] = estado_comprension.value
        resultado_json["fuente_entrada"] = fuente_entrada.value
        
        clasificacion = ClasificacionIncidente(
            id_solicitud=solicitud_id,
            categoria_predicha=classification_result.categoria.value,
            subcategoria_predicha=classification_result.subcategoria,
            id_especialidad_requerida=id_especialidad,
            id_servicio_sugerido=id_servicio,
            nivel_urgencia_predicho=classification_result.nivel_urgencia.value if classification_result.nivel_urgencia else None,
            confianza_modelo=classification_result.confianza,
            modelo_utilizado="TextIncidentClassifier_v1_RulesBased",
            fuente_entrada=fuente_entrada.value,
            resultado_json=json.dumps(resultado_json, ensure_ascii=False),
        )
        
        db.add(clasificacion)
        
        # FASE 6: Actualizar solicitud
        if transcripcion_audio:
            solicitud.transcripcion_audio = transcripcion_audio
        
        # Actualizar categoría de incidente si no la tenía
        if not solicitud.categoria_incidente or not solicitud.categoria_incidente.strip():
            solicitud.categoria_incidente = classification_result.categoria.value
        
        # Nota: NO actualizamos nivel_urgencia de solicitud para no romper contrato existente
        # Solo persiste en ClasificacionIncidente
        
        db.commit()
        db.refresh(solicitud)
        db.refresh(clasificacion)
        
        # Registrar éxito en bitácora
        detalle_bitacora = f"Análisis completado: {classification_result.categoria.value}"
        if classification_result.confianza:
            detalle_bitacora += f" (confianza: {classification_result.confianza:.2%})"
        self._registrar_bitacora(
            db=db,
            solicitud_id=solicitud_id,
            accion="Análisis de incidente completado",
            resultado=ResultadoAuditoria.EXITO,
            detalle=detalle_bitacora,
        )
        
        self.logger.info(f"Análisis completado para solicitud {solicitud_id}")
        
        return IncidentAnalysisResult(
            solicitud_id=solicitud_id,
            descripcion_texto=solicitud.descripcion_texto,
            transcripcion_audio=transcripcion_audio,
            estado_comprension=estado_comprension,
            categoria_predicha=classification_result.categoria,
            subcategoria_predicha=classification_result.subcategoria,
            especialidad_sugerida=classification_result.especialidad_sugerida,
            id_especialidad_requerida=id_especialidad,
            servicio_sugerido=classification_result.servicio_sugerido,
            id_servicio_sugerido=id_servicio,
            nivel_urgencia_predicho=classification_result.nivel_urgencia,
            confianza_modelo=classification_result.confianza,
            fuente_entrada=fuente_entrada,
            observaciones=classification_result.observaciones,
        )
    
    def _result_from_db_classification(
        self,
        db: Session,
        clasificacion: ClasificacionIncidente,
    ) -> IncidentAnalysisResult:
        """Convierte una clasificación de BD a IncidentAnalysisResult"""
        # Cargar especialidad y servicio por ID
        especialidad_sugerida = None
        servicio_sugerido = None
        
        if clasificacion.id_especialidad_requerida:
            esp = db.query(Especialidad).filter(
                Especialidad.id_especialidad == clasificacion.id_especialidad_requerida
            ).first()
            if esp:
                especialidad_sugerida = esp.nombre_especialidad
        
        if clasificacion.id_servicio_sugerido:
            srv = db.query(Servicio).filter(
                Servicio.id_servicio == clasificacion.id_servicio_sugerido
            ).first()
            if srv:
                servicio_sugerido = srv.nombre_servicio
        
        # Obtener solicitud para datos complementarios
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == clasificacion.id_solicitud
        ).first()
        
        return IncidentAnalysisResult(
            solicitud_id=clasificacion.id_solicitud,
            descripcion_texto=solicitud.descripcion_texto if solicitud else None,
            transcripcion_audio=solicitud.transcripcion_audio if solicitud else None,
            categoria_predicha=CategoriaIncidenteAuto(clasificacion.categoria_predicha),
            subcategoria_predicha=clasificacion.subcategoria_predicha,
            especialidad_sugerida=especialidad_sugerida,
            id_especialidad_requerida=clasificacion.id_especialidad_requerida,
            servicio_sugerido=servicio_sugerido,
            id_servicio_sugerido=clasificacion.id_servicio_sugerido,
            nivel_urgencia_predicho=NivelUrgencia(clasificacion.nivel_urgencia_predicho) if clasificacion.nivel_urgencia_predicho else None,
            confianza_modelo=clasificacion.confianza_modelo or 0.0,
            fuente_entrada=FuenteAnalisisIncidente(clasificacion.fuente_entrada),
        )
