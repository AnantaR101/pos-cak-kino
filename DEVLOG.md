# Development Log — POS System "Cak Kino"

This log tracks the progress, decisions, and reasoning behind this project. Unlike the README (which explains what the project *is*), this file explains what was *done* and *why*, in chronological order. New entries should be appended at the bottom.

---

## Phase 1 — Scope Definition

**What happened:**
Initial plan was to build a full multi-unit restaurant ERP system (menu, inventory, procurement, multi-branch). After evaluating time constraints and portfolio goals, the scope was deliberately reduced to a **standalone POS (cashier) system** for a single restaurant.

**Decision:** Build POS only, not a full ERP.

**Rationale:** A focused, fully-working POS system with solid data design demonstrates more relevant skill (for BA/BI/Strategy & Ops roles) than a half-finished multi-module ERP. Depth over breadth.

---

## Phase 2 — Tech Stack Selection

**Decision:** FastAPI + SQLAlchemy + PostgreSQL + Jinja2 + vanilla JS (not React/Node).

**Rationale:**
- Python-only stack keeps the project approachable while learning, and stays consistent with the data/analytics skills this portfolio is meant to showcase.
- FastAPI over Flask: built-in request validation (Pydantic) and auto-generated API docs (`/docs`), which is useful both for development and for later exposing endpoints to external tools (e.g. Power BI).
- Jinja2 over a JS framework: server-rendered HTML is simpler to reason about for a first full-stack project, and avoids unnecessary frontend complexity for a single-page cashier screen.

---

## Phase 3 — Initial Database Design

**What happened:**
Designed a normalized schema based on a generic restaurant POS: `users`, `menu_categories`, `menus`, `orders`, `order_details`, `payments`. Every ordered item stored as one row in `order_details` (no comma-separated fields), so that reporting (best sellers, revenue by category, etc.) would not require string parsing.

**Decision:** Fully normalized, one-item-per-row order structure from the start.

**Rationale:** This is the foundation that makes later analytics (SQL/Python/Power BI) possible without a costly ETL/reshaping step.

---

## Phase 4 — Grounding the Design in a Real Reference

**What happened:**
Received a photo of the restaurant's actual paper order ticket (nota). This revealed real-world complexity the generic design hadn't accounted for:
- Some items have two price points (Goreng / Bakar — fried vs. grilled)
- Free condiment ("sambal") selection with no price impact
- A "Paket" (bundle) category combining multiple items under one price
- Drinks tracked with a separate queue numbering on the original ticket

**Decision:** Redesign the schema around these real constraints rather than a generic template.

**Rationale:** Portfolio value comes from solving a real operational problem, not a textbook one. This also surfaced a requirement that wasn't in the original scope: inventory/stock tracking.

---

## Phase 5 — Stock Management & the Paket-as-Bill-of-Materials Decision

**What happened:**
Added requirement: track opening stock per item, deduct stock on every sale, and validate availability before checkout. The tricky part: a "Paket" (bundle) needed to deduct stock from its *component* items rather than have its own stock count.

**Decision:** Model bundles using a Bill-of-Materials (BOM) pattern — a `paket_components` table maps each bundle to its component menu items and quantities. Bundles themselves are never given a row in the `stock` table; selling a bundle triggers a deduction on each of its components. All stock changes (opening balance, sale, adjustment) are logged individually in `stock_movements` rather than only keeping a running total, to preserve a full audit trail for later analysis.

**Rationale:** This mirrors how bundled/composite products are handled in real inventory systems, and produces richer data for analytics (e.g. actual ingredient-level consumption) than a naive "bundle has its own stock" approach would.

---

## Phase 6 — Environment Setup

**What happened:**
Set up local development environment: Python, VS Code, PostgreSQL (via pgAdmin), virtual environment, and initial package installation (`fastapi`, `sqlalchemy`, `psycopg2-binary`, `python-dotenv`, `jinja2`, `alembic`).

**Issues encountered and resolved:**
- PostgreSQL password authentication failures — root cause was a mismatch between the assumed password and the actual server password; resolved by verifying credentials directly through pgAdmin and resetting via `ALTER USER`.
- Database name mismatch — the database had accidentally been created with a space in the name (`POS_Penyetan_Cak Kino`) instead of the intended underscore-separated name. Diagnosed by comparing `DATABASE_URL` against `pg_database` contents, then fixed with `ALTER DATABASE ... RENAME TO`.
- General lesson: when a connection succeeds but expected data doesn't appear, verify the exact database name/identity being used on both sides (application and admin tool) before assuming the data itself is missing.

---

## Phase 7 — ORM Models & First Migration

**What happened:**
Wrote `app/database.py` (engine/session setup) and `app/models.py` (SQLAlchemy models for all 11 tables). Verified the schema by generating tables directly in PostgreSQL and confirming their existence via query, then initialized Alembic for future migrations.

**Status:** Complete — models finalized, migration applied successfully, connection verified.

---

## Phase 8 — GitHub Repository & Documentation

**What happened:**
Created the GitHub repository, fixed `.gitignore` to exclude `venv/` and `.env`, and wrote a professional `README.md` covering background, design decisions, tech stack, schema, and setup instructions for other developers/reviewers.

---

## Phase 9 — Pricing Model Revision

**What happened:**
Originally, `price` lived directly on the `menus` table. After reviewing the real menu structure (Phase 4), this was revised: `menus.price` is now considered legacy/unused (kept only for backward compatibility, defaulted to 0), and **all pricing lives in `menu_variants`**. Items without real variants (e.g. plain rice, drinks) still get exactly one variant row named `Default`.

**Decision:** Single source of truth for price = `menu_variants`, with no exceptions.

**Rationale:** Having two possible places for price (`menus.price` vs `menu_variants.price`) creates ambiguity about which one an application should trust. Forcing every menu item — variant or not — through the same table removes that ambiguity and keeps downstream logic (checkout, reporting) simple and consistent.

---

## Phase 10 — Master Data Strategy: Excel over JSON/Hardcoding

**What happened:**
Decided how menu/category/price/stock master data should be maintained and fed into the database.

**Options considered:** hardcoded Python data structures, a JSON file, or an Excel workbook.

**Decision:** Excel workbook (`data/master_menu.xlsx`), read via `pandas`/`openpyxl` in a `seed.py` script.

**Rationale:** This project simulates a small independent restaurant (UMKM). A real owner in that context would far more plausibly maintain their menu in Excel than edit Python or JSON directly. It also fits the project owner's accounting background, where spreadsheet-based data maintenance is a familiar, realistic workflow.

**Workbook design decisions:**
- Every entity gets its own sheet (`Categories`, `Menus`, `Variants`, `Sambals`, `OpeningStock`, `PaketComponents`), mirroring the normalized database structure rather than one flat sheet.
- Explicit `*_code` columns (e.g. `menu_code`) are used as the key linking sheets together, instead of relying on menu names as text. Free-text names are easy to mistype or rename inconsistently across sheets, which would cause silent data loss when the sheets are joined in Python — the same reason relational databases use IDs instead of names as foreign keys.
- Added a `ReadMe` sheet explaining what each sheet is for and which cells are safe to edit, since this workbook is meant to be maintainable by a non-technical restaurant owner in the simulated scenario.
- `menus.price` is intentionally absent from the `Menus` sheet — consistent with the Phase 9 decision, price only exists in `Variants`.

**Status:** Workbook structure designed and drafted with example data transcribed from the real order ticket (photo). Bundle composition (`PaketComponents`) left as a labeled placeholder, pending confirmation of real recipe/composition data. Not yet connected to `seed.py`.

---

## Phase 11 — Base-Unit Pattern for Multi-Yield Items

**What happened:**
While finalizing `PaketComponents`, found a case the schema didn't cleanly support: "Lele isi 2" (catfish, sold as a pair) is sold as one product, but its stock must be tracked per individual fish, not per pair — and "Paket 2" also uses catfish as a component, at a different quantity than the pair-sized product.

**Decision:** Introduced a "base unit" pattern. Added a new regular menu item, `IKAN-LELE-PC` ("Lele per ekor"), which holds the actual physical stock and is never directly sellable/visible on the POS screen. `IKAN-LELE-2` ("Lele isi 2") was reclassified from `type=regular` to `type=paket`, defined as a bundle of 2x `IKAN-LELE-PC`. Both a direct sale of "Lele isi 2" and a sale via "Paket 2" (which now also references `IKAN-LELE-PC`) draw from the same underlying stock record.

**Rationale:** This reuses the existing bundle/BOM mechanism instead of introducing a separate "unit conversion" concept, keeping the data model consistent. It also generalizes to any other multi-yield item discovered later.

**Known follow-up (not yet implemented):** a `is_sellable` flag on `menus` will be needed so base units like `IKAN-LELE-PC` can be excluded from the POS menu grid without being excluded from the database. Logged as a pending schema change, deferred until the POS UI is being built.

---

## Phase 12 — `seed.py` Implementation & Debugging

**What happened:**
Implemented `seed.py` to read all six sheets of `master_menu.xlsx` via `pandas` and populate PostgreSQL in dependency order (Categories → Menus → Variants/Sambals → OpeningStock → PaketComponents), using a get-or-create pattern per row to keep the script idempotent (safe to re-run).

**Issues encountered and resolved:**
- **Stray rows read as data.** Explanatory note text had been placed directly beneath the data tables in the `OpeningStock` and `PaketComponents` sheets. `pandas.read_excel` read these (and the blank row separating them from real data) as additional rows, causing a `KeyError: nan` when the code tried to look up a blank menu code. Fixed by moving all explanatory notes to the dedicated `ReadMe` sheet, and by hardening `load_sheet()` to drop any row missing its key column, with a warning printed when rows are dropped.
- **Menu identity collision.** `seed_menus()` originally checked for an existing menu by `name` alone. Since cut names like "Dada", "Tepong", "Kepala", and "Ati" are reused across both the Ayam and Bebek categories, the second occurrence of each name was incorrectly treated as "already existing," silently reusing the first category's row instead of creating its own. This corrupted the `menu_code → id` mapping (e.g. `BEBEK-DADA` ended up pointing at `AYAM-DADA`'s database row) and surfaced later as a `UniqueViolation` when seeding `stock`, since two different Excel codes resolved to the same `menu_id`. Fixed by checking for an existing menu using the `(category_id, name)` pair instead of `name` alone. Affected data was cleared with `TRUNCATE ... RESTART IDENTITY CASCADE` and re-seeded from scratch after the fix.
- **General lesson:** a natural key that looks unique in isolation ("Dada" is a menu name) may not be unique once more data is loaded — the real key was the combination of category and name, not name by itself.

**Status:** `seed.py` runs cleanly end-to-end; all 8 categories, 38 menus, variants, sambals, and bundle components load correctly and the script can be safely re-run.

---

## Phase 13 — `crud.py`: Order Creation & Stock Validation

**What happened:**
Implemented the core checkout logic: `check_stock_availability()` and `create_order()`, plus a shared helper `_expand_to_stock_requirements()` that translates a cart (which may mix regular items and bundles) into stock requirements at the base-unit level.

**Key design points:**
- Stock requirements from all cart lines are aggregated (summed) *before* checking availability, so that two different cart lines drawing from the same underlying stock (e.g. buying both "Lele isi 2" and "Paket 2" in one order) are validated against their true combined usage, not checked independently.
- Validation runs completely before any database write. If any item is short, `InsufficientStockError` is raised (listing every shortfall, not just the first one found) and nothing is written.
- `order_details` always records what the customer actually purchased (e.g. one line for "Paket 2"), never the expanded component breakdown — the expansion exists only to drive stock deduction and is not part of the sales record.
- The whole operation (order header, order lines, payment, stock deduction, stock movement logging) is wrapped in a single try/except with an explicit rollback on any failure, guaranteeing atomicity.

**Testing performed (manually, via a standalone script):**
1. A simple order for a regular item — succeeded, correct total calculated, stock decremented correctly.
2. An order for a bundle (`type=paket`) item — correctly expanded to multiple component shortages when those components had no stock yet, confirming the expansion logic works before any deduction occurs.
3. After topping up the missing component stock, the same bundle order succeeded, and stock was correctly deducted across multiple component rows from a single order.
4. An order requesting far more than available stock was correctly rejected with a clear message and produced no database changes.

**Status:** Core order/stock logic verified working end-to-end, including the bundle (BOM) deduction path. Not yet exposed via any API — still only callable directly from Python.

---

## Phase 14 — API Layer: `schemas.py` and FastAPI Routers

**What happened:**
Built the HTTP-facing layer on top of `crud.py`: Pydantic request/response schemas (`schemas.py`), a `pos` router (`GET /api/menus`, `POST /api/checkout`), an `orders` router (`GET /api/orders`, `GET /api/orders/{id}`), and the FastAPI app entry point (`main.py`).

**Key design points:**
- Request/response shapes are kept separate from the SQLAlchemy models (`models.py`) on purpose — one describes database tables, the other describes what a client is allowed to send/receive over HTTP. Conflating the two would leak internal structure and make the API brittle to schema changes.
- Domain exceptions raised in `crud.py` (`InsufficientStockError`, `ValueError`) are caught at the router layer and translated into `HTTPException` with appropriate status codes. `crud.py` itself stays free of any HTTP-specific concepts, keeping the business logic reusable outside a web context (e.g. from a script, as already done in testing).
- `Depends(get_db)` provides a fresh database session per request, closed automatically afterward.

**Testing performed:** Verified via the auto-generated Swagger UI (`/docs`) — `GET /api/menus` returns the full category/menu/price tree, `POST /api/checkout` successfully creates orders, and an oversized quantity request correctly returns HTTP 400 with a descriptive message rather than crashing.

**Status:** Full backend flow (database → business logic → HTTP API) verified working end-to-end. No UI yet — all testing done through Swagger.

---

## Phase 15 — Cashier UI (Jinja2 Templates)

**What was built:**
- Server-rendered shell (`base.html`) + cashier page (`pos.html`), styled with a custom "nota warung" theme (`style.css`) — deep green header, chili-red accents, receipt-style cart panel with a torn-paper edge.
- `pos.js` handles all client-side state: fetching `/api/menus`, rendering category tabs + menu grid, a variant picker modal (Goreng/Bakar/etc), a sambal picker modal, cart state, and calling `POST /api/checkout`.

**Key decisions:**
- Menu data is rendered entirely client-side via `fetch`, not server-rendered with Jinja2 — keeps a single source of truth for how the cart/checkout flow works, consistent with the original design (`cart` is pure frontend state until checkout).
- Base-unit items (e.g. "Lele (per ekor - base unit...)") are filtered out of the cashier grid by a name-pattern stopgap in `isSellable()` — a real `is_sellable` column on `menus` is still a TODO from the original design discussion and should replace this before the UI is considered "real".

**Bugs hit & fixed:**
- `TemplateResponse("pos.html", {"request": request})` crashed with `TypeError: cannot use 'tuple' as a dict key` — a Jinja2/Starlette version incompatibility with the old calling convention. Fixed by switching to the newer signature: `templates.TemplateResponse(request, "pos.html")`.
- Two leftover `@app.get("/")` routes in `main.py` (one returning raw JSON, one rendering the template) meant the first-registered route always won — the JSON route had to be removed, not just reordered, and moved to `/api/status`.
- First working `/api/menus` render came back blank because the frontend assumed field names (`category`, `variant.name`) that didn't match the actual response (`name`, `variant_name`), and `price` is returned as a **string** ("18000.00") requiring `parseFloat()` before any math.

**Verified working end-to-end:** menu browsing → variant selection → sambal selection → cart → checkout → stock validation error surfaced correctly in the UI (tested with an item that had zero opening stock).

---

## Phase 16 — Order History + Nota Detail View

**What was built:**
- `GET /api/orders` — returns all orders, newest first, with cashier, payment, and full item-line detail embedded per order (not just header totals).
- `GET /api/orders/{id}` — single-order detail, same shape, for a dedicated receipt view.
- `/riwayat` page — list of past transactions rendered as expandable cards; clicking a card reveals a nota-style breakdown (menu, variant, sambal, quantity, subtotal) matching the physical receipt format the whole system is based on.
- **Void order**: `PATCH /api/orders/{id}/void` — cancels a completed order and reverses its stock impact. Reuses the same Paket → component expansion logic from `create_order()` in `crud.py`, so voiding a bundle correctly puts stock back on every component, not just the bundle line itself. Voided orders are marked `status = 'voided'`, not deleted — consistent with the "orders are never hard-deleted" principle from the original schema design.
- Every void is logged to `stock_movements` with `movement_type = 'void'`, keeping the audit trail complete alongside `opening` / `sale` / `adjustment`.

**Key decision:** void reverses stock rather than simply deleting the order, because the original transaction still needs to exist for reporting (e.g. "how many orders were voided today" is itself a useful metric) — this mirrors the earlier decision to never hard-delete orders.

---

## Phase 17 — Web-Based Stock Management (`/stok`)

**What was built:**
- `GET /api/stock` — current stock for every regular menu item, grouped by category for display.
- `PATCH /api/stock/{menu_id}` — apply a signed delta to stock (positive to restock, negative to correct a miscount) directly from the browser.
- `/stok` page — table grouped by category, inline quantity field + Save button per row.

**Key decision:** this replaces the Excel → `seed.py` round-trip for routine stock corrections. Excel/`master_menu.xlsx` remains the source of truth for *opening* stock and menu structure (categories, variants, bundles) — it is not meant to be re-edited for day-to-day stock corrections once the system is live. Every correction made through `/stok` is still logged as a `stock_movements` row with `movement_type = 'adjustment'`, so the audit trail stays intact regardless of whether stock changed via a sale, a void, or a manual fix.

---

## Phase 18 — Cart Quantity Controls

**What was built:** replaced the single "Hapus" (remove) action on each cart line with a `− qty +` stepper, plus a separate explicit "Hapus" for removing the line entirely.

**Bug fixed:** previously, "Hapus" removed the entire line regardless of quantity — ordering 3x of an item and clicking "Hapus" once wiped all 3, not 1. This wasn't a backend issue; the cart is pure frontend state until checkout, so the fix was entirely in `pos.js`'s cart-rendering logic.

---

## Phase 19 — Menu Name Ambiguity in the Cashier UI

**Context:** several menu names repeat across categories by design ("Dada" and "Tepong" exist under both Ayam and Bebek) — this was already handled correctly at the database level back in Phase 12 (composite key of category + name, not name alone). What remained was a **UI-level** ambiguity: the cart and nota could show "1x Dada" with no indication of which category it came from, which is confusing when both an Ayam-Dada and Bebek-Dada are in the same order.

**Fix:** cart lines and order/nota detail views now display the category alongside the menu name (e.g. "Dada (Ayam)") wherever a name collision is possible, rather than relying on the database-level uniqueness fix alone to prevent confusion for the person reading the receipt.

---

## Phase 20 — `is_sellable` as a Real Column (Retiring the Name-Pattern Stopgap)

**Context:** since Phase 15, "base unit" items (e.g. "Lele per ekor") were hidden from the cashier grid using a frontend name-pattern match (`isSellable()` checking for "base unit" in the name) — flagged at the time as a stopgap, not a real fix.

**What was built:**
- Alembic migration adding `is_sellable BOOLEAN NOT NULL DEFAULT true` to `menus`, with a one-time data fix in the same migration marking existing base-unit items (name matching "base unit" or "per ekor") as `false` — so the correction ships with the schema change itself rather than depending on a manual follow-up step.
- `seed.py` (`seed_menus()`) updated to read an `is_sellable` column ("Y"/"N") from the `Menus` sheet in `master_menu.xlsx`, using a `getattr(..., "Y")` fallback so the script doesn't break on an Excel file that hasn't been updated with the new column yet.
- Also fixed while in there: `is_active` previously only got set on first insert and was never re-synced on subsequent `seed.py` runs. Both `is_active` and `is_sellable` are now updated every run, so changing either flag in Excel and re-seeding actually takes effect.
- `GET /api/menus` now filters on the real `is_sellable` column; `isSellable()` in `pos.js` — the name-pattern check — is retired.

**Migration order matters here:** `alembic upgrade head` must run before `python seed.py` — the seed script assumes the `is_sellable` column already exists in the database.

---

## Documentation Update (Phase 16-20)

`README.md` updated: new endpoints (`/api/orders/{id}`, `/api/orders/{id}/void`, `/api/stock`, `PATCH /api/stock/{menu_id}`), updated project structure (`orders.py` / `stock.py` routers, `orders.html` / `stock.html` templates, `orders.js` / `stock.js`), updated roadmap reflecting Riwayat/Stok/void/`is_sellable` as done.

---

## Next Steps

- [ ] Cashier login / authentication (replace the plain-text test user — `password_hash = 'not_hashed_yet'` — with real password hashing once auth is addressed)
- [ ] End-to-end testing through the actual UI, not just Swagger/direct Python calls
- [ ] Sample SQL / Power BI reporting queries, connecting directly to PostgreSQL
- [ ] Push completed milestones to GitHub with updated documentation