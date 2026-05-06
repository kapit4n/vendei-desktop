from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import InventoryLot, Product


@dataclass(frozen=True)
class StockDao:
    session_factory: sessionmaker

    def reduce_stock_fefo(self, product_id: int, quantity: float) -> None:
        """Reduce stock and, if track_expiry, consume lots first (best-effort FEFO)."""
        with self.session_factory() as s:
            p = s.get(Product, product_id)
            if not p:
                raise ValueError("Product not found")
            q = max(0.0, float(quantity))
            if q <= 0:
                return

            cur = float(p.stock or 0.0)
            to_reduce = min(q, cur)
            if to_reduce <= 0:
                return

            if bool(p.track_expiry):
                lots = list(
                    s.execute(
                        select(InventoryLot)
                        .where(InventoryLot.product_id == product_id)
                        .where(InventoryLot.quantity > 0)
                        .order_by(InventoryLot.expiry_date.asc().nullsfirst(), InventoryLot.id.asc())
                    )
                    .scalars()
                    .all()
                )
                rem = to_reduce
                for lot in lots:
                    if rem <= 0:
                        break
                    lot_q = float(lot.quantity or 0.0)
                    d = min(lot_q, rem)
                    rem -= d
                    next_q = lot_q - d
                    if next_q <= 0:
                        s.delete(lot)
                    else:
                        lot.quantity = next_q

            p.stock = max(0.0, cur - to_reduce)
            s.commit()

