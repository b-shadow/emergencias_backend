from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller
from app.core.database import SessionLocal
from app.models.taller import Taller
from app.models.taller_subscription import TallerSubscription


def main() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        approved = db.query(Taller).filter(Taller.estado_aprobacion == EstadoAprobacionTaller.APROBADO).all()

        suspended = 0
        ok = 0
        for taller in approved:
            active = (
                db.query(TallerSubscription)
                .filter(
                    TallerSubscription.id_taller == taller.id_taller,
                    TallerSubscription.estado == "ACTIVA",
                    TallerSubscription.fecha_inicio <= now,
                    TallerSubscription.fecha_fin >= now,
                )
                .first()
            )
            if active:
                ok += 1
                continue

            taller.estado_operativo = EstadoOperativoTaller.SUSPENDIDO
            suspended += 1

        db.commit()
        print(f"OK: talleres aprobados con plan activo={ok}, suspendidos sin plan={suspended}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
