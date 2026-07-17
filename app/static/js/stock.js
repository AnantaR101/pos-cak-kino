/*
 * Manajemen Stok page.
 *
 * GET /api/stock -> list of StockOut { menu_id, menu_name, category_name,
 *   current_qty, updated_at }
 * PATCH /api/stock/{menu_id}  body: { delta: <int> }  -> updated StockOut
 *   delta positif = nambah, negatif = mengurangi. Server menolak (400) kalau
 *   hasilnya jadi negatif, atau kalau menu_id itu Paket (tidak punya stok
 *   sendiri, lihat DEVLOG Phase 5).
 */

const state = {
    stock: [],
    filtered: [],
};

const el = (id) => document.getElementById(id);

function formatDateTime(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

// ---------- Load & render ----------

async function loadStock() {
    const res = await fetch("/api/stock");
    if (!res.ok) throw new Error("Gagal memuat stok");
    state.stock = await res.json();
    state.filtered = state.stock;
    renderTable();
}

function renderTable() {
    const container = el("stockTable");

    if (state.filtered.length === 0) {
        container.innerHTML = `<p class="admin-empty">Menu tidak ditemukan.</p>`;
        return;
    }

    container.innerHTML = `
        <div class="stock-row stock-row--head">
            <span>Menu</span>
            <span>Kategori</span>
            <span>Stok</span>
            <span>Terakhir Update</span>
            <span>Koreksi</span>
        </div>
        ${state.filtered
            .map(
                (s) => `
        <div class="stock-row ${s.current_qty === 0 ? "stock-row--empty" : ""}">
            <span class="stock-row__name">${s.menu_name}</span>
            <span class="stock-row__category">${s.category_name}</span>
            <span class="stock-row__qty">${s.current_qty}</span>
            <span class="stock-row__updated">${formatDateTime(s.updated_at)}</span>
            <span class="stock-row__adjust">
                <input type="number" class="stock-delta" id="delta-${s.menu_id}" placeholder="+/-" step="1">
                <button class="btn-ghost btn-adjust" data-menu-id="${s.menu_id}">Terapkan</button>
            </span>
        </div>`
            )
            .join("")}
    `;

    container.querySelectorAll(".btn-adjust").forEach((btn) => {
        btn.addEventListener("click", () => applyAdjustment(Number(btn.dataset.menuId)));
    });
}

// ---------- Adjustment ----------

async function applyAdjustment(menuId) {
    const input = el(`delta-${menuId}`);
    const delta = Number(input.value);

    if (!delta) {
        input.focus();
        return;
    }

    try {
        const res = await fetch(`/api/stock/${menuId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ delta }),
        });
        const data = await res.json();

        if (!res.ok) {
            alert(data.detail ?? "Gagal menyesuaikan stok.");
            return;
        }

        const stockItem = state.stock.find((s) => s.menu_id === menuId);
        if (stockItem) {
            stockItem.current_qty = data.current_qty;
            stockItem.updated_at = data.updated_at;
        }
        renderTable();
    } catch (err) {
        alert("Tidak bisa terhubung ke server.");
        console.error(err);
    }
}

// ---------- Search ----------

function handleSearch() {
    const q = el("stockSearch").value.trim().toLowerCase();
    state.filtered = q
        ? state.stock.filter(
              (s) => s.menu_name.toLowerCase().includes(q) || s.category_name.toLowerCase().includes(q)
          )
        : state.stock;
    renderTable();
}

// ---------- Init ----------

document.addEventListener("DOMContentLoaded", async () => {
    el("stockSearch").addEventListener("input", handleSearch);
    try {
        await loadStock();
    } catch (err) {
        el("stockTable").innerHTML = `<p class="admin-empty">Gagal memuat stok. Pastikan server FastAPI sedang berjalan.</p>`;
        console.error(err);
    }
});