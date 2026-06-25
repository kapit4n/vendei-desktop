# Vendei Desktop — Project Rules

## Overview
Desktop POS app built with **PySide6** (Qt), **SQLite**, **SQLAlchemy 2.0 ORM**, **Pydantic**.
Packaged under `vendei_desktop/`, run via `python -m vendei_desktop`.

## Architecture (layered, dependencies point inward)

```
ui/  →  app/viewmodels/  →  app/services/  →  infra/dao/  →  infra/db/  →  SQLite
```

| Layer | Dir | Responsibility |
|-------|-----|----------------|
| **UI** | `ui/` | PySide6 widgets, dialogs, `ui/main.py` (single file, ~2200 lines) |
| **App** | `app/viewmodels/` | ViewModel holds mutable state (`PosState`), mediates UI ↔ Service |
| **App** | `app/services/` | Orchestrator (`PosService`) with business rules, receives DAOs via constructor |
| **Infra** | `infra/dao/` | 7 DAOs (`BrandDao`, `CatalogDao`, `CustomerDao`, `OrderDao`, `PurchaseRequestDao`, `StockDao`, `UnitDao`) |
| **Infra** | `infra/db/` | SQLAlchemy engine, `DeclarativeBase`, 10 ORM models, schema+migrations+seeds |

## Key Patterns

- **DAO**: frozen dataclass with `session_factory: sessionmaker`. Each method opens its own session, commits, returns ORM models.
- **Service**: `PosService` receives all DAOs via constructor injection (no DI framework).
- **ViewModel**: `PosViewModel` holds mutable `PosState` dataclass. Handles line merging, payment validation.
- **DI Container**: `build_container()` factory in `app/container.py` → returns `AppContainer` frozen dataclass.
- **Value Objects**: frozen dataclasses (`TicketLine`, `ProductListing`, `PosState`, `SalesRow`, `DbConfig`).

## Conventions

- **Imports**: absolute from `vendei_desktop.*` (except within `infra/db/` which uses relative).
- **`from __future__ import annotations`** at top of every `.py` file.
- **Type hints**: full PEP 484 everywhere; PEP 604 union syntax (`str | None`).
- **Keyword-only args**: `def method(*, param: str) -> None:` for all non-trivial methods.
- **Naming**: `snake_case` for modules/functions/vars, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- **No ABCs/protocols** — layers couple through concrete classes.
- **No async** — fully synchronous. SQLite WAL mode for concurrency.
- **No custom exceptions** — `ValueError` for business rule violations, caught at UI layer as `QMessageBox`.
- **Validation**: input validation in DAOs (length, uniqueness, existence) + services (business rules) + UI (basic).
- **Session-per-call**: each DAO method opens/closes its own session. No shared/request-scoped sessions.
- **Database**: `data/vendei.sqlite` created on first run. Schema migrations in `bootstrap.py`.
- **Seeding**: `seed_if_empty()` in bootstrap — idempotent, runs only when tables are empty.

## ORM Models (10 tables)

units_of_measure, brands, categories, products, product_offerings, inventory_lots, customers, orders, order_lines, purchase_requests, purchase_request_items

Key relationships: products → (category, default_unit_of_measure), product_offerings → (product, brand, unit_of_measure), inventory_lots → (product, product_offering), orders → (customer, brand, lines cascade delete), purchase_requests → items

## Testing
Run tests with: `python -m pytest` (if pytest configured) or `python -m unittest discover`.

## Commands
- Run: `python -m vendei_desktop`
- Install: `pip install -r requirements.txt`
- Venv: `.venv/` at project root
