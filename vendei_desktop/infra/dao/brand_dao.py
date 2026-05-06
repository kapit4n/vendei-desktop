from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import Brand, Order, ProductOffering


@dataclass(frozen=True)
class BrandDao:
    session_factory: sessionmaker

    def list_brands(self) -> list[Brand]:
        with self.session_factory() as s:
            return list(s.execute(select(Brand).order_by(Brand.name.asc())).scalars().all())

    def create_brand(self, *, name: str, code: str | None = None) -> Brand:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("Brand name is required")
        if len(nm) > 120:
            raise ValueError("Name is too long (max 120).")
        cd = (code or "").strip() or None
        if cd and len(cd) > 32:
            raise ValueError("Code is too long (max 32).")
        with self.session_factory() as s:
            if s.execute(select(Brand).where(Brand.name == nm)).scalars().first():
                raise ValueError(f'Brand "{nm}" already exists.')
            b = Brand(name=nm, code=cd)
            s.add(b)
            s.commit()
            s.refresh(b)
            return b

    def delete_brand(self, brand_id: int) -> None:
        with self.session_factory() as s:
            b = s.get(Brand, int(brand_id))
            if not b:
                raise ValueError("Brand not found.")
            if s.query(Order).filter(Order.brand_id == int(brand_id)).first():
                raise ValueError("This brand has orders; it cannot be deleted.")
            if s.query(ProductOffering).filter(ProductOffering.brand_id == int(brand_id)).first():
                raise ValueError("This brand has product offerings; remove them first.")
            s.delete(b)
            s.commit()
