from datetime import datetime
from uuid import UUID
import logging

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.enums import (
    TipoNotificacion,
    CategoriaNotificacion,
    EstadoLecturaNotificacion,
    EstadoEnvioNotificacion,
    TipoActor,
    ResultadoAuditoria,
)
from app.core.exceptions import not_found, forbidden
from app.models.notificacion import Notificacion
from app.models.bitacora import Bitacora
from app.models.usuario import Usuario
from app.services.dispositivo_push_service import DispositivoPushService
from app.services.fcm_service import FCMService

logger = logging.getLogger(__name__)


class NotificacionService:
    """
    Servicio para gestionar notificaciones y envío push.
    
    Responsabilidades:
    - Crear y persistir notificaciones en BD
    - Listar notificaciones del usuario actual
    - Listar historial administrativo
    - Marcar notificaciones como leídas
    - Enviar notificaciones push a través de FCM
    - Integración con bitácora
    """

    @staticmethod
    def create_notification(
        db: Session,
        id_usuario_destino: UUID,
        tipo_usuario_destino: str,
        titulo: str,
        mensaje: str,
        tipo_notificacion: TipoNotificacion,
        categoria_evento: CategoriaNotificacion,
        referencia_entidad: str | None = None,
        referencia_id: UUID | None = None,
        estado_envio: EstadoEnvioNotificacion = EstadoEnvioNotificacion.PENDIENTE,
    ) -> Notificacion:
        """
        Crea un nuevo registro de notificación en la base de datos.
        
        Args:
            db: Sesión de base de datos
            id_usuario_destino: ID del usuario que recibe la notificación
            tipo_usuario_destino: Tipo de usuario (CLIENTE, TALLER, ADMINISTRADOR)
            titulo: Título de la notificación
            mensaje: Cuerpo/mensaje de la notificación
            tipo_notificacion: Tipo (PUSH, INTERNA, EMAIL)
            categoria_evento: Categoría (SOLICITUD, POSTULACION, etc)
            referencia_entidad: Entidad relacionada (solicitud, postulacion, etc)
            referencia_id: ID de la entidad relacionada
            estado_envio: Estado inicial del envío
            
        Returns:
            Notificación creada
        """
        notificacion = Notificacion(
            tipo_usuario_destino=tipo_usuario_destino,
            id_usuario_destino=id_usuario_destino,
            titulo=titulo,
            mensaje=mensaje,
            tipo_notificacion=tipo_notificacion,
            categoria_evento=categoria_evento,
            referencia_entidad=referencia_entidad,
            referencia_id=referencia_id,
            estado_lectura=EstadoLecturaNotificacion.NO_LEIDA,
            estado_envio=estado_envio,
            fecha_envio=datetime.utcnow(),
        )
        db.add(notificacion)
        db.commit()
        db.refresh(notificacion)
        return notificacion

    @staticmethod
    def send_notification_to_user(
        db: Session,
        id_usuario_destino: UUID,
        tipo_usuario_destino: str,
        titulo: str,
        mensaje: str,
        tipo_notificacion: TipoNotificacion,
        categoria_evento: CategoriaNotificacion,
        referencia_entidad: str | None = None,
        referencia_id: UUID | None = None,
        data: dict | None = None,
        actor_id: UUID | None = None,
        actor_tipo: TipoActor | None = None,
        ip_origen: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """
        Función principal para enviar una notificación a un usuario.
        
        Esta función:
        1. Crea el registro en BD
        2. Obtiene tokens activos del usuario
        3. Intenta enviar push a través de FCM si hay tokens
        4. Actualiza el estado de envío
        5. Registra en bitácora
        
        Args:
            db: Sesión de base de datos
            id_usuario_destino: ID del usuario destino
            tipo_usuario_destino: Tipo de usuario destino
            titulo: Título del mensaje
            mensaje: Cuerpo del mensaje
            tipo_notificacion: Tipo de notificación
            categoria_evento: Categoría de evento
            referencia_entidad: Entidad relacionada (opcional)
            referencia_id: ID de entidad relacionada (opcional)
            data: Datos adicionales para push (diccionario)
            actor_id: ID de quien genera la notificación (opcional)
            actor_tipo: Tipo de actor que genera (opcional)
            ip_origen: IP del cliente (para bitácora)
            user_agent: User agent (para bitácora)
            
        Returns:
            Diccionario con resultado del envío:
            {
                'notification_id': UUID,
                'estado_envio': EstadoEnvioNotificacion,
                'tokens_intentados': int,
                'tokens_exitosos': int,
                'tokens_fallidos': int,
                'mensaje': str
            }
        """
        # 1. Crear notificación en BD con estado PENDIENTE
        notificacion = NotificacionService.create_notification(
            db=db,
            id_usuario_destino=id_usuario_destino,
            tipo_usuario_destino=tipo_usuario_destino,
            titulo=titulo,
            mensaje=mensaje,
            tipo_notificacion=tipo_notificacion,
            categoria_evento=categoria_evento,
            referencia_entidad=referencia_entidad,
            referencia_id=referencia_id,
            estado_envio=EstadoEnvioNotificacion.PENDIENTE,
        )

        # 2. Obtener tokens activos del usuario
        tokens_activos = DispositivoPushService.get_active_tokens_for_user(
            db=db,
            id_usuario=id_usuario_destino
        )

        tokens_fcm = [t.token_fcm for t in tokens_activos]
        tokens_exitosos = 0
        tokens_fallidos = len(tokens_fcm)
        estado_envio = EstadoEnvioNotificacion.PENDIENTE

        # 3. Intentar envío push si hay tokens
        if tokens_fcm and FCMService.is_available():
            # Preparar datos para push
            push_data = data or {}
            push_data.update({
                'notification_id': str(notificacion.id_notificacion),
                'categoria_evento': categoria_evento.value,
                'tipo_notificacion': tipo_notificacion.value,
            })
            if referencia_entidad:
                push_data['referencia_entidad'] = referencia_entidad
            if referencia_id:
                push_data['referencia_id'] = str(referencia_id)

            # Enviar multicast
            fcm_result = FCMService.send_to_tokens(
                tokens=tokens_fcm,
                title=titulo,
                body=mensaje,
                data=push_data
            )

            tokens_exitosos = fcm_result['success_count']
            tokens_fallidos = fcm_result['failure_count']

            # Procesar resultados y desactivar tokens inválidos
            for result in fcm_result.get('results', []):
                if result.get('token_invalid'):
                    # Encontrar dispositivo por token y desactivarlo
                    for dispositivo in tokens_activos:
                        if dispositivo.token_fcm == result['token']:
                            DispositivoPushService.deactivate_token(
                                db=db,
                                id_dispositivo_push=dispositivo.id_dispositivo_push
                            )
                            logger.warning(
                                f"Token inválido desactivado: {result['token'][:20]}..."
                            )
                            break

            # Establecer estado de envío
            if tokens_exitosos > 0:
                estado_envio = EstadoEnvioNotificacion.ENVIADA
            else:
                estado_envio = EstadoEnvioNotificacion.FALLIDA
        elif tokens_fcm and not FCMService.is_available():
            # Hay tokens, pero FCM no está disponible: fue intento fallido de push.
            # Marcar como FALLIDA para no ocultar este problema como "pendiente".
            logger.warning(
                "[NOTIFICACION] Push no enviado: hay tokens activos pero FCM no está disponible"
            )
            estado_envio = EstadoEnvioNotificacion.FALLIDA
            tokens_exitosos = 0
            tokens_fallidos = len(tokens_fcm)
        else:
            # No hay tokens activos para el usuario (queda pendiente de próxima sesión/token)
            estado_envio = EstadoEnvioNotificacion.PENDIENTE

        # 4. Actualizar estado en BD
        notificacion.estado_envio = estado_envio
        db.commit()

        # 5. Registrar en bitácora
        NotificacionService._registrar_bitacora(
            db=db,
            tipo_actor=actor_tipo or TipoActor.SISTEMA,
            id_actor=actor_id,
            accion="Enviar notificación",
            modulo="Notificaciones",
            entidad_afectada="Notificacion",
            id_entidad_afectada=notificacion.id_notificacion,
            resultado=ResultadoAuditoria.EXITO if tokens_exitosos > 0 or len(tokens_fcm) == 0 else ResultadoAuditoria.ADVERTENCIA,
            detalle=f"Notificación enviada a {id_usuario_destino}. "
                   f"Tokens intentados: {len(tokens_fcm)}, "
                   f"Exitosos: {tokens_exitosos}, "
                   f"Fallidos: {tokens_fallidos}",
            ip_origen=ip_origen,
            user_agent=user_agent,
        )

        return {
            'notification_id': notificacion.id_notificacion,
            'estado_envio': estado_envio,
            'tokens_intentados': len(tokens_fcm),
            'tokens_exitosos': tokens_exitosos,
            'tokens_fallidos': tokens_fallidos,
            'mensaje': f"Notificación {'enviada' if tokens_exitosos > 0 else 'registrada'}"
        }

    @staticmethod
    def list_my_notifications(
        db: Session,
        id_usuario: UUID,
        tipo_notificacion: TipoNotificacion | None = None,
        categoria_evento: CategoriaNotificacion | None = None,
        estado_lectura: EstadoLecturaNotificacion | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """
        Lista las notificaciones del usuario autenticado.
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario actual
            tipo_notificacion: Filtro por tipo (opcional)
            categoria_evento: Filtro por categoría (opcional)
            estado_lectura: Filtro por estado de lectura (opcional)
            fecha_desde: Filtro desde fecha (opcional)
            fecha_hasta: Filtro hasta fecha (opcional)
            limit: Límite de registros
            offset: Desplazamiento
            
        Returns:
            Diccionario con lista paginada de notificaciones
        """
        query = db.query(Notificacion).filter(
            Notificacion.id_usuario_destino == id_usuario
        )

        # Aplicar filtros
        if tipo_notificacion:
            query = query.filter(Notificacion.tipo_notificacion == tipo_notificacion)
        if categoria_evento:
            query = query.filter(Notificacion.categoria_evento == categoria_evento)
        if estado_lectura:
            query = query.filter(Notificacion.estado_lectura == estado_lectura)
        if fecha_desde:
            query = query.filter(Notificacion.fecha_envio >= fecha_desde)
        if fecha_hasta:
            query = query.filter(Notificacion.fecha_envio <= fecha_hasta)

        # Contar total
        total = query.count()

        # Obtener registros ordenados por fecha descendente
        notificaciones = query.order_by(
            Notificacion.fecha_envio.desc()
        ).offset(offset).limit(limit).all()

        return {
            'items': notificaciones,
            'total': total,
            'limit': limit,
            'offset': offset,
        }

    @staticmethod
    def get_my_notification_detail(
        db: Session,
        id_usuario: UUID,
        id_notificacion: UUID,
        registrar_consulta: bool = True,
    ) -> Notificacion:
        """
        Obtiene el detalle de una notificación del usuario.
        
        Si no estaba leída, la marca como leída.
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario actual
            id_notificacion: ID de la notificación
            registrar_consulta: Si se debe registrar en bitácora
            
        Returns:
            Notificación encontrada
            
        Raises:
            not_found: Si no existe
            forbidden: Si no pertenece al usuario
        """
        notificacion = db.query(Notificacion).filter(
            Notificacion.id_notificacion == id_notificacion
        ).first()

        if not notificacion:
            raise not_found("Notificación no encontrada")

        if notificacion.id_usuario_destino != id_usuario:
            raise forbidden("No tienes acceso a esta notificación")

        # Marcar como leída si no lo estaba
        if notificacion.estado_lectura == EstadoLecturaNotificacion.NO_LEIDA:
            notificacion.estado_lectura = EstadoLecturaNotificacion.LEIDA
            notificacion.fecha_lectura = datetime.utcnow()
            db.commit()

            # Registrar en bitácora si se solicita
            if registrar_consulta:
                NotificacionService._registrar_bitacora(
                    db=db,
                    tipo_actor=TipoActor.CLIENTE if notificacion.tipo_usuario_destino == "CLIENTE" else TipoActor.TALLER,
                    id_actor=id_usuario,
                    accion="Ver notificación",
                    modulo="Notificaciones",
                    entidad_afectada="Notificacion",
                    id_entidad_afectada=id_notificacion,
                    resultado=ResultadoAuditoria.EXITO,
                    detalle=f"Usuario visualizó notificación"
                )

        return notificacion

    @staticmethod
    def mark_as_read(
        db: Session,
        id_usuario: UUID,
        id_notificacion: UUID,
        registrar_en_bitacora: bool = True,
    ) -> Notificacion:
        """
        Marca explícitamente una notificación como leída.
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario actual
            id_notificacion: ID de la notificación
            registrar_en_bitacora: Si se debe registrar
            
        Returns:
            Notificación actualizada
            
        Raises:
            not_found: Si no existe
            forbidden: Si no pertenece al usuario
        """
        notificacion = db.query(Notificacion).filter(
            Notificacion.id_notificacion == id_notificacion
        ).first()

        if not notificacion:
            raise not_found("Notificación no encontrada")

        if notificacion.id_usuario_destino != id_usuario:
            raise forbidden("No tienes acceso a esta notificación")

        # Marcar como leída
        if notificacion.estado_lectura == EstadoLecturaNotificacion.NO_LEIDA:
            notificacion.estado_lectura = EstadoLecturaNotificacion.LEIDA
            notificacion.fecha_lectura = datetime.utcnow()
            db.commit()

            if registrar_en_bitacora:
                NotificacionService._registrar_bitacora(
                    db=db,
                    tipo_actor=TipoActor.CLIENTE if notificacion.tipo_usuario_destino == "CLIENTE" else TipoActor.TALLER,
                    id_actor=id_usuario,
                    accion="Marcar notificación como leída",
                    modulo="Notificaciones",
                    entidad_afectada="Notificacion",
                    id_entidad_afectada=id_notificacion,
                    resultado=ResultadoAuditoria.EXITO,
                    detalle=f"Notificación '{notificacion.titulo}' marcada como leída",
                )

        return notificacion

    @staticmethod
    def list_all_notifications_admin(
        db: Session,
        tipo_notificacion: TipoNotificacion | None = None,
        categoria_evento: CategoriaNotificacion | None = None,
        id_usuario_destino: UUID | None = None,
        estado_envio: EstadoEnvioNotificacion | None = None,
        estado_lectura: EstadoLecturaNotificacion | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """
        Lista todas las notificaciones del sistema (solo ADMINISTRADOR).
        
        Args:
            db: Sesión de base de datos
            tipo_notificacion: Filtro por tipo (opcional)
            categoria_evento: Filtro por categoría (opcional)
            id_usuario_destino: Filtro por usuario destino (opcional)
            estado_envio: Filtro por estado de envío (opcional)
            estado_lectura: Filtro por estado de lectura (opcional)
            fecha_desde: Filtro desde fecha (opcional)
            fecha_hasta: Filtro hasta fecha (opcional)
            limit: Límite de registros
            offset: Desplazamiento
            
        Returns:
            Diccionario con lista paginada incluyendo datos del usuario
        """
        # Query con JOIN a Usuario para obtener nombre_completo y rol
        query = db.query(
            Notificacion,
            Usuario.nombre_completo,
            Usuario.rol
        ).outerjoin(
            Usuario,
            Notificacion.id_usuario_destino == Usuario.id_usuario
        )

        # Aplicar filtros
        if tipo_notificacion:
            query = query.filter(Notificacion.tipo_notificacion == tipo_notificacion)
        if categoria_evento:
            query = query.filter(Notificacion.categoria_evento == categoria_evento)
        if id_usuario_destino:
            query = query.filter(Notificacion.id_usuario_destino == id_usuario_destino)
        if estado_envio:
            query = query.filter(Notificacion.estado_envio == estado_envio)
        if estado_lectura:
            query = query.filter(Notificacion.estado_lectura == estado_lectura)
        if fecha_desde:
            query = query.filter(Notificacion.fecha_envio >= fecha_desde)
        if fecha_hasta:
            query = query.filter(Notificacion.fecha_envio <= fecha_hasta)

        # Contar total
        total = query.count()

        # Obtener registros
        resultados = query.order_by(
            Notificacion.fecha_envio.desc()
        ).offset(offset).limit(limit).all()

        # Formatear resultados para que contengan los datos del usuario
        items = []
        for resultado in resultados:
            notificacion = resultado[0]
            nombre_usuario = resultado[1]
            rol_usuario = resultado[2]
            
            # Convertir a diccionario y enriquecer con datos del usuario
            notif_dict = {
                'id_notificacion': notificacion.id_notificacion,
                'tipo_usuario_destino': notificacion.tipo_usuario_destino,
                'id_usuario_destino': notificacion.id_usuario_destino,
                'titulo': notificacion.titulo,
                'mensaje': notificacion.mensaje,
                'tipo_notificacion': notificacion.tipo_notificacion,
                'categoria_evento': notificacion.categoria_evento,
                'referencia_entidad': notificacion.referencia_entidad,
                'referencia_id': notificacion.referencia_id,
                'estado_lectura': notificacion.estado_lectura,
                'estado_envio': notificacion.estado_envio,
                'fecha_envio': notificacion.fecha_envio,
                'fecha_lectura': notificacion.fecha_lectura,
                'nombre_usuario': nombre_usuario,
                'rol_usuario': rol_usuario.value if rol_usuario else None,
            }
            items.append(notif_dict)

        return {
            'items': items,
            'total': total,
            'limit': limit,
            'offset': offset,
        }

    @staticmethod
    def get_notification_detail_admin(
        db: Session,
        id_notificacion: UUID,
        registrar_consulta: bool = True,
    ) -> dict:
        """
        Obtiene el detalle de una notificación (solo ADMINISTRADOR).
        
        Args:
            db: Sesión de base de datos
            id_notificacion: ID de la notificación
            registrar_consulta: Si se debe registrar en bitácora
            
        Returns:
            Diccionario con notificación enriquecida con datos del usuario
            
        Raises:
            not_found: Si no existe
        """
        # Query con JOIN a Usuario para obtener nombre_completo y rol
        resultado = db.query(
            Notificacion,
            Usuario.nombre_completo,
            Usuario.rol
        ).outerjoin(
            Usuario,
            Notificacion.id_usuario_destino == Usuario.id_usuario
        ).filter(
            Notificacion.id_notificacion == id_notificacion
        ).first()

        if not resultado:
            raise not_found("Notificación no encontrada")

        notificacion = resultado[0]
        nombre_usuario = resultado[1]
        rol_usuario = resultado[2]

        if registrar_consulta:
            NotificacionService._registrar_bitacora(
                db=db,
                tipo_actor=TipoActor.ADMINISTRADOR,
                id_actor=None,  # Se rellenará después con el usuario actual
                accion="Ver detalle de notificación (admin)",
                modulo="Notificaciones",
                entidad_afectada="Notificacion",
                id_entidad_afectada=id_notificacion,
                resultado=ResultadoAuditoria.EXITO,
            )

        # Convertir a diccionario y enriquecer con datos del usuario
        notif_dict = {
            'id_notificacion': notificacion.id_notificacion,
            'tipo_usuario_destino': notificacion.tipo_usuario_destino,
            'id_usuario_destino': notificacion.id_usuario_destino,
            'titulo': notificacion.titulo,
            'mensaje': notificacion.mensaje,
            'tipo_notificacion': notificacion.tipo_notificacion,
            'categoria_evento': notificacion.categoria_evento,
            'referencia_entidad': notificacion.referencia_entidad,
            'referencia_id': notificacion.referencia_id,
            'estado_lectura': notificacion.estado_lectura,
            'estado_envio': notificacion.estado_envio,
            'fecha_envio': notificacion.fecha_envio,
            'fecha_lectura': notificacion.fecha_lectura,
            'nombre_usuario': nombre_usuario,
            'rol_usuario': rol_usuario.value if rol_usuario else None,
        }

        return notif_dict

    @staticmethod
    def _registrar_bitacora(
        db: Session,
        tipo_actor: TipoActor,
        id_actor: UUID | None,
        accion: str,
        modulo: str,
        entidad_afectada: str,
        id_entidad_afectada: UUID | None,
        resultado: ResultadoAuditoria,
        detalle: str | None = None,
        ip_origen: str | None = None,
        user_agent: str | None = None,
    ) -> Bitacora:
        """
        Registra un evento en la bitácora.
        
        Args:
            Parámetros estándar de bitácora
            
        Returns:
            Registro de bitácora creado
        """
        bitacora = Bitacora(
            tipo_actor=tipo_actor,
            id_actor=id_actor,
            accion=accion,
            modulo=modulo,
            entidad_afectada=entidad_afectada,
            id_entidad_afectada=id_entidad_afectada,
            resultado=resultado,
            detalle=detalle,
            ip_origen=ip_origen,
            user_agent=user_agent,
        )
        db.add(bitacora)
        db.commit()
        return bitacora
