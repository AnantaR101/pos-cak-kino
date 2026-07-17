"""
routers/pos.py

Endpoint yang dipakai layar kasir: ambil daftar menu, dan proses checkout.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MenuCategory
from app.schemas import CheckoutRequest, OrderOut, MenuCategoryOut
from app.crud import create_order, CartItem, InsufficientStockError

router = APIRouter(prefix="/api", tags=["pos"])


@router.get("/menus", response_model=List[MenuCategoryOut])
def get_menus(db: Session = Depends(get_db)):
    """
    Menu grid untuk layar kasir, dikelompokkan per kategori
    (urutan sesuai sort_order yang ditentukan di master data).
    """
    return db.query(MenuCategory).order_by(MenuCategory.id).all()


@router.post("/checkout", response_model=OrderOut)
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    """
    Proses transaksi: validasi stok, buat order, catat pembayaran,
    dan potong stok (termasuk expand komponen Paket).

    - 400: stok tidak cukup, atau data yang dikirim tidak valid
          (menu/variant tidak ditemukan, dsb)
    """
    cart_items = [
        CartItem(
            menu_id=item.menu_id,
            quantity=item.quantity,
            variant_id=item.variant_id,
            sambal_id=item.sambal_id,
        )
        for item in payload.items
    ]

    try:
        order = create_order(
            db,
            cashier_id=payload.cashier_id,
            customer_type=payload.customer_type,
            payment_method=payload.payment_method,
            amount_paid=payload.amount_paid,
            items=cart_items,
        )
        return order

    except InsufficientStockError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))