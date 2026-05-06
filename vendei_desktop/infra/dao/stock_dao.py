from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import InventoryLot, Product, ProductOffering


@dataclass(frozen=True)
class StockDao:
    session_factory: sessionmaker

    @staticmethod
    def _sync_product_aggregate_stock(session, product_id: int) -> None:
        p = session.get(Product, int(product_id))
        if not p:
            return
        n_offer = int(
            session.execute(
                select(func.count()).select_from(ProductOffering).where(ProductOffering.product_id == int(product_id))
            ).scalar_one()
            or 0
        )
        if n_offer <= 0:
            return
        total = float(
            session.execute(
                select(func.coalesce(func.sum(ProductOffering.stock), 0.0)).where(
                    ProductOffering.product_id == int(product_id)
                )
            ).scalar_one()
            or 0.0
        )
        p.stock = total

    def list_lots(self, product_id: int, *, product_offering_id: int | None = None) -> list[InventoryLot]:
        with self.session_factory() as s:
            q = (
                select(InventoryLot)
                .where(InventoryLot.product_id == product_id)
                .order_by(InventoryLot.expiry_date.asc().nullsfirst(), InventoryLot.id.asc())
            )
            if product_offering_id is not None:
                q = q.where(InventoryLot.product_offering_id == int(product_offering_id))
            return list(s.execute(q).scalars().all())

    def add_stock(
        self,
        *,
        product_id: int,
        quantity: float,
        product_offering_id: int | None = None,
        expiry_date: date | None = None,
        batch_code: str | None = None,
    ) -> None:
        with self.session_factory() as s:
            p = s.get(Product, product_id)
            if not p:
                raise ValueError("Product not found")
            q = float(quantity)
            if q <= 0:
                raise ValueError("Quantity must be > 0")

            n_offer = int(
                s.execute(
                    select(func.count())
                    .select_from(ProductOffering)
                    .where(ProductOffering.product_id == int(product_id))
                ).scalar_one()
                or 0
            )

            offering: ProductOffering | None = None
            if product_offering_id is not None:
                offering = s.get(ProductOffering, int(product_offering_id))
                if not offering or int(offering.product_id) != int(product_id):
                    raise ValueError("Invalid product offering for this product")

            if n_offer > 0 and offering is None:
                raise ValueError("Select a brand and unit of measure (product offering) for inventory.")

            batch_clean = (batch_code.strip() or None) if batch_code is not None else None
            wants_lot = (expiry_date is not None) or (batch_clean is not None)
            if wants_lot and not bool(p.track_expiry):
                p.track_expiry = True

            if offering is not None:
                offering.stock = float(offering.stock or 0.0) + q
            else:
                p.stock = float(p.stock or 0.0) + q

            if bool(p.track_expiry):
                oid = int(offering.id) if offering is not None else None
                s.add(
                    InventoryLot(
                        product_id=product_id,
                        product_offering_id=oid,
                        quantity=q,
                        expiry_date=expiry_date,
                        batch_code=batch_clean,
                    )
                )
            self._sync_product_aggregate_stock(s, product_id)
            s.commit()

    def reduce_stock_fefo(
        self, product_id: int, quantity: float, *, product_offering_id: int | None = None
    ) -> None:
        """Reduce stock; when product_offering_id is set, only that offering (and its lots)."""
        with self.session_factory() as s:
            p = s.get(Product, product_id)
            if not p:
                raise ValueError("Product not found")
            q = max(0.0, float(quantity))
            if q <= 0:
                return

            n_offer = int(
                s.execute(
                    select(func.count())
                    .select_from(ProductOffering)
                    .where(ProductOffering.product_id == int(product_id))
                ).scalar_one()
                or 0
            )

            offering: ProductOffering | None = None
            if product_offering_id is not None:
                offering = s.get(ProductOffering, int(product_offering_id))
                if not offering or int(offering.product_id) != int(product_id):
                    raise ValueError("Invalid product offering for this product")

            if n_offer > 0 and offering is None:
                raise ValueError("Missing product offering for stock reduction.")

            if offering is not None:
                cur = float(offering.stock or 0.0)
            else:
                cur = float(p.stock or 0.0)
            to_reduce = min(q, cur)
            if to_reduce <= 0:
                return

            if bool(p.track_expiry):
                lot_q = (
                    select(InventoryLot)
                    .where(InventoryLot.product_id == product_id)
                    .where(InventoryLot.quantity > 0)
                    .order_by(InventoryLot.expiry_date.asc().nullsfirst(), InventoryLot.id.asc())
                )
                if offering is not None:
                    lot_q = lot_q.where(InventoryLot.product_offering_id == int(offering.id))
                lots = list(s.execute(lot_q).scalars().all())
                rem = to_reduce
                for lot in lots:
                    if rem <= 0:
                        break
                    lot_qty = float(lot.quantity or 0.0)
                    d = min(lot_qty, rem)
                    rem -= d
                    next_q = lot_qty - d
                    if next_q <= 0:
                        s.delete(lot)
                    else:
                        lot.quantity = next_q

            if offering is not None:
                offering.stock = max(0.0, cur - to_reduce)
            else:
                p.stock = max(0.0, cur - to_reduce)

            self._sync_product_aggregate_stock(s, product_id)
            s.commit()
