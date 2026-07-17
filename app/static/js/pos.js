/*
 * Actual API contract (confirmed from /api/menus response):
 *
 * GET /api/menus  ->
 *   [
 *     { "id": 2, "name": "Ayam",
 *       "menus": [
 *         { "id": 4, "name": "Dada", "type": "regular", "is_active": true,
 *           "variants": [ { "id": 4, "variant_name": "Goreng", "price": "18000.00" },
 *                          { "id": 5, "variant_name": "Bakar",  "price": "18000.00" } ] }
 *       ] }
 *   ]
 *   Note: price comes back as a STRING (e.g. "4000.00") - must parseFloat() before math.
 *
 *   Some menu names repeat across categories (e.g. "Dada", "Tepong" exist under
 *   both Ayam and Bebek). The category tabs already disambiguate them while
 *   browsing, but once added to the cart the category name is shown in the
 *   cart line's meta row (alongside variant/sambal) so the nota stays
 *   unambiguous too - see categoryName plumbing below.
 *
 *   Menus also carry "is_sellable": some are internal base-unit items (e.g.
 *   "Lele (per ekor)") that exist only so Paket items can deduct stock from
 *   them via paket_components - they're excluded from the cashier grid below
 *   but still show up on the /stok page since they still need restocking.
 *
 * GET /api/sambals (optional) -> [ { "id": 1, "name": "Sambal Terasi" }, ... ]
 *
 * POST /api/checkout -> body:
 *   { "cashier_id": 1, "customer_type": "dine_in", "payment_method": "cash",
 *     "amount_paid": 50000,
 *     "items": [ { "menu_id": 4, "variant_id": 4, "quantity": 2, "sambal_id": 1 } ] }
 *   -> OrderOut: { "invoice_number": "INV-...", "grand_total": ..., "order_details": [...], ... }
 */

const state = {
    categories: [],
    activeCategory: null,
    sambals: [],
    cart: [], // { key, menuId, variantId, name, categoryName, variantName, price, qty, sambalId, sambalName }
    pendingVariantMenu: null,
    pendingVariantCategory: null,
    pendingMenu: null, // { menu, variant, categoryName } waiting for sambal selection
};

const CASHIER_ID = 1; // TODO: replace with real logged-in cashier once auth exists

const el = (id) => document.getElementById(id);

function rupiah(n) {
    return "Rp " + Math.round(n).toLocaleString("id-ID");
}

// ---------- Load data ----------

async function loadMenus() {
    const res = await fetch("/api/menus");
    if (!res.ok) throw new Error("Gagal memuat menu");
    state.categories = await res.json();
    state.activeCategory = state.categories[0]?.name ?? null;
    renderCategoryTabs();
    renderMenus();
}

async function loadSambals() {
    try {
        const res = await fetch("/api/sambals");
        if (res.ok) state.sambals = await res.json();
    } catch {
        state.sambals = []; // sambal picker just won't show if endpoint isn't ready yet
    }
}

// ---------- Rendering: categories + grid ----------

function renderCategoryTabs() {
    const nav = el("categoryTabs");
    nav.innerHTML = "";
    state.categories.forEach((cat) => {
        const btn = document.createElement("button");
        btn.className = "category-tab" + (cat.name === state.activeCategory ? " is-active" : "");
        btn.textContent = cat.name;
        btn.addEventListener("click", () => {
            state.activeCategory = cat.name;
            renderCategoryTabs();
            renderMenus();
        });
        nav.appendChild(btn);
    });
}

function renderMenus() {
    const grid = el("menuGrid");
    grid.innerHTML = "";
    const cat = state.categories.find((c) => c.name === state.activeCategory);
    const menus = (cat?.menus ?? []).filter((m) => m.is_active && m.is_sellable);

    if (menus.length === 0) {
        grid.innerHTML = `<p class="menu-empty">Belum ada menu di kategori ini.</p>`;
        return;
    }

    menus.forEach((menu) => {
        const card = document.createElement("button");
        card.className = "menu-card";
        const variants = (menu.variants ?? []).map((v) => ({ ...v, price: parseFloat(v.price) }));
        const minPrice = Math.min(...variants.map((v) => v.price));
        const maxPrice = Math.max(...variants.map((v) => v.price));
        const priceLabel =
            variants.length > 1 && minPrice !== maxPrice
                ? `mulai ${rupiah(minPrice)}`
                : rupiah(minPrice);

        card.innerHTML = `
            <span class="menu-card__name">${menu.name}</span>
            ${menu.type === "paket" ? `<span class="menu-card__badge">Paket</span>` : ""}
            <span class="menu-card__price"><strong>${priceLabel}</strong></span>
        `;
        card.addEventListener("click", () => handleMenuClick({ ...menu, variants }, cat.name));
        grid.appendChild(card);
    });
}

// ---------- Menu click -> variant + sambal flow ----------

function handleMenuClick(menu, categoryName) {
    const variants = menu.variants ?? [];
    if (variants.length === 0) return;

    if (variants.length > 1) {
        openVariantModal(menu, categoryName);
    } else {
        proceedAfterVariant(menu, variants[0], categoryName);
    }
}

function openVariantModal(menu, categoryName) {
    state.pendingVariantMenu = menu;
    state.pendingVariantCategory = categoryName;
    const opts = el("variantOptions");
    opts.innerHTML = menu.variants
        .map(
            (v, i) => `
        <label>
            <input type="radio" name="variant" value="${v.id}" ${i === 0 ? "checked" : ""}>
            ${v.variant_name} - ${rupiah(v.price)}
        </label>`
        )
        .join("");
    el("variantModalTitle").textContent = `Pilih Varian - ${categoryName} ${menu.name}`;
    el("variantModal").hidden = false;
}

function closeVariantModal() {
    el("variantModal").hidden = true;
    state.pendingVariantMenu = null;
    state.pendingVariantCategory = null;
}

function confirmVariant() {
    const checked = document.querySelector('input[name="variant"]:checked');
    const menu = state.pendingVariantMenu;
    const categoryName = state.pendingVariantCategory;
    const variant = menu.variants.find((v) => String(v.id) === checked.value);
    closeVariantModal();
    proceedAfterVariant(menu, variant, categoryName);
}

function proceedAfterVariant(menu, variant, categoryName) {
    if (state.sambals.length > 0) {
        openSambalModal(menu, variant, categoryName);
    } else {
        addToCart(menu, variant, null, null, categoryName);
    }
}

function openSambalModal(menu, variant, categoryName) {
    state.pendingMenu = { menu, variant, categoryName };
    const opts = el("sambalOptions");
    opts.innerHTML = `
        <label><input type="radio" name="sambal" value="" checked> Tanpa sambal</label>
        ${state.sambals
            .map((s) => `<label><input type="radio" name="sambal" value="${s.id}"> ${s.name}</label>`)
            .join("")}
    `;
    el("sambalModalTitle").textContent = `Pilih Sambal - ${categoryName} ${menu.name}`;
    el("sambalModal").hidden = false;
}

function closeSambalModal() {
    el("sambalModal").hidden = true;
    state.pendingMenu = null;
}

function confirmSambal() {
    const checked = document.querySelector('input[name="sambal"]:checked');
    const sambalId = checked?.value ? Number(checked.value) : null;
    const sambalName = sambalId ? state.sambals.find((s) => s.id === sambalId)?.name : null;

    const { menu, variant, categoryName } = state.pendingMenu;
    addToCart(menu, variant, sambalId, sambalName, categoryName);
    closeSambalModal();
}

// ---------- Cart ----------

function addToCart(menu, variant, sambalId, sambalName, categoryName) {
    const key = `${menu.id}-${variant.id}-${sambalId ?? "none"}`;
    const existing = state.cart.find((line) => line.key === key);

    if (existing) {
        existing.qty += 1;
    } else {
        state.cart.push({
            key,
            menuId: menu.id,
            variantId: variant.id,
            name: menu.name,
            categoryName,
            variantName: variant.variant_name,
            price: variant.price,
            qty: 1,
            sambalId,
            sambalName,
        });
    }
    renderCart();
}

function removeFromCart(key) {
    state.cart = state.cart.filter((line) => line.key !== key);
    renderCart();
}

function changeQty(key, delta) {
    const line = state.cart.find((l) => l.key === key);
    if (!line) return;

    line.qty += delta;
    if (line.qty <= 0) {
        removeFromCart(key);
        return;
    }
    renderCart();
}

function renderCart() {
    const container = el("cartLines");

    if (state.cart.length === 0) {
        container.innerHTML = `<p class="receipt__empty">Keranjang masih kosong.<br>Pilih menu di sebelah kiri untuk memulai.</p>`;
    } else {
        container.innerHTML = state.cart
            .map(
                (line) => `
            <div class="cart-line">
                <span class="cart-line__name">${line.name}</span>
                <span class="cart-line__amount">${rupiah(line.price * line.qty)}</span>
                <span class="cart-line__meta">${[line.categoryName, line.variantName, line.sambalName].filter(Boolean).join(" \u00b7 ")}</span>
                <div class="cart-line__actions">
                    <div class="cart-line__qty">
                        <button class="qty-btn" data-action="dec" data-key="${line.key}" aria-label="Kurangi jumlah">&minus;</button>
                        <span class="qty-value">${line.qty}</span>
                        <button class="qty-btn" data-action="inc" data-key="${line.key}" aria-label="Tambah jumlah">+</button>
                    </div>
                    <button class="cart-line__remove" data-key="${line.key}">Hapus</button>
                </div>
            </div>
        `
            )
            .join("");

        container.querySelectorAll(".qty-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                changeQty(btn.dataset.key, btn.dataset.action === "inc" ? 1 : -1);
            });
        });
        container.querySelectorAll(".cart-line__remove").forEach((btn) => {
            btn.addEventListener("click", () => removeFromCart(btn.dataset.key));
        });
    }

    const subtotal = state.cart.reduce((sum, l) => sum + l.price * l.qty, 0);
    el("subtotal").textContent = rupiah(subtotal);
    el("grandTotal").textContent = rupiah(subtotal);
    el("checkoutBtn").disabled = state.cart.length === 0;
}

// ---------- Checkout ----------

function buildCheckoutPayload() {
    const amountPaid = Number(el("amountPaid").value || 0);
    return {
        cashier_id: CASHIER_ID,
        customer_type: el("customerType").value,
        payment_method: el("paymentMethod").value,
        amount_paid: amountPaid,
        items: state.cart.map((line) => ({
            menu_id: line.menuId,
            variant_id: line.variantId,
            quantity: line.qty,
            sambal_id: line.sambalId,
        })),
    };
}

async function handleCheckout() {
    const note = el("statusNote");
    note.textContent = "";
    note.className = "receipt__note";

    if (state.cart.length === 0) return;

    el("checkoutBtn").disabled = true;
    try {
        const res = await fetch("/api/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(buildCheckoutPayload()),
        });

        const data = await res.json();

        if (!res.ok) {
            note.textContent = data.detail ?? "Transaksi gagal, coba lagi.";
            note.classList.add("is-error");
            el("checkoutBtn").disabled = false;
            return;
        }

        note.textContent = `Pembayaran berhasil - ${data.invoice_number}`;
        note.classList.add("is-success");
        el("invoiceLabel").textContent = data.invoice_number;

        state.cart = [];
        renderCart();
        el("amountPaid").value = "";
    } catch (err) {
        note.textContent = "Tidak bisa terhubung ke server.";
        note.classList.add("is-error");
        el("checkoutBtn").disabled = false;
    }
}

// ---------- Clock ----------

function tickClock() {
    const now = new Date();
    el("clock").textContent = now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

// ---------- Init ----------

document.addEventListener("DOMContentLoaded", async () => {
    tickClock();
    setInterval(tickClock, 30000);

    el("checkoutBtn").addEventListener("click", handleCheckout);
    el("variantCancel").addEventListener("click", closeVariantModal);
    el("variantConfirm").addEventListener("click", confirmVariant);
    el("sambalCancel").addEventListener("click", closeSambalModal);
    el("sambalConfirm").addEventListener("click", confirmSambal);

    try {
        await loadSambals();
        await loadMenus();
    } catch (err) {
        el("menuGrid").innerHTML = `<p class="menu-empty">Gagal memuat menu. Pastikan server FastAPI sedang berjalan.</p>`;
        console.error(err);
    }
});