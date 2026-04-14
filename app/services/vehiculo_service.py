from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import RolUsuario, EstadoRegistroVehiculo, TipoActor, ResultadoAuditoria
from app.core.exceptions import not_found, forbidden, bad_request
from app.models.vehiculo import Vehiculo
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.bitacora import Bitacora


class VehiculoService:
    @staticmethod
    def list_vehiculos(db: Session, current_user: Usuario):
        """
        Lista vehículos.
        - ADMINISTRADOR: Ve todos los vehículos
        - CLIENTE: Solo ve sus propios vehículos
        """
        if current_user.rol == RolUsuario.ADMINISTRADOR:
            return db.query(Vehiculo).all()
        elif current_user.rol == RolUsuario.CLIENTE:
            # Un cliente solo ve sus propios vehículos
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente:
                return []
            return db.query(Vehiculo).filter(Vehiculo.id_cliente == cliente.id_cliente).all()
        else:
            return []

    @staticmethod
    def get_vehiculo(db: Session, vehiculo_id: UUID, current_user: Usuario):
        """
        Obtiene un vehículo.
        - Ownership: El usuario solo puede ver sus propios vehículos
        - ADMINISTRADOR: Puede ver cualquier vehículo
        """
        vehiculo = db.query(Vehiculo).filter(Vehiculo.id_vehiculo == vehiculo_id).first()
        if vehiculo is None:
            raise not_found("Vehículo no encontrado")
        
        # Ownership check
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or vehiculo.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes permiso para acceder a este vehículo")
        
        return vehiculo

    @staticmethod
    def create_vehiculo(db: Session, data: dict, current_user: Usuario):
        """
        Crea un vehículo.
        - CLIENTE: Solo puede crear vehículos para sí mismo
        - ADMINISTRADOR: Puede crear vehículos para cualquier cliente
        """
        cliente_id = data.get("id_cliente")
        
        if current_user.rol == RolUsuario.CLIENTE:
            # Un cliente solo puede crear vehículos para sí mismo
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente:
                raise forbidden("No se encontró tu perfil de cliente")
            data["id_cliente"] = cliente.id_cliente
        elif current_user.rol != RolUsuario.ADMINISTRADOR:
            raise forbidden("No tienes permiso para crear vehículos")
        
        vehiculo = Vehiculo(**data)
        db.add(vehiculo)
        db.commit()
        db.refresh(vehiculo)
        return vehiculo

    @staticmethod
    def update_vehiculo(db: Session, vehiculo_id: UUID, data: dict, current_user: Usuario):
        """
        Actualiza un vehículo.
        - Ownership: El usuario solo puede actualizar sus propios vehículos
        - ADMINISTRADOR: Puede actualizar cualquier vehículo
        """
        vehiculo = VehiculoService.get_vehiculo(db, vehiculo_id, current_user)
        
        # Ownership check (redundante pero explícito)
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or vehiculo.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes permiso para modificar este vehículo")
        
        payload = {k: v for k, v in data.items() if v is not None}
        for key, value in payload.items():
            setattr(vehiculo, key, value)
        db.commit()
        db.refresh(vehiculo)
        return vehiculo

    @staticmethod
    def delete_vehiculo(db: Session, vehiculo_id: UUID, current_user: Usuario) -> None:
        """
        Elimina un vehículo.
        - CLIENTE: Solo puede eliminar sus propios vehículos
        - ADMINISTRADOR: Puede eliminar cualquier vehículo
        """
        vehiculo = VehiculoService.get_vehiculo(db, vehiculo_id, current_user)
        
        if current_user.rol != RolUsuario.ADMINISTRADOR:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or vehiculo.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes permiso para eliminar este vehículo")
        
        db.delete(vehiculo)
        db.commit()

    # Métodos específicos para cliente (con bitácora)
    @staticmethod
    def _registrar_bitacora(db: Session, user_id: UUID, accion: str, resultado: ResultadoAuditoria, detalle: str | None = None, id_entidad: UUID | None = None):
        """Registra evento en bitácora"""
        evento = Bitacora(
            tipo_actor=TipoActor.CLIENTE,
            id_actor=user_id,
            accion=accion,
            modulo="Gestión de Vehículos",
            entidad_afectada="Vehículo",
            id_entidad_afectada=id_entidad,
            resultado=resultado,
            detalle=detalle
        )
        db.add(evento)
        db.commit()

    @staticmethod
    def list_my_vehiculos(db: Session, current_user: Usuario):
        """
        Lista vehículos del cliente autenticado.
        
        Requiere:
        - Cliente autenticado
        - Rol CLIENTE
        
        Retorna:
        - Lista de vehículos del cliente
        """
        cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
        if not cliente:
            return []
        
        return db.query(Vehiculo).filter(
            Vehiculo.id_cliente == cliente.id_cliente,
            Vehiculo.estado_registro == EstadoRegistroVehiculo.ACTIVO
        ).all()

    @staticmethod
    def get_my_vehiculo(db: Session, vehiculo_id: UUID, current_user: Usuario):
        """
        Obtiene un vehículo del cliente autenticado.
        
        Requiere:
        - Cliente autenticado
        - Vehículo existe y pertenece al cliente
        
        Excepciones:
        - E3: Vehículo no encontrado
        """
        cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
        if not cliente:
            raise forbidden("Perfil de cliente no encontrado")
        
        vehiculo = db.query(Vehiculo).filter(
            Vehiculo.id_vehiculo == vehiculo_id,
            Vehiculo.id_cliente == cliente.id_cliente
        ).first()
        
        if not vehiculo:
            raise not_found("Vehículo no encontrado")
        
        return vehiculo

    @staticmethod
    def create_my_vehiculo(db: Session, data: dict, current_user: Usuario):
        """
        Crea un vehículo para el cliente autenticado.
        
        Validaciones (E1):
        - Placa: 5-20 caracteres, debe ser única
        - Marca: max 120 caracteres
        - Modelo: max 120 caracteres
        - Año: 1900-2100
        - Color: max 50 caracteres
        - Tipo combustible: max 50 caracteres
        - Observaciones: max 1000 caracteres
        
        Excepciones:
        - E2: Placa ya existe (duplicado)
        """
        cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
        if not cliente:
            raise forbidden("Perfil de cliente no encontrado")
        
        # Validación E2: Placa duplicada
        placa = data.get("placa", "").upper().strip()
        vehiculo_existente = db.query(Vehiculo).filter(
            Vehiculo.placa == placa
        ).first()
        
        if vehiculo_existente:
            VehiculoService._registrar_bitacora(
                db, 
                current_user.id_usuario,
                "Intento de registrar vehículo duplicado",
                ResultadoAuditoria.ADVERTENCIA,
                f"Placa {placa} ya registrada",
                None
            )
            raise bad_request(f"La placa {placa} ya está registrada en el sistema")
        
        try:
            vehiculo = Vehiculo(
                id_cliente=cliente.id_cliente,
                placa=placa,
                marca=data.get("marca"),
                modelo=data.get("modelo"),
                anio=data.get("anio"),
                color=data.get("color"),
                tipo_combustible=data.get("tipo_combustible"),
                observaciones=data.get("observaciones"),
                estado_registro=EstadoRegistroVehiculo.ACTIVO
            )
            db.add(vehiculo)
            db.commit()
            db.refresh(vehiculo)
            
            # Registrar en bitácora
            VehiculoService._registrar_bitacora(
                db,
                current_user.id_usuario,
                "Registro de vehículo",
                ResultadoAuditoria.EXITO,
                f"Placa: {placa}, Marca: {data.get('marca')}, Modelo: {data.get('modelo')}",
                vehiculo.id_vehiculo
            )
            
            return vehiculo
        except Exception as e:
            VehiculoService._registrar_bitacora(
                db,
                current_user.id_usuario,
                "Error al registrar vehículo",
                ResultadoAuditoria.ERROR,
                str(e),
                None
            )
            raise

    @staticmethod
    def update_my_vehiculo(db: Session, vehiculo_id: UUID, data: dict, current_user: Usuario):
        """
        Actualiza un vehículo del cliente autenticado.
        
        Validaciones (E1):
        - Placa: 5-20 caracteres, debe ser única (si se modifica)
        - Otros campos: mismas validaciones que create
        
        Excepciones:
        - E2: Nueva placa ya existe (duplicado)
        - E3: Vehículo no encontrado
        """
        vehiculo = VehiculoService.get_my_vehiculo(db, vehiculo_id, current_user)
        
        try:
            campos_modificados = []
            
            # Si se intenta cambiar la placa, validar que sea única
            if "placa" in data and data["placa"]:
                nueva_placa = data["placa"].upper().strip()
                if nueva_placa != vehiculo.placa:
                    vehiculo_existente = db.query(Vehiculo).filter(
                        Vehiculo.placa == nueva_placa,
                        Vehiculo.id_vehiculo != vehiculo_id
                    ).first()
                    if vehiculo_existente:
                        VehiculoService._registrar_bitacora(
                            db,
                            current_user.id_usuario,
                            "Intento de actualizar vehículo con placa duplicada",
                            ResultadoAuditoria.ADVERTENCIA,
                            f"Placa {nueva_placa} ya registrada",
                            vehiculo.id_vehiculo
                        )
                        raise bad_request(f"La placa {nueva_placa} ya está registrada en el sistema")
                vehiculo.placa = nueva_placa
                campos_modificados.append("placa")
            
            # Actualizar otros campos
            for key, value in data.items():
                if key != "placa" and value is not None:
                    if hasattr(vehiculo, key) and getattr(vehiculo, key) != value:
                        setattr(vehiculo, key, value)
                        campos_modificados.append(key)
            
            db.commit()
            db.refresh(vehiculo)
            
            # Registrar en bitácora
            if campos_modificados:
                VehiculoService._registrar_bitacora(
                    db,
                    current_user.id_usuario,
                    "Actualización de vehículo",
                    ResultadoAuditoria.EXITO,
                    f"Campos actualizados: {', '.join(campos_modificados)}",
                    vehiculo.id_vehiculo
                )
            
            return vehiculo
        except Exception as e:
            VehiculoService._registrar_bitacora(
                db,
                current_user.id_usuario,
                "Error al actualizar vehículo",
                ResultadoAuditoria.ERROR,
                str(e),
                vehiculo.id_vehiculo
            )
            raise

    @staticmethod
    def delete_my_vehiculo(db: Session, vehiculo_id: UUID, current_user: Usuario) -> None:
        """
        Elimina (desactiva) un vehículo del cliente autenticado.
        
        Excepción:
        - E3: Vehículo no encontrado
        
        Nota:
        - Lógica soft-delete: marca como INACTIVO en lugar de eliminar
        """
        vehiculo = VehiculoService.get_my_vehiculo(db, vehiculo_id, current_user)
        
        try:
            vehiculo.estado_registro = EstadoRegistroVehiculo.INACTIVO
            db.commit()
            
            VehiculoService._registrar_bitacora(
                db,
                current_user.id_usuario,
                "Eliminación de vehículo",
                ResultadoAuditoria.EXITO,
                f"Vehículo con placa {vehiculo.placa} desactivado",
                vehiculo.id_vehiculo
            )
        except Exception as e:
            VehiculoService._registrar_bitacora(
                db,
                current_user.id_usuario,
                "Error al eliminar vehículo",
                ResultadoAuditoria.ERROR,
                str(e),
                vehiculo.id_vehiculo
            )
            raise
