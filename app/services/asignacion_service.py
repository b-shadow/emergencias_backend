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
        Obtiene los servicios disponibles del taller asignado a una solicitud.
        
        Retorna:
        - Servicios del taller (según taller_servicio) con id_taller_servicio
        - Sin realizar aún (realizado=False)
        """
        from app.models.taller_servicio import TallerServicio
        from app.models.servicio import Servicio
        
        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)
        
        # Obtener servicios del taller desde taller_servicio
        servicios_taller = db.query(TallerServicio).filter(
            TallerServicio.id_taller == asignacion.id_taller
        ).join(Servicio).all()
        
        resultado = []
        for ts in servicios_taller:
            resultado.append({
                'id_taller_servicio': str(ts.id_taller_servicio),  # IMPORTANTE: ID para enlazar en resultado_servicio
                'id_servicio': str(ts.servicio.id_servicio),
                'nombre_servicio': ts.servicio.nombre_servicio,
                'descripcion': ts.servicio.descripcion,
                'realizado': False,  # Por defecto no realizados
            })
        
        return resultado

    @staticmethod
    def guardar_servicios_realizados(
        db: Session,
        asignacion_id: UUID,
        servicios: list,
        current_user: Usuario,
    ):
        """
        Guarda los servicios realizados en una asignación.
        
        Este método crea un registro en resultado_servicio para cada servicio realizado,
        enlazándolo con taller_servicio (id_taller_servicio).
        """
        from app.models.resultado_servicio import ResultadoServicio
        from app.core.enums import EstadoResultado
        
        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)
        
        # TALLER solo puede guardar servicios de sus asignaciones
        if current_user.rol == RolUsuario.TALLER:
            if asignacion.taller.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para registrar servicios en esta asignación")
        
        # Guardar servicios realizados
        for servicio_req in servicios:
            if servicio_req.realizado:
                # Crear registro de servicio realizado en resultado_servicio
                # Conectado con taller_servicio a través de id_taller_servicio
                resultado = ResultadoServicio(
                    id_asignacion=asignacion_id,
                    id_solicitud=asignacion.id_solicitud,
                    id_taller_servicio=servicio_req.id_taller_servicio,  # Conexión con taller_servicio
                    diagnostico=servicio_req.diagnostico,
                    solucion_aplicada=servicio_req.solucion_aplicada,
                    estado_resultado=EstadoResultado.RESUELTO,
                    observaciones=servicio_req.observaciones,
                    requiere_seguimiento=servicio_req.requiere_seguimiento,
                )
                db.add(resultado)
        
        db.commit()
        
        # Notificar al cliente que servicios han sido registrados como realizados
        from app.core.enums import TipoNotificacion, CategoriaNotificacion
        from app.services.notificacion_service import NotificacionService
        
        cliente = asignacion.solicitud.cliente
        if cliente:
            count = sum(1 for s in servicios if s.realizado)
            mensaje = f"El taller {asignacion.taller.nombre_taller} ha registrado {count} servicio(s) realizado(s) en tu solicitud {asignacion.solicitud.codigo_solicitud}."
            
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
        Obtiene los servicios realizados de una asignación específica.
        Retorna lista de servicios con su información (id_taller_servicio, diagnostico, etc).
        """
        from app.models.resultado_servicio import ResultadoServicio
        from app.models.taller_servicio import TallerServicio
        
        # Verificar que la asignación existe y el usuario tiene permiso
        asignacion = AsignacionService.get_asignacion(db, asignacion_id, current_user)
        
        # Obtener todos los servicios realizados de esta asignación
        servicios_realizados = db.query(ResultadoServicio).filter(
            ResultadoServicio.id_asignacion == asignacion_id
        ).all()
        
        # Retornar lista de servicios con información completa
        resultado = []
        for servicio in servicios_realizados:
            resultado.append({
                'id_resultado_servicio': str(servicio.id_resultado_servicio),
                'id_taller_servicio': str(servicio.id_taller_servicio),
                'diagnostico': servicio.diagnostico,
                'solucion_aplicada': servicio.solucion_aplicada,
                'observaciones': servicio.observaciones,
                'requiere_seguimiento': servicio.requiere_seguimiento,
                'estado_resultado': servicio.estado_resultado.value,
                'fecha_registro': servicio.fecha_registro.isoformat() if servicio.fecha_registro else None,
            })
        
        return resultado

