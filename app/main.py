"""
main.py

Entry point aplikasi FastAPI. Menyatukan semua router jadi 1 aplikasi.
Jalankan dengan: uvicorn app.main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import pos, orders, stock

app = FastAPI(title="POS Cak Kino")

app.include_router(pos.router)
app.include_router(orders.router)
app.include_router(stock.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/")
def read_pos(request: Request):
    return templates.TemplateResponse(request, "pos.html")


@app.get("/riwayat")
def read_orders(request: Request):
    return templates.TemplateResponse(request, "orders.html")


@app.get("/stok")
def read_stock(request: Request):
    return templates.TemplateResponse(request, "stock.html")


@app.get("/api/status")
def api_status():
    return {"message": "POS Cak Kino API is running. Visit /docs for interactive API documentation."}