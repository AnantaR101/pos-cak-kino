from app.database import engine, Base
import app.models

# Cek DULU sebelum create_all - ada berapa tabel yang "dikenali" Python?
print("Tabel yang terdaftar di Base.metadata:", list(Base.metadata.tables.keys()))

Base.metadata.create_all(bind=engine)
print("✅ create_all() dijalankan")