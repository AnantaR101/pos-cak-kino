"""
schemas.py

Pydantic models untuk validasi data yang masuk (request) dan bentuk data
yang keluar (response) lewat API. Terpisah dari models.py (SQLAlchemy,
representasi tabel database) karena tujuannya beda: ini soal bentuk JSON
di HTTP, bukan soal struktur tabel.
"""

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
    variants: List[MenuVariantOut] = []


class MenuCategoryOut(BaseModel):
    """Dipakai untuk GET /api/menus -- 1 kategori berisi daftar menunya."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    menus: List[MenuOut] = []


class OrderDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_id: int
    variant_id: Optional[int]
    sambal_id: Optional[int]
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderOut(BaseModel):
    """Dipakai sebagai response setelah checkout berhasil, dan untuk riwayat order."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    customer_type: str
    grand_total: Decimal
    status: str
    order_details: List[OrderDetailOut] = []