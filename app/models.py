"""
Semua tabel database didefinisikan di sini sebagai class Python (ORM model).
Tiap class = 1 tabel. Tiap Column = 1 kolom. Tiap relationship() = koneksi
antar tabel biar gampang diakses dari kode (misal order.order_details).
"""

from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="cashier")  # cashier / admin

    orders = relationship("Order", back_populates="cashier")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)

    menus = relationship("Menu", back_populates="category")


class Menu(Base):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), default="regular")  # "regular" atau "paket"
    price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)

    category = relationship("MenuCategory", back_populates="menus")
    variants = relationship("MenuVariant", back_populates="menu")
    stock = relationship("Stock", back_populates="menu", uselist=False)

    # kalau menu ini type="paket", dia punya daftar komponen penyusun
    components = relationship(
        "PaketComponent",
        foreign_keys="PaketComponent.paket_menu_id",
        back_populates="paket_menu",
    )


class MenuVariant(Base):
    __tablename__ = "menu_variants"

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    variant_name = Column(String(30), nullable=False)  # "Goreng" / "Bakar"
    price = Column(Numeric(10, 2), nullable=False)

    menu = relationship("Menu", back_populates="variants")


class Sambal(Base):
    __tablename__ = "sambals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)


class Stock(Base):
    __tablename__ = "stock"

    # menu_id jadi primary key SEKALIGUS foreign key -> 1 menu = 1 baris stok
    menu_id = Column(Integer, ForeignKey("menus.id"), primary_key=True)
    current_qty = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    menu = relationship("Menu", back_populates="stock")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    movement_type = Column(String(20), nullable=False)  # "opening" / "sale" / "adjustment"
    quantity = Column(Integer, nullable=False)  # negatif = berkurang, positif = nambah
    reference_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaketComponent(Base):
    __tablename__ = "paket_components"

    id = Column(Integer, primary_key=True, index=True)
    paket_menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    component_menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    qty_per_paket = Column(Integer, nullable=False, default=1)

    paket_menu = relationship(
        "Menu", foreign_keys=[paket_menu_id], back_populates="components"
    )
    component_menu = relationship("Menu", foreign_keys=[component_menu_id])


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(30), unique=True, nullable=False)
    cashier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_time = Column(DateTime(timezone=True), server_default=func.now())
    customer_type = Column(String(20), nullable=False)  # "dine_in" / "take_away"
    grand_total = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), default="completed")  # "completed" / "voided"

    cashier = relationship("User", back_populates="orders")
    order_details = relationship("OrderDetail", back_populates="order")
    payment = relationship("Payment", back_populates="order", uselist=False)


class OrderDetail(Base):
    __tablename__ = "order_details"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("menu_variants.id"), nullable=True)
    sambal_id = Column(Integer, ForeignKey("sambals.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)  # snapshot harga saat transaksi
    subtotal = Column(Numeric(12, 2), nullable=False)

    order = relationship("Order", back_populates="order_details")
    menu = relationship("Menu")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    payment_method = Column(String(20), nullable=False)  # "cash" / "qris" / "transfer"
    amount_paid = Column(Numeric(12, 2), nullable=False)
    change_amount = Column(Numeric(12, 2), default=0)

    order = relationship("Order", back_populates="payment")
