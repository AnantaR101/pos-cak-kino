/*
 * Riwayat Transaksi page.
 *
 * GET /api/orders -> list of OrderOut (see schemas.py), each order already
 * includes order_details with menu_name / category_name / variant_name /
 * sambal_name filled in (via crud.serialize_order) so the nota can be
 * rendered directly without extra lookups.
 */

const state = {
    orders: [],
    filtered: [],
    activeId: null,
};

const el = (id) => document.getElementById(id);

function rupiah(n) {
    return "Rp " + Math.round(n).toLocaleString("id-ID");
}

function formatDateTime(iso) {
    const d = new Date(iso);
    return d.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

function statusLabel(status) {
    return status === "voided" ? "Dibatalkan" : "Selesai";
}

// ---------- Load & list ----------

async function loadOrders() {
    const res = await fetch("/api/orders");
    if (!res.ok) throw new Error("Gagal memuat riwayat order");
    state.orders = await res.json();
    state.filtered = state.orders;
    renderOrderList();
}

function renderOrderList() {
    const container = el("orderList");

    if (state.filtered.length === 0) {
        container.innerHTML = `<p class="admin-empty">Belum ada transaksi yang cocok.</p>`;
        return;
    }

    container.innerHTML = state.filtered
        .map(
            (o) => `
        <button class="order-row ${o.id === state.activeId ? "is-active" : ""}" data-id="${o.id}">
            <span class="order-row__invoice">${o.invoice_number}</span>
            <span class="order-row__time">${formatDateTime(o.order_time)}</span>
            <span class="order-row__total">${rupiah(o.grand_total)}</span>
            <span class="order-row__status order-row__status--${o.status}">${statusLabel(o.status)}</span>
        </button>`
        )
        .join("");

    container.querySelectorAll(".order-row").forEach((btn) => {
        btn.addEventListener("click", () => showNota(Number(btn.dataset.id)));
    });
}

// ---------- Nota detail ----------

function showNota(orderId) {
    state.activeId = orderId;
    renderOrderList();

    const order = state.orders.find((o) => o.id === orderId);
    if (!order) return;

    const lines = order.order_details
        .map(
            (d) => `
        <div class="cart-line">
            <span class="cart-line__name">${d.quantity}x ${d.menu_name}</span>
            <span class="cart-line__amount">${rupiah(d.subtotal)}</span>
            <span class="cart-line__meta">${[d.category_name, d.variant_name, d.sambal_name].filter(Boolean).join(" \u00b7 ")}</span>
        </div>`
        )
        .join("");

    const payment = order.payment;
    const paymentLabel =
        payment?.payment_method === "cash" ? "Tunai" : (payment?.payment_method ?? "").toUpperCase();

    el("notaDetail").innerHTML = `
        <div class="receipt__head">
            <h2>Nota</h2>
            <span class="receipt__invoice">${order.invoice_number}</span>
        </div>
        <p class="nota-meta">
            ${formatDateTime(order.order_time)} &middot; ${order.cashier_name} &middot;
            ${order.customer_type === "dine_in" ? "Makan di Tempat" : "Bawa Pulang"}
        </p>
        <div class="receipt__lines receipt__lines--static">${lines}</div>
        <div class="receipt__totals">
            <div class="receipt__row receipt__row--grand">
                <span>Total</span>
                <span>${rupiah(order.grand_total)}</span>
            </div>
            ${
                payment
                    ? `
            <div class="receipt__row">
                <span>${paymentLabel}</span>
                <span>${rupiah(payment.amount_paid)}</span>
            </div>
            <div class="receipt__row">
                <span>Kembalian</span>
                <span>${rupiah(payment.change_amount)}</span>
            </div>`
                    : ""
            }
        </div>
        <p class="nota-status nota-status--${order.status}">${
        order.status === "voided" ? "Transaksi dibatalkan" : "Transaksi selesai"
    }</p>
    `;
}

// ---------- Search ----------

function handleSearch() {
    const q = el("orderSearch").value.trim().toLowerCase();
    state.filtered = q ? state.orders.filter((o) => o.invoice_number.toLowerCase().includes(q)) : state.orders;
    renderOrderList();
}

// ---------- Init ----------

document.addEventListener("DOMContentLoaded", async () => {
    el("orderSearch").addEventListener("input", handleSearch);
    try {
        await loadOrders();
    } catch (err) {
        el("orderList").innerHTML = `<p class="admin-empty">Gagal memuat riwayat. Pastikan server FastAPI sedang berjalan.</p>`;
        console.error(err);
    }
});