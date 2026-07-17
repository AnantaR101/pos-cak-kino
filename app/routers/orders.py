"""
routers/orders.py

Endpoint untuk melihat riwayat transaksi & detail 1 order (dipakai untuk
tampilan nota di halaman /riwayat).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order
from app.schemas import OrderOut
from app.crud import serialize_order, void_order

router = APIRouter(prefix="/api", tags=["orders"])


@router.get("/orders", response_model=List[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    """Daftar semua order, terbaru duluan, lengkap dengan nama item (untuk nota)."""
    orders = db.query(Order).order_by(Order.id.desc()).all()
    return [serialize_order(o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Detail 1 order, termasuk item-itemnya -- bentuk siap tampil sebagai nota."""
    order = db.query(Order).filter_by(id=order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    return serialize_order(order)


@router.patch("/orders/{order_id}/void", response_model=OrderOut)
def void_order_endpoint(order_id: int, db: Session = Depends(get_db)):
    """
    Batalkan order: status -> 'voided', stok dikembalikan (lihat crud.void_order).

    - 400: order tidak ditemukan, atau sudah pernah dibatalkan sebelumnya.
    """
    try:
        order = void_order(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return serialize_order(order)