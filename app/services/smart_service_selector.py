from __future__ import annotations

import re

from app.core.enums import TipoSeguroVehiculo


class SmartServiceSelector:
    @staticmethod
    def _normalize(text: str | None) -> str:
        value = (text or "").lower()
        value = (
            value.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
        )
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        return " ".join(value.split())

    @staticmethod
    def suggest(descripcion: str | None, tipo_seguro: str | None, categoria_incidente: str | None) -> dict:
        text = SmartServiceSelector._normalize(descripcion)
        categoria = SmartServiceSelector._normalize(categoria_incidente)
        seguro = (tipo_seguro or TipoSeguroVehiculo.SIN_SEGURO.value).upper()

        prioridad = "BAJA"
        requiere_grua = False
        requiere_cotizacion_previa = True
        aplica_pago_minimo_ida = True
        servicios: list[str] = []
        especialidades: list[str] = []
        motivo = "Sin patron claro, requiere evaluacion inicial"

        if any(k in text for k in ["incendio", "fuego", "explosion", "humo intenso", "olor a gasolina"]):
            prioridad = "ALTA"
            requiere_grua = True
            motivo = "Riesgo critico detectado"
            servicios = ["GRUA", "REVISION_SOBRECALENTAMIENTO", "DIAGNOSTICO_GENERAL"]
            especialidades = ["MECANICA_GENERAL", "AUXILIO_VIAL_RESCATE"]
        elif any(k in text for k in ["no enciende", "apagado", "se apaga", "no arranca", "bateria", "descargada", "sin corriente"]):
            prioridad = "ALTA"
            requiere_grua = True
            motivo = "Falla de arranque o bateria"
            servicios = ["GRUA", "ENCENDIDO_BATERIA_DESCARGADA", "DIAGNOSTICO_ELECTRICO"]
            especialidades = ["ELECTRICIDAD_AUTOMOTRIZ", "AUXILIO_VIAL_RESCATE"]
        elif any(k in text for k in ["choque", "colision", "accidente", "golpe", "carroceria", "parachoques"]):
            prioridad = "ALTA"
            requiere_grua = True
            motivo = "Incidente de carroceria o accidente"
            servicios = ["GRUA", "REPARACION_CARROCERIA", "DIAGNOSTICO_GENERAL"]
            especialidades = ["CHAPERIA_CARROCERIA", "MECANICA_GENERAL"]
        elif any(k in text for k in ["llanta", "neumatico", "pinch", "ponch", "desinfl", "flat tire"]):
            prioridad = "MEDIA"
            motivo = "Problema en llanta o neumatico"
            servicios = ["REPARACION_LLANTA_PINCHADA", "CAMBIO_LLANTA", "BALANCEO_Y_ALINEACION"]
            especialidades = ["GOMERIA_LLANTAS", "MECANICA_GENERAL"]
        elif any(k in text for k in ["sobrecalent", "calienta", "temperatura", "radiador", "anticongelante", "vapor"]):
            prioridad = "ALTA"
            requiere_grua = True
            motivo = "Posible sobrecalentamiento o falla en refrigeracion"
            servicios = ["REVISION_SOBRECALENTAMIENTO", "DIAGNOSTICO_GENERAL", "GRUA"]
            especialidades = ["MECANICA_GENERAL"]
        elif any(k in text for k in ["freno", "direccion", "transmision", "cambio", "embrague", "motor", "ruido", "vibracion"]):
            prioridad = "MEDIA"
            motivo = "Falla mecanica o de seguridad detectada"
            servicios = ["DIAGNOSTICO_MECANICO", "REVISION_SISTEMA_FRENOS", "REVISION_TRANSMISION"]
            especialidades = ["MECANICA_GENERAL", "SISTEMA_FRENOS", "TRANSMISION_EMBRAGUE"]
        elif any(k in text for k in ["electrico", "luces", "fusible", "alternador", "tablero", "starter", "bateria baja"]):
            prioridad = "MEDIA"
            motivo = "Falla electrica probable"
            servicios = ["DIAGNOSTICO_ELECTRICO", "REPARACION_SISTEMA_ELECTRICO"]
            especialidades = ["ELECTRICIDAD_AUTOMOTRIZ"]

        if categoria in {"colision_visible", "colision"} and "REPARACION_CARROCERIA" not in servicios:
            servicios = ["REPARACION_CARROCERIA", *servicios]
            especialidades = ["CHAPERIA_CARROCERIA", *especialidades]
            prioridad = "ALTA"

        if seguro == TipoSeguroVehiculo.SIN_SEGURO.value and "AUXILIO_RAPIDO" not in servicios:
            servicios = [*servicios, "AUXILIO_RAPIDO"]
            requiere_cotizacion_previa = True

        if not servicios:
            servicios = ["DIAGNOSTICO_GENERAL"]
        if not especialidades:
            especialidades = ["MECANICA_GENERAL"]

        primary_service = servicios[0]
        if primary_service == "GRUA":
            primary_service = "REMOLQUE_VEHICULO"

        servicios_unicos = list(dict.fromkeys(servicios))
        especialidades_unicas = list(dict.fromkeys(especialidades))

        return {
            "servicio_sugerido": primary_service,
            "servicios_sugeridos": servicios_unicos,
            "especialidades_sugeridas": especialidades_unicas,
            "motivo": motivo,
            "prioridad": prioridad,
            "requiere_grua": requiere_grua,
            "requiere_cotizacion_previa": requiere_cotizacion_previa,
            "aplica_pago_minimo_ida": aplica_pago_minimo_ida,
        }
