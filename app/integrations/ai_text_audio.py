"""
AI Text & Audio Integration Service
Façade that orchestrates speech-to-text and incident classification
"""

from typing import Optional
from uuid import UUID
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.speech_to_text_service import SpeechToTextService
from app.services.text_incident_classifier import TextIncidentClassifier
from app.services.incident_analysis_service import IncidentAnalysisService


class AITextAudioService:
    """
    Servicio de integración para IA de texto y audio
    Orquesta transcripción y análisis de incidentes
    """
    
    def __init__(self):
        self.provider = settings.ai_text_audio_provider
        self.stt_service = SpeechToTextService()
        self.classifier = TextIncidentClassifier()
        self.analysis_service = IncidentAnalysisService()
        self.logger = logger
    
    async def transcribe_audio(self, audio_url: str) -> dict:
        """
        Transcribe un archivo de audio desde URL
        
        Args:
            audio_url: URL del archivo de audio
            
        Returns:
            Dict con texto transcrito y metadatos
        """
        self.logger.info(f"Transcribiendo audio: {audio_url}")
        result = await self.stt_service.transcribe_from_url(audio_url)
        return result.to_dict()
    
    def classify_incident(self, text: str, min_confidence: float = 0.5) -> dict:
        """
        Clasifica un incidente basado en texto
        
        Args:
            text: Texto del incidente (manual o transcrito)
            min_confidence: Confianza mínima requerida para clasificación
            
        Returns:
            Dict con categoría, especialidad, servicio y metadatos
        """
        self.logger.info(f"Clasificando incidente: {text[:100]}...")
        result = self.classifier.classify_with_confidence_threshold(text, min_confidence)
        return result.to_dict()
    
    async def analyze_incident(
        self,
        db: Session,
        solicitud_id: UUID,
        force_reanalysis: bool = False,
    ) -> dict:
        """
        Análisis completo de incidente: transcripción + clasificación
        
        Args:
            db: Sesión de base de datos
            solicitud_id: ID de la solicitud a analizar
            force_reanalysis: Si True, reprocesa incluso si ya existe clasificación
            
        Returns:
            Dict con resultado completo del análisis
        """
        self.logger.info(f"Analizando incidente completo: {solicitud_id}")
        result = await self.analysis_service.analyze_solicitud(
            db,
            solicitud_id,
            force_reanalysis
        )
        return result.to_dict()

