from app.database import SessionLocal
from app.models import MenuCategory


def seed_categories(db):
    categories = [
        "Nasi",
        "Ayam",
        "Bebek",
        "Ikan",
        "Tusukan",
        "Paket",
        "Tambahan",
        "Minuman",
    ]

    for name in categories:
        exists = db.query(MenuCategory).filter_by(name=name).first()

        if not exists:
            db.add(MenuCategory(name=name))

    db.commit()


def main():
    db = SessionLocal()

    try:
        seed_categories(db)
        print("✅ Categories seeded successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    main()