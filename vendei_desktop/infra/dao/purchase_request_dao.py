from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload, sessionmaker

from vendei_desktop.infra.db.models import PurchaseRequest, PurchaseRequestItem


@dataclass(frozen=True)
class PurchaseRequestDao:
    session_factory: sessionmaker

    def get_open(self) -> PurchaseRequest:
        with self.session_factory() as s:
            pr = (
                s.execute(
                    select(PurchaseRequest)
                    .where(PurchaseRequest.status == "open")
                    .options(joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.product))
                    .order_by(PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc())
                )
                .unique()
                .scalars()
                .first()
            )
            if pr:
                return pr
            pr = PurchaseRequest(created_at=datetime.utcnow(), status="open", notes=None)
            s.add(pr)
            s.commit()
            s.refresh(pr)
            return pr

    def set_item(self, *, request_id: int, product_id: int, quantity: float) -> None:
        q = float(quantity)
        if q <= 0:
            raise ValueError("Quantity must be > 0")
        with self.session_factory() as s:
            item = (
                s.execute(
                    select(PurchaseRequestItem)
                    .where(PurchaseRequestItem.request_id == int(request_id))
                    .where(PurchaseRequestItem.product_id == int(product_id))
                )
                .scalars()
                .first()
            )
            if item:
                item.quantity = q
            else:
                s.add(PurchaseRequestItem(request_id=int(request_id), product_id=int(product_id), quantity=q))
            s.commit()

    def remove_item(self, *, request_id: int, product_id: int) -> None:
        with self.session_factory() as s:
            item = (
                s.execute(
                    select(PurchaseRequestItem)
                    .where(PurchaseRequestItem.request_id == int(request_id))
                    .where(PurchaseRequestItem.product_id == int(product_id))
                )
                .scalars()
                .first()
            )
            if not item:
                return
            s.delete(item)
            s.commit()

    def get_open_with_items(self) -> PurchaseRequest:
        with self.session_factory() as s:
            pr = (
                s.execute(
                    select(PurchaseRequest)
                    .where(PurchaseRequest.status == "open")
                    .options(joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.product))
                    .order_by(PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc())
                )
                .unique()
                .scalars()
                .first()
            )
            if pr:
                return pr
        # fallback: create outside the read session
        return self.get_open()
