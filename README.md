# Vendei Desktop (PySide6)

Desktop POS app inspired by `ng-vendei-full`, built with:

- **PySide6** (Qt) UI
- **SQLite** database (single file)
- **SQLAlchemy** ORM
- Clean-ish architecture: **DAO / Services (use-cases) / ViewModels / Views**

## Quick start

Create a venv and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
python -m vendei_desktop
```

Database file is created at `./data/vendei.sqlite` on first run.

## Structure

- `vendei_desktop/domain/` — entities + domain services
- `vendei_desktop/infra/` — SQLAlchemy engine/session, ORM models, DAOs
- `vendei_desktop/app/` — use-cases (services), controllers, view-models
- `vendei_desktop/ui/` — PySide6 views/widgets

## Current feature coverage (MVP)

- Catalog list with search
- Quick add by product code (Enter)
- Ticket lines + total
- Customer picker dialog
- Submit order (persists order + lines) and reduces stock (FEFO lots when `track_expiry=True`)

Next steps to reach parity with `ng-vendei-full`:

- Category chips + manage screens (CRUD)
- Payment methods + partial payments/discount/change lines
- Printing
- Reports screens

