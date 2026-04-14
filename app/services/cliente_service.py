from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import RolUsuario, TipoActor, ResultadoAuditoria
from app.core.exceptions import not_found, forbidden
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.bitacora import Bitacora


class ClienteService:
    @staticmethod
    def get_cliente_by_usuario_id(db: Session, usuario_id: UUID) -> Cliente | None:
        """
        Obtiene el cliente asociado a un usuario_id.
        Retorna None si no existe.
        """
        return db.query(Cliente).filter(Cliente.id_usuario == usuario_id).first()

    @staticmethod
    def list_clientes(db: Session, current_user: Usuario):
        """
        Lista clientes.
        - ADMINISTRADOR: Ve todos
        - CLIENTE: Solo ve su propio perfil
        """
        if current_user.rol == RolUsuario.ADMINISTRADOR:
            return db.query(Cliente).all()
        elif current_user.rol == RolUsuario.CLIENTE:
            # Un cliente solo ve su propio perfil
            cliente = ClienteService.get_cliente_by_usuario_id(db, current_user.id_usuario)
            if cliente is None:
                raise not_found("Tu perfil de cliente no existe")
            return [cliente]
        else:
            return []

    @staticmethod
    def get_cliente(db: Session, cliente_id: UUID, current_user: Usuario):
        """
        Obtiene un cliente.
        - Ownership: El usuario solo puede ver su propio cliente
        - ADMINISTRADOR: Puede ver cualquier cliente
        """
        cliente = db.query(Cliente).filter(Cliente.id_cliente == cliente_id).first()
        if cliente is None:
            raise not_found("Cliente no encontrado")
        
        # Ownership check
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            if cliente.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para acceder a este cliente")
        
        return cliente

    @staticmethod
    def create_cliente(db: Session, data: dict, current_user: Usuario):
        """
        Crea un cliente (uso interno/admin solamente).
        Los clientes normales se registran mediante auth.register_cliente
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden crear clientes")
        
        cliente = Cliente(**data)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def update_cliente(db: Session, cliente_id: UUID, data: dict, current_user: Usuario):
        """
        Actualiza un cliente.
        - Ownership: Solo puede actualizar su propio cliente
        - ADMINISTRADOR: Puede actualizar cualquier cliente
        """
        cliente = ClienteService.get_cliente(db, cliente_id, current_user)
        
        # Ownership check (redundante pero explícito)
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            if cliente.id_usuario != current_user.id_usuario:
                raise forbidden("No tienes permiso para modificar este cliente")
        
        payload = {k: v for k, v in data.items() if v is not None}
        for key, value in payload.items():
            setattr(cliente, key, value)
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def delete_cliente(db: Session, cliente_id: UUID, current_user: Usuario) -> None:
        """
        Elimina un cliente (solo ADMINISTRADOR).
        """
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("Solo administradores pueden eliminar clientes")
        
        cliente = ClienteService.get_cliente(db, cliente_id, current_user)
        db.delete(cliente)
        db.commit()

    @staticmethod
    def _registrar_bitacora(
        db: Session,
        usuario_id: UUID,
        accion: str,
        resultado: ResultadoAuditoria,
        detalle: str | None = None,
    ) -> None:
        """Registra eventos en la bitácora"""
        bitacora = Bitacora(
            tipo_actor=TipoActor.CLIENTE,
            id_actor=usuario_id,
            accion=accion,
            modulo="Perfil de Cliente",
            entidad_afectada="Cliente",
            id_entidad_afectada=usuario_id,
            resultado=resultado,
            detalle=detalle,
        )
        db.add(bitacora)
        db.commit()

    @staticmethod
    def get_my_profile(db: Session, current_user: Usuario) -> Cliente:
        """
        Obtiene el perfil propio del cliente autenticado.
        
        Precondiciones:
        - El usuario debe estar autenticado con rol CLIENTE
        
        Postcondiciones:
        - Retorna la información del cliente asociado al usuario
        """
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo clientes pueden acceder a su perfil")
        
        cliente = ClienteService.get_cliente_by_usuario_id(db, current_user.id_usuario)
        if cliente is None:
            raise not_found("Tu perfil de cliente no existe")
        
        return cliente

    @staticmethod
    def update_my_profile(db: Session, current_user: Usuario, data: dict) -> Cliente:
        """
        Actualiza el perfil propio del cliente autenticado.
        
        Precondiciones:
        - El usuario debe estar autenticado con rol CLIENTE
        - El perfil del cliente debe existir
        
        Validaciones (Excepción E1):
        - Los datos deben cumplir con los formatos requeridos
        - Se validan campos como nombre, apellido, teléfono, dirección, CI
        
        Efectos:
        - Actualiza la información en la BD
        - Registra el evento en bitácora (EXITO o ERROR)
        
        Postcondiciones:
        - La información del perfil está actualizada
        - El evento queda registrado en bitácora
        
        Excepciones:
        - E1: Datos inválidos (401 Forbidden para rol incorrecto)
        - E2: Error al actualizar (capturado y registrado en bitácora)
        """
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo clientes pueden actualizar su perfil")
        
        cliente = ClienteService.get_cliente_by_usuario_id(db, current_user.id_usuario)
        if cliente is None:
            ClienteService._registrar_bitacora(
                db=db,
                usuario_id=current_user.id_usuario,
                accion="Intento de actualizar perfil - Perfil no encontrado",
                resultado=ResultadoAuditoria.ERROR,
                detalle="El cliente no existe en el sistema",
            )
            raise not_found("Tu perfil de cliente no existe")
        
        try:
            # Filtrar solo los campos que vienen (no None)
            campos_actualizables = {
                "nombre", "apellido", "telefono", "ci", "direccion", "foto_perfil_url"
            }
            
            for key, value in data.items():
                if key in campos_actualizables and value is not None:
                    setattr(cliente, key, value)
            
            db.commit()
            db.refresh(cliente)
            
            # Registrar en bitácora
            campos_str = ", ".join([f"{k}={v}" for k, v in data.items() if v is not None])
            ClienteService._registrar_bitacora(
                db=db,
                usuario_id=current_user.id_usuario,
                accion="Actualización de perfil de cliente",
                resultado=ResultadoAuditoria.EXITO,
                detalle=f"Campos actualizados: {campos_str}",
            )
            
            return cliente
        
        except Exception as e:
            ClienteService._registrar_bitacora(
                db=db,
                usuario_id=current_user.id_usuario,
                accion="Error al actualizar perfil de cliente",
                resultado=ResultadoAuditoria.ERROR,
                detalle=f"Error técnico: {str(e)}",
            )
            raise
