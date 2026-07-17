"""
routers/stock.py

Endpoint untuk melihat & mengoreksi stok langsung dari web, tanpa harus
edit master_menu.xlsx + re-run seed.py setiap kali ada koreksi stok
harian (lihat DEVLOG Phase 10 -- Excel tetap dipakai untuk data master
awal/opening stock, endpoint ini untuk operasional harian: restock,
koreksi selisih, dsb).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Menu, Stock
from app.schemas import StockOut, StockAdjustmentIn
from app.crud import adjust_stock, StockAdjustmentError

router = APIRouter(prefix="/api", tags=["stock"])


def _to_stock_out(menu: Menu, stock: Stock | None) -> StockOut:
    return StockOut(
        menu_id=menu.id,
        menu_name=menu.name,
        category_name=menu.category.name if menu.category else "-",
        current_qty=stock.current_qty if stock else 0,
        updated_at=stock.updated_at if stock else None,
    )


@router.get("/stock", response_model=List[StockOut])
def list_stock(db: Session = Depends(get_db)):
    """
    Stok semua menu reguler (base unit), termasuk item base-unit
    "tersembunyi" seperti IKAN-LELE-PC (lihat Phase 11) -- item itu justru
    yang paling butuh dikoreksi manual di sini. Menu bertipe 'paket' tidak
    punya baris stok sendiri (Phase 5) jadi tidak muncul di daftar ini.
    """
    menus = (
        db.query(Menu)
        .filter(Menu.type == "regular")
        .order_by(Menu.category_id, Menu.name)
        .all()
    )
    result = []
    for menu in menus:
        stock = db.query(Stock).filter_by(menu_id=menu.id).first()
        result.append(_to_stock_out(menu, stock))
    return result


@router.patch("/stock/{menu_id}", response_model=StockOut)
def adjust_stock_endpoint(menu_id: int, payload: StockAdjustmentIn, db: Session = Depends(get_db)):
    """
    Koreksi stok manual. payload.delta positif = nambah, negatif = mengurangi.

    - 400: menu tidak ditemukan, menu-nya Paket (tidak punya stok sendiri),
      atau koreksi akan membuat stok jadi negatif.
    """
    try:
        stock = adjust_stock(db, menu_id=menu_id, delta=payload.delta)
    except (StockAdjustmentError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    menu = db.query(Menu).filter_by(id=menu_id).first()
    return _to_stock_out(menu, stock)