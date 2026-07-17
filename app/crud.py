"""
crud.py

Business logic inti untuk POS: membuat order, memvalidasi & mengurangi
stok (termasuk expand komponen Paket / BOM), dan mencatat pembayaran.

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