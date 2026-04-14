"""
Speech-to-Text Service using faster-whisper
Handles audio transcription with configurable model size and language
"""

import io
import os
import tempfile
from typing import Optional, Tuple
import httpx
from loguru import logger

from app.core.config import settings
from app.core.enums import EstadoComprensionAudio
from faster_whisper import WhisperModel


class TranscriptionResult:
    """Resultado de una transcripción de audio"""
    def __init__(
        self,
        texto: str,
        idioma: Optional[str] = None,
        estado_comprension: EstadoComprensionAudio = EstadoComprensionAudio.COMPRENDIDO,
        duracion_segundos: Optional[float] = None,
        confianza_promedio: Optional[float] = None,
    ):
        self.texto = texto
        self.idioma = idioma
        self.estado_comprension = estado_comprension
        self.duracion_segundos = duracion_segundos
        self.confianza_promedio = confianza_promedio
        
    def to_dict(self) -> dict:
        return {
            "texto": self.texto,
            "idioma": self.idioma,
            "estado_comprension": self.estado_comprension.value,
            "duracion_segundos": self.duracion_segundos,
            "confianza_promedio": self.confianza_promedio,
        }


class SpeechToTextService:
    """Servicio para transcripción de audio usando faster-whisper"""
    
    _model_instance = None  # Singleton pattern para evitar cargar modelo múltiples veces
    
    def __init__(self):
        """Inicializa el servicio, cargando el modelo si es necesario"""
        self.config = settings
        self.model = self._load_model()
        
    @classmethod
    def _load_model(cls):
        """Carga el modelo de whisper de forma lazy (singleton)"""
        if cls._model_instance is None:
            try:
                logger.info(
                    f"Cargando modelo Whisper: {settings.stt_model_size} "
                    f"(device={settings.stt_device}, compute={settings.stt_compute_type})"
                )
                cls._model_instance = WhisperModel(
                    model_size_or_path=settings.stt_model_size,
                    device=settings.stt_device,
                    compute_type=settings.stt_compute_type,
                    num_workers=1,  # Single worker to avoid memory issues
                    cpu_threads=4,  # Adjust based on available CPU
                    download_root=os.path.join(tempfile.gettempdir(), "whisper_models"),
                )
                logger.info("Modelo Whisper cargado exitosamente")
            except Exception as e:
                logger.error(f"Error al cargar modelo Whisper: {e}")
                raise
        return cls._model_instance
    
    async def transcribe_from_url(
        self,
        audio_url: str,
        timeout_seconds: Optional[int] = None,
    ) -> TranscriptionResult:
        """
        Descarga un audio desde URL y lo transcribe
        
        Args:
            audio_url: URL del archivo de audio
            timeout_seconds: Timeout para descarga y transcripción
            
        Returns:
            TranscriptionResult con el texto transcrito y metadatos
        """
        timeout = timeout_seconds or self.config.stt_timeout_seconds
        
        try:
            # Descargar archivo de audio
            logger.info(f"Descargando audio desde: {audio_url}")
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(audio_url)
                response.raise_for_status()
                audio_bytes = response.content
                
            # Guardar en archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                resultado = await self.transcribe_from_file(tmp_path)
                return resultado
            finally:
                # Limpiar archivo temporal
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except httpx.HTTPError as e:
            logger.error(f"Error descargando audio: {e}")
            return TranscriptionResult(
                texto="",
                estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
            )
        except Exception as e:
            logger.error(f"Error en transcribe_from_url: {e}")
            return TranscriptionResult(
                texto="",
                estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
            )
    
    async def transcribe_from_file(
        self,
        file_path: str,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe un archivo de audio local
        
        Args:
            file_path: Ruta del archivo de audio
            language: Código de idioma (ej: 'es', 'en')
            
        Returns:
            TranscriptionResult con el texto transcrito y metadatos
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Archivo no encontrado: {file_path}")
                return TranscriptionResult(
                    texto="",
                    estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
                )
            
            # Validar tamaño de archivo
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.config.stt_max_file_size_mb:
                logger.warning(f"Archivo demasiado grande: {file_size_mb}MB")
                return TranscriptionResult(
                    texto="",
                    estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
                )
            
            logger.info(f"Transcribiendo archivo: {file_path} ({file_size_mb:.2f}MB)")
            
            language_code = language or self.config.stt_language
            
            # Transcribir
            segments, info = self.model.transcribe(
                file_path,
                language=language_code,
                beam_size=self.config.stt_beam_size,
                vad_filter=self.config.stt_vad_filter,
            )
            
            # Extraer texto de segmentos
            textos = []
            confianzas = []
            
            for segment in segments:
                if segment.text and segment.text.strip():
                    textos.append(segment.text.strip())
                    if hasattr(segment, 'confidence'):
                        confianzas.append(segment.confidence)
            
            texto_completo = " ".join(textos)
            
            if not texto_completo.strip():
                logger.warning("Transcripción vacía")
                return TranscriptionResult(
                    texto="",
                    idioma=info.language if hasattr(info, 'language') else None,
                    estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
                    duracion_segundos=info.duration if hasattr(info, 'duration') else None,
                )
            
            # Calcular confianza promedio
            confianza_promedio = None
            if confianzas:
                confianza_promedio = sum(confianzas) / len(confianzas)
            
            # Determinar estado de comprensión
            estado = EstadoComprensionAudio.COMPRENDIDO
            if confianza_promedio and confianza_promedio < 0.6:
                estado = EstadoComprensionAudio.PARCIALMENTE_COMPRENDIDO
            elif not confianza_promedio or len(texto_completo) < 3:
                estado = EstadoComprensionAudio.PARCIALMENTE_COMPRENDIDO
            
            logger.info(
                f"Transcripción exitosa: {len(texto_completo)} caracteres, "
                f"confianza={confianza_promedio}"
            )
            
            return TranscriptionResult(
                texto=texto_completo,
                idioma=info.language if hasattr(info, 'language') else language_code,
                estado_comprension=estado,
                duracion_segundos=info.duration if hasattr(info, 'duration') else None,
                confianza_promedio=confianza_promedio,
            )
            
        except Exception as e:
            logger.error(f"Error transcribiendo archivo: {e}")
            return TranscriptionResult(
                texto="",
                estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
            )
    
    async def transcribe_from_bytes(
        self,
        audio_bytes: bytes,
        file_extension: str = "mp3",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio desde bytes en memoria
        
        Args:
            audio_bytes: Contenido del archivo de audio
            file_extension: Extensión del archivo (mp3, wav, ogg, etc.)
            language: Código de idioma
            
        Returns:
            TranscriptionResult con el texto transcrito y metadatos
        """
        # Validar tamaño
        file_size_mb = len(audio_bytes) / (1024 * 1024)
        if file_size_mb > self.config.stt_max_file_size_mb:
            logger.warning(f"Datos de audio demasiado grandes: {file_size_mb}MB")
            return TranscriptionResult(
                texto="",
                estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
            )
        
        # Guardar datos en archivo temporal
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f".{file_extension}"
            ) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                resultado = await self.transcribe_from_file(tmp_path, language)
                return resultado
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except Exception as e:
            logger.error(f"Error transcribiendo bytes: {e}")
            return TranscriptionResult(
                texto="",
                estado_comprension=EstadoComprensionAudio.NO_ENTENDIBLE,
            )
