from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.client import (
    ClienteCreate,
    ClienteRead,
    ClienteUpdate,
    ClientePerfilResponse,
    ClientePerfilUpdate,
)
from app.schemas.vehicle import (
    VehiculoCreateByClient,
    VehiculoUpdateByClient,
    VehiculoResponseClient,
)
from app.services.cliente_service import ClienteService
from app.services.vehiculo_service import VehiculoService


router = APIRouter(dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.CLIENTE))])


@router.get("", response_model=list[ClienteRead])
def list_clientes(
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista clientes.
    - ADMINISTRADOR: Ve todos los clientes
    - CLIENTE: Solo ve su propio perfil
    """
    return ClienteService.list_clientes(db, current_user)


# ============================================================================
# ENDPOINTS DE PERFIL PROPIO DEL CLIENTE (CASO DE USO: GESTIONAR PERFIL)
# ============================================================================
# IMPORTANTE: Deben estar ANTES de /{cliente_id} para evitar conflicto de rutas


@router.get("/me", response_model=ClientePerfilResponse)
def get_my_client_profile(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Obtiene el perfil propio del cliente autenticado.
    
    Precondición:
    - El Cliente debe haber iniciado sesión correctamente en la aplicación móvil.
    
    Flujo Principal (Paso 1-2):
    - El cliente accede a su perfil desde el menú principal
    - El sistema muestra la información actual del perfil del cliente
    
    Postcondición:
    - Los datos del cliente están disponibles para consulta
    
    Solo accesible por usuarios con rol CLIENTE.
    Retorna información completa del perfil incluida información del usuario.
    """
    cliente = ClienteService.get_my_profile(db, current_user)
    
    # Construir respuesta manualmente para incluir correo del usuario
    return ClientePerfilResponse(
        id_cliente=cliente.id_cliente,
        id_usuario=cliente.id_usuario,
        nombre=cliente.nombre,
        apellido=cliente.apellido,
        telefono=cliente.telefono,
        ci=cliente.ci,
        direccion=cliente.direccion,
        foto_perfil_url=cliente.foto_perfil_url,
        fecha_registro=cliente.fecha_registro,
        correo=cliente.usuario.correo if cliente.usuario else None,
    )


@router.patch("/me", response_model=ClientePerfilResponse)
def update_my_client_profile(
    payload: ClientePerfilUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Actualiza el perfil propio del cliente autenticado.
    
    Precondición:
    - El Cliente debe haber iniciado sesión correctamente
    
    Flujo Principal (Pasos 3-10):
    - El cliente selecciona editar perfil
    - El sistema habilita campos permitidos (nombre, apellido, teléfono, dirección, CI)
    - El cliente actualiza datos personales
    - El cliente confirma guardar cambios
    - El sistema valida que los datos cumplan con formatos requeridos (E1)
    - El sistema actualiza la información en la BD
    - El sistema registra el evento en bitácora
    - El sistema muestra mensaje de confirmación
    
    Campos permitidos para edición:
    - nombre
    - apellido
    - telefono
    - ci
    - direccion
    - foto_perfil_url
    
    Validaciones (Excepción E1):
    - Nombre: mínimo 2 caracteres
    - Apellido: mínimo 2 caracteres
    - Teléfono: máximo 30 caracteres
    - CI: entre 5 y 50 caracteres
    - Dirección: máximo 255 caracteres
    - Foto: máximo 500 caracteres (URL)
    
    Postcondiciones:
    - La información del perfil está actualizada en el sistema
    - Los nuevos datos quedan disponibles para futuros procesos
    - El evento de modificación queda registrado en bitácora
    """
    cliente = ClienteService.update_my_profile(db, current_user, payload.model_dump())
    
    # Construir respuesta manualmente para incluir correo del usuario
    return ClientePerfilResponse(
        id_cliente=cliente.id_cliente,
        id_usuario=cliente.id_usuario,
        nombre=cliente.nombre,
        apellido=cliente.apellido,
        telefono=cliente.telefono,
        ci=cliente.ci,
        direccion=cliente.direccion,
        foto_perfil_url=cliente.foto_perfil_url,
        fecha_registro=cliente.fecha_registro,
        correo=cliente.usuario.correo if cliente.usuario else None,
    )


# ============================================================================
# ENDPOINTS DE GESTIÓN DE VEHÍCULOS DEL CLIENTE
# (CASO DE USO: GESTIONAR VEHÍCULOS)
# ============================================================================


@router.get("/me/vehiculos", response_model=list[VehiculoResponseClient])
def list_my_vehiculos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Lista vehículos del cliente autenticado.
    
    Precondición:
    - El Cliente debe haber iniciado sesión correctamente en la aplicación móvil.
    - El sistema debe estar operativo (PRE1, PRE2)
    
    Flujo Principal (Paso 1-2):
    - El cliente accede a la sección de gestión de vehículos
    - El sistema muestra el listado de vehículos previamente registrados por el cliente
    
    Postcondición:
    - Los vehículos activos están disponibles para consulta
    - El cliente puede seleccionar un vehículo para operaciones
    
    Retorna:
    - Lista de vehículos activos del cliente autenticado
    - Solo vehículos con estado ACTIVO
    """
    return VehiculoService.list_my_vehiculos(db, current_user)


@router.post("/me/vehiculos", response_model=VehiculoResponseClient, status_code=status.HTTP_201_CREATED)
def create_my_vehiculo(
    payload: VehiculoCreateByClient,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Registra un nuevo vehículo para el cliente autenticado.
    
    Precondición:
    - El Cliente debe haber iniciado sesión correctamente
    
    Flujo Principal (Pasos 3-8):
    - El cliente selecciona registrar nuevo vehículo
    - El sistema muestra formulario de registro
    - El cliente ingresa información: placa, marca, modelo, color, año, otros datos
    - El cliente confirma guardar
    - El sistema valida que datos obligatorios estén completos (E1)
    - El sistema valida que no exista placa duplicada (E2)
    - El sistema registra el vehículo asociado al cliente
    - El sistema registra la acción en bitácora
    
    Postcondición:
    - El vehículo queda registrado y disponible para emergencias
    - El evento queda registrado en bitácora
    - Se muestra mensaje de confirmación
    
    Validaciones (Excepción E1):
    - Placa: 5-20 caracteres (obligatorio)
    - Marca: máximo 120 caracteres
    - Modelo: máximo 120 caracteres
    - Año: 1900-2100
    - Color: máximo 50 caracteres
    - Tipo combustible: máximo 50 caracteres
    - Observaciones: máximo 1000 caracteres
    
    Excepción E2: Vehículo duplicado
    - Si placa ya existe en el sistema, rechaza la operación
    
    Retorna:
    - Vehículo creado con su información completa
    """
    return VehiculoService.create_my_vehiculo(db, payload.model_dump(), current_user)


@router.get("/me/vehiculos/{vehiculo_id}", response_model=VehiculoResponseClient)
def get_my_vehiculo(
    vehiculo_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Obtiene un vehículo específico del cliente autenticado.
    
    Precondición:
    - El Cliente debe estar autenticado
    - El vehículo debe existir y pertenecer al cliente
    
    Excepción E3: Vehículo no encontrado
    - Si el vehículo no existe o no pertenece al cliente
    - El sistema muestra mensaje y retorna al listado
    
    Retorna:
    - Información completa del vehículo
    """
    return VehiculoService.get_my_vehiculo(db, vehiculo_id, current_user)


@router.patch("/me/vehiculos/{vehiculo_id}", response_model=VehiculoResponseClient)
def update_my_vehiculo(
    vehiculo_id: UUID,
    payload: VehiculoUpdateByClient,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Actualiza un vehículo del cliente autenticado.
    
    Precondición:
    - El Cliente debe estar autenticado
    - El vehículo debe existir y pertenecer al cliente
    
    Flujo Principal (Pasos 9-11):
    - El cliente selecciona editar vehículo
    - El sistema muestra información actual del vehículo
    - El cliente modifica datos permitidos
    - El cliente confirma los cambios
    - El sistema valida información actualizada (E1)
    - El sistema valida que no exista nueva placa duplicada (E2)
    - El sistema guarda la modificación
    - El sistema registra el evento en bitácora
    
    Postcondición:
    - El vehículo está actualizado
    - La información modificada está disponible inmediatamente
    - El evento queda registrado en bitácora
    
    Validaciones (Excepción E1):
    - Placa: 5-20 caracteres (si se modifica)
    - Marca: máximo 120 caracteres
    - Modelo: máximo 120 caracteres
    - Año: 1900-2100
    - Color: máximo 50 caracteres
    - Tipo combustible: máximo 50 caracteres
    - Observaciones: máximo 1000 caracteres
    
    Excepción E2: Nueva placa duplicada
    - Si intenta cambiar a una placa que ya existe
    
    Excepción E3: Vehículo no encontrado
    - Si el vehículo no existe o no pertenece al cliente
    
    Retorna:
    - Vehículo actualizado
    """
    return VehiculoService.update_my_vehiculo(db, vehiculo_id, payload.model_dump(), current_user)


@router.delete("/me/vehiculos/{vehiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_vehiculo(
    vehiculo_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE)),
):
    """
    Elimina (desactiva) un vehículo del cliente autenticado.
    
    Precondición:
    - El Cliente debe estar autenticado
    - El vehículo debe existir y pertenecer al cliente
    
    Flujo Principal (Pasos 12-17):
    - El cliente selecciona eliminar vehículo
    - El sistema solicita confirmación antes de ejecutar la acción
    - El cliente confirma la eliminación
    - El sistema desactiva el registro del vehículo (soft-delete)
    - El sistema actualiza el listado de vehículos registrados
    - El sistema registra la acción en bitácora
    - El sistema muestra mensaje confirmando operación
    
    Postcondición:
    - El vehículo queda desactivado (no disponible para nuevas emergencias)
    - El evento queda registrado en bitácora
    - El listado actualizado no incluye el vehículo
    
    Excepción E3: Vehículo no encontrado
    - Si el vehículo no existe o no pertenece al cliente
    - El sistema muestra mensaje y retorna al listado actualizado
    
    Nota:
    - La operación marca el vehículo como INACTIVO en lugar de eliminarlo
    - Esto mantiene el historial para auditoría y emergencias pasadas
    """
    VehiculoService.delete_my_vehiculo(db, vehiculo_id, current_user)


@router.post("", response_model=ClienteRead, status_code=status.HTTP_201_CREATED)
def create_cliente(
    payload: ClienteCreate, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea un nuevo cliente (solo ADMINISTRADOR).
    Los clientes normales se crean mediante el endpoint de registro.
    """
    return ClienteService.create_cliente(db, payload.model_dump(), current_user)


@router.get("/{cliente_id}", response_model=ClienteRead)
def get_cliente(
    cliente_id: UUID, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene un cliente específico.
    - CLIENTE solo puede acceder a su propio perfil
    - ADMINISTRADOR puede ver cualquier cliente
    """
    return ClienteService.get_cliente(db, cliente_id, current_user)@router.put("/{cliente_id}", response_model=ClienteRead)
def update_cliente(
    cliente_id: UUID,
    payload: ClienteUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualiza un cliente.
    - CLIENTE solo puede actualizar su propio perfil
    - ADMINISTRADOR puede actualizar cualquier cliente
    """
    return ClienteService.update_cliente(db, cliente_id, payload.model_dump(), current_user)


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cliente(
    cliente_id: UUID, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Elimina un cliente (solo ADMINISTRADOR).
    """
    ClienteService.delete_cliente(db, cliente_id, current_user)
