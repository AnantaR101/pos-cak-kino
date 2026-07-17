"""
main.py

Entry point aplikasi FastAPI. Menyatukan semua router jadi 1 aplikasi.
Jalankan dengan: uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.routers import pos, orders

app = FastAPI(title="POS Cak Kino")

app.include_router(pos.router)
app.include_router(orders.router)


@app.get("/")
def root():
    return {"message": "POS Cak Kino API is running. Visit /docs for interactive API documentation."}