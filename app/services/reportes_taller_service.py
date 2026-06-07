from __future__ import annotations

import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.core.enums import EstadoAsignacion, EstadoOrdenRecojo, RolUsuario
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.cliente import Cliente
from app.models.orden_recojo import OrdenRecojo
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.resultado_servicio import ResultadoServicio
from app.models.taller import Taller
from app.models.taller_servicio import TallerServicio
from app.models.trabajador import Trabajador
from app.schemas.estadisticas_taller import (
    ColumnaReporteTaller,
    ReporteConsultaTallerResponse,
)


class ReportesTallerService:
    """Genera reportes tabulares interpretando consultas libres del taller."""

    @staticmethod
    def generar_reporte(
        db: Session,
        id_taller: str,
        consulta: str,
    ) -> ReporteConsultaTallerResponse:
        consulta_limpia = (consulta or "").strip()
        consulta_norm = ReportesTallerService._normalizar(consulta_limpia)

        if ReportesTallerService._es_reporte_usuarios(consulta_norm):
            return ReportesTallerService._reporte_usuarios_empresa(
                db=db,
                id_taller=id_taller,
                consulta_original=consulta_limpia,
            )

        if ReportesTallerService._es_reporte_ordenes_finalizadas(consulta_norm):
            return ReportesTallerService._reporte_ordenes_finalizadas(
                db=db,
                id_taller=id_taller,
                consulta_original=consulta_limpia,
            )

        return ReporteConsultaTallerResponse(
            consulta_original=consulta_limpia,
            tipo_reporte="no_soportado",
            titulo="Consulta todavía no soportada",
            descripcion="Por ahora el taller puede pedir usuarios del taller o órdenes finalizadas.",
            columnas=[],
            filas=[],
            total_registros=0,
            mensaje=(
                "Prueba con frases como 'quiero ver todos los usuarios de la empresa' "
                "o 'quiero ver todas las órdenes finalizadas'."
            ),
        )

    @staticmethod
    def _reporte_usuarios_empresa(
        db: Session,
        id_taller: str,
        consulta_original: str,
    ) -> ReporteConsultaTallerResponse:
        taller = (
            db.query(Taller)
            .options(
                joinedload(Taller.usuario),
                joinedload(Taller.trabajadores).joinedload(Trabajador.usuario),
            )
            .filter(Taller.id_taller == id_taller)
            .first()
        )

        if not taller:
            return ReporteConsultaTallerResponse(
                consulta_original=consulta_original,
                tipo_reporte="usuarios_empresa",
                titulo="Usuarios del taller",
                descripcion="No se encontró el taller autenticado.",
                columnas=ReportesTallerService._columnas_usuarios(),
                filas=[],
                total_registros=0,
                mensaje="No se pudo ubicar el taller asociado a la sesión actual.",
            )

        filas: list[dict[str, object]] = []

        if taller.usuario:
            filas.append(
                {
                    "tipo_usuario": "Administrador del taller",
                    "nombre_completo": taller.usuario.nombre_completo,
                    "correo": taller.usuario.correo,
                    "rol": ReportesTallerService._enum_value(taller.usuario.rol),
                    "telefono": taller.telefono or "",
                    "licencia": "",
                    "activo": "Sí" if taller.usuario.es_activo else "No",
                    "fecha_registro": ReportesTallerService._fmt_dt(taller.fecha_registro),
                }
            )

        trabajadores = sorted(
            taller.trabajadores or [],
            key=lambda item: (
                item.usuario.nombre_completo.lower()
                if item.usuario and item.usuario.nombre_completo
                else ""
            ),
        )
        for trabajador in trabajadores:
            nombre = trabajador.usuario.nombre_completo if trabajador.usuario else ""
            correo = trabajador.usuario.correo if trabajador.usuario else ""
            rol = (
                ReportesTallerService._enum_value(trabajador.usuario.rol)
                if trabajador.usuario
                else RolUsuario.TRABAJADOR.value
            )
            activo = (
                "Sí"
                if (trabajador.usuario.es_activo if trabajador.usuario else trabajador.es_activo)
                else "No"
            )
            filas.append(
                {
                    "tipo_usuario": "Trabajador",
                    "nombre_completo": nombre,
                    "correo": correo,
                    "rol": rol,
                    "telefono": trabajador.telefono or "",
                    "licencia": trabajador.licencia_conducir or "",
                    "activo": activo,
                    "fecha_registro": ReportesTallerService._fmt_dt(trabajador.fecha_registro),
                }
            )

        return ReporteConsultaTallerResponse(
            consulta_original=consulta_original,
            tipo_reporte="usuarios_empresa",
            titulo="Usuarios del taller",
            descripcion="Equipo administrativo y operativo asociado al taller.",
            columnas=ReportesTallerService._columnas_usuarios(),
            filas=filas,
            total_registros=len(filas),
            mensaje=None if filas else "No hay usuarios asociados al taller todavía.",
        )

    @staticmethod
    def _reporte_ordenes_finalizadas(
        db: Session,
        id_taller: str,
        consulta_original: str,
    ) -> ReporteConsultaTallerResponse:
        asignaciones = (
            db.query(AsignacionAtencion)
            .options(
                joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.cliente),
                joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.vehiculo),
                joinedload(AsignacionAtencion.orden_recojo)
                .joinedload(OrdenRecojo.trabajador)
                .joinedload(Trabajador.usuario),
                joinedload(AsignacionAtencion.resultados)
                .joinedload(ResultadoServicio.taller_servicio)
                .joinedload(TallerServicio.servicio),
            )
            .filter(
                AsignacionAtencion.id_taller == id_taller,
                AsignacionAtencion.estado_asignacion == EstadoAsignacion.FINALIZADA,
            )
            .order_by(AsignacionAtencion.fecha_fin_atencion.desc().nullslast())
            .all()
        )

        filas: list[dict[str, object]] = []
        for asignacion in asignaciones:
            solicitud = asignacion.solicitud
            cliente = solicitud.cliente if solicitud else None
            vehiculo = solicitud.vehiculo if solicitud else None
            orden = asignacion.orden_recojo
            trabajador = orden.trabajador if orden else None
            trabajador_usuario = trabajador.usuario if trabajador else None
            resultados = asignacion.resultados or []

            base_fila = {
                "codigo_solicitud": solicitud.codigo_solicitud if solicitud else "",
                "cliente": ReportesTallerService._nombre_cliente(cliente),
                "telefono_cliente": cliente.telefono if cliente and cliente.telefono else "",
                "placa": vehiculo.placa if vehiculo and vehiculo.placa else "",
                "marca": vehiculo.marca if vehiculo and vehiculo.marca else "",
                "modelo": vehiculo.modelo if vehiculo and vehiculo.modelo else "",
                "trabajador": (
                    trabajador_usuario.nombre_completo
                    if trabajador_usuario
                    else ""
                ),
                "estado_orden": (
                    ReportesTallerService._enum_value(orden.estado_orden)
                    if orden
                    else EstadoOrdenRecojo.FINALIZADA.value
                ),
                "fecha_llegada_auxilio": (
                    ReportesTallerService._fmt_dt(orden.fecha_llegada_auxilio) if orden else ""
                ),
                "fecha_inicio_taller": (
                    ReportesTallerService._fmt_dt(orden.fecha_inicio_regreso) if orden else ""
                ),
                "fecha_llegada_taller": (
                    ReportesTallerService._fmt_dt(orden.fecha_llegada_taller) if orden else ""
                ),
                "fecha_completada": ReportesTallerService._fmt_dt(asignacion.fecha_fin_atencion),
            }

            if not resultados:
                filas.append(
                    {
                        **base_fila,
                        "servicio": "",
                        "diagnostico": "",
                        "solucion_aplicada": "",
                        "estado_resultado": "",
                    }
                )
                continue

            for resultado in resultados:
                nombre_servicio = ""
                if resultado.taller_servicio and resultado.taller_servicio.servicio:
                    nombre_servicio = resultado.taller_servicio.servicio.nombre_servicio
                filas.append(
                    {
                        **base_fila,
                        "servicio": nombre_servicio,
                        "diagnostico": resultado.diagnostico or "",
                        "solucion_aplicada": resultado.solucion_aplicada or "",
                        "estado_resultado": ReportesTallerService._enum_value(resultado.estado_resultado),
                    }
                )

        return ReporteConsultaTallerResponse(
            consulta_original=consulta_original,
            tipo_reporte="ordenes_finalizadas",
            titulo="Órdenes finalizadas",
            descripcion="Órdenes de recojo y resultados de servicio terminados por el taller.",
            columnas=ReportesTallerService._columnas_ordenes_finalizadas(),
            filas=filas,
            total_registros=len(filas),
            mensaje=None if filas else "Todavía no hay órdenes finalizadas para mostrar.",
        )

    @staticmethod
    def _columnas_usuarios() -> list[ColumnaReporteTaller]:
        return [
            ColumnaReporteTaller(key="tipo_usuario", label="Tipo de usuario"),
            ColumnaReporteTaller(key="nombre_completo", label="Nombre completo"),
            ColumnaReporteTaller(key="correo", label="Correo"),
            ColumnaReporteTaller(key="rol", label="Rol"),
            ColumnaReporteTaller(key="telefono", label="Teléfono"),
            ColumnaReporteTaller(key="licencia", label="Licencia"),
            ColumnaReporteTaller(key="activo", label="Activo"),
            ColumnaReporteTaller(key="fecha_registro", label="Fecha de registro"),
        ]

    @staticmethod
    def _columnas_ordenes_finalizadas() -> list[ColumnaReporteTaller]:
        return [
            ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
            ColumnaReporteTaller(key="cliente", label="Cliente"),
            ColumnaReporteTaller(key="telefono_cliente", label="Teléfono cliente"),
            ColumnaReporteTaller(key="placa", label="Placa"),
            ColumnaReporteTaller(key="marca", label="Marca"),
            ColumnaReporteTaller(key="modelo", label="Modelo"),
            ColumnaReporteTaller(key="trabajador", label="Trabajador"),
            ColumnaReporteTaller(key="estado_orden", label="Estado orden"),
            ColumnaReporteTaller(key="fecha_llegada_auxilio", label="Llegada al auxilio"),
            ColumnaReporteTaller(key="fecha_inicio_taller", label="Salida al taller"),
            ColumnaReporteTaller(key="fecha_llegada_taller", label="Llegada al taller"),
            ColumnaReporteTaller(key="fecha_completada", label="Completada"),
            ColumnaReporteTaller(key="servicio", label="Servicio"),
            ColumnaReporteTaller(key="diagnostico", label="Diagnóstico"),
            ColumnaReporteTaller(key="solucion_aplicada", label="Solución aplicada"),
            ColumnaReporteTaller(key="estado_resultado", label="Estado resultado"),
        ]

    @staticmethod
    def _es_reporte_usuarios(consulta: str) -> bool:
        return (
            "usuario" in consulta
            or "usuarios" in consulta
            or "trabajador" in consulta
            or "trabajadores" in consulta
            or "personal" in consulta
            or "equipo" in consulta
        )

    @staticmethod
    def _es_reporte_ordenes_finalizadas(consulta: str) -> bool:
        menciona_ordenes = any(
            termino in consulta
            for termino in [
                "orden finalizada",
                "ordenes finalizadas",
                "orden finalizada",
                "orden",
                "ordenes",
                "resultado de servicio",
                "resultados de servicio",
                "servicios finalizados",
                "atenciones finalizadas",
            ]
        )
        menciona_fin = any(
            termino in consulta
            for termino in [
                "finalizada",
                "finalizadas",
                "terminada",
                "terminadas",
                "completada",
                "completadas",
                "atendida",
                "atendidas",
            ]
        )
        return menciona_ordenes and menciona_fin

    @staticmethod
    def _normalizar(texto: str) -> str:
        texto = texto.lower().strip()
        texto = "".join(
            caracter
            for caracter in unicodedata.normalize("NFD", texto)
            if unicodedata.category(caracter) != "Mn"
        )
        return " ".join(texto.split())

    @staticmethod
    def _fmt_dt(valor: datetime | None) -> str:
        if not valor:
            return ""
        return valor.strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _enum_value(valor: object) -> str:
        return valor.value if hasattr(valor, "value") else str(valor or "")

    @staticmethod
    def _nombre_cliente(cliente: object | None) -> str:
        if not cliente:
            return ""
        nombre = getattr(cliente, "nombre", "") or ""
        apellido = getattr(cliente, "apellido", "") or ""
        return f"{nombre} {apellido}".strip()
