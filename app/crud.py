"""
crud.py

Business logic inti untuk POS: membuat order, memvalidasi & mengurangi
stok (termasuk expand komponen Paket / BOM), mencatat pembayaran, koreksi
stok manual dari web, dan menyusun representasi order yang siap ditampilkan
sebagai nota / riwayat transaksi.

Semua proses checkout dibungkus dalam SATU transaction: kalau ada satu
langkah gagal (termasuk stok kurang), semuanya dibatalkan -- tidak ada
kondisi order tercatat tapi stok tidak terpotong, atau sebaliknya.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Menu, MenuVariant, Stock, StockMovement, PaketComponent,
    Order, OrderDetail, Payment,
)


@dataclass
class CartItem:
    """Representasi 1 baris di keranjang belanja kasir."""
    menu_id: int
    quantity: int
    variant_id: Optional[int] = None
    sambal_id: Optional[int] = None


class InsufficientStockError(Exception):
    """Dilempar kalau stok tidak cukup untuk memenuhi 1 atau lebih item di cart."""
    pass


class StockAdjustmentError(Exception):
    """Dilempar kalau koreksi stok manual (mis. dari halaman /stok) tidak valid."""
    pass


def _expand_to_stock_requirements(db: Session, items: list[CartItem]) -> dict[int, int]:
    """
    Mengubah isi cart jadi kebutuhan stok per menu REGULER (base unit).

    - Item type='regular' -> kebutuhannya = quantity langsung.
    - Item type='paket'   -> di-'expand' lewat paket_components, kebutuhan
      tiap komponen = qty_per_paket x quantity paket yang dibeli.

    Kalau beberapa baris cart butuh menu reguler yang sama (misal 'Lele isi 2'
    dan 'Paket 2' dibeli sekaligus, dua-duanya butuh IKAN-LELE-PC), kebutuhannya
    DIJUMLAHKAN di sini -- bukan dicek satu-satu terpisah.
    """
    requirements: dict[int, int] = defaultdict(int)

    for item in items:
        menu = db.query(Menu).filter_by(id=item.menu_id).first()
        if menu is None:
            raise ValueError(f"Menu id {item.menu_id} tidak ditemukan")

        if menu.type == "regular":
            requirements[menu.id] += item.quantity

        elif menu.type == "paket":
            components = db.query(PaketComponent).filter_by(paket_menu_id=menu.id).all()
            if not components:
                raise ValueError(f"Paket '{menu.name}' belum punya komponen terdaftar")
            for comp in components:
                requirements[comp.component_menu_id] += comp.qty_per_paket * item.quantity

        else:
            raise ValueError(f"Tipe menu tidak dikenal: {menu.type}")

    return requirements


def check_stock_availability(db: Session, items: list[CartItem]) -> None:
    """
    Cek semua kebutuhan stok SEBELUM ada satupun perubahan ditulis ke database.
    Raise InsufficientStockError (menyebutkan menu mana saja yang kurang) kalau
    ada yang tidak cukup -- caller (create_order) tidak akan lanjut insert apapun.
    """
    requirements = _expand_to_stock_requirements(db, items)

    shortages = []
    for menu_id, needed_qty in requirements.items():
        stock = db.query(Stock).filter_by(menu_id=menu_id).first()
        available = stock.current_qty if stock else 0
        if available < needed_qty:
            menu = db.query(Menu).filter_by(id=menu_id).first()
            shortages.append(f"{menu.name}: butuh {needed_qty}, stok tersedia {available}")

    if shortages:
        raise InsufficientStockError("Stok tidak cukup:\n" + "\n".join(shortages))


def _generate_invoice_number(db: Session) -> str:
    """Format: INV-YYYYMMDD-XXXX, XXXX = urutan transaksi hari ini."""
    today = date.today()
    prefix = f"INV-{today.strftime('%Y%m%d')}-"
    count_today = db.query(Order).filter(Order.invoice_number.like(f"{prefix}%")).count()
    return f"{prefix}{count_today + 1:04d}"


def _get_unit_price(db: Session, menu_id: int, variant_id: Optional[int]) -> Decimal:
    """Ambil harga dari MenuVariant -- satu-satunya sumber harga (lihat DEVLOG Phase 9)."""
    if variant_id is None:
        # menu tanpa pilihan varian tetap wajib punya 1 baris 'Default' di MenuVariant
        variant = db.query(MenuVariant).filter_by(menu_id=menu_id).first()
    else:
        variant = db.query(MenuVariant).filter_by(id=variant_id, menu_id=menu_id).first()

    if variant is None:
        raise ValueError(f"Variant untuk menu id {menu_id} tidak ditemukan")
    return Decimal(str(variant.price))


def create_order(
    db: Session,
    cashier_id: int,
    customer_type: str,
    payment_method: str,
    amount_paid: Decimal,
    items: list[CartItem],
) -> Order:
    """
    Membuat 1 order lengkap dalam SATU transaction:
      1. Validasi stok (semua item sekaligus, all-or-nothing)
      2. Insert Order + OrderDetail (apa adanya -- paket tetap 1 baris,
         TIDAK dipecah jadi komponennya di sini; order_details mencatat
         apa yang dibeli customer, bukan apa yang dipakai dari gudang)
      3. Insert Payment
      4. Deduct stock + catat StockMovement di level base unit (hasil
         _expand_to_stock_requirements)

    Kalau ada error di tengah jalan, semuanya di-rollback.
    """
    check_stock_availability(db, items)  # lempar exception kalau kurang, SEBELUM nulis apapun

    try:
        order = Order(
            invoice_number=_generate_invoice_number(db),
            cashier_id=cashier_id,
            customer_type=customer_type,
            grand_total=Decimal("0"),
            status="completed",
        )
        db.add(order)
        db.flush()  # supaya order.id ke-generate, dipakai order_details & stock_movements

        grand_total = Decimal("0")
        for item in items:
            unit_price = _get_unit_price(db, item.menu_id, item.variant_id)
            subtotal = unit_price * item.quantity
            grand_total += subtotal

            db.add(OrderDetail(
                order_id=order.id,
                menu_id=item.menu_id,
                variant_id=item.variant_id,
                sambal_id=item.sambal_id,
                quantity=item.quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            ))

        order.grand_total = grand_total

        db.add(Payment(
            order_id=order.id,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change_amount=amount_paid - grand_total,
        ))

        # deduct stock di level base unit / menu reguler (hasil expand Paket)
        requirements = _expand_to_stock_requirements(db, items)
        for menu_id, qty_needed in requirements.items():
            stock = db.query(Stock).filter_by(menu_id=menu_id).first()
            stock.current_qty -= qty_needed

            db.add(StockMovement(
                menu_id=menu_id,
                movement_type="sale",
                quantity=-qty_needed,
                reference_order_id=order.id,
            ))

        db.commit()
        db.refresh(order)
        return order

    except Exception:
        db.rollback()
        raise


def adjust_stock(db: Session, menu_id: int, delta: int) -> Stock:
    """
    Koreksi stok manual dari halaman /stok, tanpa lewat Excel + seed.py.
    delta positif = nambah (restock), negatif = mengurangi (koreksi selisih,
    rusak/expired, dsb). Tetap dicatat sebagai StockMovement type='adjustment'
    supaya jejak auditnya konsisten dengan pola di Phase 5 devlog -- bukan
    cuma nimpa angka current_qty.

    Menu bertipe 'paket' sengaja ditolak di sini: bundle tidak punya baris
    stok sendiri (lihat Phase 5), jadi stoknya harus dikoreksi lewat
    komponen penyusunnya masing-masing, bukan lewat menu paket-nya.
    """
    menu = db.query(Menu).filter_by(id=menu_id).first()
    if menu is None:
        raise ValueError(f"Menu id {menu_id} tidak ditemukan")
    if menu.type != "regular":
        raise ValueError(
            f"'{menu.name}' adalah Paket -- stoknya diatur lewat komponen penyusunnya, bukan langsung"
        )

    stock = db.query(Stock).filter_by(menu_id=menu_id).first()
    if stock is None:
        stock = Stock(menu_id=menu_id, current_qty=0)
        db.add(stock)
        db.flush()

    new_qty = stock.current_qty + delta
    if new_qty < 0:
        raise StockAdjustmentError(
            f"Stok '{menu.name}' tidak bisa dikurangi jadi negatif "
            f"(saat ini {stock.current_qty}, diminta {delta:+d})"
        )

    try:
        stock.current_qty = new_qty
        db.add(StockMovement(
            menu_id=menu_id,
            movement_type="adjustment",
            quantity=delta,
        ))
        db.commit()
        db.refresh(stock)
        return stock
    except Exception:
        db.rollback()
        raise


def void_order(db: Session, order_id: int) -> Order:
    """
    Membatalkan sebuah order: menandai status jadi 'voided' dan MENGEMBALIKAN
    stok yang sebelumnya dipotong saat checkout -- termasuk expand komponen
    Paket, memakai helper (_expand_to_stock_requirements) yang SAMA PERSIS
    dengan yang dipakai create_order, supaya jumlah yang dikembalikan akurat
    walaupun ordernya campuran item reguler dan bundle.

    Setiap komponen yang dikembalikan dicatat sebagai StockMovement
    type='void' (quantity positif), mereferensikan order yang sama --
    konsisten dengan pola audit-trail di Phase 5 devlog.

    Order yang statusnya sudah 'voided' tidak bisa dibatalkan lagi kedua kalinya.
    """
    order = db.query(Order).filter_by(id=order_id).first()
    if order is None:
        raise ValueError(f"Order id {order_id} tidak ditemukan")
    if order.status == "voided":
        raise ValueError(f"Order {order.invoice_number} sudah dibatalkan sebelumnya")

    cart_items = [
        CartItem(
            menu_id=d.menu_id,
            quantity=d.quantity,
            variant_id=d.variant_id,
            sambal_id=d.sambal_id,
        )
        for d in order.order_details
    ]

    try:
        requirements = _expand_to_stock_requirements(db, cart_items)
        for menu_id, qty_to_restore in requirements.items():
            stock = db.query(Stock).filter_by(menu_id=menu_id).first()
            if stock is None:
                # Kasus langka: stok item ini sempat dihapus manual setelah
                # order dibuat. Buat barisnya lagi daripada gagal void.
                stock = Stock(menu_id=menu_id, current_qty=0)
                db.add(stock)
                db.flush()
            stock.current_qty += qty_to_restore

            db.add(StockMovement(
                menu_id=menu_id,
                movement_type="void",
                quantity=qty_to_restore,
                reference_order_id=order.id,
            ))

        order.status = "voided"
        db.commit()
        db.refresh(order)
        return order

    except Exception:
        db.rollback()
        raise


def serialize_order(order: Order) -> dict:
    """
    Menyusun 1 Order (beserta relasinya) jadi dict yang cocok dengan
    schemas.OrderOut -- dipakai bareng oleh POST /api/checkout dan
    GET /api/orders(/id), supaya nota di layar kasir dan di halaman
    riwayat selalu menampilkan data yang sama persis.

    OrderOut butuh nama (menu/kategori/varian/sambal/kasir), bukan cuma
    ID, jadi tidak bisa diserialisasi otomatis dari objek ORM -- harus
    ditelusuri manual lewat relationship di models.py.
    """
    return {
        "id": order.id,
        "invoice_number": order.invoice_number,
        "order_time": order.order_time,
        "cashier_name": order.cashier.full_name if order.cashier else "-",
        "customer_type": order.customer_type,
        "grand_total": order.grand_total,
        "status": order.status,
        "order_details": [
            {
                "menu_id": d.menu_id,
                "menu_name": d.menu.name if d.menu else "-",
                "category_name": (d.menu.category.name if d.menu and d.menu.category else "-"),
                "variant_id": d.variant_id,
                "variant_name": d.variant.variant_name if d.variant else None,
                "sambal_id": d.sambal_id,
                "sambal_name": d.sambal.name if d.sambal else None,
                "quantity": d.quantity,
                "unit_price": d.unit_price,
                "subtotal": d.subtotal,
            }
            for d in order.order_details
        ],
        "payment": (
            {
                "payment_method": order.payment.payment_method,
                "amount_paid": order.payment.amount_paid,
                "change_amount": order.payment.change_amount,
            }
            if order.payment
            else None
        ),
    }