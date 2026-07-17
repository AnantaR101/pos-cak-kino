"""
routers/orders.py

Endpoint untuk melihat riwayat transaksi.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order
from app.schemas import OrderOut

router = APIRouter(prefix="/api", tags=["orders"])


@router.get("/orders", response_model=List[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    """Daftar semua order, terbaru duluan."""
    return db.query(Order).order_by(Order.id.desc()).all()


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Detail 1 order, termasuk item-itemnya."""
    order = db.query(Order).filter_by(id=order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    return order