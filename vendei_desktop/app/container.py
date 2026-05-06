from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from vendei_desktop.infra.db.bootstrap import create_schema, seed_if_empty
from vendei_desktop.infra.db.engine import DbConfig, create_session_factory, create_sqlite_engine
from vendei_desktop.infra.dao.catalog_dao import CatalogDao
from vendei_desktop.infra.dao.customer_dao import CustomerDao
from vendei_desktop.infra.dao.order_dao import OrderDao
from vendei_desktop.infra.dao.purchase_request_dao import PurchaseRequestDao
from vendei_desktop.infra.dao.stock_dao import StockDao

from .services.pos_service import PosService


@dataclass(frozen=True)
class AppContainer:
    session_factory: sessionmaker
    catalog_dao: CatalogDao
    customer_dao: CustomerDao
    stock_dao: StockDao
    order_dao: OrderDao
    purchase_request_dao: PurchaseRequestDao
    pos_service: PosService


def build_container() -> AppContainer:
    cfg = DbConfig.default()
    engine = create_sqlite_engine(cfg)
    create_schema(engine)
    session_factory = create_session_factory(engine)

    # seed
    with session_factory() as s:
        seed_if_empty(s)

    catalog_dao = CatalogDao(session_factory)
    customer_dao = CustomerDao(session_factory)
    stock_dao = StockDao(session_factory)
    order_dao = OrderDao(session_factory)
    purchase_request_dao = PurchaseRequestDao(session_factory)
    pos_service = PosService(catalog_dao, customer_dao, stock_dao, order_dao, purchase_request_dao)

    return AppContainer(
        session_factory=session_factory,
        catalog_dao=catalog_dao,
        customer_dao=customer_dao,
        stock_dao=stock_dao,
        order_dao=order_dao,
        purchase_request_dao=purchase_request_dao,
        pos_service=pos_service,
    )

