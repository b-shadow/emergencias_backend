from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import and_

from app.core.enums import (
    RolUsuario,
    EstadoAsignacion,
    EstadoSolicitud,
    TipoActor,
    ResultadoAuditoria,
    TipoNotificacion,
    CategoriaNotificacion,
    EstadoLecturaNotificacion,
    EstadoEnvioNotificacion,
)
from app.core.exceptions import not_found, forbidden, bad_request
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.usuario import Usuario
from app.models.bitacora import Bitacora
from app.models.notificacion import Notificacion
from app.models.historial_estado_solicitud import HistorialEstadoSolicitud
from app.services.servicio_ejecutado_service import ServicioEjecutadoService


class AsignacionService:
    
    @staticmethod
    def _registrar_bitacora(
        db: Session,
        accion: str,
        resultado: ResultadoAuditoria,
        detalle: str | None = None,
        id_entidad: UUID | None = None,
        tipo_actor: TipoActor = TipoActor.SISTEMA,
        id_actor: UUID | None = None,
    ) -> None:
        """Registra evento en bitácora para asignaciones."""
        bitacora = Bitacora(
            tipo_actor=tipo_actor,
            id_actor=id_actor,
            accion=accion,
            modulo="AsignacionAtencion",
            entidad_afectada="AsignacionAtencion",
            id_entidad_afectada=id_entidad,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()
    
    @staticmethod
    def get_asignaciones_activas(db: Session, current_user: Usuario) -> list[AsignacionAtencion]:
        """Obtiene las asignaciones activas del usuario actual."""
        from app.models.solicitud_emergencia import SolicitudEmergencia
        from app.models.taller import Taller
        from app.models.cliente import Cliente
        
        # Base query con eager loading
        query = db.query(AsignacionAtencion).options(
            joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.cliente),
            joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.vehiculo),
            joinedload(AsignacionAtencion.taller)
        )
        
        # Filtrar solo estados activos (ACTIVA)
        query = query.filter(
            AsignacionAtencion.estado_asignacion == EstadoAsignacion.ACTIVA
        )
        
        # TALLER solo puede ver sus propias asignaciones
        if current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if not taller:
                raise not_found("Taller no encontrado")
            query = query.filter(AsignacionAtencion.id_taller == taller.id_taller)
        
        # CLIENTE solo puede ver asignaciones de sus solicitudes
        elif current_user.rol == RolUsuario.CLIENTE:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente:
                raise not_found("Cliente no encontrado")
            
            # Usar query base sin joinedload para filtrar correctamente
            query = db.query(AsignacionAtencion).options(
                joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.cliente),
                joinedload(AsignacionAtencion.solicitud).joinedload(SolicitudEmergencia.vehiculo),
                joinedload(AsignacionAtencion.taller)
            ).join(
                SolicitudEmergencia,
                AsignacionAtencion.id_solicitud == SolicitudEmergencia.id_solicitud
            ).filter(
                and_(
                    SolicitudEmergencia.id_cliente == cliente.id_cliente,
                    AsignacionAtencion.estado_asignacion == EstadoAsignacion.ACTIVA
                )
            )
        
        return query.all()
    
    @staticmethod
    def get_asignacion(db: Session, asignacion_id: UUID, current_user: Usuario) -> AsignacionAtencion:
        """Obtiene una asignación validando permisos."""
        asignacion = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_asignacion == asignacion_id
        ).first()
        
        if not asignacion:
            raise not_found("Asignación no encontrada")
        
        # TALLER solo puede ver sus propias asignaciones
        if current_user.rol == RolUsuario.TALLER:
            if asignacion.taller.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para acceder a esta asignación")
        
        # CLIENTE solo puede ver asignaciones de sus solicitudes
        if current_user.rol == RolUsuario.CLIENTE:
            from app.models.cliente import Cliente
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if asignacion.solicitud.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes permiso para acceder a esta asignación")
        
        return asignacion
    
    @staticmethod
    def update_estado_asignacion(
        db: Session,
        asignacion_id: UUID,
        nuevo_estado: str,
        comentario: str | None = None,
        current_user: Usuario | None = None,
    ) -> AsignacionAtencion:
        """
        Actualiza el estado de atención de una solicitud (CU-20: Actualizar estado de atención).
        
        El taller actualiza el progreso de la atención (EN_CAMINO, EN_PROCESO, etc),
        esto actualiza el estado_actual de la SolicitudEmergencia, no la AsignacionAtencion.
        
        Validaciones:
        - Solo TALLER puede actualizar sus asignaciones
        - Solicitud debe estar activa
        - Transición de estado debe ser válida
        
        Registra en bitácora y notifica al cliente
        """
        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)
        
        # TALLER solo puede actualizar sus propias asignaciones
        if current_user and current_user.rol == RolUsuario.TALLER:
            if asignacion.taller.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para actualizar esta asignación")
        
        # Mapear estados que el taller puede usar
        estados_disponibles = {
            'EN_CAMINO': EstadoSolicitud.EN_CAMINO,
            'EN_PROCESO': EstadoSolicitud.EN_PROCESO,
            'ATENDIDA': EstadoSolicitud.ATENDIDA,
            'CANCELADA': EstadoSolicitud.CANCELADA,
        }
        
        if nuevo_estado not in estados_disponibles:
            raise bad_request(
                f"Estado no válido: {nuevo_estado}. "
                f"Estados disponibles: {', '.join(estados_disponibles.keys())}"
            )
        
        nuevo_estado_solicitud = estados_disponibles[nuevo_estado]
        solicitud = asignacion.solicitud
        estado_anterior = solicitud.estado_actual
        
        # Validar transición de estado permitida para la solicitud
        transiciones_validas = {
            EstadoSolicitud.TALLER_SELECCIONADO: [EstadoSolicitud.EN_CAMINO, EstadoSolicitud.EN_PROCESO, EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA],
            EstadoSolicitud.EN_CAMINO: [EstadoSolicitud.EN_PROCESO, EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA],
            EstadoSolicitud.EN_PROCESO: [EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA],
            EstadoSolicitud.ATENDIDA: [EstadoSolicitud.CANCELADA],  # Puede cancelarse aunque esté atendida
            EstadoSolicitud.CANCELADA: [],  # Final
        }
        
        if nuevo_estado_solicitud not in transiciones_validas.get(estado_anterior, []):
            raise bad_request(
                f"No se puede cambiar de {estado_anterior.value} a {nuevo_estado_solicitud.value}. "
                f"Transiciones válidas: {[e.value for e in transiciones_validas.get(estado_anterior, [])]}"
            )

        if nuevo_estado_solicitud == EstadoSolicitud.ATENDIDA:
            from app.services.pago_service import PagoService

            pendientes = ServicioEjecutadoService.pendientes_cotizados(asignacion, list(asignacion.resultados or []))
            if pendientes:
                detalle_pendiente = ", ".join(
                    f"{item.get('nombre_servicio') or item['id_taller_servicio']} x{item['faltantes']}"
                    for item in pendientes
                )
                raise bad_request(
                    f"No puedes finalizar la atencion. Faltan servicios cotizados obligatorios: {detalle_pendiente}"
                )

            resumen_pago = PagoService.obtener_resumen(db, solicitud.id_solicitud, current_user)
            if float(resumen_pago.get("saldo_pendiente", 0) or 0) > 0:
                raise bad_request("No puedes finalizar la atencion hasta que el cliente complete el pago")

        # Actualizar estado de solicitud
        solicitud.estado_actual = nuevo_estado_solicitud
        
        # Actualizar timestamps en asignación si corresponde
        if nuevo_estado == 'EN_CAMINO':
            asignacion.fecha_inicio_atencion = datetime.now()
        elif nuevo_estado in ['EN_PROCESO', 'ATENDIDA']:
            # Si no tiene fecha_inicio, establecerla ahora
            if not asignacion.fecha_inicio_atencion:
                asignacion.fecha_inicio_atencion = datetime.now()
            asignacion.fecha_fin_atencion = datetime.now()
        elif nuevo_estado == 'CANCELADA':
            # Si no tiene fecha_inicio, establecerla ahora
            if not asignacion.fecha_inicio_atencion:
                asignacion.fecha_inicio_atencion = datetime.now()
            asignacion.fecha_fin_atencion = datetime.now()
            asignacion.motivo_cancelacion = comentario
        
        db.add(solicitud)
        db.add(asignacion)
        db.flush()
        
        # Registrar en historial de solicitud
        historial = HistorialEstadoSolicitud(
            id_solicitud=solicitud.id_solicitud,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado_solicitud,
            actualizado_por_tipo=TipoActor.TALLER,
            actualizado_por_id=current_user.id_usuario if current_user else None,
            comentario=comentario or f"Actualizado a {nuevo_estado_solicitud.value} por taller",
        )
        db.add(historial)
        
        # Notificar al cliente sobre el cambio de estado
        cliente = solicitud.cliente
        if cliente:
            mensaje = f"El taller {asignacion.taller.nombre_taller} ha actualizado el estado de tu solicitud a: {nuevo_estado_solicitud.value}"
            if comentario:
                mensaje += f". {comentario}"
            
            # Usar servicio central de notificaciones en lugar de crear manualmente
            from app.services.notificacion_service import NotificacionService
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=cliente.id_usuario,
                tipo_usuario_destino="cliente",
                titulo="Estado de solicitud actualizado",
                mensaje=mensaje,
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.ESTADO,
                referencia_entidad="SolicitudEmergencia",
                referencia_id=str(solicitud.id_solicitud),
                actor_id=asignacion.id_taller,
                actor_tipo=TipoActor.TALLER,
            )
        
        db.commit()
        db.refresh(asignacion)
        db.refresh(solicitud)
        
        # Registrar en bitácora
        detalle = f"Estado de atención actualizado a {nuevo_estado_solicitud.value}. Solicitud: {solicitud.codigo_solicitud}"
        if comentario:
            detalle += f". Comentario: {comentario}"
        
        AsignacionService._registrar_bitacora(
            db=db,
            accion="Actualización de estado de atención",
            resultado=ResultadoAuditoria.EXITO,
            detalle=detalle,
            id_entidad=asignacion_id,
            tipo_actor=TipoActor.TALLER if current_user and current_user.rol == RolUsuario.TALLER else TipoActor.SISTEMA,
            id_actor=current_user.id_usuario if current_user else None,
        )
        
        return asignacion

    @staticmethod
    def get_servicios_taller(db: Session, asignacion_id: UUID, current_user: Usuario):
        """
        Obtiene el cat?logo de servicios del taller con metadatos de cotizaci?n y ejecuci?n.
        """
        from app.models.taller_servicio import TallerServicio
        from app.models.servicio import Servicio

        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)
        servicios_taller = db.query(TallerServicio).filter(
            TallerServicio.id_taller == asignacion.id_taller
        ).join(Servicio).all()

        return ServicioEjecutadoService.build_servicios_catalogo(
            asignacion,
            servicios_taller,
            list(asignacion.resultados or []),
        )

    @staticmethod
    def guardar_servicios_realizados(
        db: Session,
        asignacion_id: UUID,
        servicios: list,
        current_user: Usuario,
    ):
        """
        Guarda servicios ejecutados diferenciando entre cotizados obligatorios y extras.
        """
        from app.models.resultado_servicio import ResultadoServicio
        from app.models.taller_servicio import TallerServicio
        from app.core.enums import EstadoResultado

        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)

        if current_user.rol == RolUsuario.TALLER and asignacion.taller.id_usuario != current_user.id_usuario:
            raise forbidden("No tienes permiso para registrar servicios en esta asignaci?n")

        servicios_taller = db.query(TallerServicio).filter(
            TallerServicio.id_taller == asignacion.id_taller
        ).all()
        servicios_taller_map = {str(item.id_taller_servicio): item for item in servicios_taller}
        cotizacion_index = ServicioEjecutadoService.build_cotizacion_index(asignacion)
        resultados_actuales = ServicioEjecutadoService.enrich_resultados(asignacion, list(asignacion.resultados or []))
        cotizados_existentes: dict[str, int] = {}
        for item in resultados_actuales:
            if item["origen_item"] == "COTIZADO":
                key = item["id_taller_servicio"] or ""
                cotizados_existentes[key] = cotizados_existentes.get(key, 0) + 1

        nuevos_registros = 0
        for servicio_req in servicios:
            if not servicio_req.realizado:
                continue

            service_key = str(servicio_req.id_taller_servicio)
            taller_servicio = servicios_taller_map.get(service_key)
            if not taller_servicio:
                raise bad_request("El servicio seleccionado no pertenece al taller de la asignaci?n")

            origen_item = (getattr(servicio_req, "origen_item", None) or "EXTRA").upper()
            if origen_item not in {"COTIZADO", "EXTRA"}:
                raise bad_request("Origen de servicio inv?lido. Usa COTIZADO o EXTRA")

            precio_unitario = float(getattr(taller_servicio, "precio_base", 0) or 0)
            if origen_item == "COTIZADO":
                cotizados = cotizacion_index.get(service_key, [])
                usados = cotizados_existentes.get(service_key, 0)
                if usados >= len(cotizados):
                    raise bad_request(
                        f"El servicio {taller_servicio.servicio.nombre_servicio} ya no tiene items cotizados pendientes"
                    )
                precio_unitario = float(cotizados[usados]["precio_servicio"] or 0)
                cotizados_existentes[service_key] = usados + 1

            observaciones = ServicioEjecutadoService.encode_observaciones(
                servicio_req.observaciones,
                {
                    "origen_item": origen_item,
                    "precio_unitario": round(precio_unitario, 2),
                },
            )

            resultado = ResultadoServicio(
                id_asignacion=asignacion_id,
                id_solicitud=asignacion.id_solicitud,
                id_taller_servicio=servicio_req.id_taller_servicio,
                diagnostico=servicio_req.diagnostico,
                solucion_aplicada=servicio_req.solucion_aplicada,
                estado_resultado=EstadoResultado.RESUELTO,
                observaciones=observaciones,
                requiere_seguimiento=servicio_req.requiere_seguimiento,
            )
            db.add(resultado)
            nuevos_registros += 1

        db.commit()

        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService

        cliente = asignacion.solicitud.cliente
        if cliente and nuevos_registros > 0:
            mensaje = f"El taller {asignacion.taller.nombre_taller} ha registrado {nuevos_registros} servicio(s) realizado(s) en tu solicitud {asignacion.solicitud.codigo_solicitud}."

            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=cliente.id_usuario,
                tipo_usuario_destino="CLIENTE",
                titulo="Servicios registrados",
                mensaje=mensaje,
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.SOLICITUD,
                referencia_entidad="AsignacionAtencion",
                referencia_id=asignacion_id,
            )

    @staticmethod
    def get_servicios_realizados(
        db: Session,
        asignacion_id: UUID,
        current_user: Usuario,
    ):
        """
        Obtiene servicios realizados enriquecidos con origen y precio aplicado.
        """
        from app.models.resultado_servicio import ResultadoServicio

        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)
        servicios_realizados = db.query(ResultadoServicio).filter(
            ResultadoServicio.id_asignacion == asignacion_id
        ).all()

        resultado = []
        for item in ServicioEjecutadoService.enrich_resultados(asignacion, servicios_realizados):
            servicio = item["resultado"]
            resultado.append({
                'id_resultado_servicio': str(servicio.id_resultado_servicio),
                'id_taller_servicio': str(servicio.id_taller_servicio),
                'nombre_servicio': servicio.taller_servicio.servicio.nombre_servicio if servicio.taller_servicio and servicio.taller_servicio.servicio else None,
                'diagnostico': servicio.diagnostico,
                'solucion_aplicada': servicio.solucion_aplicada,
                'observaciones': item["observaciones_limpias"],
                'requiere_seguimiento': servicio.requiere_seguimiento,
                'estado_resultado': servicio.estado_resultado.value,
                'fecha_registro': servicio.fecha_registro.isoformat() if servicio.fecha_registro else None,
                'origen_item': item["origen_item"],
                'precio_unitario': item["precio_unitario"],
            })

        return resultado
