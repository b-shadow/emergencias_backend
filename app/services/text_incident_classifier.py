"""
Text-based Incident Classifier Service
Classifies vehicle incidents using rule-based approach with keywords and patterns
"""

import re
from typing import Optional, Dict, List, Tuple
from loguru import logger

from app.core.enums import (
    CategoriaIncidenteAuto,
    NivelUrgencia,
    EstadoComprensionAudio,
)


class ClassificationResult:
    """Resultado de clasificación de un incidente"""
    def __init__(
        self,
        categoria: CategoriaIncidenteAuto,
        subcategoria: Optional[str] = None,
        nivel_urgencia: Optional[NivelUrgencia] = None,
        confianza: float = 0.0,
        especialidad_sugerida: Optional[str] = None,
        servicio_sugerido: Optional[str] = None,
        observaciones: Optional[str] = None,
        fuente_clasificacion: str = "REGLAS_BASADAS",
    ):
        self.categoria = categoria
        self.subcategoria = subcategoria
        self.nivel_urgencia = nivel_urgencia
        self.confianza = confianza
        self.especialidad_sugerida = especialidad_sugerida
        self.servicio_sugerido = servicio_sugerido
        self.observaciones = observaciones
        self.fuente_clasificacion = fuente_clasificacion
        
    def to_dict(self) -> dict:
        return {
            "categoria": self.categoria.value,
            "subcategoria": self.subcategoria,
            "nivel_urgencia": self.nivel_urgencia.value if self.nivel_urgencia else None,
            "confianza": self.confianza,
            "especialidad_sugerida": self.especialidad_sugerida,
            "servicio_sugerido": self.servicio_sugerido,
            "observaciones": self.observaciones,
            "fuente_clasificacion": self.fuente_clasificacion,
        }


class TextIncidentClassifier:
    """Clasificador de incidentes vehiculares basado en reglas y palabras clave"""
    
    # Palabras clave por categoría de incidente
    KEYWORDS_BATERIA = {
        "batería", "bateria", "descargada", "descargado", "muerta", "no prende",
        "no enciende", "no arranca", "no anda", "sin poder", "se descargó",
        "dead battery", "discharged", "no se enciende",
    }
    
    KEYWORDS_COLISION = {
        "colisión", "colision", "choque", "impactó", "impacto", "accidente",
        "choqué", "colisioné", "me impactaron", "golpe", "chocado", "crash",
        "hit", "collision", "tengo daño", "daño frontal", "daño trasero",
        "daño lateral", "vidrio roto", "parachoques", "fender", "carrocería",
    }
    
    KEYWORDS_LLANTA = {
        "llanta", "llantas", "neumático", "neumáticos", "pinchada", "pinchado",
        "pinche", "desinflada", "desinfló", "pinchazo", "ponchada", "ponche",
        "sin aire", "vacía", "flat tire", "blowout", "puncture", "deflated",
    }
    
    KEYWORDS_SOBRECALENTAMIENTO = {
        "sobrecalentamiento", "sobrecaliente", "calentado", "caliente", "sale humo",
        "vapor", "recalenta", "recalentamiento", "anticongelante", "refrigeración",
        "temperatura", "termostato", "radiador", "overheat", "overheating", "steam",
        "hot", "temperature warning", "coolant",
    }
    
    KEYWORDS_INMOVILIZADO = {
        "varado", "parado", "inmovilizado", "no se mueve", "sin poder avanzar",
        "sin poder mover", "atrapado", "bloqueado", "estancado", "stuck",
        "stranded", "unable to move", "won't move", "can't move",
    }
    
    KEYWORDS_FALLA_ELECTRICA = {
        "eléctrica", "electrica", "electrical", "falla eléctrica", "problema eléctrico",
        "luces", "luz", "intermitentes", "alarma", "tablero", "dashboard",
        "batería baja", "fusible", "alternador", "motor de arranque", "starter",
    }
    
    KEYWORDS_FALLA_MECANICA = {
        "mecánica", "mecanica", "mechanical", "falla mecánica", "problema mecánico",
        "motor", "engine", "aceite", "oil", "correa", "manguera", "hose",
        "ruido extraño", "vibración", "vibracion",
    }
    
    # Mapeos de categoría a especialidad y servicio
    CATEGORY_MAPPINGS = {
        CategoriaIncidenteAuto.BATERIA_DESCARGADA: {
            "nivel_urgencia": NivelUrgencia.MEDIO,
            "especialidad": "ELECTRICIDAD_AUTOMOTRIZ",
            "servicio": "ENCENDIDO_BATERIA_DESCARGADA",
            "confianza_base": 0.8,
        },
        CategoriaIncidenteAuto.COLISION: {
            "nivel_urgencia": NivelUrgencia.ALTO,
            "especialidad": "CHAPERIA_CARROCERIA",
            "servicio": "REPARACION_CARROCERIA",
            "confianza_base": 0.85,
        },
        CategoriaIncidenteAuto.PINCHAZO_LLANTA: {
            "nivel_urgencia": NivelUrgencia.MEDIO,
            "especialidad": "GOMERIA_LLANTAS",
            "servicio": "REPARACION_LLANTA_PINCHADA",
            "confianza_base": 0.8,
        },
        CategoriaIncidenteAuto.SOBRECALENTAMIENTO: {
            "nivel_urgencia": NivelUrgencia.ALTO,
            "especialidad": "MECANICA_GENERAL",
            "servicio": "REVISION_SOBRECALENTAMIENTO",
            "confianza_base": 0.75,
        },
        CategoriaIncidenteAuto.VEHICULO_INMOVILIZADO: {
            "nivel_urgencia": NivelUrgencia.MEDIO,
            "especialidad": "AUXILIO_VIAL_RESCATE",
            "servicio": "REMOLQUE_VEHICULO",
            "confianza_base": 0.7,
        },
        CategoriaIncidenteAuto.FALLA_ELECTRICA: {
            "nivel_urgencia": NivelUrgencia.MEDIO,
            "especialidad": "ELECTRICIDAD_AUTOMOTRIZ",
            "servicio": "DIAGNOSTICO_ELECTRICO",
            "confianza_base": 0.65,
        },
        CategoriaIncidenteAuto.FALLA_MECANICA: {
            "nivel_urgencia": NivelUrgencia.MEDIO,
            "especialidad": "MECANICA_GENERAL",
            "servicio": "DIAGNOSTICO_MECANICO",
            "confianza_base": 0.6,
        },
        CategoriaIncidenteAuto.NO_ENTENDIBLE: {
            "nivel_urgencia": NivelUrgencia.BAJO,
            "especialidad": None,
            "servicio": None,
            "confianza_base": 0.0,
        },
        CategoriaIncidenteAuto.SIN_CLASIFICACION_CLARA: {
            "nivel_urgencia": NivelUrgencia.BAJO,
            "especialidad": None,
            "servicio": None,
            "confianza_base": 0.3,
        },
    }
    
    def __init__(self):
        """Inicializa el clasificador"""
        self.logger = logger
    
    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para clasificación"""
        if not text:
            return ""
        
        # Convertir a minúsculas
        text = text.lower()
        
        # Remover acentos (normalización simple)
        text = text.replace("á", "a").replace("é", "e").replace("í", "i")
        text = text.replace("ó", "o").replace("ú", "u")
        
        # Remover signos de puntuación pero mantener espacios
        text = re.sub(r"[^\w\s]", " ", text)
        
        # Remover espacios extras
        text = " ".join(text.split())
        
        return text
    
    def _calculate_match_score(
        self,
        text: str,
        keywords: set,
    ) -> Tuple[bool, float]:
        """
        Calcula puntuación de coincidencia con palabras clave
        
        Returns:
            Tupla (tiene_coincidencia, puntuacion)
        """
        normalized = self._normalize_text(text)
        words = set(normalized.split())
        
        # Normalizar palabras clave también
        normalized_keywords = set()
        for kw in keywords:
            nkw = self._normalize_text(kw)
            normalized_keywords.update(nkw.split())
        
        # Contar coincidencias
        matches = words & normalized_keywords
        if not matches:
            return False, 0.0
        
        # Calcular puntuación (proporción de palabras clave encontradas)
        score = len(matches) / len(normalized_keywords) if normalized_keywords else 0.0
        return True, min(score, 1.0)  # Cap at 1.0
    
    def classify(self, text: str) -> ClassificationResult:
        """
        Clasifica un incidente basado en texto
        
        Args:
            text: Texto del incidente (manual o transcrito)
            
        Returns:
            ClassificationResult con la clasificación y metadatos
        """
        if not text or not text.strip():
            self.logger.warning("Texto vacío recibido para clasificación")
            return ClassificationResult(
                categoria=CategoriaIncidenteAuto.NO_ENTENDIBLE,
                confianza=0.0,
            )
        
        # Buscar coincidencias con cada categoría
        scores = {}
        
        # Evaluar BATERIA_DESCARGADA
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_BATERIA)
        scores[CategoriaIncidenteAuto.BATERIA_DESCARGADA] = score if has_match else 0.0
        
        # Evaluar COLISION
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_COLISION)
        scores[CategoriaIncidenteAuto.COLISION] = score if has_match else 0.0
        
        # Evaluar PINCHAZO_LLANTA
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_LLANTA)
        scores[CategoriaIncidenteAuto.PINCHAZO_LLANTA] = score if has_match else 0.0
        
        # Evaluar SOBRECALENTAMIENTO
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_SOBRECALENTAMIENTO)
        scores[CategoriaIncidenteAuto.SOBRECALENTAMIENTO] = score if has_match else 0.0
        
        # Evaluar VEHICULO_INMOVILIZADO
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_INMOVILIZADO)
        scores[CategoriaIncidenteAuto.VEHICULO_INMOVILIZADO] = score if has_match else 0.0
        
        # Evaluar FALLA_ELECTRICA
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_FALLA_ELECTRICA)
        scores[CategoriaIncidenteAuto.FALLA_ELECTRICA] = score if has_match else 0.0
        
        # Evaluar FALLA_MECANICA
        has_match, score = self._calculate_match_score(text, self.KEYWORDS_FALLA_MECANICA)
        scores[CategoriaIncidenteAuto.FALLA_MECANICA] = score if has_match else 0.0
        
        # Encontrar categoría con mayor puntuación
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        # Determinar si la clasificación es clara (threshold 0.3)
        confidence_threshold = 0.3
        if best_score < confidence_threshold:
            self.logger.info(
                f"Clasificación poco clara: mejor='{best_category.value}' "
                f"(score={best_score:.2f}), usando SIN_CLASIFICACION_CLARA"
            )
            return ClassificationResult(
                categoria=CategoriaIncidenteAuto.SIN_CLASIFICACION_CLARA,
                confianza=best_score,
                observaciones="Texto muy genérico o incidente no identificado claramente",
            )
        
        # Obtener mapeo de la categoría
        mapping = self.CATEGORY_MAPPINGS.get(best_category)
        if not mapping:
            self.logger.warning(f"No hay mapeo para categoría: {best_category}")
            return ClassificationResult(
                categoria=CategoriaIncidenteAuto.SIN_CLASIFICACION_CLARA,
                confianza=0.0,
            )
        
        # Calcular confianza final
        base_confidence = mapping.get("confianza_base", 0.5)
        final_confidence = base_confidence * best_score  # Ajustar por score de palabras clave
        
        self.logger.info(
            f"Clasificación: {best_category.value} "
            f"(confianza={final_confidence:.2f}, score={best_score:.2f})"
        )
        
        return ClassificationResult(
            categoria=best_category,
            nivel_urgencia=mapping.get("nivel_urgencia"),
            especialidad_sugerida=mapping.get("especialidad"),
            servicio_sugerido=mapping.get("servicio"),
            confianza=final_confidence,
            observaciones=f"Coincidencia con palabras clave para '{best_category.value}'",
        )
    
    def classify_with_confidence_threshold(
        self,
        text: str,
        min_confidence: float = 0.5,
    ) -> ClassificationResult:
        """
        Clasifica pero valida confianza mínima
        
        Args:
            text: Texto del incidente
            min_confidence: Confianza mínima requerida
            
        Returns:
            ClassificationResult (puede ser NO_ENTENDIBLE si no cumple umbral)
        """
        result = self.classify(text)
        
        if result.confianza < min_confidence and result.categoria != CategoriaIncidenteAuto.NO_ENTENDIBLE:
            self.logger.warning(
                f"Clasificación por debajo del umbral: {result.categoria.value} "
                f"(confianza={result.confianza:.2f} < {min_confidence})"
            )
            return ClassificationResult(
                categoria=CategoriaIncidenteAuto.SIN_CLASIFICACION_CLARA,
                confianza=result.confianza,
                observaciones="Confianza insuficiente para clasificación definitiva",
            )
        
        return result
