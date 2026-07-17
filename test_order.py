from decimal import Decimal
from app.database import SessionLocal
from app.crud import create_order, CartItem, InsufficientStockError

db = SessionLocal()

try:
    order = create_order(
        db,
        cashier_id=1,  # sesuaikan dengan id user yang ada di tabel users
        customer_type="dine_in",
        payment_method="cash",
        amount_paid=Decimal("50000"),
        items=[
            CartItem(menu_id=34, quantity=2),   # ganti id sesuai menu di database lo
        ],
    )
    print(f"✅ Order berhasil: {order.invoice_number}, total: {order.grand_total}")
except InsufficientStockError as e:
    print(f"❌ Stok tidak cukup:\n{e}")
finally:
    db.close()
