from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from loguru import logger

from app.core.enums import RolUsuario, EstadoSolicitud, ResultadoAuditoria, TipoActor, TipoNotificacion, CategoriaNotificacion
from app.core.exceptions import not_found, forbidden, bad_request
from app.models.solicitud_emergencia import SolicitudEmergencia, EspecialidadSolicitudEmergencia, ServicioSolicitudEmergencia
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.models.historial_estado_solicitud import HistorialEstadoSolicitud
from app.models.bitacora import Bitacora
from app.models.taller import Taller
from app.services.notificacion_service import NotificacionService


class SolicitudService:
    
    @staticmethod
    def _registrar_bitacora(
        db: Session,
        accion: str,
        resultado: ResultadoAuditoria,
        detalle: str | None = None,
        id_entidad: UUID | None = None,
        tipo_actor: TipoActor | None = None,
        id_actor: UUID | None = None,
    ) -> None:
        """
        Registra evento en bitácora para solicitudes.
        
        Por defecto registra como SISTEMA, pero permite especificar otro tipo_actor e id_actor.
        """
        bitacora = Bitacora(
            tipo_actor=tipo_actor or TipoActor.SISTEMA,
            id_actor=id_actor,
            accion=accion,
            modulo="SolicitudEmergencia",
            entidad_afectada="SolicitudEmergencia",
            id_entidad_afectada=id_entidad,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()
    
    @staticmethod
    def _validar_solicitud_request(data: dict, cliente: Cliente) -> dict:
        """
        Valida que el request tenga la información mínima requerida.
        
        Validaciones:
        - Al menos código_solicitud
        - O descripción_texto O descripción_audio_url (pero no ambas vacías)
        - Si tiene id_vehiculo, debe verificarse que existe
        - Ubicación idealmente debe tener latitud/longitud
        
        Returns:
            dict con datos validados
            
        Raises:
            bad_request si no cumple validaciones
        """
        # Validar código de solicitud
        if not data.get("codigo_solicitud") or not str(data.get("codigo_solicitud")).strip():
            raise bad_request("El código de solicitud es requerido")
        
        # Validar información mínima de descripción
        descripcion_texto = data.get("descripcion_texto")
        descripcion_audio_url = data.get("descripcion_audio_url")
        transcripcion_audio = data.get("transcripcion_audio")
        
        texto_disponible = bool(
            (descripcion_texto and str(descripcion_texto).strip()) or
            (transcripcion_audio and str(transcripcion_audio).strip())
        )
        audio_url_disponible = bool(descripcion_audio_url and str(descripcion_audio_url).strip())
        
        if not (texto_disponible or audio_url_disponible):
            raise bad_request(
                "E1: Información incompleta. "
                "Debe proporcionar al menos: descripción de texto o URL de audio"
            )
        
        # Validar vehículo si lo proporciona
        id_vehiculo = data.get("id_vehiculo")
        if id_vehiculo:
            # Ya será validado en la BD por FK, pero podemos hacer check anticipado
            # Por ahora confiaremos en la FK de BD
            pass
        
        # Validar ubicación (no es requerida pero si existe debe ser válida)
        latitud = data.get("latitud")
        longitud = data.get("longitud")
        
        if latitud is not None and (latitud < -90 or latitud > 90):
            raise bad_request("Latitud debe estar entre -90 y 90")
        if longitud is not None and (longitud < -180 or longitud > 180):
            raise bad_request("Longitud debe estar entre -180 y 180")
        
        # Si tiene latitud, debe tener longitud y viceversa
        if (latitud is not None and longitud is None) or (latitud is None and longitud is not None):
            raise bad_request("E2: Ubicación inválida. Si proporciona latitud, debe proporcionar longitud y viceversa")
        
        return data
    
    
    @staticmethod
    def list_solicitudes(db: Session, current_user: Usuario):
        """
        Lista solicitudes de emergencia.
        - ADMINISTRADOR: Ve todas las solicitudes
        - CLIENTE: Solo ve sus propias solicitudes
        - TALLER: No tiene permisos (usa endpoints separados para postulaciones)
        """
        if current_user.rol == RolUsuario.ADMINISTRADOR:
            return db.query(SolicitudEmergencia).all()
        elif current_user.rol == RolUsuario.CLIENTE:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente:
                return []
            return db.query(SolicitudEmergencia).filter(
                SolicitudEmergencia.id_cliente == cliente.id_cliente
            ).all()
        else:
            raise forbidden("No tienes permisos para listar solicitudes")

    @staticmethod
    def get_solicitud(db: Session, solicitud_id: UUID, current_user: Usuario):
        """
        Obtiene una solicitud específica.
        - CLIENTE: Solo puede acceder a sus propias solicitudes
        - ADMINISTRADOR/TALLER: Pueden ver cualquier solicitud
        """
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        if solicitud is None:
            raise not_found("Solicitud de emergencia no encontrada")
        
        # Ownership check para clientes
        if current_user.rol == RolUsuario.CLIENTE:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or solicitud.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes permiso para acceder a esta solicitud")
        
        return solicitud

    @staticmethod
    def get_solicitud_estado_detalle(db: Session, solicitud_id: UUID, current_user: Usuario):
        """
        Obtiene el estado detallado de una solicitud para el caso de uso: Consultar estado.
        
        Incluye:
        - Información básica de la solicitud (paso 3)
        - Historial de cambios de estado (paso 4)
        - Información del taller asignado si existe (paso 5)
        - Progreso de la atención si existe (paso 6)
        
        Excepciones:
        - E1: Solicitud no encontrada
        - E2: Solicitud sin taller seleccionado (retorna None en asignacion_actual)
        
        Registra la consulta en bitácora (paso 8)
        
        Returns:
            Diccionario con solicitud y sus detalles relacionados
        """
        # Validar acceso a la solicitud (E1: No encontrada)
        solicitud = SolicitudService.get_solicitud(db, solicitud_id, current_user)
        
        # Obtener historial de estado (paso 4)
        historial = db.query(HistorialEstadoSolicitud).filter(
            HistorialEstadoSolicitud.id_solicitud == solicitud_id
        ).order_by(HistorialEstadoSolicitud.fecha_cambio.asc()).all()
        
        # Obtener asignación actual si existe (paso 5, E2)
        from app.models.asignacion_atencion import AsignacionAtencion
        asignacion_actual = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_solicitud == solicitud_id
        ).order_by(AsignacionAtencion.fecha_asignacion.desc()).first()
        
        # Registrar consulta en bitácora (paso 8)
        detalle = f"Consulta de estado. Solicitud: {solicitud.codigo_solicitud}"
        if asignacion_actual:
            detalle += f". Taller asignado"
        else:
            detalle += f". Sin taller asignado (E2)"
        
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Consulta de estado de solicitud",
            resultado=ResultadoAuditoria.EXITO,
            detalle=detalle,
            id_entidad=solicitud_id,
        )
        
        logger.info(f"Cliente consultó estado de solicitud {solicitud_id}")
        
        return {
            "solicitud": solicitud,
            "historial_estado": historial,
            "asignacion_actual": asignacion_actual,
        }

    @staticmethod
    def create_solicitud(db: Session, data: dict, current_user: Usuario):
        """
        Crea una nueva solicitud de emergencia.
        
        Validaciones (Caso de Uso: Registrar emergencia vehicular):
        - Solo CLIENTE puede crear solicitudes
        - Cliente debe existir
        - Información mínima requerida (E1)
        - Ubicación válida si se proporciona (E2)
        - Vehículo válido si se proporciona (E4)
        
        Registra en bitácora al completar exitosamente
        """
        # Validación: Solo CLIENTE puede crear
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo los clientes pueden registrar solicitudes de emergencia")
        
        # Validación: Cliente debe existir
        cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
        if not cliente:
            raise forbidden("No se encontró tu perfil de cliente")
        
        # Validar request completo
        data = SolicitudService._validar_solicitud_request(data, cliente)
        
        # Validación E4: Si proporciona vehículo, debe ser válido
        id_vehiculo = data.get("id_vehiculo")
        if id_vehiculo:
            # Verificar que el vehículo existe y pertenece al cliente
            vehiculo = db.query(Vehiculo).filter(
                Vehiculo.id_vehiculo == id_vehiculo,
                Vehiculo.id_cliente == cliente.id_cliente
            ).first()
            if not vehiculo:
                raise bad_request(
                    "E4: Vehículo no disponible. "
                    "El vehículo seleccionado no existe o no te pertenece"
                )
        else:
            # Verificar que el cliente tenga al menos un vehículo
            vehiculos = db.query(Vehiculo).filter(Vehiculo.id_cliente == cliente.id_cliente).all()
            if not vehiculos:
                raise bad_request(
                    "E4: Vehículo no disponible. "
                    "Debes registrar al menos un vehículo antes de crear una solicitud"
                )
        
        # Asignar cliente y estado inicial
        data["id_cliente"] = cliente.id_cliente
        data["estado_actual"] = EstadoSolicitud.REGISTRADA
        
        # Extraer especialidades y servicios (no son atributos del modelo)
        id_especialidades = data.pop("id_especialidades", [])
        id_servicios = data.pop("id_servicios", [])
        
        # Crear solicitud
        solicitud = SolicitudEmergencia(**data)
        db.add(solicitud)
        db.flush()  # Para obtener id_solicitud
        
        # Guardar especialidades relacionadas
        for id_especialidad in id_especialidades:
            rel_especialidad = EspecialidadSolicitudEmergencia(
                id_solicitud=solicitud.id_solicitud,
                id_especialidad=id_especialidad
            )
            db.add(rel_especialidad)
        
        # Guardar servicios relacionados
        for id_servicio in id_servicios:
            rel_servicio = ServicioSolicitudEmergencia(
                id_solicitud=solicitud.id_solicitud,
                id_servicio=id_servicio
            )
            db.add(rel_servicio)
        
        # Registrar en historial de estados
        historial = HistorialEstadoSolicitud(
            id_solicitud=solicitud.id_solicitud,
            estado_anterior=None,
            estado_nuevo=EstadoSolicitud.REGISTRADA,
            actualizado_por_tipo=TipoActor.CLIENTE,
            actualizado_por_id=current_user.id_usuario,
            comentario="Solicitud de emergencia creada",
        )
        db.add(historial)
        db.commit()
        db.refresh(solicitud)
        
        # Registrar en bitácora (como indica paso 11 del caso de uso)
        detalle = f"Solicitud creada exitosamente. Código: {solicitud.codigo_solicitud}"
        if solicitud.id_vehiculo:
            detalle += f". Vehículo asociado."
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Solicitud de emergencia registrada",
            resultado=ResultadoAuditoria.EXITO,
            detalle=detalle,
            id_entidad=solicitud.id_solicitud,
        )
        
        logger.info(f"Solicitud de emergencia creada: {solicitud.id_solicitud} por cliente {cliente.id_cliente}")
        
        # NUEVO: Enviar notificaciones a TODOS los talleres disponibles (como en Solicitudes Compatibles)
        try:
            from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller
            
            # Recargar solicitud
            db.refresh(solicitud)
            
            # Obtener todos los talleres APROBADOS y DISPONIBLES
            talleres_disponibles = db.query(Taller).filter(
                Taller.estado_aprobacion == EstadoAprobacionTaller.APROBADO,
                Taller.estado_operativo == EstadoOperativoTaller.DISPONIBLE,
            ).all()
            
            if not talleres_disponibles:
                logger.warning(f"No hay talleres disponibles para notificar sobre solicitud {solicitud.codigo_solicitud}")
            else:
                logger.info(f"Encontrados {len(talleres_disponibles)} talleres disponibles. Enviando notificaciones...")
                
                # Enviar notificación a cada taller disponible
                for taller in talleres_disponibles:
                    try:
                        # Calcular distancia si ambos tienen ubicación
                        distancia_km = 0
                        if (solicitud.latitud and solicitud.longitud and 
                            taller.latitud and taller.longitud):
                            distancia_km = SolicitudService._calcular_distancia_haversine(
                                taller.latitud,
                                taller.longitud,
                                solicitud.latitud,
                                solicitud.longitud
                            )
                        
                        if taller.id_usuario:
                            # Enviar notificación al propietario del taller
                            titulo_notif = "Nueva Solicitud de Emergencia Disponible"
                            mensaje_notif = (
                                f"Se ha registrado una nueva emergencia vehicular. "
                                f"Código: {solicitud.codigo_solicitud}"
                            )
                            
                            NotificacionService.send_notification_to_user(
                                db=db,
                                id_usuario_destino=taller.id_usuario,
                                tipo_usuario_destino="TALLER",
                                titulo=titulo_notif,
                                mensaje=mensaje_notif,
                                tipo_notificacion=TipoNotificacion.PUSH,
                                categoria_evento=CategoriaNotificacion.SOLICITUD,
                                referencia_entidad="SolicitudEmergencia",
                                referencia_id=solicitud.id_solicitud,
                                data={
                                    "solicitud_codigo": solicitud.codigo_solicitud,
                                    "categoria_incidente": solicitud.categoria_incidente,
                                    "distancia_km": str(distancia_km),
                                    "accion": "ver_solicitud_disponible"
                                }
                            )
                            logger.info(f"Notificación enviada a {taller.nombre_taller} para solicitud {solicitud.codigo_solicitud}")
                    except Exception as e:
                        logger.error(f"Error enviando notificación a taller {taller.nombre_taller}: {e}")
                        # Continuar con los demás talleres
                        continue
                
                logger.info(f"Notificaciones enviadas a {len(talleres_disponibles)} taller(es) para solicitud {solicitud.codigo_solicitud}")
        except Exception as e:
            # Si hay error en envío de notificaciones, loguear pero no fallar
            logger.error(f"Error enviando notificaciones a talleres: {e}")
        
        return solicitud

    @staticmethod
    def update_solicitud(db: Session, solicitud_id: UUID, data: dict, current_user: Usuario):
        """
        Actualiza una solicitud.
        - CLIENTE: Solo puede actualizar sus propias solicitudes (campos limitados)
        - ADMINISTRADOR: Puede actualizar cualquier campo
        """
        from app.models.solicitud_emergencia import EspecialidadSolicitudEmergencia, ServicioSolicitudEmergencia
        
        solicitud = SolicitudService.get_solicitud(db, solicitud_id, current_user)
        
        # Extraer listas de especialidades y servicios antes de filtrar
        id_especialidades = data.pop("id_especialidades", None)
        id_servicios = data.pop("id_servicios", None)
        
        if current_user.rol == RolUsuario.CLIENTE:
            # Los clientes solo pueden actualizar ciertos campos
            allowed_fields = {
                "descripcion_texto",
                "descripcion_audio_url",
                "transcripcion_audio",
                "latitud",
                "longitud",
                "direccion_referencial",
                "radio_busqueda_km",
                "categoria_incidente",
            }
            data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
        else:
            # Administrador puede actualizar más campos
            data = {k: v for k, v in data.items() if v is not None}
        
        # Actualizar campos simples
        for key, value in data.items():
            setattr(solicitud, key, value)
        
        # Actualizar especialidades si se proporciona lista
        if id_especialidades is not None:
            # Eliminar especialidades existentes
            db.query(EspecialidadSolicitudEmergencia).filter(
                EspecialidadSolicitudEmergencia.id_solicitud == solicitud_id
            ).delete()
            # Agregar nuevas especialidades
            for id_esp in id_especialidades:
                esp_rel = EspecialidadSolicitudEmergencia(
                    id_solicitud=solicitud_id,
                    id_especialidad=id_esp
                )
                db.add(esp_rel)
        
        # Actualizar servicios si se proporciona lista
        if id_servicios is not None:
            # Eliminar servicios existentes
            db.query(ServicioSolicitudEmergencia).filter(
                ServicioSolicitudEmergencia.id_solicitud == solicitud_id
            ).delete()
            # Agregar nuevos servicios
            for id_serv in id_servicios:
                serv_rel = ServicioSolicitudEmergencia(
                    id_solicitud=solicitud_id,
                    id_servicio=id_serv
                )
                db.add(serv_rel)
        
        db.commit()
        db.refresh(solicitud)
        
        # Registrar en bitácora
        detalle = f"Solicitud actualizada. Código: {solicitud.codigo_solicitud}"
        if id_especialidades is not None:
            detalle += f". Especialidades actualizadas ({len(id_especialidades)} seleccionadas)"
        if id_servicios is not None:
            detalle += f". Servicios actualizados ({len(id_servicios)} seleccionados)"
        
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Solicitud de emergencia actualizada",
            resultado=ResultadoAuditoria.EXITO,
            detalle=detalle,
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.CLIENTE if current_user.rol == RolUsuario.CLIENTE else TipoActor.ADMINISTRADOR,
            id_actor=current_user.id_usuario,
        )
        
        return solicitud

    @staticmethod
    def cancel_solicitud(db: Session, solicitud_id: UUID, current_user: Usuario, razon: str = None):
        """
        Cancela una solicitud de emergencia.
        
        Flujo (Caso de Uso):
        1. Obtiene la solicitud (validar acceso)
        2. Valida que se pueda cancelar (E1)
        3. Obtiene asignaciones/postulaciones existentes
        4. Actualiza estado a CANCELADA
        5. Registra en historial
        6. Notifica a talleres involucrados (E2)
        7. Registra en bitácora
        
        Excepciones:
        - E1: Solicitud no disponible para cancelación (ya atendida, finalizada, cerrada)
        - E2: Cancelación con taller seleccionado (notifica al taller)
        
        Precondiciones:
        - CLIENTE solo puede cancelar sus propias solicitudes
        - ADMINISTRADOR puede cancelar cualquiera
        - Solicitud debe estar en estado cancelable
        """
        # Paso 1: Obtener y validar acceso a la solicitud
        solicitud = SolicitudService.get_solicitud(db, solicitud_id, current_user)
        
        # Paso 2: Validar que está en estado cancelable (E1)
        estados_no_cancelables = [
            EstadoSolicitud.ATENDIDA,
            EstadoSolicitud.CANCELADA,
        ]
        
        if solicitud.estado_actual in estados_no_cancelables:
            raise bad_request(
                f"E1 - No se puede cancelar una solicitud en estado {solicitud.estado_actual.value}. "
                "La solicitud ya no está disponible para cancelación."
            )
        
        # Paso 3: Obtener asignaciones/talleres involucrados (E2)
        from app.models.asignacion_atencion import AsignacionAtencion
        from app.models.postulacion_taller import PostulacionTaller
        from app.models.notificacion import Notificacion
        from app.core.enums import TipoNotificacion, CategoriaNotificacion, EstadoLecturaNotificacion, EstadoEnvioNotificacion
        
        asignacion_actual = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_solicitud == solicitud_id
        ).first()
        
        postulaciones = db.query(PostulacionTaller).filter(
            PostulacionTaller.id_solicitud == solicitud_id
        ).all()
        
        # Guardar estado anterior
        estado_anterior = solicitud.estado_actual
        
        # Paso 4: Actualizar estado a CANCELADA
        solicitud.estado_actual = EstadoSolicitud.CANCELADA
        solicitud.fecha_cierre = datetime.now()
        
        # Paso 5: Registrar en historial
        historial = HistorialEstadoSolicitud(
            id_historial_estado=uuid4(),
            id_solicitud=solicitud.id_solicitud,
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoSolicitud.CANCELADA,
            comentario=razon or "Solicitud cancelada por el cliente",
            actualizado_por_tipo=TipoActor.CLIENTE if current_user.rol == RolUsuario.CLIENTE else TipoActor.ADMINISTRADOR,
            actualizado_por_id=current_user.id_usuario,
        )
        db.add(historial)
        db.flush()
        
        # Paso 6: Notificar a talleres involucrados (E2) usando servicio central
        talleres_notificados = set()
        
        # Si hay asignación actual, notificar al taller asignado
        if asignacion_actual:
            taller = asignacion_actual.taller
            if taller and taller.id_taller not in talleres_notificados:
                NotificacionService.send_notification_to_user(
                    db=db,
                    id_usuario_destino=taller.id_usuario,
                    tipo_usuario_destino="taller",
                    titulo="Solicitud Cancelada",
                    mensaje=f"La solicitud {solicitud.codigo_solicitud} ha sido cancelada por el cliente. " +
                            f"Motivo: {razon or 'No especificado'}",
                    tipo_notificacion=TipoNotificacion.PUSH,
                    categoria_evento=CategoriaNotificacion.ESTADO,
                    referencia_entidad="SolicitudEmergencia",
                    referencia_id=str(solicitud.id_solicitud),
                    actor_id=current_user.id_usuario,
                    actor_tipo=TipoActor.CLIENTE if current_user.rol == RolUsuario.CLIENTE else TipoActor.ADMINISTRADOR,
                )
                talleres_notificados.add(taller.id_taller)
                logger.info(f"Notificación enviada a taller {taller.id_taller} sobre cancelación")
        
        # Notificar a talleres con postulaciones pendientes
        for postulacion in postulaciones:
            if postulacion.taller.id_taller not in talleres_notificados:
                NotificacionService.send_notification_to_user(
                    db=db,
                    id_usuario_destino=postulacion.taller.id_usuario,
                    tipo_usuario_destino="taller",
                    titulo="Solicitud Cancelada",
                    mensaje=f"La solicitud {solicitud.codigo_solicitud} ha sido cancelada. " +
                            f"Su postulación ha sido retirada. Motivo: {razon or 'No especificado'}",
                    tipo_notificacion=TipoNotificacion.PUSH,
                    categoria_evento=CategoriaNotificacion.ESTADO,
                    referencia_entidad="SolicitudEmergencia",
                    referencia_id=str(solicitud.id_solicitud),
                    actor_id=current_user.id_usuario,
                    actor_tipo=TipoActor.CLIENTE if current_user.rol == RolUsuario.CLIENTE else TipoActor.ADMINISTRADOR,
                )
                talleres_notificados.add(postulacion.taller.id_taller)
                logger.info(f"Notificación enviada a taller {postulacion.taller.id_taller} sobre cancelación")
        
        # Paso 7: Registrar en bitácora
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Cancelación de solicitud",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Solicitud {solicitud.codigo_solicitud} cancelada. Motivo: {razon or 'No especificado'}. " +
                   f"Talleres notificados: {len(talleres_notificados)}",
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.CLIENTE if current_user.rol == RolUsuario.CLIENTE else TipoActor.ADMINISTRADOR,
            id_actor=current_user.id_usuario,
        )
        
        db.commit()
        db.refresh(solicitud)
        
        logger.info(f"Solicitud {solicitud_id} cancelada correctamente. "
                   f"Estado anterior: {estado_anterior}. Talleres notificados: {len(talleres_notificados)}")
        
        return solicitud

    @staticmethod
    def get_historial_solicitudes(
        db: Session,
        current_user: Usuario,
        orden_por: str = "fecha",
        descendente: bool = True,
        skip: int = 0,
        limit: int = 100,
    ):
        """
        Obtiene el historial de solicitudes del cliente (Caso de Uso: Consultar historial).
        
        Flujo:
        1. Cliente accede a sección de historial (paso 1)
        2. Sistema consulta solicitudes del cliente (paso 2)
        3. Sistema muestra listado ordenado por fecha o estado (paso 3)
        
        Excepciones:
        - E1: Historial vacío (retorna lista vacía)
        
        Registra la consulta en bitácora (paso 8)
        
        Args:
            db: Session de BD
            current_user: Usuario actual
            orden_por: "fecha" o "estado" (default: fecha)
            descendente: True = más recientes primero (default: True)
            skip: Paginación offset
            limit: Paginación limit
        
        Returns:
            Dict con estadísticas y lista de solicitudes
        """
        # Obtener cliente
        cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
        if not cliente:
            raise forbidden("No se encontró tu perfil de cliente")
        
        # Consultar todas las solicitudes del cliente
        query = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_cliente == cliente.id_cliente
        )
        
        # Ordenamiento
        if orden_por == "estado":
            query = query.order_by(
                SolicitudEmergencia.estado_actual.desc() if descendente else SolicitudEmergencia.estado_actual.asc()
            )
        else:  # "fecha" (default)
            query = query.order_by(
                SolicitudEmergencia.fecha_creacion.desc() if descendente else SolicitudEmergencia.fecha_creacion.asc()
            )
        
        # Contar totales
        total_solicitudes = query.count()
        total_finalizadas = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_cliente == cliente.id_cliente,
            SolicitudEmergencia.estado_actual.in_([EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA])
        ).count()
        total_activas = total_solicitudes - total_finalizadas
        
        # Aplicar paginación
        solicitudes = query.offset(skip).limit(limit).all()
        
        # Registrar consulta en bitácora (paso 8)
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Consulta de historial de solicitudes",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Cliente consultó historial. Total: {total_solicitudes}, " +
                   f"Finalizadas: {total_finalizadas}, Activas: {total_activas}",
            id_entidad=cliente.id_cliente,
            tipo_actor=TipoActor.CLIENTE,
            id_actor=current_user.id_usuario,
        )
        
        logger.info(f"Cliente {cliente.id_cliente} consultó historial de {total_solicitudes} solicitudes")
        
        return {
            "total_solicitudes": total_solicitudes,
            "total_finalizadas": total_finalizadas,
            "total_activas": total_activas,
            "solicitudes": solicitudes,
        }

    @staticmethod
    def get_solicitud_historial_detalle(db: Session, solicitud_id: UUID, current_user: Usuario):
        """
        Obtiene el detalle completo de una solicitud del historial (Caso de Uso: Consultar historial).
        
        Flujo:
        4. Cliente selecciona una solicitud del historial (paso 4)
        5. Sistema muestra el detalle completo (paso 5)
        6. El detalle incluye: vehículo, descripción, ubicación, estado, taller que atendió (paso 6)
        7. Cliente revisa información (paso 7)
        8. Sistema registra la consulta en bitácora (paso 8)
        
        Excepciones:
        - E2: Solicitud no encontrada
        
        Returns:
            Dict con información completa de la solicitud
        """
        # Validar acceso (ownership) - E2: Solicitud no encontrada
        solicitud = SolicitudService.get_solicitud(db, solicitud_id, current_user)
        
        # Obtener vehículo si existe
        vehiculo = None
        if solicitud.id_vehiculo:
            vehiculo = db.query(Vehiculo).filter(
                Vehiculo.id_vehiculo == solicitud.id_vehiculo
            ).first()
        
        # Obtener taller asignado si existe
        from app.models.asignacion_atencion import AsignacionAtencion
        asignacion = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_solicitud == solicitud_id
        ).first()
        
        taller_asignado = None
        if asignacion:
            taller_asignado = asignacion.taller
        
        # Obtener resultado de servicio si existe
        from app.models.resultado_servicio import ResultadoServicio
        resultado = db.query(ResultadoServicio).filter(
            ResultadoServicio.id_solicitud == solicitud_id
        ).first()
        
        # Obtener historial de estado
        historial = db.query(HistorialEstadoSolicitud).filter(
            HistorialEstadoSolicitud.id_solicitud == solicitud_id
        ).order_by(HistorialEstadoSolicitud.fecha_cambio.asc()).all()
        
        # Registrar consulta en bitácora (paso 8)
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Consulta de detalle de historial",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Cliente consultó detalle de solicitud {solicitud.codigo_solicitud}. " +
                   f"Estado: {solicitud.estado_actual.value}",
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.CLIENTE,
            id_actor=current_user.id_usuario,
        )
        
        logger.info(f"Cliente consultó detalle de solicitud {solicitud_id}")
        
        return {
            "solicitud": solicitud,
            "vehiculo": vehiculo,
            "taller_asignado": taller_asignado,
            "resultado_servicio": resultado,
            "historial_estado": historial,
        }

    @staticmethod
    def _calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calcula la distancia en kilómetros entre dos puntos geográficos
        usando la fórmula haversine.
        
        Args:
            lat1, lon1: Coordenadas del primer punto (latitud, longitud)
            lat2, lon2: Coordenadas del segundo punto (latitud, longitud)
            
        Returns:
            Distancia en kilómetros
        """
        import math
        
        # Si alguna coordenada es None, retornar None
        if any(x is None for x in [lat1, lon1, lat2, lon2]):
            return None
        
        # Radio de la tierra en km
        radio_tierra_km = 6371.0
        
        # Convertir grados a radianes
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Diferencias
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Fórmula haversine
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        distancia = radio_tierra_km * c
        
        return round(distancia, 2)

    @staticmethod
    def get_solicitudes_disponibles_para_taller(
        db: Session,
        current_user: Usuario,
        skip: int = 0,
        limit: int = 100,
    ):
        """
        Obtiene listado de solicitudes disponibles para que un taller se postule
        (Caso de Uso: Visualizar solicitudes de emergencia - Perspectiva TALLER).
        
        Flujo:
        1. Taller accede a ver solicitudes disponibles (paso 1)
        2. Sistema valida que taller está aprobado y habilitado (paso 2, E3)
        3. Sistema valida que tiene especialidades registradas (paso 2, E3)
        4. Sistema consulta solicitudes compatibles (paso 3):
           - En estados REGISTRADA o ASIGNADA (disponibles para postulación)
           - Cuya categoría coincide con especialidades del taller
           - Dentro de radio de búsqueda del taller usando distancia
        5. Sistema calcula distancia para cada solicitud (paso 4)
        6. Sistema agrupa por especialidad para estadísticas (paso 5)
        7. Taller revisa listado (paso 6)
        8. Sistema registra consulta en bitácora (paso 7)
        
        Excepciones:
        - E1: No hay solicitudes disponibles (retorna lista vacía con mensaje)
        - E3: Taller sin especialidades o no aprobado (bad_request)
        
        Returns:
            Dict con estadísticas y lista de solicitudes disponibles
        """
        from app.models.taller import Taller
        from app.models.taller_especialidad import TallerEspecialidad
        from app.models.especialidad import Especialidad
        from app.models.asignacion_atencion import AsignacionAtencion
        
        # Validación: Solo TALLER puede acceder
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo los talleres pueden consultar solicitudes disponibles")
        
        # Paso 2: Obtener taller y validar estado (E3)
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise bad_request("E3: No se encontró el perfil de taller")
        
        # Validar que taller esté aprobado y habilitado
        from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller
        if taller.estado_aprobacion != EstadoAprobacionTaller.APROBADO:
            raise bad_request(
                f"E3: Taller no aprobado. "
                f"Estado: {taller.estado_aprobacion.value}. "
                "Contacta con administración."
            )
        
        if taller.estado_operativo != EstadoOperativoTaller.DISPONIBLE:
            raise bad_request(
                f"E3: Taller no habilitado operativamente. "
                f"Estado: {taller.estado_operativo.value}. "
                "Contacta con administración."
            )
        
        # Validar que tiene especialidades registradas (E3)
        especialidades_taller = db.query(TallerEspecialidad).filter(
            TallerEspecialidad.id_taller == taller.id_taller
        ).all()
        
        if not especialidades_taller:
            raise bad_request(
                "E3: Taller sin especialidades registradas. "
                "Debes registrar al menos una especialidad antes de ver solicitudes disponibles."
            )
        
        # Paso 3-4: Consultar solicitudes compatibles
        # Obtener todas las solicitudes sin validación de categoría
        
        solicitudes = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.estado_actual.in_([
                EstadoSolicitud.REGISTRADA,
                EstadoSolicitud.EN_ESPERA_RESPUESTAS
            ])
        ).all()
        
        # Filtrar por distancia
        solicitudes_disponibles = []
        cantidad_por_especialidad = {}
        
        for solicitud in solicitudes:
            # Calcular distancia (Paso 4)
            distancia_km = None
            if (taller.latitud is not None and taller.longitud is not None and
                solicitud.latitud is not None and solicitud.longitud is not None):
                distancia_km = SolicitudService._calcular_distancia_haversine(
                    taller.latitud,
                    taller.longitud,
                    solicitud.latitud,
                    solicitud.longitud
                )
                # Filtro: Distancia debe estar dentro del radio de búsqueda de la solicitud
                if solicitud.radio_busqueda_km and distancia_km > solicitud.radio_busqueda_km:
                    continue
            
            # Si todos los filtros pasaron, incluir solicitud
            solicitud_dto = {
                "solicitud": solicitud,
                "distancia_km": distancia_km,
            }
            solicitudes_disponibles.append(solicitud_dto)
            
            # Contar por especialidad (Paso 5)
            categoria = solicitud.categoria_incidente
            if categoria not in cantidad_por_especialidad:
                cantidad_por_especialidad[categoria] = 0
            cantidad_por_especialidad[categoria] += 1
        
        # Ordenar por distancia (más cercanas primero)
        solicitudes_disponibles.sort(
            key=lambda x: x["distancia_km"] if x["distancia_km"] is not None else float("inf")
        )
        
        # Paginación
        total_disponibles = len(solicitudes_disponibles)
        solicitudes_paginadas = solicitudes_disponibles[skip:skip + limit]
        
        # Paso 7: Registrar en bitácora
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Consulta de solicitudes disponibles",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller consultó solicitudes disponibles. " +
                   f"Total disponibles: {total_disponibles}. " +
                   f"Breakdown: {cantidad_por_especialidad}",
            id_entidad=taller.id_taller,
            tipo_actor=TipoActor.TALLER,
            id_actor=current_user.id_usuario,
        )
        
        logger.info(f"Taller {taller.id_taller} consultó {total_disponibles} solicitudes disponibles")
        
        return {
            "total_disponibles": total_disponibles,
            "cantidad_por_especialidad": cantidad_por_especialidad,
            "solicitudes": solicitudes_paginadas,
        }

    @staticmethod
    def get_solicitud_disponible_detalle(db: Session, solicitud_id: UUID, current_user: Usuario):
        """
        Obtiene el detalle completo de una solicitud disponible para un taller
        (Caso de Uso: Visualizar solicitudes - Vista detallada del taller).
        
        Flujo:
        9. Taller selecciona una solicitud del listado (paso 9)
        10. Sistema valida que taller sigue siendo compatible (E2)
        11. Sistema muestra detalle completo (paso 10):
            - Información de la solicitud
            - Evidencias adjuntas
            - Categoría/especialidad requerida
            - Ubicación y distancia
        12. Sistema registra consulta en bitácora (paso 11)
        
        Excepciones:
        - E2: Solicitud no disponible anymore (estado cambió, radio expiró, etc.)
        - E3: Taller sin especialidades
        
        Returns:
            Dict con detalle completo de la solicitud
        """
        from app.models.taller import Taller
        from app.models.taller_especialidad import TallerEspecialidad
        from app.models.especialidad import Especialidad
        from app.models.evidencia import Evidencia
        
        # Validación: Solo TALLER puede acceder
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo los talleres pueden consultar detalles de solicitudes disponibles")
        
        # Obtener taller
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise bad_request("No se encontró el perfil de taller")
        
        # Validar que tiene especialidades (E3)
        especialidades_taller = db.query(TallerEspecialidad).filter(
            TallerEspecialidad.id_taller == taller.id_taller
        ).all()
        
        if not especialidades_taller:
            raise bad_request(
                "E3: Taller sin especialidades registradas"
            )
        
        # Obtener solicitud
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        
        if not solicitud:
            raise not_found("Solicitud no encontrada")
        
        # Validar E2: Solicitud debe estar en estado disponible
        if solicitud.estado_actual not in [EstadoSolicitud.REGISTRADA, EstadoSolicitud.EN_ESPERA_RESPUESTAS]:
            raise bad_request(
                f"E2: Solicitud no disponible. "
                f"Estado actual: {solicitud.estado_actual.value}"
            )
        
        # Calcular distancia (información para el usuario, no validaciónn)
        distancia_km = None
        if (taller.latitud is not None and taller.longitud is not None and
            solicitud.latitud is not None and solicitud.longitud is not None):
            distancia_km = SolicitudService._calcular_distancia_haversine(
                taller.latitud,
                taller.longitud,
                solicitud.latitud,
                solicitud.longitud
            )
        
        # Obtener evidencias
        evidencias = db.query(Evidencia).filter(
            Evidencia.id_solicitud == solicitud_id
        ).all()
        
        # Paso 11: Registrar en bitácora
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Consulta de detalle de solicitud disponible",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller consultó detalle de solicitud {solicitud.codigo_solicitud}. " +
                   f"Categoría: {solicitud.categoria_incidente}. " +
                   f"Distancia: {distancia_km}km. " +
                   f"Evidencias: {len(evidencias)}",
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.TALLER,
            id_actor=current_user.id_usuario,
        )
        
        logger.info(f"Taller {taller.id_taller} consultó detalle de solicitud {solicitud_id}")
        
        return {
            "solicitud": solicitud,
            "distancia_km": distancia_km,
            "evidencias": evidencias,
            "especialidad_requerida": solicitud.categoria_incidente,
        }

    @staticmethod
    def create_postulacion(
        db: Session,
        solicitud_id: UUID,
        current_user: Usuario,
        data: dict,
    ):
        """
        Crea una postulación de taller para atender una solicitud
        (Caso de Uso: Solicitar atención de emergencia).
        
        Flujo (Pasos 1-13):
        1. Taller accede al listado de solicitudes
        2. Taller selecciona una solicitud compatible
        3. Sistema muestra información completa
        4. Taller decide postularse
        5. Taller selecciona opción de solicitar atención
        6. Sistema confirma disponibilidad
        7. Taller ingresa tiempo estimado de llegada
        8. Taller confirma envío
        9. Sistema valida que solicitud sigue disponible (E1)
        10. Sistema registra postulación
        11. Sistema notifica al cliente
        12. Sistema registra en bitácora
        13. Sistema muestra confirmación
        
        Excepciones:
        - E1: Solicitud no disponible (CANCELADA, ATENDIDA, o ya ASIGNADA sin más postulantes)
        - E2: Taller ya se postulo a esta solicitud
        - E3: Taller no aprobado o no habilitado
        - E4: Taller sin especialidades compatibles
        
        Precondiciones:
        - Solo TALLER puede postularse
        - Solicitud debe existir
        - Taller debe estar aprobado y habilitado
        """
        from app.models.postulacion_taller import PostulacionTaller
        from app.models.taller import Taller
        from app.core.enums import (
            EstadoPostulacion,
            TipoNotificacion,
            CategoriaNotificacion,
            EstadoAprobacionTaller,
            EstadoOperativoTaller,
        )
        
        # Paso 1-2: Validar que es TALLER
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo los talleres pueden postularse a solicitudes")
        
        # Obtener taller
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise bad_request("No se encontró el perfil de taller")
        
        # Validar E3: Taller debe estar aprobado y habilitado
        if taller.estado_aprobacion != EstadoAprobacionTaller.APROBADO:
            raise bad_request(
                f"E3: Taller no aprobado. "
                f"Estado: {taller.estado_aprobacion.value}"
            )
        
        if taller.estado_operativo != EstadoOperativoTaller.DISPONIBLE:
            raise bad_request(
                f"E3: Taller no habilitado operativamente. "
                f"Estado: {taller.estado_operativo.value}"
            )
        
        # Paso 3: Obtener solicitud
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        
        if not solicitud:
            raise not_found("Solicitud no encontrada")
        
        # Paso 9: Validar E1 - Solicitud disponible
        if solicitud.estado_actual not in [EstadoSolicitud.REGISTRADA, EstadoSolicitud.EN_ESPERA_RESPUESTAS]:
            raise bad_request(
                f"E1: Solicitud no disponible. "
                f"Estado actual: {solicitud.estado_actual.value}"
            )
        
        # Validar E4: Taller tiene especialidad compatible
        from app.models.taller_especialidad import TallerEspecialidad
        from app.models.especialidad import Especialidad
        
        especialidades_taller = db.query(TallerEspecialidad).filter(
            TallerEspecialidad.id_taller == taller.id_taller
        ).all()
        
        if not especialidades_taller:
            raise bad_request(
                "E4: Taller sin especialidades registradas"
            )
        
        categorias_permitidas = set()
        for te in especialidades_taller:
            especialidad = db.query(Especialidad).filter(
                Especialidad.id_especialidad == te.id_especialidad
            ).first()
            if especialidad:
                categorias_permitidas.add(especialidad.nombre_especialidad)
        
        if solicitud.categoria_incidente not in categorias_permitidas:
            raise bad_request(
                f"E4: Taller no tiene especialidad en {solicitud.categoria_incidente}"
            )
        
        # Validar E2: Taller no ha postulado antes a esta solicitud
        postulacion_existente = db.query(PostulacionTaller).filter(
            PostulacionTaller.id_solicitud == solicitud_id,
            PostulacionTaller.id_taller == taller.id_taller,
            PostulacionTaller.estado_postulacion != EstadoPostulacion.RECHAZADA,
        ).first()
        
        if postulacion_existente:
            raise bad_request(
                f"E2: El taller ya tiene una postulación activa en esta solicitud. "
                f"Estado: {postulacion_existente.estado_postulacion.value}"
            )
        
        # Paso 10: Crear postulación
        tiempo_estimado = data.get("tiempo_estimado_llegada_min")
        mensaje = data.get("mensaje_propuesta")
        
        postulacion = PostulacionTaller(
            id_postulacion=uuid4(),
            id_solicitud=solicitud_id,
            id_taller=taller.id_taller,
            tiempo_estimado_llegada_min=tiempo_estimado,
            mensaje_propuesta=mensaje,
            estado_postulacion=EstadoPostulacion.PENDIENTE,  # Pendiente de respuesta del cliente
        )
        db.add(postulacion)
        db.flush()
        
        # Paso 11: Notificar al cliente
        logger.info(f"Iniciando notificación para solicitud {solicitud_id}, cliente: {solicitud.id_cliente}")
        
        try:
            if not solicitud.id_cliente:
                logger.warning(f"Solicitud {solicitud_id} no tiene cliente asignado")
            else:
                cliente = db.query(Cliente).filter(
                    Cliente.id_cliente == solicitud.id_cliente
                ).first()
                
                if not cliente:
                    logger.warning(f"No se encontró cliente con ID {solicitud.id_cliente} para solicitud {solicitud_id}")
                elif not cliente.id_usuario:
                    logger.warning(f"Cliente {cliente.id_cliente} no tiene id_usuario asignado")
                else:
                    logger.info(f"Enviando notificación a usuario {cliente.id_usuario}")
                    
                    mensaje_notif = (
                        f"El taller '{taller.nombre_taller}' se ha postulado para atender tu solicitud {solicitud.codigo_solicitud}. "
                    )
                    if tiempo_estimado:
                        mensaje_notif += f"Tiempo estimado de llegada: {tiempo_estimado} minutos. "
                    if mensaje:
                        mensaje_notif += f"Mensaje: {mensaje}"
                    
                    # Enviar notificación por Firebase
                    from app.services.notificacion_service import NotificacionService
                    
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
                    logger.info(f"Notificación enviada: {resultado}")
        except Exception as e:
            logger.exception(f"Error al enviar notificación al cliente: {str(e)}")
        
        # Paso 12: Registrar en bitácora
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Postulación a solicitud de emergencia",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Taller se postulo a solicitud {solicitud.codigo_solicitud}. " +
                   f"Tiempo estimado: {tiempo_estimado or 'No especificado'} min. " +
                   f"Taller: {taller.nombre_taller}",
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.TALLER,
            id_actor=current_user.id_usuario,
        )
        
        db.commit()
        db.refresh(postulacion)
        
        logger.info(f"Taller {taller.id_taller} creó postulación a solicitud {solicitud_id}")
        
        # Paso 13: Retornar confirmación
        return postulacion

    @staticmethod
    def expand_search_radius(db: Session, solicitud_id: UUID, current_user: Usuario, incremento_km: float = 5.0):
        """
        Amplía el radio de búsqueda de una solicitud (Phase 10: Ampliar zona de búsqueda).
        
        Flujo:
        1-2. Sistema detecta falta de respuestas o muestra opción de ampliar
        3-5. Cliente confirma ampliación
        6. Sistema incrementa el radio geográfico
        7-9. Sistema re-ejecuta búsqueda dentro del nuevo radio
        10. Registra en bitácora
        11. Retorna confirmación con nuevas opciones disponibles
        
        Excepciones:
        - E1: No hay talleres compatibles incluso en zona ampliada
        - E2: Solicitud ya asignada (no se puede ampliar)
        
        Precondiciones:
        - Solo CLIENTE puede ampliar zona
        - Solicitud debe estar en estado disponible (REGISTRADA/EN_BUSQUEDA)
        - No debe tener asignación activa
        
        Args:
            db: Sesión de BD
            solicitud_id: ID de la solicitud
            current_user: Usuario actual (debe ser CLIENTE)
            incremento_km: Cuántos km ampliar (default: 5 km)
        
        Returns:
            Dict con solicitud actualizada y nuevas opciones disponibles
        """
        from app.models.asignacion_atencion import AsignacionAtencion
        from app.models.taller import Taller
        from app.models.taller_especialidad import TallerEspecialidad
        from app.models.especialidad import Especialidad
        
        # Validar rol
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo los clientes pueden ampliar la zona de búsqueda")
        
        # Paso 1: Obtener y validar acceso a la solicitud
        solicitud = SolicitudService.get_solicitud(db, solicitud_id, current_user)
        
        # Validar estados permitidos
        estados_amplibles = [
            EstadoSolicitud.REGISTRADA,
            EstadoSolicitud.EN_BUSQUEDA,
            EstadoSolicitud.EN_ESPERA_RESPUESTAS,
        ]
        
        if solicitud.estado_actual not in estados_amplibles:
            raise bad_request(
                f"No se puede ampliar la zona de búsqueda de una solicitud en estado "
                f"{solicitud.estado_actual.value}"
            )
        
        # Paso 2: E2 - Validar que no esté ya asignada
        asignacion_existente = db.query(AsignacionAtencion).filter(
            AsignacionAtencion.id_solicitud == solicitud_id,
            AsignacionAtencion.estado_asignacion == EstadoAsignacion.ACTIVA,
        ).first()
        
        if asignacion_existente:
            raise bad_request(
                "E2: La solicitud ya cuenta con una asignación activa. "
                "No se puede ampliar la zona de búsqueda"
            )
        
        # Guardar radio anterior
        radio_anterior = solicitud.radio_busqueda_km
        
        # Paso 6: Incrementar el radio geográfico
        nuevo_radio = radio_anterior + incremento_km
        solicitud.radio_busqueda_km = nuevo_radio
        db.flush()
        
        # Paso 7-9: Re-ejecutar búsqueda de talleres compatibles dentro del nuevo radio
        talleres_compatibles = []
        
        if solicitud.latitud and solicitud.longitud:
            # Obtener todos los talleres aprobados y habilitados
            from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller
            
            talleres = db.query(Taller).filter(
                Taller.estado_aprobacion == EstadoAprobacionTaller.APROBADO,
                Taller.estado_operativo == EstadoOperativoTaller.DISPONIBLE,
            ).all()
            
            for taller in talleres:
                # Validar que tiene especialidades
                especialidades = db.query(TallerEspecialidad).filter(
                    TallerEspecialidad.id_taller == taller.id_taller
                ).all()
                
                if not especialidades:
                    continue
                
                # Validar que tiene especialidad compatible
                categorias = set()
                for te in especialidades:
                    espec = db.query(Especialidad).filter(
                        Especialidad.id_especialidad == te.id_especialidad
                    ).first()
                    if espec:
                        categorias.add(espec.nombre)
                
                if solicitud.categoria_incidente not in categorias:
                    continue
                
                # Validar ubicación
                if not (taller.latitud and taller.longitud):
                    continue
                
                # Calcular distancia
                distancia = SolicitudService._calcular_distancia_haversine(
                    taller.latitud,
                    taller.longitud,
                    solicitud.latitud,
                    solicitud.longitud
                )
                
                # Filtro: Debe estar dentro del nuevo radio
                if distancia <= nuevo_radio:
                    talleres_compatibles.append({
                        "taller": taller,
                        "distancia_km": distancia,
                    })
            
            # Ordenar por distancia
            talleres_compatibles.sort(key=lambda x: x["distancia_km"])
        
        # Paso 10: Registrar en bitácora
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Ampliación de zona de búsqueda",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Zona de búsqueda ampliada para solicitud {solicitud.codigo_solicitud}. "
                   f"Radio anterior: {radio_anterior}km → Nuevo radio: {nuevo_radio}km. "
                   f"Incremento: {incremento_km}km. Talleres compatibles encontrados en nueva zona: {len(talleres_compatibles)}",
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.CLIENTE,
            id_actor=current_user.id_usuario,
        )
        
        # E1: Validar que al menos haya 1 taller compatible en la zona ampliada
        if not talleres_compatibles:
            # Registrar en bitácora también esto
            SolicitudService._registrar_bitacora(
                db=db,
                accion="Intento fallido de ampliación (E1)",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"No se encontraron talleres compatibles en zona ampliada. "
                       f"Radio: {nuevo_radio}km, Categoría: {solicitud.categoria_incidente}",
                id_entidad=solicitud_id,
                tipo_actor=TipoActor.CLIENTE,
                id_actor=current_user.id_usuario,
            )
        
        db.commit()
        db.refresh(solicitud)
        
        logger.info(f"Zona de búsqueda ampliada para solicitud {solicitud_id}. "
                   f"Radio: {radio_anterior}km → {nuevo_radio}km. "
                   f"Talleres disponibles: {len(talleres_compatibles)}")
        
        # Paso 11: Retornar confirmación
        return {
            "solicitud": solicitud,
            "radio_anterior": radio_anterior,
            "radio_nuevo": nuevo_radio,
            "talleres_compatibles_encontrados": len(talleres_compatibles),
            "talleres": talleres_compatibles[:10],  # Primeros 10 más cercanos
        }

    @staticmethod
    def find_compatible_workshops(db: Session, solicitud_id: UUID) -> dict:
        """
        Busca talleres compatibles con una solicitud (Phase 11: Caso de Uso del SISTEMA).
        
        Flujo (Automatizado):
        1. Sistema detecta solicitud lista (REGISTRADA, EN_BUSQUEDA, EN_ESPERA_RESPUESTAS)
        2-3. Obtiene información de solicitud y listado de talleres
        4. Filtra por especialidad/servicio requerido
        5. Filtra por disponibilidad (APROBADA + HABILITADA)
        6. Filtra por cercanía geográfica dentro del radio
        7. Genera listado de compatibles
        8. Registra hallazgo en bitácora
        9. Habilita visualización para esos talleres (implícito)
        
        Excepciones:
        - E1: No hay talleres compatibles (retorna lista vacía, sin error)
        - E2: No hay talleres habilitados (retorna lista vacía, sin error)
        
        Precondiciones:
        - Solicitud debe existir
        - Solicitud debe tener categoría_incidente definida
        - Solicitud debe tener ubicación (latitud/longitud) si applies
        
        Args:
            db: Sesión de BD
            solicitud_id: ID de la solicitud
        
        Returns:
            Dict with search results:
            {
                "solicitud_id": uuid,
                "total_encontrados": int,
                "cantidad_por_distancia": {
                    "cercanos_0_5km": int,
                    "mediano_5_10km": int,
                    "lejanos_10km": int
                },
                "talleres": [
                    {"taller_id": uuid, "nombre": str, "distancia_km": float, ...}
                ]
            }
        """
        from app.models.taller import Taller
        from app.models.taller_especialidad import TallerEspecialidad
        from app.models.especialidad import Especialidad
        from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller
        
        # Paso 1-2: Obtener solicitud
        solicitud = db.query(SolicitudEmergencia).filter(
            SolicitudEmergencia.id_solicitud == solicitud_id
        ).first()
        
        if not solicitud:
            raise not_found("Solicitud no encontrada")
        
        # Validar que solicitud está en estado apropiado
        estados_buscables = [
            EstadoSolicitud.REGISTRADA,
            EstadoSolicitud.EN_BUSQUEDA,
            EstadoSolicitud.EN_ESPERA_RESPUESTAS,
        ]
        
        if solicitud.estado_actual not in estados_buscables:
            raise bad_request(
                f"No se pueden buscar talleres para solicitud en estado {solicitud.estado_actual.value}"
            )
        
        # Paso 3: Obtener listado de todos los talleres
        # Validar que existe la categoría
        if not solicitud.categoria_incidente:
            raise bad_request("Solicitud sin categoría de incidente definida")
        
        # Paso 4-5: Filtrar por especialidad y disponibilidad (E2)
        talleres_compatibles = []
        
        # Obtener todos los talleres aprobados y habilitados
        talleres = db.query(Taller).filter(
            Taller.estado_aprobacion == EstadoAprobacionTaller.APROBADO,
            Taller.estado_operativo == EstadoOperativoTaller.DISPONIBLE,
        ).all()
        
        # E2: Si no hay talleres habilitados
        if not talleres:
            logger.warning(f"No hay talleres habilitados en la plataforma")
            SolicitudService._registrar_bitacora(
                db=db,
                accion="Búsqueda de talleres compatibles",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"E2: No hay talleres habilitados en la plataforma. Solicitud: {solicitud.codigo_solicitud}",
                id_entidad=solicitud_id,
                tipo_actor=TipoActor.SISTEMA,
            )
            
            return {
                "solicitud_id": solicitud_id,
                "total_encontrados": 0,
                "razon": "E2: No hay talleres habilitados",
                "cantidad_por_distancia": {},
                "talleres": [],
            }
        
        # Procesar cada taller
        cantidad_por_distancia = {
            "cercanos_0_5km": 0,
            "mediano_5_10km": 0,
            "lejanos_10km": 0,
        }
        
        for taller in talleres:
            # Validar que tiene especialidades
            especialidades = db.query(TallerEspecialidad).filter(
                TallerEspecialidad.id_taller == taller.id_taller
            ).all()
            
            if not especialidades:
                continue
            
            # Paso 4: Filtrar por especialidad (categoría de incidente)
            categorias_permitidas = set()
            for te in especialidades:
                espec = db.query(Especialidad).filter(
                    Especialidad.id_especialidad == te.id_especialidad
                ).first()
                if espec:
                    categorias_permitidas.add(espec.nombre_especialidad)
            
            if solicitud.categoria_incidente not in categorias_permitidas:
                continue
            
            # Validar ubicación
            if not (solicitud.latitud and solicitud.longitud and taller.latitud and taller.longitud):
                continue
            
            # Paso 6: Calcular distancia y filtrar por radio
            distancia_km = SolicitudService._calcular_distancia_haversine(
                taller.latitud,
                taller.longitud,
                solicitud.latitud,
                solicitud.longitud
            )
            
            # Filtro: Debe estar dentro del radio de búsqueda
            if distancia_km > solicitud.radio_busqueda_km:
                continue
            
            # Incluir en resultados
            taller_info = {
                "taller_id": str(taller.id_taller),
                "nombre": taller.nombre_taller,
                "distancia_km": distancia_km,
                "especialidades": list(categorias_permitidas),
            }
            talleres_compatibles.append(taller_info)
            
            # Contar por distancia
            if distancia_km <= 5.0:
                cantidad_por_distancia["cercanos_0_5km"] += 1
            elif distancia_km <= 10.0:
                cantidad_por_distancia["mediano_5_10km"] += 1
            else:
                cantidad_por_distancia["lejanos_10km"] += 1
        
        # Paso 7: Ordenar por distancia
        talleres_compatibles.sort(key=lambda x: x["distancia_km"])
        
        # E1: Si no encontró compatibles
        if not talleres_compatibles:
            logger.warning(f"No hay talleres compatibles para solicitud {solicitud_id}")
            SolicitudService._registrar_bitacora(
                db=db,
                accion="Búsqueda de talleres compatibles",
                resultado=ResultadoAuditoria.ADVERTENCIA,
                detalle=f"E1: No hay talleres compatibles encontrados. "
                       f"Solicitud: {solicitud.codigo_solicitud}, "
                       f"Categoría: {solicitud.categoria_incidente}, "
                       f"Radio: {solicitud.radio_busqueda_km}km",
                id_entidad=solicitud_id,
                tipo_actor=TipoActor.SISTEMA,
            )
            
            return {
                "solicitud_id": solicitud_id,
                "total_encontrados": 0,
                "razon": "E1: No hay talleres compatibles",
                "cantidad_por_distancia": cantidad_por_distancia,
                "talleres": [],
            }
        
        # Paso 8: Registrar evento exitoso en bitácora
        SolicitudService._registrar_bitacora(
            db=db,
            accion="Búsqueda de talleres compatibles",
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Se encontraron {len(talleres_compatibles)} talleres compatibles. "
                   f"Solicitud: {solicitud.codigo_solicitud}, "
                   f"Categoría: {solicitud.categoria_incidente}, "
                   f"Radio: {solicitud.radio_busqueda_km}km. "
                   f"Distribucion: 0-5km={cantidad_por_distancia['cercanos_0_5km']}, "
                   f"5-10km={cantidad_por_distancia['mediano_5_10km']}, "
                   f">10km={cantidad_por_distancia['lejanos_10km']}",
            id_entidad=solicitud_id,
            tipo_actor=TipoActor.SISTEMA,
        )
        
        logger.info(f"Búsqueda completada: {len(talleres_compatibles)} talleres encontrados para solicitud {solicitud_id}")
        
        # Paso 9: Retornar resultados
        return {
            "solicitud_id": solicitud_id,
            "codigo_solicitud": solicitud.codigo_solicitud,
            "categoria_incidente": solicitud.categoria_incidente,
            "radio_busqueda_km": solicitud.radio_busqueda_km,
            "total_encontrados": len(talleres_compatibles),
            "cantidad_por_distancia": cantidad_por_distancia,
            "talleres": talleres_compatibles,
        }
