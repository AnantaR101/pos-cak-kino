# POS System — Penyetan Sedap Malam Cak Kino

A point-of-sale (POS) system built for real project as my current role as Business Operations and Strategy Advisor at Cak Kino Group, designed to replace manual, paper-based order tracking with a structured, database-driven workflow that also supports inventory deduction and future business intelligence reporting.

> **Status:** Work in progress — database design and architecture finalized, implementation in progress. This README will be updated as features are completed.

## Background

The restaurant currently records every order on a paper ticket (see `docs/original-order-ticket.png`). At closing time, staff manually tally revenue, best-selling items, and remaining stock. This process is slow, error-prone, and produces no reusable data for analysis.

This project digitizes that exact paper workflow into a relational database and a lightweight web-based cashier application, while preserving the real menu structure of the restaurant — including priced variants (fried vs. grilled), free condiment choices, and bundled combo items.

The goal is not just a working cashier app, but a system where every transaction becomes structured data that can later be analyzed for sales trends, best sellers, and inventory consumption using SQL, Python, or BI tools.

## Key Design Decisions

- **Variant pricing** — items such as chicken and duck have two price points (fried / grilled) under the same menu entry, modeled as a separate `menu_variants` table rather than duplicate menu items.
- **Free modifiers** — condiment (sambal) choice does not affect price and is tracked separately for future preference analysis.
- **Bundle items (Paket) as a Bill of Materials** — a "Paket" is not a standalone stocked item. It is defined as a set of component menu items with quantities (`paket_components`), so selling one Paket automatically deducts stock from each of its components rather than requiring separate inventory tracking for every bundle.
- **Auditable stock movements** — every stock change (opening balance, sale, manual adjustment) is logged as an individual row in `stock_movements`, rather than only keeping a running total, to preserve history for later analysis (e.g. peak consumption hours, stockout frequency).
- **Price snapshotting** — the unit price at the time of sale is stored directly on the order line (`order_details.unit_price`), so historical reports remain accurate even if menu prices change later.
- **Atomic checkout** — placing an order (order header, order lines, payment, and stock deduction) happens inside a single database transaction. If stock validation fails for any item, the entire order is rejected rather than partially processed.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Migrations | Alembic |
| Frontend | Jinja2 templates, HTML/CSS, vanilla JavaScript |
| Reporting (planned) | Power BI / Tableau, connected directly to PostgreSQL |

## Database Schema

The schema is normalized to keep every ordered item as an individual record (no comma-separated fields), which is what makes downstream reporting possible.

**Core tables:**
- `menu_categories` — menu groupings (Rice, Chicken, Duck, Fish, Skewers, Bundles, Extras, Drinks)
- `menus` — individual menu items, including a `type` flag distinguishing regular items from bundles
- `menu_variants` — priced variants of a menu item (e.g. fried vs. grilled)
- `sambals` — condiment options
- `stock` — current stock level per regular menu item
- `stock_movements` — full audit log of stock changes
- `paket_components` — bundle-to-component mapping with quantities
- `orders` — order header (invoice number, cashier, totals, status)
- `order_details` — individual order lines
- `payments` — payment record per order
- `users` — cashier/admin accounts

Full entity-relationship diagram: see `docs/erd.png` *(add this once exported from the design tool)*.

## Project Structure

```
pos-cak-kino/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLAlchemy engine & session setup
│   ├── models.py             # ORM models
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── crud.py                # Business logic (stock validation, order creation)
│   ├── routers/
│   │   ├── pos.py             # POS screen + checkout endpoints
│   │   └── orders.py          # Order history endpoints
│   ├── templates/            # Jinja2 HTML templates
│   └── static/                # CSS / JS assets
├── docs/                      # ERD, original paper ticket reference, notes
├── requirements.txt
└── .env.example
```

## Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 18+
- Git

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/<AnantaR101>/pos-cak-kino.git
cd pos-cak-kino

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# then edit .env with your local PostgreSQL credentials

# 5. Create the database (in psql or pgAdmin)
createdb pos_cak_kino

# 6. Run migrations
alembic upgrade head

# 7. Seed initial menu data (optional)
python seed.py

# 8. Run the application
uvicorn app.main:app --reload
```

The app will be available at `http://127.0.0.1:8000`, with interactive API docs at `http://127.0.0.1:8000/docs`.

## Roadmap

- [x] Business requirements gathering (based on real restaurant paper ticket)
- [x] Database schema design, including stock and bundle-deduction logic
- [ ] SQLAlchemy models + Alembic migrations
- [ ] Seed data script
- [ ] Core order/stock transaction logic
- [ ] FastAPI endpoints
- [ ] Cashier UI (Jinja2 + JS)
- [ ] End-to-end testing
- [ ] Sample SQL/Power BI reporting queries

## Author

Built as a real portfolio project to demonstrate database design, business logic modeling, and full-stack development skills, with a focus on translating a real operational process into a structured software system.
