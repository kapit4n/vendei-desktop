from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import OrderLine, Product, ProductOffering, UnitOfMeasure


@dataclass(frozen=True)
class UnitDao:
    session_factory: sessionmaker

    def list_units(self) -> list[UnitOfMeasure]:
        with self.session_factory() as s:
            return list(s.execute(select(UnitOfMeasure).order_by(UnitOfMeasure.name.asc())).scalars().all())

    def create_unit(self, *, name: str, abbreviation: str | None = None) -> UnitOfMeasure:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("Unit name is required")
        if len(nm) > 80:
            raise ValueError("Name is too long (max 80).")
        ab = (abbreviation or "").strip() or None
        if ab and len(ab) > 16:
            raise ValueError("Abbreviation is too long (max 16).")
        with self.session_factory() as s:
            exists = s.execute(select(UnitOfMeasure).where(UnitOfMeasure.name == nm)).scalars().first()
            if exists:
                raise ValueError(f'Unit of measure "{nm}" already exists.')
            u = UnitOfMeasure(name=nm, abbreviation=ab)
            s.add(u)
            s.commit()
            s.refresh(u)
            return u

    def delete_unit(self, unit_id: int) -> None:
        with self.session_factory() as s:
            u = s.get(UnitOfMeasure, int(unit_id))
            if not u:
                raise ValueError("Unit not found.")
            if s.query(Product).filter(Product.default_unit_of_measure_id == int(unit_id)).first():
                raise ValueError("This unit is set as default on one or more products.")
            if s.query(ProductOffering).filter(ProductOffering.unit_of_measure_id == int(unit_id)).first():
                raise ValueError("This unit is used in product offerings.")
            if s.query(OrderLine).filter(OrderLine.unit_of_measure_id == int(unit_id)).first():
                raise ValueError("This unit is referenced on past order lines.")
            s.delete(u)
            s.commit()
