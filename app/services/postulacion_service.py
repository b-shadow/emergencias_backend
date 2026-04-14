from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.enums import (
    RolUsuario,
    EstadoPostulacion,
    EstadoSolicitud,
    EstadoAsignacion,
    TipoActor,
    TipoNotificacion,
    CategoriaNotificacion,
    ResultadoAuditoria,
)
from app.core.exceptions import not_found, forbidden, bad_request
from app.models.postulacion_taller import PostulacionTaller
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller
from app.models.usuario import Usuario
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.historial_estado_solicitud import HistorialEstadoSolicitud
from app.models.bitacora import Bitacora


class PostulacionService:
    @staticmethod
    def _registrar_bitacora(
        db: Session,
        accion: str,
        entidad_afectada: str,
        id_entidad_afectada: UUID,
        id_actor: UUID,
        resultado: ResultadoAuditoria,
        tipo_actor: TipoActor = TipoActor.CLIENTE,
        detalle: str | None = None,
    ) -> None:
        """
        Registra una acción en bitácora.
        
        Args:
            db: Sesión de base de datos
            accion: Descripción de la acción realizada
            entidad_afectada: Tipo de entidad afectada (e.g., "Postulación")
            id_entidad_afectada: ID de la entidad afectada
            id_actor: ID del usuario que realizó la acción
            resultado: Resultado de la acción (EXITO, ERROR, ADVERTENCIA)
            tipo_actor: Tipo de actor que realiza la acción (por defecto CLIENTE)
            detalle: Detalle adicional de la acción
        """
        bitacora = Bitacora(
            tipo_actor=tipo_actor,
            id_actor=id_actor,
            accion=accion,
            modulo="Postulaciones",
            entidad_afectada=entidad_afectada,
            id_entidad_afectada=id_entidad_afectada,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()

    @staticmethod
    def list_postulaciones_for_solicitud(db: Session, solicitud_id: UUID, current_user: Usuario):
        """
        Lista postulaciones para una solicitud específica.
        - CLIENTE: Solo puede ver postulaciones de sus propias solicitudes
        - TALLER: Solo puede ver su propia postulación
        - ADMINISTRADOR: Puede ver todas
        """
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        if not solicitud:
            raise not_found("Solicitud no encontrada")
        
        # Verificar acceso a la solicitud
        if current_user.rol == RolUsuario.CLIENTE:
            # Obtener id_cliente del usuario actual
            from app.models.cliente import Cliente
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or solicitud.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes acceso a esta solicitud")
        
        query = db.query(PostulacionTaller).filter(PostulacionTaller.id_solicitud == solicitud_id)
        
        # Si es TALLER, filtrar solo su postulación
        if current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if taller:
                query = query.filter(PostulacionTaller.id_taller == taller.id_taller)
        
        return query.all()

    @staticmethod
    def get_mis_postulaciones(db: Session, current_user: Usuario):
        """
        Obtiene todas las postulaciones del taller actual (CU-18, CU-19).
        - Solo TALLER puede acceder a sus propias postulaciones
        """
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo los talleres pueden acceder a sus postulaciones")
        
        from app.models.taller import Taller
        from sqlalchemy.orm import joinedload
        
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise not_found("Taller no encontrado")
        
        postulaciones = db.query(PostulacionTaller).options(
            joinedload(PostulacionTaller.solicitud)
        ).filter(
            PostulacionTaller.id_taller == taller.id_taller
        ).all()
        
        return postulaciones

    @staticmethod
    def get_postulacion(db: Session, postulacion_id: UUID, current_user: Usuario):
        """
        Obtiene una postulación específica.
        - CLIENTE: Puede ver postulaciones de sus solicitudes
        - TALLER: Puede ver su propia postulación
        - ADMINISTRADOR: Puede ver cualquiera
        """
        postulacion = db.query(PostulacionTaller).filter(
            PostulacionTaller.id_postulacion == postulacion_id
        ).first()
        if not postulacion:
            raise not_found("Postulación no encontrada")
        
        # Access control
        if current_user.rol == RolUsuario.CLIENTE:
            from app.models.cliente import Cliente
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or postulacion.solicitud.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes acceso a esta postulación")
        elif current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if not taller or postulacion.id_taller != taller.id_taller:
                raise forbidden("No tienes acceso a esta postulación")
        
        return postulacion

    @staticmethod
    def create_postulacion(
        db: Session,
        solicitud_id: UUID,
        data: dict,
        current_user: Usuario,
    ):
        """
        Crea una postulación de taller.
        - Solo TALLER puede postularse
        - No debe existir postulación activa del mismo taller
        - La solicitud debe estar en estado EN_BUSQUEDA o EN_ESPERA_RESPUESTAS
        """
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo los talleres pueden postularse")
        
        # Obtener la solicitud
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        if not solicitud:
            raise not_found("Solicitud no encontrada")
        
        logger.info(f"[POSTULACION] Solicitud obtenida: id_solicitud={solicitud_id}, id_cliente={solicitud.id_cliente}, estado={solicitud.estado_actual}")
        
        # Validar estado de solicitud
        if solicitud.estado_actual not in (
            EstadoSolicitud.REGISTRADA,
            EstadoSolicitud.EN_BUSQUEDA,
            EstadoSolicitud.EN_ESPERA_RESPUESTAS,
        ):
            raise bad_request(
                f"No se puede postular en una solicitud en estado: {solicitud.estado_actual}"
            )
        
        # Obtener id del taller
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise not_found("Perfil de taller no encontrado")
        
        # Validar que no exista postulación activa del mismo taller
        postulacion_existente = db.query(PostulacionTaller).filter(
            PostulacionTaller.id_solicitud == solicitud_id,
            PostulacionTaller.id_taller == taller.id_taller,
            PostulacionTaller.estado_postulacion == EstadoPostulacion.POSTULADA,
        ).first()
        if postulacion_existente:
            raise bad_request("Ya existe una postulación activa de tu taller para esta solicitud")
        
        # Crear postulación
        data["id_solicitud"] = solicitud_id
        data["id_taller"] = taller.id_taller
        data["estado_postulacion"] = EstadoPostulacion.POSTULADA
        
        postulacion = PostulacionTaller(**data)
        db.add(postulacion)
        db.flush()
        
        # Enviar notificación al cliente
        logger.info(f"[POSTULACION] Iniciando envío de notificación para solicitud {solicitud_id}")
        logger.info(f"[POSTULACION] Detalles: id_cliente={solicitud.id_cliente}, taller={taller.nombre_taller}")
        
        try:
            if not solicitud.id_cliente:
                logger.warning(f"[POSTULACION] ⚠️ Solicitud {solicitud_id} NO TIENE cliente asignado")
            else:
                from app.models.cliente import Cliente
                logger.info(f"[POSTULACION] 🔍 Buscando Cliente con id_cliente={solicitud.id_cliente}")
                cliente = db.query(Cliente).filter(
                    Cliente.id_cliente == solicitud.id_cliente
                ).first()
                
                if not cliente:
                    logger.warning(f"[POSTULACION] ⚠️ No se encontró cliente con ID {solicitud.id_cliente}")
                elif not cliente.id_usuario:
                    logger.warning(f"[POSTULACION] ⚠️ Cliente {cliente.id_cliente} NO TIENE id_usuario asignado")
                else:
                    logger.info(f"[POSTULACION] ✅ Cliente válido: id_usuario={cliente.id_usuario}")
                    
                    mensaje_notif = (
                        f"El taller '{taller.nombre_taller}' se ha postulado para atender tu solicitud {solicitud.codigo_solicitud}. "
                    )
                    tiempo_estimado = data.get("tiempo_estimado_llegada_min")
                    if tiempo_estimado:
                        mensaje_notif += f"Tiempo estimado de llegada: {tiempo_estimado} minutos. "
                    
                    from app.core.enums import TipoNotificacion, CategoriaNotificacion
                    from app.services.notificacion_service import NotificacionService
                    
                    logger.info(f"[POSTULACION] 📤 Llamando NotificacionService.send_notification_to_user()...")
                    resultado = NotificacionService.send_notification_to_user(
                        db=db,
                        id_usuario_destino=cliente.id_usuario,
                        tipo_usuario_destino="CLIENTE",
                        titulo="Nuevo Taller Interesado",
                        mensaje=mensaje_notif,
                        tipo_notificacion=TipoNotificacion.PUSH,
                        categoria_evento=CategoriaNotificacion.POSTULACION,
                        referencia_entidad="PostulacionTaller",
                        referencia_id=postulacion.id_postulacion,
                    )
                    logger.info(f"[POSTULACION] ✅ Notificación enviada exitosamente: {resultado}")
        except Exception as e:
            logger.exception(f"[POSTULACION] ❌ Error al enviar notificación al cliente: {str(e)}")
        
        db.commit()
        db.refresh(postulacion)
        
        # Registrar en bitácora
        PostulacionService._registrar_bitacora(
            db=db,
            accion="Postulación de taller en solicitud",
            entidad_afectada="Postulación",
            id_entidad_afectada=postulacion.id_postulacion,
            id_actor=current_user.id_usuario,
            tipo_actor=TipoActor.TALLER,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller '{taller.nombre_taller}' se postuló para solicitud {solicitud_id}",
        )
        
        return postulacion

    @staticmethod
    def accept_postulacion(db: Session, postulacion_id: UUID, current_user: Usuario):
        """
        Acepta una postulación: CLIENTE selecciona el taller (Phase 9).
        - Solo CLIENTE puede aceptar postulaciones de su solicitud
        - Valida que haya postulaciones disponibles (E1)
        - Valida que solicitud no esté ya asignada (E2)
        - Rechaza otras postulaciones y crea asignación
        - Notifica a taller aceptado y talleres rechazados
        
        Excepciones:
        - E1: No existen postulaciones -> "E1: No hay talleres disponibles"
        - E2: Solicitud ya asignada -> "E2: Solicitud ya cuenta con taller asignado"
        """
        # Validar rol
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo el cliente puede aceptar postulaciones")
        
        # Obtener postulación
        postulacion = PostulacionService.get_postulacion(db, postulacion_id, current_user)
        
        # Obtener solicitud
        solicitud = postulacion.solicitud
        
        # E1: Verificar que existan postulaciones en POSTULADA
        postulaciones_disponibles = db.query(PostulacionTaller).filter(
            PostulacionTaller.id_solicitud == postulacion.id_solicitud,
            PostulacionTaller.estado_postulacion == EstadoPostulacion.POSTULADA,
        ).count()
        
        if postulaciones_disponibles == 0:
            raise bad_request(
                "E1: No hay talleres disponibles para esta solicitud. "
                "Por favor, intenta ampliar la zona de búsqueda"
            )
        
        # E2: Verificar que solicitud no esté ya asignada
        asignacion_existente = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_solicitud == postulacion.id_solicitud,
            AsignacionAtencion.estado_asignacion == EstadoAsignacion.ACTIVA,
        ).first()
        
        if asignacion_existente:
            raise bad_request(
                "E2: La solicitud ya cuenta con un taller asignado. "
                "No se puede seleccionar otro taller"
            )
        
        # Validar que la postulación esté en estado POSTULADA
        if postulacion.estado_postulacion != EstadoPostulacion.POSTULADA:
            raise bad_request(
                f"La postulación no está disponible. "
                f"Estado actual: {postulacion.estado_postulacion}"
            )
        
        # Validar que solicitud esté en estado apropiado
        estados_validos = [
            EstadoSolicitud.REGISTRADA,
            EstadoSolicitud.EN_BUSQUEDA,
            EstadoSolicitud.EN_ESPERA_RESPUESTAS,
        ]
        if solicitud.estado_actual not in estados_validos:
            raise bad_request(
                f"No se puede asignar en una solicitud en estado: {solicitud.estado_actual}"
            )
        
        # Obtener otras postulaciones POSTULADA para rechazarlas
        otras_postulaciones_ids = db.query(PostulacionTaller.id_postulacion).filter(
            PostulacionTaller.id_solicitud == postulacion.id_solicitud,
            PostulacionTaller.id_postulacion != postulacion_id,
            PostulacionTaller.estado_postulacion == EstadoPostulacion.POSTULADA,
        ).all()
        
        # Rechazar otras postulaciones
        db.query(PostulacionTaller).filter(
            PostulacionTaller.id_solicitud == postulacion.id_solicitud,
            PostulacionTaller.id_postulacion != postulacion_id,
            PostulacionTaller.estado_postulacion == EstadoPostulacion.POSTULADA,
        ).update({"estado_postulacion": EstadoPostulacion.RECHAZADA, 
                  "fecha_respuesta": datetime.now()})
        
        # Actualizar postulación a ACEPTADA
        postulacion.estado_postulacion = EstadoPostulacion.ACEPTADA
        postulacion.fecha_respuesta = datetime.now()
        
        # Crear asignación
        asignacion = AsignacionAtencion(
            id_solicitud=postulacion.id_solicitud,
            id_taller=postulacion.id_taller,
            id_postulacion=postulacion.id_postulacion,
            estado_asignacion=EstadoAsignacion.ACTIVA,
        )
        db.add(asignacion)
        
        # Actualizar estado de solicitud
        estado_anterior = solicitud.estado_actual
        solicitud.estado_actual = EstadoSolicitud.TALLER_SELECCIONADO
        
        # Registrar en historial
        historial = HistorialEstadoSolicitud(
            id_solicitud=postulacion.id_solicitud,
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoSolicitud.TALLER_SELECCIONADO,
            actualizado_por_tipo=TipoActor.CLIENTE,
            actualizado_por_id=current_user.id_usuario,
            comentario=f"Taller seleccionado: {postulacion.taller.nombre_taller}",
        )
        db.add(historial)
        
        # Notificar al taller seleccionado - Usar servicio central
        from app.services.notificacion_service import NotificacionService
        
        if postulacion.taller.id_usuario:
            NotificacionService.send_notification_to_user(
                db=db,
                id_usuario_destino=postulacion.taller.id_usuario,
                tipo_usuario_destino="TALLER",
                titulo="¡Tu postulación fue aceptada!",
                mensaje=f"Tu postulación para la solicitud {solicitud.codigo_solicitud} ha sido aceptada. "
                       f"Cliente: {solicitud.cliente.nombre} {solicitud.cliente.apellido}. "
                       f"Procede a atender la emergencia.",
                tipo_notificacion=TipoNotificacion.PUSH,
                categoria_evento=CategoriaNotificacion.POSTULACION,
                referencia_entidad="PostulacionTaller",
                referencia_id=str(postulacion.id_postulacion),
                actor_id=current_user.id_usuario,
                actor_tipo=TipoActor.CLIENTE,
            )
        
        # Notificar a talleres rechazados
        for postulacion_rechazada_id in otras_postulaciones_ids:
            postulacion_rechazada = db.query(PostulacionTaller).filter(
                PostulacionTaller.id_postulacion == postulacion_rechazada_id[0]
            ).first()
            
            if postulacion_rechazada and postulacion_rechazada.taller.id_usuario:
                NotificacionService.send_notification_to_user(
                    db=db,
                    id_usuario_destino=postulacion_rechazada.taller.id_usuario,
                    tipo_usuario_destino="TALLER",
                    titulo="Postulación no seleccionada",
                    mensaje=f"Tu postulación para {solicitud.codigo_solicitud} no fue seleccionada. "
                           f"El cliente eligió otro taller. Puedes intentar con otras solicitudes.",
                    tipo_notificacion=TipoNotificacion.PUSH,
                    categoria_evento=CategoriaNotificacion.POSTULACION,
                    referencia_entidad="PostulacionTaller",
                    referencia_id=str(postulacion_rechazada.id_postulacion),
                    actor_id=current_user.id_usuario,
                    actor_tipo=TipoActor.CLIENTE,
                )
        
        db.commit()
        db.refresh(postulacion)
        
        # Registrar en bitácora
        PostulacionService._registrar_bitacora(
            db=db,
            accion="Selección de taller para atención de emergencia",
            entidad_afectada="Postulación",
            id_entidad_afectada=postulacion.id_postulacion,
            id_actor=current_user.id_usuario,
            tipo_actor=TipoActor.CLIENTE,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Cliente seleccionó taller '{postulacion.taller.nombre_taller}' "
                    f"({postulaciones_disponibles} postulaciones disponibles) "
                    f"para solicitud {postulacion.id_solicitud}",
        )
        
        return postulacion

    @staticmethod
    def reject_postulacion(db: Session, postulacion_id: UUID, current_user: Usuario):
        """
        Rechaza una postulación: CLIENTE desestima el taller.
        - Solo CLIENTE puede rechazar postulaciones de su solicitud
        """
        postulacion = PostulacionService.get_postulacion(db, postulacion_id, current_user)
        
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo el cliente puede rechazar postulaciones")
        
        # Validar que la postulación esté en estado POSTULADA
        if postulacion.estado_postulacion != EstadoPostulacion.POSTULADA:
            raise bad_request(f"La postulación está en estado: {postulacion.estado_postulacion}")
        
        # Actualizar estado
        postulacion.estado_postulacion = EstadoPostulacion.RECHAZADA
        postulacion.fecha_respuesta = datetime.now()
        
        db.commit()
        db.refresh(postulacion)
        
        # Registrar en bitácora
        PostulacionService._registrar_bitacora(
            db=db,
            accion="Rechazo de postulación de taller",
            entidad_afectada="Postulación",
            id_entidad_afectada=postulacion.id_postulacion,
            id_actor=current_user.id_usuario,
            tipo_actor=TipoActor.CLIENTE,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Cliente rechazó la postulación del taller '{postulacion.taller.nombre_taller}' para la solicitud {postulacion.id_solicitud}",
        )
        
        return postulacion

    @staticmethod
    def withdraw_postulacion(db: Session, postulacion_id: UUID, current_user: Usuario):
        """
        Retira una postulación: TALLER se arrepiente.
        - Solo TALLER propietario puede retirar su postulación
        - Solo si está en estado POSTULADA (no si fue ACEPTADA)
        
        Excepciones:
        - E1: Solicitud ya aceptada (estado ACEPTADA) -> No puede retirar
        - E2: Postulación no encontrada -> Se maneja en get_postulacion()
        """
        # Validar rol
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede retirar su postulación")
        
        # Obtener postulación
        postulacion = PostulacionService.get_postulacion(db, postulacion_id, current_user)
        
        # E1: Verificar que no esté ACEPTADA (ya fue seleccionada por cliente)
        if postulacion.estado_postulacion == EstadoPostulacion.ACEPTADA:
            raise bad_request(
                f"E1: La postulación ya fue aceptada por el cliente. "
                f"No puede retirar una postulación que ya está en atención"
            )
        
        # Verificar que esté en POSTULADA (único estado válido para retirar)
        if postulacion.estado_postulacion != EstadoPostulacion.POSTULADA:
            raise bad_request(
                f"E2: La postulación no está disponible para retiro. "
                f"Estado actual: {postulacion.estado_postulacion}"
            )
        
        # Obtener taller para bitácora
        taller = db.query(Usuario).filter(Usuario.id_usuario == postulacion.id_taller).first()
        taller_nombre = taller.nombre_razon_social if taller else "Desconocido"
        
        # Actualizar estado
        postulacion.estado_postulacion = EstadoPostulacion.RETIRADA
        postulacion.fecha_respuesta = datetime.now()
        
        db.commit()
        db.refresh(postulacion)
        
        # Registrar en bitácora
        PostulacionService._registrar_bitacora(
            db=db,
            accion="Retiro de postulación de taller",
            entidad_afectada="Postulación",
            id_entidad_afectada=postulacion.id_postulacion,
            id_actor=current_user.id_usuario,
            tipo_actor=TipoActor.TALLER,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller '{taller_nombre}' retiró su postulación para la solicitud {postulacion.id_solicitud}",
        )
        
        return postulacion
