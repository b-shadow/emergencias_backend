from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.enums import EstadoAprobacionTaller
from app.core.database import SessionLocal
from app.models.taller import Taller
from app.models.subscription_plan import SubscriptionPlan
from app.models.taller_subscription import TallerSubscription


def main() -> None:
    db = SessionLocal()
    try:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.codigo_plan == "BRONCE").first()
        if not plan:
            raise RuntimeError("No existe el plan BRONCE. Ejecuta primero seed_subscription_plans.py")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        fecha_fin = now + timedelta(days=plan.duracion_dias)

        approved = (
            db.query(Taller)
            .filter(Taller.estado_aprobacion == EstadoAprobacionTaller.APROBADO)
            .all()
        )

        created = 0
        skipped = 0
        for taller in approved:
            active = (
                db.query(TallerSubscription)
                .filter(
                    TallerSubscription.id_taller == taller.id_taller,
                    TallerSubscription.estado == "ACTIVA",
                    TallerSubscription.fecha_fin >= now,
                )
                .first()
            )
            if active:
                skipped += 1
                continue

            db.add(
                TallerSubscription(
                    id_taller=taller.id_taller,
                    id_plan=plan.id_plan,
                    estado="ACTIVA",
                    fecha_inicio=now,
                    fecha_fin=fecha_fin,
                )
            )
            created += 1

        db.commit()
        print(f"OK: membresias BRONCE creadas={created}, omitidas={skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
