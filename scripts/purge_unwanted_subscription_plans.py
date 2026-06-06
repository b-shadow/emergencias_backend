from __future__ import annotations

from app.core.database import SessionLocal
from app.models.subscription_plan import SubscriptionPlan
from app.models.workshop_checkout import WorkshopCheckout
from app.models.taller_subscription import TallerSubscription


KEEP_CODES = {"BRONCE", "PLATA", "ORO", "DIAMANTE"}


def main() -> None:
    db = SessionLocal()
    try:
        plans = db.query(SubscriptionPlan).all()
        to_delete = [p for p in plans if (p.codigo_plan or "").upper() not in KEEP_CODES]

        if not to_delete:
            print("No hay planes sobrantes para eliminar.")
            return

        deleted_plans = 0
        deleted_checkouts = 0
        deleted_memberships = 0

        for plan in to_delete:
            checkouts = db.query(WorkshopCheckout).filter(WorkshopCheckout.id_plan == plan.id_plan).all()
            for c in checkouts:
                db.delete(c)
                deleted_checkouts += 1

            memberships = db.query(TallerSubscription).filter(TallerSubscription.id_plan == plan.id_plan).all()
            for m in memberships:
                db.delete(m)
                deleted_memberships += 1

            db.delete(plan)
            deleted_plans += 1
            print(f"Eliminado plan: {plan.codigo_plan} - {plan.nombre_plan}")

        db.commit()
        print(
            f"OK: planes eliminados={deleted_plans}, "
            f"checkouts eliminados={deleted_checkouts}, "
            f"membresias eliminadas={deleted_memberships}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
