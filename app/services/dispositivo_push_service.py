from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.models.dispositivo_push import DispositivoPush
from app.core.enums import PlataformaPush


class DispositivoPushService:
    """Servicio para gestionar dispositivos push y tokens FCM"""

    @staticmethod
    def register_token(
        db: Session,
        id_usuario: UUID,
        plataforma: PlataformaPush,
        token_fcm: str,
        device_id: str | None = None,
        nombre_dispositivo: str | None = None,
        user_agent: str | None = None,
    ) -> DispositivoPush:
        """
        Registra o actualiza un token FCM para un usuario.
        
        Usa device_id como clave primaria de upsert para evitar duplicados.
        Si FCM renueva el token del mismo dispositivo:
        - Busca por id_usuario + device_id
        - Si existe, actualiza el token_fcm
        - Si no existe, crea nuevo dispositivo
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario
            plataforma: Plataforma del dispositivo (WEB, ANDROID, IOS)
            token_fcm: Token FCM del dispositivo
            device_id: ID del dispositivo (opcional)
            nombre_dispositivo: Nombre descriptivo del dispositivo (opcional)
            user_agent: User agent del cliente (opcional)
            
        Returns:
            Dispositivo push registrado o actualizado
        """
        # Estrategia de upsert mejorada:
        # 1. Si tenemos device_id, buscar por id_usuario + device_id (clave principal)
        if device_id:
            dispositivo = db.query(DispositivoPush).filter(
                DispositivoPush.id_usuario == id_usuario,
                DispositivoPush.device_id == device_id
            ).first()
            
            if dispositivo:
                # Dispositivo existente en este equipo: actualizar token
                dispositivo.plataforma = plataforma
                dispositivo.token_fcm = token_fcm  # Actualizar token renovado
                dispositivo.nombre_dispositivo = nombre_dispositivo
                dispositivo.user_agent = user_agent
                dispositivo.activo = True
                dispositivo.fecha_actualizacion = datetime.utcnow()
                db.commit()
                db.refresh(dispositivo)
                return dispositivo

        # 2. Si no hay device_id o no encontramos por device_id,
        # buscar si el token ya existe por cualquier razón
        dispositivo = db.query(DispositivoPush).filter(
            DispositivoPush.id_usuario == id_usuario,
            DispositivoPush.token_fcm == token_fcm
        ).first()

        if dispositivo:
            # Token ya existe en registros: actualizar metadatos
            if device_id:
                dispositivo.device_id = device_id
            dispositivo.plataforma = plataforma
            dispositivo.nombre_dispositivo = nombre_dispositivo
            dispositivo.user_agent = user_agent
            dispositivo.activo = True
            dispositivo.fecha_actualizacion = datetime.utcnow()
            db.commit()
            db.refresh(dispositivo)
            return dispositivo

        # 3. Crear nuevo dispositivo si no existe
        dispositivo = DispositivoPush(
            id_usuario=id_usuario,
            plataforma=plataforma,
            token_fcm=token_fcm,
            device_id=device_id,
            nombre_dispositivo=nombre_dispositivo,
            user_agent=user_agent,
            activo=True
        )
        db.add(dispositivo)
        db.commit()
        db.refresh(dispositivo)
        return dispositivo

    @staticmethod
    def unregister_token(
        db: Session,
        id_usuario: UUID,
        token_fcm: str
    ) -> bool:
        """
        Desactiva un token FCM (lo marca como inactivo).
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario
            token_fcm: Token FCM a desactivar
            
        Returns:
            True si se desactivó, False si no existía
        """
        dispositivo = db.query(DispositivoPush).filter(
            DispositivoPush.id_usuario == id_usuario,
            DispositivoPush.token_fcm == token_fcm
        ).first()

        if not dispositivo:
            return False

        dispositivo.activo = False
        dispositivo.fecha_actualizacion = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def get_active_tokens_for_user(
        db: Session,
        id_usuario: UUID
    ) -> list[DispositivoPush]:
        """
        Obtiene todos los tokens activos de un usuario.
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario
            
        Returns:
            Lista de dispositivos con tokens activos
        """
        return db.query(DispositivoPush).filter(
            DispositivoPush.id_usuario == id_usuario,
            DispositivoPush.activo == True
        ).all()

    @staticmethod
    def deactivate_token(
        db: Session,
        id_dispositivo_push: UUID
    ) -> bool:
        """
        Desactiva un token por su ID (usado cuando FCM reporta token inválido).
        
        Args:
            db: Sesión de base de datos
            id_dispositivo_push: ID del dispositivo
            
        Returns:
            True si se desactivó, False si no existía
        """
        dispositivo = db.query(DispositivoPush).filter(
            DispositivoPush.id_dispositivo_push == id_dispositivo_push
        ).first()

        if not dispositivo:
            return False

        dispositivo.activo = False
        dispositivo.fecha_actualizacion = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def update_last_used(
        db: Session,
        id_dispositivo_push: UUID
    ) -> bool:
        """
        Actualiza la marca de tiempo de último uso de un dispositivo.
        
        Args:
            db: Sesión de base de datos
            id_dispositivo_push: ID del dispositivo
            
        Returns:
            True si se actualizó, False si no existía
        """
        dispositivo = db.query(DispositivoPush).filter(
            DispositivoPush.id_dispositivo_push == id_dispositivo_push
        ).first()

        if not dispositivo:
            return False

        dispositivo.ultima_vez_usado = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def list_devices_for_user(
        db: Session,
        id_usuario: UUID
    ) -> list[DispositivoPush]:
        """
        Lista todos los dispositivos registrados de un usuario.
        
        Args:
            db: Sesión de base de datos
            id_usuario: ID del usuario
            
        Returns:
            Lista de dispositivos
        """
        return db.query(DispositivoPush).filter(
            DispositivoPush.id_usuario == id_usuario
        ).order_by(DispositivoPush.fecha_actualizacion.desc()).all()
