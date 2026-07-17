"""
seed.py

Membaca data master (kategori, menu, harga, sambal, stok awal, komposisi paket)
dari data/master_menu.xlsx, lalu memasukkannya ke PostgreSQL.

Script ini IDEMPOTENT: aman dijalankan berkali-kali. Kalau data sudah ada
(dicek berdasarkan nama), tidak akan membuat duplikat -- hanya diperbarui.

Cara jalanin:
    python seed.py
"""

import pandas as pd
from app.database import SessionLocal
from app.models import MenuCategory, Menu, MenuVariant, Sambal, Stock, PaketComponent

EXCEL_PATH = "data/master_menu.xlsx"


def load_sheet(sheet_name: str, key_column: str) -> pd.DataFrame:
    """
    Baca satu sheet Excel jadi DataFrame, lalu buang baris yang
    'key_column'-nya kosong (baris blank atau baris catatan yang
    kebaca ikut karena ada di kolom yang sama dengan data).

    key_column = nama kolom yang WAJIB ada isinya di setiap baris data asli
    (misal 'menu_code'). Baris yang kolom ini kosong dianggap bukan data.
    """
    df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name)
    before = len(df)
    df = df.dropna(subset=[key_column])
    dropped = before - len(df)
    if dropped:
        print(f"⚠️  Sheet '{sheet_name}': {dropped} baris kosong/catatan di-skip")
    return df


def seed_categories(db, df: pd.DataFrame) -> dict:
    """
    Insert semua kategori. Return dict {category_code: id_di_database},
    dipakai sheet lain buat 'nerjemahin' kode jadi id.
    """
    code_to_id = {}
    for row in df.itertuples():
        existing = db.query(MenuCategory).filter_by(name=row.category_name).first()
        if existing:
            code_to_id[row.category_code] = existing.id
            continue

        category = MenuCategory(name=row.category_name)
        db.add(category)
        db.flush()  # supaya category.id langsung ke-generate, tanpa commit dulu
        code_to_id[row.category_code] = category.id

    db.commit()
    print(f"✅ Categories ready: {len(code_to_id)}")
    return code_to_id


def seed_menus(db, df: pd.DataFrame, category_map: dict) -> dict:
    """
    Insert semua menu. Return dict {menu_code: id_di_database}.

    Membaca kolom 'is_sellable' ('Y'/'N') dari sheet Menus, sama polanya
    dengan 'is_active' -- dipakai buat nandain item base-unit (mis.
    IKAN-LELE-PC) yang tidak boleh muncul di grid kasir tapi tetap butuh
    baris stok sendiri (lihat DEVLOG Phase 11 & Phase 15).

    Kolom ini opsional: kalau sheet Excel-mu belum di-update dan belum
    punya kolom 'is_sellable', semua menu dianggap 'Y' (default lama,
    sebelum flag ini ada) -- supaya seed.py tidak langsung error di
    workbook lama. Tambahkan kolomnya di Excel begitu sempat.
    """
    code_to_id = {}
    for row in df.itertuples():
        category_id = category_map[row.category_code]
        is_active = (row.is_active == "Y")
        # getattr dengan fallback "Y", bukan row.is_sellable langsung,
        # supaya workbook lama yang belum punya kolom ini tetap jalan.
        is_sellable = (getattr(row, "is_sellable", "Y") == "Y")

        # PENTING: cek "sudah ada" berdasarkan (category_id, name), BUKAN
        # name saja -- karena nama seperti "Dada"/"Tepong"/"Kepala" dipakai
        # ulang di kategori Ayam maupun Bebek. Kalau cuma cek name, dua menu
        # yang beda kategori tapi nama sama bakal ketuker jadi 1 baris.
        existing = db.query(Menu).filter_by(
            category_id=category_id, name=row.menu_name
        ).first()
        if existing:
            # Sinkronkan flag dari Excel kalau berubah (mis. item yang tadinya
            # tersembunyi mau ditampilkan lagi, atau sebaliknya).
            existing.is_active = is_active
            existing.is_sellable = is_sellable
            code_to_id[row.menu_code] = existing.id
            continue

        menu = Menu(
            category_id=category_id,
            name=row.menu_name,
            type=row.type,
            price=0,  # legacy, harga asli ada di MenuVariant
            is_active=is_active,
            is_sellable=is_sellable,
        )
        db.add(menu)
        db.flush()
        code_to_id[row.menu_code] = menu.id

    db.commit()
    print(f"✅ Menus ready: {len(code_to_id)}")
    return code_to_id


def seed_variants(db, df: pd.DataFrame, menu_map: dict) -> None:
    """Insert harga tiap menu. Menu tanpa varian tetap punya 1 baris 'Default'."""
    added = 0
    for row in df.itertuples():
        menu_id = menu_map[row.menu_code]
        existing = db.query(MenuVariant).filter_by(
            menu_id=menu_id, variant_name=row.variant_name
        ).first()
        if existing:
            existing.price = row.price  # update harga kalau berubah
            continue

        db.add(MenuVariant(menu_id=menu_id, variant_name=row.variant_name, price=row.price))
        added += 1

    db.commit()
    print(f"✅ Variants added: {added}")


def seed_sambals(db, df: pd.DataFrame) -> None:
    added = 0
    for row in df.itertuples():
        existing = db.query(Sambal).filter_by(name=row.sambal_name).first()
        if existing:
            continue
        db.add(Sambal(name=row.sambal_name))
        added += 1

    db.commit()
    print(f"✅ Sambals added: {added}")


def seed_opening_stock(db, df: pd.DataFrame, menu_map: dict, menu_types: dict) -> None:
    """
    Insert stok awal. Item type='paket' SENGAJA di-skip -- paket tidak
    boleh punya stok sendiri, stoknya nurun dari komponennya.
    """
    added = 0
    for row in df.itertuples():
        if menu_types.get(row.menu_code) == "paket":
            print(f"⚠️  Skip {row.menu_code}: type=paket tidak boleh punya stok sendiri")
            continue

        menu_id = menu_map[row.menu_code]
        existing = db.query(Stock).filter_by(menu_id=menu_id).first()
        if existing:
            existing.current_qty = row.opening_qty
            continue

        db.add(Stock(menu_id=menu_id, current_qty=row.opening_qty))
        added += 1

    db.commit()
    print(f"✅ Stock entries added: {added}")


def seed_paket_components(db, df: pd.DataFrame, menu_map: dict, menu_types: dict) -> None:
    """
    Insert komposisi paket. Akan berhenti dengan error kalau ada komponen
    yang ternyata paket lain (paket-di-dalam-paket tidak didukung).
    """
    added = 0
    for row in df.itertuples():
        if menu_types.get(row.component_menu_code) == "paket":
            raise ValueError(
                f"{row.paket_code}: komponen '{row.component_menu_code}' adalah "
                "paket lain. Paket-di-dalam-paket tidak didukung -- cek ulang "
                "sheet PaketComponents di Excel."
            )

        paket_id = menu_map[row.paket_code]
        component_id = menu_map[row.component_menu_code]

        existing = db.query(PaketComponent).filter_by(
            paket_menu_id=paket_id, component_menu_id=component_id
        ).first()
        if existing:
            existing.qty_per_paket = row.qty_per_paket
            continue

        db.add(PaketComponent(
            paket_menu_id=paket_id,
            component_menu_id=component_id,
            qty_per_paket=row.qty_per_paket,
        ))
        added += 1

    db.commit()
    print(f"✅ Paket components added: {added}")


def main():
    db = SessionLocal()
    try:
        categories_df = load_sheet("Categories", key_column="category_code")
        menus_df = load_sheet("Menus", key_column="menu_code")
        variants_df = load_sheet("Variants", key_column="menu_code")
        sambals_df = load_sheet("Sambals", key_column="sambal_code")
        stock_df = load_sheet("OpeningStock", key_column="menu_code")
        paket_df = load_sheet("PaketComponents", key_column="paket_code")

        # Urutan ini WAJIB -- mengikuti urutan foreign key dependency
        category_map = seed_categories(db, categories_df)
        menu_map = seed_menus(db, menus_df, category_map)
        menu_types = dict(zip(menus_df.menu_code, menus_df.type))

        seed_variants(db, variants_df, menu_map)
        seed_sambals(db, sambals_df)
        seed_opening_stock(db, stock_df, menu_map, menu_types)
        seed_paket_components(db, paket_df, menu_map, menu_types)

        print("🎉 Seeding selesai!")
    finally:
        db.close()


if __name__ == "__main__":
    main()