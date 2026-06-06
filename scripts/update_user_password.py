from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.usuario import Usuario


def main() -> None:
    correo = "herlin@gmail.com"
    nueva_contrasena = "Herlin.1"

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.correo == correo).first()
        if usuario is None:
            raise SystemExit(f"No se encontró usuario con correo {correo}")

        usuario.contrasena_hash = get_password_hash(nueva_contrasena)
        db.commit()
        print(f"Contraseña actualizada para {correo}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
