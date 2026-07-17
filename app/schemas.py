"""
schemas.py

Pydantic models untuk validasi data yang masuk (request) dan bentuk data
yang keluar (response) lewat API. Terpisah dari models.py (SQLAlchemy,
representasi tabel database) karena tujuannya beda: ini soal bentuk JSON
di HTTP, bukan soal struktur tabel.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# REQUEST SCHEMAS - bentuk data yang dikirim client ke server
# ============================================================

class CartItemIn(BaseModel):
    """Satu baris item di keranjang, dikirim dari layar kasir saat checkout."""
    menu_id: int
    quantity: int = Field(gt=0, description="Jumlah item, harus lebih dari 0")
    variant_id: Optional[int] = None
    sambal_id: Optional[int] = None


class CheckoutRequest(BaseModel):
    """Body request untuk POST /api/checkout."""
    cashier_id: int
    customer_type: str  # "dine_in" / "take_away"
    payment_method: str  # "cash" / "qris" / "transfer"
    amount_paid: Decimal
    items: List[CartItemIn]


class StockAdjustmentIn(BaseModel):
    """
    Body request untuk PATCH /api/stock/{menu_id}.
    delta positif = nambah stok (restock), negatif = mengurangi (koreksi
    selisih, rusak, dsb). Bukan "set ke angka X" -- ini supaya tetap
    konsisten dengan pola stock_movements sebagai log auditable (Phase 5),
    bukan cuma nimpa angka current_qty tanpa jejak.
    """
    delta: int = Field(..., description="Positif = nambah stok, negatif = mengurangi")


# ============================================================
# RESPONSE SCHEMAS - bentuk data yang dikirim server ke client
# ============================================================

class MenuVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_name: str
    price: Decimal


class MenuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    is_active: bool
    is_sellable: bool
    variants: List[MenuVariantOut] = []


class MenuCategoryOut(BaseModel):
    """Dipakai untuk GET /api/menus -- 1 kategori berisi daftar menunya."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    menus: List[MenuOut] = []


class OrderDetailOut(BaseModel):
    """
    Satu baris item di riwayat order / nota. Menyertakan nama menu,
    kategori, varian, dan sambal (bukan cuma ID) karena tampilan nota
    dan riwayat order butuh nama yang bisa langsung ditampilkan --
    lihat crud.serialize_order() untuk cara field ini diisi.
    category_name dipakai buat membedakan menu yang namanya sama persis
    di kategori berbeda, misalnya "Dada" (Ayam) vs "Dada" (Bebek).
    """
    menu_id: int
    menu_name: str
    category_name: str
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    sambal_id: Optional[int] = None
    sambal_name: Optional[str] = None
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class PaymentOut(BaseModel):
    payment_method: str
    amount_paid: Decimal
    change_amount: Decimal


class OrderOut(BaseModel):
    """Dipakai sebagai response setelah checkout berhasil, dan untuk riwayat order/nota."""
    id: int
    invoice_number: str
    order_time: datetime
    cashier_name: str
    customer_type: str
    grand_total: Decimal
    status: str
    order_details: List[OrderDetailOut] = []
    payment: Optional[PaymentOut] = None


class StockOut(BaseModel):
    menu_id: int
    menu_name: str
    category_name: str
    current_qty: int
    updated_at: Optional[datetime] = None