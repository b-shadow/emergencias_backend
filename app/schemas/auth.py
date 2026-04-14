from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str
    client_type: Literal["mobile", "web"] = "web"  # mobile para Cliente, web para Taller/Admin


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    rol: str  # CLIENTE, TALLER, ADMINISTRADOR
    id_usuario: str  # UUID como string
    nombre_completo: str


class LogoutResponse(BaseModel):
    mensaje: str
    estado: str = "logout_exitoso"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    correo: EmailStr


class ForgotPasswordResponse(BaseModel):
    mensaje: str
    nota: str


class ResetPasswordRequest(BaseModel):
    token: str
    nueva_contrasena: str
    confirmar_contrasena: str

    @field_validator("nueva_contrasena")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        """Valida que la contraseña tenga al menos 8 caracteres y contenga números y letras"""
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        if not any(c.isalpha() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra")
        return v

    def validar_coincidencia_contrasena(self) -> None:
        """Valida que las contraseñas coincidan"""
        if self.nueva_contrasena != self.confirmar_contrasena:
            raise ValueError("Las contraseñas no coinciden")


class ResetPasswordResponse(BaseModel):
    mensaje: str
    estado: str = "contrasena_actualizada"


class ClienteRegisterRequest(BaseModel):
    correo: EmailStr
    contrasena: str
    confirmar_contrasena: str
    nombre: str
    apellido: str
    telefono: str | None = None
    ci: str | None = None
    direccion: str | None = None

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        """Valida que la contraseña tenga al menos 8 caracteres y contenga números y letras"""
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        if not any(c.isalpha() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra")
        return v

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        """Valida que el nombre no esté vacío"""
        if not v or not v.strip():
            raise ValueError("El nombre es obligatorio")
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v.strip()

    @field_validator("apellido")
    @classmethod
    def validar_apellido(cls, v: str) -> str:
        """Valida que el apellido no esté vacío"""
        if not v or not v.strip():
            raise ValueError("El apellido es obligatorio")
        if len(v) < 2:
            raise ValueError("El apellido debe tener al menos 2 caracteres")
        return v.strip()

    def validar_coincidencia_contrasena(self) -> None:
        """Valida que las contraseñas coincidan"""
        if self.contrasena != self.confirmar_contrasena:
            raise ValueError("Las contraseñas no coinciden")


class TallerRegisterRequest(BaseModel):
    correo: EmailStr
    contrasena: str
    confirmar_contrasena: str
    nombre_taller: str
    razon_social: str | None = None
    nit: str | None = None
    telefono: str
    direccion: str
    latitud: float | None = None
    longitud: float | None = None
    descripcion: str | None = None

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        """Valida que la contraseña tenga al menos 8 caracteres y contenga números y letras"""
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        if not any(c.isalpha() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra")
        return v

    @field_validator("nombre_taller")
    @classmethod
    def validar_nombre_taller(cls, v: str) -> str:
        """Valida que el nombre no esté vacío"""
        if not v or not v.strip():
            raise ValueError("El nombre del taller es obligatorio")
        if len(v) < 3:
            raise ValueError("El nombre debe tener al menos 3 caracteres")
        return v.strip()

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: str) -> str:
        """Valida que el teléfono tenga formato válido"""
        if not v or not v.strip():
            raise ValueError("El teléfono es obligatorio")
        if len(v) < 7:
            raise ValueError("El teléfono debe tener al menos 7 caracteres")
        return v.strip()

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, v: str) -> str:
        """Valida que la dirección no esté vacía"""
        if not v or not v.strip():
            raise ValueError("La dirección es obligatoria")
        if len(v) < 5:
            raise ValueError("La dirección debe tener al menos 5 caracteres")
        return v.strip()

    def validar_coincidencia_contrasena(self) -> None:
        """Valida que las contraseñas coincidan"""
        if self.contrasena != self.confirmar_contrasena:
            raise ValueError("Las contraseñas no coinciden")
