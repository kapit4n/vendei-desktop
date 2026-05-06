from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.models import Category, Product


@dataclass(frozen=True)
class CatalogDao:
    session_factory: sessionmaker

    def list_categories(self) -> list[Category]:
        with self.session_factory() as s:
            return list(s.execute(select(Category).order_by(Category.name.asc())).scalars().all())

    def list_products(
        self,
        *,
        query: str | None = None,
        category_id: int | None = None,
        only_visible: bool = True,
        limit: int = 500,
    ) -> list[Product]:
        q = select(Product).order_by(Product.name.asc()).limit(limit)
        if only_visible:
            q = q.where(Product.visible.is_(True))
        if category_id is not None:
            q = q.where(Product.category_id == category_id)
        if query:
            like = f"%{query.strip()}%"
            q = q.where((Product.name.ilike(like)) | (Product.code.ilike(like)))
        with self.session_factory() as s:
            return list(s.execute(q).scalars().all())

    def get_product_by_code(self, code: str) -> Product | None:
        with self.session_factory() as s:
            return s.execute(select(Product).where(Product.code == code.strip())).scalars().first()

