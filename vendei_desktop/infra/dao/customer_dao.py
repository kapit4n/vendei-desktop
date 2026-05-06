from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import Customer


@dataclass(frozen=True)
class CustomerDao:
    session_factory: sessionmaker

    def list_customers(self, query: str | None = None, limit: int = 100) -> list[Customer]:
        q = select(Customer).order_by(Customer.name.asc()).limit(limit)
        if query:
            like = f"%{query.strip()}%"
            q = q.where((Customer.name.ilike(like)) | (Customer.document.ilike(like)))
        with self.session_factory() as s:
            return list(s.execute(q).scalars().all())

    def get_anonymous(self) -> Customer:
        with self.session_factory() as s:
            c = s.execute(select(Customer).where(Customer.name == "Anonymous")).scalars().first()
            if c:
                return c
            c = Customer(name="Anonymous", document=None)
            s.add(c)
            s.commit()
            s.refresh(c)
            return c

    def create_customer(self, *, name: str, document: str | None) -> Customer:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("Customer name is required")
        doc = (document or "").strip() or None
        with self.session_factory() as s:
            c = Customer(name=nm, document=doc)
            s.add(c)
            s.commit()
            s.refresh(c)
            return c

