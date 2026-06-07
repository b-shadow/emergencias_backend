from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.enums import (
    EstadoAprobacionTaller,
    EstadoAsignacion,
    EstadoCotizacion,
    EstadoEnvioNotificacion,
    EstadoLecturaNotificacion,
    EstadoOperativoTaller,
    EstadoOrdenRecojo,
    EstadoPostulacion,
    EstadoResultado,
    ResultadoAuditoria,
    RolUsuario,
)
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.bitacora import Bitacora
from app.models.calificacion_atencion import CalificacionAtencion
from app.models.cliente import Cliente
from app.models.cotizacion_atencion import CotizacionAtencion
from app.models.notificacion import Notificacion
from app.models.orden_recojo import OrdenRecojo
from app.models.pago_atencion import PagoAtencion
from app.models.postulacion_taller import PostulacionTaller
from app.models.resultado_servicio import ResultadoServicio
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller
from app.models.taller_servicio import TallerServicio
from app.models.tenant_taller import TenantTaller
from app.models.trabajador import Trabajador
from app.models.usuario import Usuario
from app.schemas.estadisticas_taller import ColumnaReporteTaller, ReporteConsultaTallerResponse


@dataclass
class ReportScope:
    rol: RolUsuario
    id_taller: str | None = None
    id_tenant: str | None = None


class ReportesConsultaService:
    """Parser y generador de reportes tabulares con restricciones por rol."""

    @classmethod
    def generar_reporte(
        cls,
        db: Session,
        consulta: str,
        scope: ReportScope,
    ) -> ReporteConsultaTallerResponse:
        consulta_original = (consulta or "").strip()
        consulta_norm = cls._normalize(consulta_original)
        named = cls._extract_named_filters(consulta_original, consulta_norm)

        if cls._matches(consulta_norm, "usuarios"):
            return cls._report_usuarios(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "trabajadores"):
            return cls._report_trabajadores(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "clientes"):
            return cls._report_clientes(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "postulaciones"):
            return cls._report_postulaciones(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "cotizaciones"):
            return cls._report_cotizaciones(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "asignaciones"):
            return cls._report_asignaciones(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "ordenes"):
            return cls._report_ordenes(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "servicios_realizados"):
            return cls._report_resultados_servicio(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "pagos"):
            return cls._report_pagos(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "talleres") and scope.rol == RolUsuario.ADMINISTRADOR:
            return cls._report_talleres(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "notificaciones"):
            return cls._report_notificaciones(db, scope, consulta_original, consulta_norm, named)
        if cls._matches(consulta_norm, "bitacora") and scope.rol == RolUsuario.ADMINISTRADOR:
            return cls._report_bitacora(db, scope, consulta_original, consulta_norm, named)

        return ReporteConsultaTallerResponse(
            consulta_original=consulta_original,
            tipo_reporte="no_soportado",
            titulo="Consulta no soportada todavía",
            descripcion="La consulta no coincide con un reporte conocido dentro del sistema.",
            columnas=[],
            filas=[],
            total_registros=0,
            mensaje=(
                "Puedes pedir usuarios, trabajadores, clientes, postulaciones, cotizaciones, "
                "asignaciones, órdenes, servicios realizados, pagos, notificaciones y más."
            ),
        )

    @classmethod
    def _report_usuarios(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        tenant = cls._resolve_tenant_if_present(db, named.get("empresa"))

        if scope.rol == RolUsuario.ADMINISTRADOR and ("todos los usuarios" in consulta_norm or consulta_norm.strip() == "quiero ver todos los usuarios"):
            usuarios = (
                db.query(Usuario)
                .options(
                    joinedload(Usuario.cliente),
                    joinedload(Usuario.taller).joinedload(Taller.tenant),
                    joinedload(Usuario.trabajador).joinedload(Trabajador.taller).joinedload(Taller.tenant),
                )
                .order_by(Usuario.nombre_completo.asc())
                .all()
            )
            filas = [cls._usuario_global_row(usuario) for usuario in usuarios]
            return cls._build_response(
                consulta_original,
                "usuarios_globales",
                "Usuarios del sistema",
                "Todos los usuarios registrados en la plataforma.",
                cls._columns_usuarios_globales(),
                filas,
                "No hay usuarios registrados en el sistema." if not filas else None,
            )

        if tenant is None and scope.id_tenant:
            tenant = db.query(TenantTaller).filter(TenantTaller.id_tenant == scope.id_tenant).first()

        if not tenant:
            return cls._build_response(
                consulta_original,
                "usuarios_empresa",
                "Usuarios de la empresa",
                "No se pudo resolver la empresa solicitada.",
                cls._columns_usuarios_empresa(),
                [],
                "No encontramos la empresa o tenant pedido en la consulta.",
            )

        talleres = (
            db.query(Taller)
            .options(joinedload(Taller.usuario), joinedload(Taller.trabajadores).joinedload(Trabajador.usuario), joinedload(Taller.tenant))
            .filter(Taller.id_tenant == tenant.id_tenant)
            .order_by(Taller.nombre_taller.asc())
            .all()
        )
        filas: list[dict[str, object]] = []
        for taller in talleres:
            if taller.usuario:
                filas.append(
                    {
                        "empresa": tenant.nombre_tenant,
                        "taller": taller.nombre_taller,
                        "tipo_usuario": "Administrador del taller",
                        "nombre_completo": taller.usuario.nombre_completo,
                        "correo": taller.usuario.correo,
                        "rol": cls._enum_value(taller.usuario.rol),
                        "telefono": taller.telefono or "",
                        "licencia": "",
                        "activo": "Sí" if taller.usuario.es_activo else "No",
                        "fecha_registro": cls._fmt_dt(taller.fecha_registro),
                    }
                )
            for trabajador in sorted(taller.trabajadores or [], key=lambda t: (t.usuario.nombre_completo.lower() if t.usuario else "")):
                filas.append(
                    {
                        "empresa": tenant.nombre_tenant,
                        "taller": taller.nombre_taller,
                        "tipo_usuario": "Trabajador",
                        "nombre_completo": trabajador.usuario.nombre_completo if trabajador.usuario else "",
                        "correo": trabajador.usuario.correo if trabajador.usuario else "",
                        "rol": cls._enum_value(trabajador.usuario.rol) if trabajador.usuario else RolUsuario.TRABAJADOR.value,
                        "telefono": trabajador.telefono or "",
                        "licencia": trabajador.licencia_conducir or "",
                        "activo": "Sí" if trabajador.es_activo else "No",
                        "fecha_registro": cls._fmt_dt(trabajador.fecha_registro),
                    }
                )
        return cls._build_response(
            consulta_original,
            "usuarios_empresa",
            "Usuarios de la empresa",
            "Usuarios asociados al tenant o empresa consultada.",
            cls._columns_usuarios_empresa(),
            filas,
            "No hay usuarios asociados a esta empresa." if not filas else None,
        )

    @classmethod
    def _report_trabajadores(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(Trabajador)
            .options(joinedload(Trabajador.usuario), joinedload(Trabajador.taller).joinedload(Taller.tenant))
        )

        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            query = query.filter(Trabajador.id_taller == scope.id_taller)
        elif scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(db, named.get("empresa"))
            if tenant:
                query = query.join(Taller, Trabajador.id_taller == Taller.id_taller).filter(Taller.id_tenant == tenant.id_tenant)

        if "inactivo" in consulta_norm or "inactivos" in consulta_norm:
            query = query.filter(Trabajador.es_activo.is_(False))
        elif "activo" in consulta_norm or "activos" in consulta_norm:
            query = query.filter(Trabajador.es_activo.is_(True))

        trabajadores = query.order_by(Trabajador.fecha_registro.desc()).all()
        filas = [
            {
                "empresa": t.taller.tenant.nombre_tenant if t.taller and t.taller.tenant else "",
                "taller": t.taller.nombre_taller if t.taller else "",
                "nombre_completo": t.usuario.nombre_completo if t.usuario else "",
                "correo": t.usuario.correo if t.usuario else "",
                "telefono": t.telefono or "",
                "licencia": t.licencia_conducir or "",
                "activo": "Sí" if t.es_activo else "No",
                "fecha_registro": cls._fmt_dt(t.fecha_registro),
            }
            for t in trabajadores
        ]
        return cls._build_response(
            consulta_original,
            "trabajadores",
            "Trabajadores",
            "Listado de trabajadores según el alcance permitido.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="nombre_completo", label="Nombre completo"),
                ColumnaReporteTaller(key="correo", label="Correo"),
                ColumnaReporteTaller(key="telefono", label="Teléfono"),
                ColumnaReporteTaller(key="licencia", label="Licencia"),
                ColumnaReporteTaller(key="activo", label="Activo"),
                ColumnaReporteTaller(key="fecha_registro", label="Fecha de registro"),
            ],
            filas,
            "No encontramos trabajadores para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_clientes(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        if scope.rol == RolUsuario.ADMINISTRADOR and "todos los clientes" in consulta_norm:
            clientes = db.query(Cliente).options(joinedload(Cliente.usuario)).order_by(Cliente.nombre.asc(), Cliente.apellido.asc()).all()
        else:
            clientes = cls._clientes_interactuados(db, scope, tenant_name=named.get("empresa"))

        if named.get("cliente"):
            nombre = cls._normalize(named["cliente"] or "")
            clientes = [
                cliente
                for cliente in clientes
                if nombre in cls._normalize(cls._nombre_cliente(cliente))
            ]

        filas = [
            {
                "nombre_completo": cls._nombre_cliente(c),
                "correo": c.usuario.correo if c.usuario else "",
                "telefono": c.telefono or "",
                "ci": c.ci or "",
                "direccion": c.direccion or "",
                "fecha_registro": cls._fmt_dt(c.fecha_registro),
            }
            for c in clientes
        ]
        return cls._build_response(
            consulta_original,
            "clientes",
            "Clientes",
            "Clientes visibles según el alcance del rol y la interacción con el taller.",
            [
                ColumnaReporteTaller(key="nombre_completo", label="Nombre completo"),
                ColumnaReporteTaller(key="correo", label="Correo"),
                ColumnaReporteTaller(key="telefono", label="Teléfono"),
                ColumnaReporteTaller(key="ci", label="CI"),
                ColumnaReporteTaller(key="direccion", label="Dirección"),
                ColumnaReporteTaller(key="fecha_registro", label="Fecha de registro"),
            ],
            filas,
            "No encontramos clientes para ese criterio." if not filas else None,
        )

    @classmethod
    def _report_postulaciones(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(PostulacionTaller)
            .options(
                joinedload(PostulacionTaller.taller).joinedload(Taller.tenant),
                joinedload(PostulacionTaller.solicitud).joinedload(SolicitudEmergencia.cliente),
            )
        )
        query = cls._scope_postulaciones(query, scope, named.get("empresa"))

        estado_map = {
            "aceptada": EstadoPostulacion.ACEPTADA,
            "aceptadas": EstadoPostulacion.ACEPTADA,
            "rechazada": EstadoPostulacion.RECHAZADA,
            "rechazadas": EstadoPostulacion.RECHAZADA,
            "expirada": EstadoPostulacion.EXPIRADA,
            "expiradas": EstadoPostulacion.EXPIRADA,
            "retirada": EstadoPostulacion.RETIRADA,
            "retiradas": EstadoPostulacion.RETIRADA,
        }
        for palabra, estado in estado_map.items():
            if palabra in consulta_norm:
                query = query.filter(PostulacionTaller.estado_postulacion == estado)
                break

        rows = query.order_by(PostulacionTaller.fecha_postulacion.desc()).all()
        filas = [
            {
                "empresa": r.taller.tenant.nombre_tenant if r.taller and r.taller.tenant else "",
                "taller": r.taller.nombre_taller if r.taller else "",
                "codigo_solicitud": r.solicitud.codigo_solicitud if r.solicitud else "",
                "cliente": cls._nombre_cliente(r.solicitud.cliente if r.solicitud else None),
                "estado_postulacion": cls._enum_value(r.estado_postulacion),
                "eta_minutos": r.tiempo_estimado_llegada_min or "",
                "fecha_postulacion": cls._fmt_dt(r.fecha_postulacion),
                "fecha_respuesta": cls._fmt_dt(r.fecha_respuesta),
            }
            for r in rows
        ]
        return cls._build_response(
            consulta_original,
            "postulaciones",
            "Postulaciones",
            "Postulaciones registradas dentro del alcance de la consulta.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
                ColumnaReporteTaller(key="cliente", label="Cliente"),
                ColumnaReporteTaller(key="estado_postulacion", label="Estado"),
                ColumnaReporteTaller(key="eta_minutos", label="ETA minutos"),
                ColumnaReporteTaller(key="fecha_postulacion", label="Fecha postulación"),
                ColumnaReporteTaller(key="fecha_respuesta", label="Fecha respuesta"),
            ],
            filas,
            "No encontramos postulaciones para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_cotizaciones(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(CotizacionAtencion)
            .options(
                joinedload(CotizacionAtencion.postulacion).joinedload(PostulacionTaller.taller).joinedload(Taller.tenant),
                joinedload(CotizacionAtencion.postulacion).joinedload(PostulacionTaller.solicitud).joinedload(SolicitudEmergencia.cliente),
                joinedload(CotizacionAtencion.taller_servicio).joinedload(TallerServicio.servicio),
            )
            .join(PostulacionTaller, CotizacionAtencion.id_postulacion == PostulacionTaller.id_postulacion)
        )
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            query = query.filter(PostulacionTaller.id_taller == scope.id_taller)
        elif scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(db, named.get("empresa"))
            if tenant:
                query = query.join(Taller, PostulacionTaller.id_taller == Taller.id_taller).filter(Taller.id_tenant == tenant.id_tenant)

        if "aceptada" in consulta_norm or "aceptadas" in consulta_norm:
            query = query.filter(CotizacionAtencion.estado_cotizacion == EstadoCotizacion.ACEPTADA_CLIENTE)
        elif "rechazada" in consulta_norm or "rechazadas" in consulta_norm:
            query = query.filter(CotizacionAtencion.estado_cotizacion == EstadoCotizacion.RECHAZADA_CLIENTE)
        elif "pendiente" in consulta_norm or "pendientes" in consulta_norm:
            query = query.filter(CotizacionAtencion.estado_cotizacion == EstadoCotizacion.PENDIENTE)

        rows = query.order_by(CotizacionAtencion.fecha_creacion.desc()).all()
        filas = [
            {
                "empresa": c.postulacion.taller.tenant.nombre_tenant if c.postulacion and c.postulacion.taller and c.postulacion.taller.tenant else "",
                "taller": c.postulacion.taller.nombre_taller if c.postulacion and c.postulacion.taller else "",
                "codigo_solicitud": c.postulacion.solicitud.codigo_solicitud if c.postulacion and c.postulacion.solicitud else "",
                "cliente": cls._nombre_cliente(c.postulacion.solicitud.cliente if c.postulacion and c.postulacion.solicitud else None),
                "servicio": c.taller_servicio.servicio.nombre_servicio if c.taller_servicio and c.taller_servicio.servicio else "",
                "precio_total": float(c.precio_total_estimado or 0),
                "estado_cotizacion": cls._enum_value(c.estado_cotizacion),
                "fecha_creacion": cls._fmt_dt(c.fecha_creacion),
                "fecha_respuesta_cliente": cls._fmt_dt(c.fecha_respuesta_cliente),
            }
            for c in rows
        ]
        return cls._build_response(
            consulta_original,
            "cotizaciones",
            "Cotizaciones",
            "Cotizaciones generadas para solicitudes de emergencia.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
                ColumnaReporteTaller(key="cliente", label="Cliente"),
                ColumnaReporteTaller(key="servicio", label="Servicio"),
                ColumnaReporteTaller(key="precio_total", label="Precio total"),
                ColumnaReporteTaller(key="estado_cotizacion", label="Estado cotización"),
                ColumnaReporteTaller(key="fecha_creacion", label="Fecha creación"),
                ColumnaReporteTaller(key="fecha_respuesta_cliente", label="Fecha respuesta cliente"),
            ],
            filas,
            "No encontramos cotizaciones para ese criterio." if not filas else None,
        )

    @classmethod
    def _report_asignaciones(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(AsignacionAtencion)
            .options(
                joinedload(AsignacionAtencion.taller).joinedload(Taller.tenant),
                joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.cliente),
                joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.vehiculo),
                joinedload(AsignacionAtencion.orden_recojo).joinedload(OrdenRecojo.trabajador).joinedload(Trabajador.usuario),
            )
        )
        query = cls._scope_asignaciones(query, scope, named.get("empresa"))
        if "activa" in consulta_norm or "activas" in consulta_norm:
            query = query.filter(AsignacionAtencion.estado_asignacion == EstadoAsignacion.ACTIVA)
        elif "finalizada" in consulta_norm or "finalizadas" in consulta_norm or "atendida" in consulta_norm:
            query = query.filter(AsignacionAtencion.estado_asignacion == EstadoAsignacion.FINALIZADA)
        elif "cancelada" in consulta_norm or "canceladas" in consulta_norm:
            query = query.filter(AsignacionAtencion.estado_asignacion == EstadoAsignacion.CANCELADA)

        rows = query.order_by(AsignacionAtencion.fecha_asignacion.desc()).all()
        filas = [
            {
                "empresa": a.taller.tenant.nombre_tenant if a.taller and a.taller.tenant else "",
                "taller": a.taller.nombre_taller if a.taller else "",
                "codigo_solicitud": a.solicitud.codigo_solicitud if a.solicitud else "",
                "cliente": cls._nombre_cliente(a.solicitud.cliente if a.solicitud else None),
                "placa": a.solicitud.vehiculo.placa if a.solicitud and a.solicitud.vehiculo else "",
                "estado_asignacion": cls._enum_value(a.estado_asignacion),
                "trabajador": a.orden_recojo.trabajador.usuario.nombre_completo if a.orden_recojo and a.orden_recojo.trabajador and a.orden_recojo.trabajador.usuario else "",
                "fecha_asignacion": cls._fmt_dt(a.fecha_asignacion),
                "fecha_inicio_atencion": cls._fmt_dt(a.fecha_inicio_atencion),
                "fecha_fin_atencion": cls._fmt_dt(a.fecha_fin_atencion),
            }
            for a in rows
        ]
        return cls._build_response(
            consulta_original,
            "asignaciones",
            "Asignaciones",
            "Asignaciones de atención según el alcance y estado consultado.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
                ColumnaReporteTaller(key="cliente", label="Cliente"),
                ColumnaReporteTaller(key="placa", label="Placa"),
                ColumnaReporteTaller(key="estado_asignacion", label="Estado"),
                ColumnaReporteTaller(key="trabajador", label="Trabajador"),
                ColumnaReporteTaller(key="fecha_asignacion", label="Fecha asignación"),
                ColumnaReporteTaller(key="fecha_inicio_atencion", label="Inicio atención"),
                ColumnaReporteTaller(key="fecha_fin_atencion", label="Fin atención"),
            ],
            filas,
            "No encontramos asignaciones para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_ordenes(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(OrdenRecojo)
            .options(
                joinedload(OrdenRecojo.trabajador).joinedload(Trabajador.usuario),
                joinedload(OrdenRecojo.asignacion).joinedload(AsignacionAtencion.taller).joinedload(Taller.tenant),
                joinedload(OrdenRecojo.asignacion).joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.cliente),
                joinedload(OrdenRecojo.asignacion).joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.vehiculo),
            )
        )
        query = cls._scope_ordenes(query, scope, named.get("empresa"))

        estado_detectado = cls._detect_orden_estado(consulta_norm)
        if estado_detectado:
            query = query.filter(OrdenRecojo.estado_orden == estado_detectado)

        if named.get("trabajador"):
            worker_norm = cls._normalize(named["trabajador"] or "")
            ordenes = query.order_by(OrdenRecojo.fecha_asignacion.desc()).all()
            ordenes = [
                o for o in ordenes
                if worker_norm in cls._normalize(o.trabajador.usuario.nombre_completo if o.trabajador and o.trabajador.usuario else "")
            ]
        else:
            ordenes = query.order_by(OrdenRecojo.fecha_asignacion.desc()).all()

        filas = [
            {
                "empresa": o.asignacion.taller.tenant.nombre_tenant if o.asignacion and o.asignacion.taller and o.asignacion.taller.tenant else "",
                "taller": o.asignacion.taller.nombre_taller if o.asignacion and o.asignacion.taller else "",
                "codigo_solicitud": o.asignacion.solicitud.codigo_solicitud if o.asignacion and o.asignacion.solicitud else "",
                "cliente": cls._nombre_cliente(o.asignacion.solicitud.cliente if o.asignacion and o.asignacion.solicitud else None),
                "placa": o.asignacion.solicitud.vehiculo.placa if o.asignacion and o.asignacion.solicitud and o.asignacion.solicitud.vehiculo else "",
                "trabajador": o.trabajador.usuario.nombre_completo if o.trabajador and o.trabajador.usuario else "",
                "estado_orden": cls._enum_value(o.estado_orden),
                "fecha_asignacion": cls._fmt_dt(o.fecha_asignacion),
                "fecha_llegada_auxilio": cls._fmt_dt(o.fecha_llegada_auxilio),
                "fecha_inicio_regreso": cls._fmt_dt(o.fecha_inicio_regreso),
                "fecha_llegada_taller": cls._fmt_dt(o.fecha_llegada_taller),
                "duracion_total_segundos": round(float(o.duracion_total_segundos or 0), 2) if o.duracion_total_segundos else "",
            }
            for o in ordenes
        ]
        return cls._build_response(
            consulta_original,
            "ordenes",
            "Órdenes y tracking",
            "Órdenes de recojo según el estado o trabajador consultado.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
                ColumnaReporteTaller(key="cliente", label="Cliente"),
                ColumnaReporteTaller(key="placa", label="Placa"),
                ColumnaReporteTaller(key="trabajador", label="Trabajador"),
                ColumnaReporteTaller(key="estado_orden", label="Estado orden"),
                ColumnaReporteTaller(key="fecha_asignacion", label="Fecha asignación"),
                ColumnaReporteTaller(key="fecha_llegada_auxilio", label="Llegada auxilio"),
                ColumnaReporteTaller(key="fecha_inicio_regreso", label="Inicio taller"),
                ColumnaReporteTaller(key="fecha_llegada_taller", label="Llegada taller"),
                ColumnaReporteTaller(key="duracion_total_segundos", label="Duración total (s)"),
            ],
            filas,
            "No encontramos órdenes para ese criterio." if not filas else None,
        )

    @classmethod
    def _report_resultados_servicio(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(ResultadoServicio)
            .options(
                joinedload(ResultadoServicio.asignacion).joinedload(AsignacionAtencion.taller).joinedload(Taller.tenant),
                joinedload(ResultadoServicio.asignacion).joinedload(AsignacionAtencion.orden_recojo).joinedload(OrdenRecojo.trabajador).joinedload(Trabajador.usuario),
                joinedload(ResultadoServicio.solicitud).joinedload(SolicitudEmergencia.cliente),
                joinedload(ResultadoServicio.solicitud).joinedload(SolicitudEmergencia.vehiculo),
                joinedload(ResultadoServicio.taller_servicio).joinedload(TallerServicio.servicio),
            )
        )
        query = cls._scope_resultados(query, scope, named.get("empresa"))
        if "seguimiento" in consulta_norm:
            query = query.filter(ResultadoServicio.requiere_seguimiento.is_(True))

        resultados = query.order_by(ResultadoServicio.fecha_registro.desc()).all()
        if named.get("cliente"):
            cliente_norm = cls._normalize(named["cliente"] or "")
            resultados = [
                r for r in resultados
                if cliente_norm in cls._normalize(cls._nombre_cliente(r.solicitud.cliente if r.solicitud else None))
            ]
        if named.get("placa"):
            placa_norm = cls._normalize(named["placa"] or "")
            resultados = [
                r for r in resultados
                if placa_norm in cls._normalize(r.solicitud.vehiculo.placa if r.solicitud and r.solicitud.vehiculo else "")
            ]

        filas = [
            {
                "empresa": r.asignacion.taller.tenant.nombre_tenant if r.asignacion and r.asignacion.taller and r.asignacion.taller.tenant else "",
                "taller": r.asignacion.taller.nombre_taller if r.asignacion and r.asignacion.taller else "",
                "codigo_solicitud": r.solicitud.codigo_solicitud if r.solicitud else "",
                "cliente": cls._nombre_cliente(r.solicitud.cliente if r.solicitud else None),
                "placa": r.solicitud.vehiculo.placa if r.solicitud and r.solicitud.vehiculo else "",
                "trabajador": r.asignacion.orden_recojo.trabajador.usuario.nombre_completo if r.asignacion and r.asignacion.orden_recojo and r.asignacion.orden_recojo.trabajador and r.asignacion.orden_recojo.trabajador.usuario else "",
                "servicio": r.taller_servicio.servicio.nombre_servicio if r.taller_servicio and r.taller_servicio.servicio else "",
                "diagnostico": r.diagnostico or "",
                "solucion_aplicada": r.solucion_aplicada or "",
                "estado_resultado": cls._enum_value(r.estado_resultado),
                "requiere_seguimiento": "Sí" if r.requiere_seguimiento else "No",
                "fecha_registro": cls._fmt_dt(r.fecha_registro),
            }
            for r in resultados
        ]
        return cls._build_response(
            consulta_original,
            "resultados_servicio",
            "Resultados de servicio",
            "Resultados de servicio según cliente, vehículo o estado de seguimiento.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
                ColumnaReporteTaller(key="cliente", label="Cliente"),
                ColumnaReporteTaller(key="placa", label="Placa"),
                ColumnaReporteTaller(key="trabajador", label="Trabajador"),
                ColumnaReporteTaller(key="servicio", label="Servicio"),
                ColumnaReporteTaller(key="diagnostico", label="Diagnóstico"),
                ColumnaReporteTaller(key="solucion_aplicada", label="Solución aplicada"),
                ColumnaReporteTaller(key="estado_resultado", label="Estado resultado"),
                ColumnaReporteTaller(key="requiere_seguimiento", label="Seguimiento"),
                ColumnaReporteTaller(key="fecha_registro", label="Fecha registro"),
            ],
            filas,
            "No encontramos resultados de servicio para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_pagos(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = (
            db.query(PagoAtencion)
            .options(
                joinedload(PagoAtencion.taller).joinedload(Taller.tenant),
                joinedload(PagoAtencion.solicitud).joinedload(SolicitudEmergencia.cliente),
            )
        )
        query = cls._scope_pagos(query, scope, named.get("empresa"))
        if "pendiente" in consulta_norm or "pendientes" in consulta_norm:
            query = query.filter(PagoAtencion.estado_pago == "PENDIENTE")
        elif "confirmado" in consulta_norm or "confirmados" in consulta_norm:
            query = query.filter(PagoAtencion.estado_pago == "CONFIRMADO")

        pagos = query.order_by(PagoAtencion.fecha_registro.desc()).all()
        if named.get("cliente"):
            cliente_norm = cls._normalize(named["cliente"] or "")
            pagos = [
                p for p in pagos
                if cliente_norm in cls._normalize(cls._nombre_cliente(p.solicitud.cliente if p.solicitud else None))
            ]

        filas = [
            {
                "empresa": p.taller.tenant.nombre_tenant if p.taller and p.taller.tenant else "",
                "taller": p.taller.nombre_taller if p.taller else "",
                "codigo_solicitud": p.solicitud.codigo_solicitud if p.solicitud else "",
                "cliente": cls._nombre_cliente(p.solicitud.cliente if p.solicitud else None),
                "monto": float(p.monto or 0),
                "moneda": p.moneda,
                "metodo_pago": p.metodo_pago,
                "estado_pago": p.estado_pago,
                "referencia": p.referencia_externa or "",
                "fecha_registro": cls._fmt_dt(p.fecha_registro),
                "fecha_confirmacion": cls._fmt_dt(p.fecha_confirmacion),
            }
            for p in pagos
        ]
        return cls._build_response(
            consulta_original,
            "pagos",
            "Pagos",
            "Pagos registrados para las atenciones visibles en el alcance de la consulta.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="taller", label="Taller"),
                ColumnaReporteTaller(key="codigo_solicitud", label="Código solicitud"),
                ColumnaReporteTaller(key="cliente", label="Cliente"),
                ColumnaReporteTaller(key="monto", label="Monto"),
                ColumnaReporteTaller(key="moneda", label="Moneda"),
                ColumnaReporteTaller(key="metodo_pago", label="Método"),
                ColumnaReporteTaller(key="estado_pago", label="Estado"),
                ColumnaReporteTaller(key="referencia", label="Referencia"),
                ColumnaReporteTaller(key="fecha_registro", label="Fecha registro"),
                ColumnaReporteTaller(key="fecha_confirmacion", label="Fecha confirmación"),
            ],
            filas,
            "No encontramos pagos para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_talleres(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = db.query(Taller).options(joinedload(Taller.tenant), joinedload(Taller.usuario))
        if "aprobado" in consulta_norm or "aprobados" in consulta_norm:
            query = query.filter(Taller.estado_aprobacion == EstadoAprobacionTaller.APROBADO)
        if "activo" in consulta_norm or "activos" in consulta_norm:
            query = query.filter(Taller.estado_operativo == EstadoOperativoTaller.DISPONIBLE)
        talleres = query.order_by(Taller.nombre_taller.asc()).all()
        filas = [
            {
                "empresa": t.tenant.nombre_tenant if t.tenant else "",
                "nombre_taller": t.nombre_taller,
                "responsable": t.usuario.nombre_completo if t.usuario else "",
                "telefono": t.telefono or "",
                "estado_aprobacion": cls._enum_value(t.estado_aprobacion),
                "estado_operativo": cls._enum_value(t.estado_operativo),
                "fecha_registro": cls._fmt_dt(t.fecha_registro),
            }
            for t in talleres
        ]
        return cls._build_response(
            consulta_original,
            "talleres",
            "Talleres",
            "Talleres registrados y su estado dentro del sistema.",
            [
                ColumnaReporteTaller(key="empresa", label="Empresa"),
                ColumnaReporteTaller(key="nombre_taller", label="Taller"),
                ColumnaReporteTaller(key="responsable", label="Responsable"),
                ColumnaReporteTaller(key="telefono", label="Teléfono"),
                ColumnaReporteTaller(key="estado_aprobacion", label="Aprobación"),
                ColumnaReporteTaller(key="estado_operativo", label="Estado operativo"),
                ColumnaReporteTaller(key="fecha_registro", label="Fecha registro"),
            ],
            filas,
            "No encontramos talleres para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_notificaciones(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = db.query(Notificacion).options(joinedload(Notificacion.usuario))
        visible_user_ids = cls._visible_user_ids_for_notifications(db, scope, named.get("empresa"))
        if visible_user_ids is not None:
            query = query.filter(Notificacion.id_usuario_destino.in_(visible_user_ids))
        if "leida" in consulta_norm or "leidas" in consulta_norm:
            query = query.filter(Notificacion.estado_lectura == EstadoLecturaNotificacion.LEIDA)
        elif "no leida" in consulta_norm or "no leidas" in consulta_norm:
            query = query.filter(Notificacion.estado_lectura == EstadoLecturaNotificacion.NO_LEIDA)
        if "fallida" in consulta_norm or "fallidas" in consulta_norm:
            query = query.filter(Notificacion.estado_envio == EstadoEnvioNotificacion.FALLIDA)

        rows = query.order_by(Notificacion.fecha_envio.desc()).all()
        filas = [
            {
                "usuario_destino": n.usuario.nombre_completo if n.usuario else "",
                "correo": n.usuario.correo if n.usuario else "",
                "titulo": n.titulo,
                "categoria_evento": cls._enum_value(n.categoria_evento),
                "tipo_notificacion": cls._enum_value(n.tipo_notificacion),
                "estado_envio": cls._enum_value(n.estado_envio),
                "estado_lectura": cls._enum_value(n.estado_lectura),
                "fecha_envio": cls._fmt_dt(n.fecha_envio),
                "fecha_lectura": cls._fmt_dt(n.fecha_lectura),
            }
            for n in rows
        ]
        return cls._build_response(
            consulta_original,
            "notificaciones",
            "Notificaciones",
            "Historial de notificaciones dentro del alcance permitido.",
            [
                ColumnaReporteTaller(key="usuario_destino", label="Usuario destino"),
                ColumnaReporteTaller(key="correo", label="Correo"),
                ColumnaReporteTaller(key="titulo", label="Título"),
                ColumnaReporteTaller(key="categoria_evento", label="Categoría"),
                ColumnaReporteTaller(key="tipo_notificacion", label="Tipo"),
                ColumnaReporteTaller(key="estado_envio", label="Estado envío"),
                ColumnaReporteTaller(key="estado_lectura", label="Estado lectura"),
                ColumnaReporteTaller(key="fecha_envio", label="Fecha envío"),
                ColumnaReporteTaller(key="fecha_lectura", label="Fecha lectura"),
            ],
            filas,
            "No encontramos notificaciones para ese filtro." if not filas else None,
        )

    @classmethod
    def _report_bitacora(cls, db: Session, scope: ReportScope, consulta_original: str, consulta_norm: str, named: dict[str, str | None]) -> ReporteConsultaTallerResponse:
        query = db.query(Bitacora)
        if "error" in consulta_norm or "errores" in consulta_norm:
            query = query.filter(Bitacora.resultado == ResultadoAuditoria.ERROR)
        elif "advertencia" in consulta_norm:
            query = query.filter(Bitacora.resultado == ResultadoAuditoria.ADVERTENCIA)
        elif "exito" in consulta_norm or "exitos" in consulta_norm:
            query = query.filter(Bitacora.resultado == ResultadoAuditoria.EXITO)
        rows = query.order_by(Bitacora.fecha_evento.desc()).all()
        filas = [
            {
                "tipo_actor": cls._enum_value(r.tipo_actor),
                "accion": r.accion,
                "modulo": r.modulo,
                "entidad_afectada": r.entidad_afectada,
                "resultado": cls._enum_value(r.resultado),
                "detalle": r.detalle or "",
                "ip_origen": r.ip_origen or "",
                "fecha_evento": cls._fmt_dt(r.fecha_evento),
            }
            for r in rows
        ]
        return cls._build_response(
            consulta_original,
            "bitacora",
            "Bitácora",
            "Eventos auditados del sistema.",
            [
                ColumnaReporteTaller(key="tipo_actor", label="Tipo actor"),
                ColumnaReporteTaller(key="accion", label="Acción"),
                ColumnaReporteTaller(key="modulo", label="Módulo"),
                ColumnaReporteTaller(key="entidad_afectada", label="Entidad"),
                ColumnaReporteTaller(key="resultado", label="Resultado"),
                ColumnaReporteTaller(key="detalle", label="Detalle"),
                ColumnaReporteTaller(key="ip_origen", label="IP origen"),
                ColumnaReporteTaller(key="fecha_evento", label="Fecha evento"),
            ],
            filas,
            "No encontramos eventos de bitácora para ese filtro." if not filas else None,
        )

    @classmethod
    def _scope_asignaciones(cls, query, scope: ReportScope, empresa: str | None):
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            return query.filter(AsignacionAtencion.id_taller == scope.id_taller)
        if scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(query.session, empresa)
            if tenant:
                return query.join(Taller, AsignacionAtencion.id_taller == Taller.id_taller).filter(Taller.id_tenant == tenant.id_tenant)
        return query

    @classmethod
    def _scope_postulaciones(cls, query, scope: ReportScope, empresa: str | None):
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            return query.filter(PostulacionTaller.id_taller == scope.id_taller)
        if scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(query.session, empresa)
            if tenant:
                return query.join(Taller, PostulacionTaller.id_taller == Taller.id_taller).filter(Taller.id_tenant == tenant.id_tenant)
        return query

    @classmethod
    def _scope_ordenes(cls, query, scope: ReportScope, empresa: str | None):
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            return query.join(AsignacionAtencion, OrdenRecojo.id_asignacion == AsignacionAtencion.id_asignacion).filter(AsignacionAtencion.id_taller == scope.id_taller)
        if scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(query.session, empresa)
            if tenant:
                return (
                    query.join(AsignacionAtencion, OrdenRecojo.id_asignacion == AsignacionAtencion.id_asignacion)
                    .join(Taller, AsignacionAtencion.id_taller == Taller.id_taller)
                    .filter(Taller.id_tenant == tenant.id_tenant)
                )
        return query

    @classmethod
    def _scope_resultados(cls, query, scope: ReportScope, empresa: str | None):
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            return query.join(AsignacionAtencion, ResultadoServicio.id_asignacion == AsignacionAtencion.id_asignacion).filter(AsignacionAtencion.id_taller == scope.id_taller)
        if scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(query.session, empresa)
            if tenant:
                return (
                    query.join(AsignacionAtencion, ResultadoServicio.id_asignacion == AsignacionAtencion.id_asignacion)
                    .join(Taller, AsignacionAtencion.id_taller == Taller.id_taller)
                    .filter(Taller.id_tenant == tenant.id_tenant)
                )
        return query

    @classmethod
    def _scope_pagos(cls, query, scope: ReportScope, empresa: str | None):
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            return query.filter(PagoAtencion.id_taller == scope.id_taller)
        if scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(query.session, empresa)
            if tenant:
                return query.join(Taller, PagoAtencion.id_taller == Taller.id_taller).filter(Taller.id_tenant == tenant.id_tenant)
        return query

    @classmethod
    def _clients_query_for_scope(cls, db: Session, scope: ReportScope, empresa: str | None):
        query = (
            db.query(Cliente)
            .options(joinedload(Cliente.usuario))
        )
        if scope.rol == RolUsuario.ADMINISTRADOR and empresa is None:
            return query

        taller_ids = cls._scope_taller_ids(db, scope, empresa)
        if not taller_ids:
            return query.filter(Cliente.id_cliente == None)  # noqa: E711
        return (
            query.join(SolicitudEmergencia, Cliente.id_cliente == SolicitudEmergencia.id_cliente)
            .join(AsignacionAtencion, SolicitudEmergencia.id_solicitud == AsignacionAtencion.id_solicitud)
            .filter(AsignacionAtencion.id_taller.in_(taller_ids))
            .distinct()
        )

    @classmethod
    def _clientes_interactuados(cls, db: Session, scope: ReportScope, tenant_name: str | None = None) -> list[Cliente]:
        return cls._clients_query_for_scope(db, scope, tenant_name).order_by(Cliente.nombre.asc(), Cliente.apellido.asc()).all()

    @classmethod
    def _visible_user_ids_for_notifications(cls, db: Session, scope: ReportScope, empresa: str | None) -> list[str] | None:
        if scope.rol == RolUsuario.ADMINISTRADOR and empresa is None:
            return None
        taller_ids = cls._scope_taller_ids(db, scope, empresa)
        if not taller_ids and scope.id_tenant:
            talleres = db.query(Taller).filter(Taller.id_tenant == scope.id_tenant).all()
        else:
            talleres = db.query(Taller).filter(Taller.id_taller.in_(taller_ids)).all() if taller_ids else []
        user_ids: set[str] = set()
        for taller in talleres:
            user_ids.add(str(taller.id_usuario))
            trabajadores = db.query(Trabajador.id_usuario).filter(Trabajador.id_taller == taller.id_taller).all()
            user_ids.update(str(uid) for (uid,) in trabajadores)
        return list(user_ids)

    @classmethod
    def _scope_taller_ids(cls, db: Session, scope: ReportScope, empresa: str | None) -> list[str]:
        if scope.rol == RolUsuario.TALLER and scope.id_taller:
            return [scope.id_taller]
        if scope.rol == RolUsuario.ADMINISTRADOR:
            tenant = cls._resolve_tenant_if_present(db, empresa)
            if tenant:
                return [str(t.id_taller) for t in db.query(Taller.id_taller).filter(Taller.id_tenant == tenant.id_tenant).all()]
        return [str(tid) for (tid,) in db.query(Taller.id_taller).all()]

    @classmethod
    def _resolve_tenant_if_present(cls, db: Session, empresa: str | None) -> TenantTaller | None:
        if not empresa:
            return None
        empresa_norm = cls._normalize(empresa)
        tenants = db.query(TenantTaller).all()
        for tenant in tenants:
            if empresa_norm in cls._normalize(tenant.nombre_tenant) or empresa_norm in cls._normalize(tenant.slug_tenant):
                return tenant
        talleres = db.query(Taller).options(joinedload(Taller.tenant)).all()
        for taller in talleres:
            if empresa_norm in cls._normalize(taller.nombre_taller):
                return taller.tenant
        return None

    @classmethod
    def _extract_named_filters(cls, consulta_original: str, consulta_norm: str) -> dict[str, str | None]:
        return {
            "empresa": cls._extract_after_keyword(consulta_original, consulta_norm, ["empresa", "tenant", "taller"]),
            "trabajador": cls._extract_after_keyword(consulta_original, consulta_norm, ["trabajador"]),
            "cliente": cls._extract_after_keyword(consulta_original, consulta_norm, ["cliente", "usuario"]),
            "placa": cls._extract_after_keyword(consulta_original, consulta_norm, ["placa"]),
        }

    @classmethod
    def _extract_after_keyword(cls, consulta_original: str, consulta_norm: str, keywords: list[str]) -> str | None:
        quoted = re.findall(r'"([^"]+)"', consulta_original)
        if quoted:
            return quoted[-1].strip()
        for keyword in keywords:
            match = re.search(
                rf"{keyword}(?:\s+(?:con|de|del|llamado|llamada|nombre))?\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9 _-]+)",
                consulta_original,
                flags=re.IGNORECASE,
            )
            if match:
                value = match.group(1).strip()
                value = re.sub(
                    r"\b(tipo|que|quiero|ver|todos|todas|las|los|del|de|la|el|mi|mis|este|esta|estos|estas)\b$",
                    "",
                    value,
                    flags=re.IGNORECASE,
                ).strip()
                if value:
                    return value
        return None

    @classmethod
    def _detect_orden_estado(cls, consulta_norm: str) -> EstadoOrdenRecojo | None:
        mapping = {
            "pendiente de aceptacion": EstadoOrdenRecojo.PENDIENTE_ACEPTACION,
            "pendientes de aceptacion": EstadoOrdenRecojo.PENDIENTE_ACEPTACION,
            "en camino al auxilio": EstadoOrdenRecojo.EN_CAMINO_RECOJO,
            "en camino recojo": EstadoOrdenRecojo.EN_CAMINO_RECOJO,
            "llegada al auxilio": EstadoOrdenRecojo.LLEGADA_AUXILIO,
            "en camino al taller": EstadoOrdenRecojo.EN_CAMINO_TALLER,
            "inicio hacia el taller": EstadoOrdenRecojo.EN_CAMINO_TALLER,
            "finalizada": EstadoOrdenRecojo.FINALIZADA,
            "finalizadas": EstadoOrdenRecojo.FINALIZADA,
            "aceptada": EstadoOrdenRecojo.ACEPTADA,
            "aceptadas": EstadoOrdenRecojo.ACEPTADA,
            "cancelada": EstadoOrdenRecojo.CANCELADA,
            "canceladas": EstadoOrdenRecojo.CANCELADA,
        }
        for texto, estado in mapping.items():
            if texto in consulta_norm:
                return estado
        return None

    @classmethod
    def _matches(cls, consulta_norm: str, family: str) -> bool:
        families = {
            "usuarios": ["usuario", "usuarios"],
            "trabajadores": ["trabajador", "trabajadores"],
            "clientes": ["cliente", "clientes"],
            "postulaciones": ["postulacion", "postulaciones"],
            "cotizaciones": ["cotizacion", "cotizaciones"],
            "asignaciones": ["asignacion", "asignaciones"],
            "ordenes": ["orden", "ordenes", "tracking"],
            "servicios_realizados": ["resultado de servicio", "resultados de servicio", "servicios realizados", "servicio realizado"],
            "pagos": ["pago", "pagos"],
            "talleres": ["taller", "talleres"],
            "notificaciones": ["notificacion", "notificaciones"],
            "bitacora": ["bitacora", "auditoria", "errores de sistema", "eventos de sistema"],
        }
        return any(token in consulta_norm for token in families[family])

    @staticmethod
    def _build_response(
        consulta_original: str,
        tipo_reporte: str,
        titulo: str,
        descripcion: str,
        columnas: list[ColumnaReporteTaller],
        filas: list[dict[str, object]],
        mensaje: str | None = None,
    ) -> ReporteConsultaTallerResponse:
        return ReporteConsultaTallerResponse(
            consulta_original=consulta_original,
            tipo_reporte=tipo_reporte,
            titulo=titulo,
            descripcion=descripcion,
            columnas=columnas,
            filas=filas,
            total_registros=len(filas),
            mensaje=mensaje,
        )

    @staticmethod
    def _columns_usuarios_empresa() -> list[ColumnaReporteTaller]:
        return [
            ColumnaReporteTaller(key="empresa", label="Empresa"),
            ColumnaReporteTaller(key="taller", label="Taller"),
            ColumnaReporteTaller(key="tipo_usuario", label="Tipo usuario"),
            ColumnaReporteTaller(key="nombre_completo", label="Nombre completo"),
            ColumnaReporteTaller(key="correo", label="Correo"),
            ColumnaReporteTaller(key="rol", label="Rol"),
            ColumnaReporteTaller(key="telefono", label="Teléfono"),
            ColumnaReporteTaller(key="licencia", label="Licencia"),
            ColumnaReporteTaller(key="activo", label="Activo"),
            ColumnaReporteTaller(key="fecha_registro", label="Fecha registro"),
        ]

    @staticmethod
    def _columns_usuarios_globales() -> list[ColumnaReporteTaller]:
        return [
            ColumnaReporteTaller(key="nombre_completo", label="Nombre completo"),
            ColumnaReporteTaller(key="correo", label="Correo"),
            ColumnaReporteTaller(key="rol", label="Rol"),
            ColumnaReporteTaller(key="tipo_detalle", label="Detalle"),
            ColumnaReporteTaller(key="empresa", label="Empresa"),
            ColumnaReporteTaller(key="taller", label="Taller"),
            ColumnaReporteTaller(key="activo", label="Activo"),
            ColumnaReporteTaller(key="fecha_creacion", label="Fecha creación"),
        ]

    @classmethod
    def _usuario_global_row(cls, usuario: Usuario) -> dict[str, object]:
        empresa = ""
        taller = ""
        tipo_detalle = cls._enum_value(usuario.rol)
        if usuario.taller:
            empresa = usuario.taller.tenant.nombre_tenant if usuario.taller.tenant else ""
            taller = usuario.taller.nombre_taller
            tipo_detalle = "Administrador del taller"
        elif usuario.trabajador and usuario.trabajador.taller:
            empresa = usuario.trabajador.taller.tenant.nombre_tenant if usuario.trabajador.taller.tenant else ""
            taller = usuario.trabajador.taller.nombre_taller
            tipo_detalle = "Trabajador"
        elif usuario.cliente:
            tipo_detalle = "Cliente"
        return {
            "nombre_completo": usuario.nombre_completo,
            "correo": usuario.correo,
            "rol": cls._enum_value(usuario.rol),
            "tipo_detalle": tipo_detalle,
            "empresa": empresa,
            "taller": taller,
            "activo": "Sí" if usuario.es_activo else "No",
            "fecha_creacion": cls._fmt_dt(usuario.fecha_creacion),
        }

    @staticmethod
    def _nombre_cliente(cliente: Cliente | None) -> str:
        if not cliente:
            return ""
        return f"{cliente.nombre or ''} {cliente.apellido or ''}".strip()

    @staticmethod
    def _fmt_dt(valor: datetime | None) -> str:
        if not valor:
            return ""
        return valor.strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _enum_value(valor: object) -> str:
        return valor.value if hasattr(valor, "value") else str(valor or "")

    @staticmethod
    def _normalize(texto: str) -> str:
        texto = texto.lower().strip()
        texto = "".join(
            c for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        )
        return " ".join(texto.split())
