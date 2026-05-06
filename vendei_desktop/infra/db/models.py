from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    abbreviation: Mapped[str | None] = mapped_column(String(16), nullable=True)

    products_default: Mapped[list["Product"]] = relationship(back_populates="default_unit_of_measure")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stock: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    track_expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_selled: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quantity_selled: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    category: Mapped[Category | None] = relationship(back_populates="products")

    default_unit_of_measure_id: Mapped[int | None] = mapped_column(
        ForeignKey("units_of_measure.id"), nullable=True, index=True
    )
    default_unit_of_measure: Mapped[UnitOfMeasure | None] = relationship(
        back_populates="products_default", foreign_keys=[default_unit_of_measure_id]
    )

    lots: Mapped[list["InventoryLot"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    offerings: Mapped[list["ProductOffering"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductOffering(Base):
    __tablename__ = "product_offerings"
    __table_args__ = (
        UniqueConstraint("product_id", "brand_id", "unit_of_measure_id", name="uq_product_brand_uom"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False, index=True)
    unit_of_measure_id: Mapped[int] = mapped_column(ForeignKey("units_of_measure.id"), nullable=False, index=True)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stock: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    product: Mapped["Product"] = relationship(back_populates="offerings")
    brand: Mapped["Brand"] = relationship()
    unit_of_measure: Mapped["UnitOfMeasure"] = relationship()


class InventoryLot(Base):
    __tablename__ = "inventory_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    product_offering_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_offerings.id"), nullable=True, index=True
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    batch_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    product: Mapped[Product] = relationship(back_populates="lots")
    product_offering: Mapped["ProductOffering | None"] = relationship()


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    document: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    customer: Mapped[Customer | None] = relationship()
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    brand: Mapped["Brand | None"] = relationship()
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # CASH | QR (matches JavaFX vendei-desktop-javafx)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False, default="CASH")
    amount_received: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_given: Mapped[float | None] = mapped_column(Float, nullable=True)

    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    line_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit_of_measure_id: Mapped[int | None] = mapped_column(
        ForeignKey("units_of_measure.id"), nullable=True, index=True
    )
    product_offering_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_offerings.id"), nullable=True, index=True
    )
    unit_of_measure: Mapped[UnitOfMeasure | None] = relationship()
    product_offering: Mapped["ProductOffering | None"] = relationship()

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")  # open/closed
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    items: Mapped[list["PurchaseRequestItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class PurchaseRequestItem(Base):
    __tablename__ = "purchase_request_items"
    __table_args__ = (UniqueConstraint("request_id", "product_id", name="uq_request_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    request: Mapped[PurchaseRequest] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
