const stepMeta = {
  chat: {
    title: "Consulta comercial",
    eyebrow: "ETAPA 01 · BÚSQUEDA HÍBRIDA Y DESAMBIGUACIÓN",
  },
  stock: {
    title: "Inventario por origen y vigencia",
    eyebrow: "ETAPA 02 · SNAPSHOTS MULTI-SEDE (FRESH / STALE)",
  },
  quote: {
    title: "Borrador de cotización (DRAFT)",
    eyebrow: "ETAPA 03 · CÁLCULO DETERMINISTA CON DECIMAL",
  },
};

const connection = document.querySelector("#connection");
const tabs = Array.from(document.querySelectorAll(".step"));
const panels = Array.from(document.querySelectorAll(".panel"));

function activateStep(stepButton) {
  const stepKey = stepButton.dataset.step;
  for (const tab of tabs) {
    const isCurrent = tab === stepButton;
    tab.classList.toggle("active", isCurrent);
    tab.setAttribute("aria-selected", String(isCurrent));
  }
  for (const panel of panels) {
    panel.classList.toggle("active", panel.id === stepKey);
  }
  const meta = stepMeta[stepKey];
  if (meta) {
    document.querySelector("#panel-title").textContent = meta.title;
    const eyebrow = document.querySelector("#panel-eyebrow");
    if (eyebrow) eyebrow.textContent = meta.eyebrow;
  }
}

for (const button of tabs) {
  button.addEventListener("click", () => activateStep(button));
  button.addEventListener("keydown", (event) => {
    const index = tabs.indexOf(button);
    if (event.key === "ArrowRight") {
      event.preventDefault();
      const next = tabs[(index + 1) % tabs.length];
      next.focus();
      activateStep(next);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      const prev = tabs[(index - 1 + tabs.length) % tabs.length];
      prev.focus();
      activateStep(prev);
    }
  });
}

for (const chip of document.querySelectorAll(".chip[data-preset]")) {
  chip.addEventListener("click", () => {
    const question = document.querySelector("#question");
    question.value = chip.dataset.preset;
    document.querySelector("#chat-send").click();
  });
}

document.querySelector("#question")?.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    document.querySelector("#chat-send").click();
  }
});

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function setLoading(button, isLoading, loadingLabel) {
  if (!button) return;
  const labelNode = button.querySelector(".action-text") || button;
  if (isLoading) {
    button.dataset.originalLabel = labelNode.textContent;
    labelNode.textContent = loadingLabel;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  } else {
    if (button.dataset.originalLabel) {
      labelNode.textContent = button.dataset.originalLabel;
    }
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

function showError(target, error) {
  target.replaceChildren();
  target.classList.add("error");
  const title = document.createElement("strong");
  title.textContent = "Regla de dominio aplicada / Aviso:";
  const body = document.createElement("p");
  body.className = "reply-body";
  body.textContent = error.message;
  target.append(title, body);
}

try {
  const health = await request("/health");
  connection.textContent =
    health.provider === "mock"
      ? "● API conectada · mock ($0)"
      : `● API conectada · ${health.provider} (usa mock para esta demo)`;
  connection.classList.toggle("warn", health.provider !== "mock");
} catch {
  connection.textContent = "● API local no iniciada (:8001)";
  connection.classList.add("warn");
}

document.querySelector("#chat-send").addEventListener("click", async () => {
  const button = document.querySelector("#chat-send");
  const target = document.querySelector("#chat-result");
  target.classList.remove("error");
  setLoading(button, true, "Consultando catálogo y reglas…");
  try {
    const message = document.querySelector("#question").value.trim();
    if (!message) throw new Error("Escribe una consulta comercial para enviar a XEON.");
    const result = await request("/v1/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    });
    target.replaceChildren();
    const header = document.createElement("div");
    header.className = "result-header";
    const label = document.createElement("strong");
    label.textContent = `RESPUESTA VERIFICADA · PROVEEDOR: ${result.provider.toUpperCase()}`;
    const modelBadge = document.createElement("span");
    modelBadge.className = "stock-badge badge-kind";
    modelBadge.textContent = result.model || "deterministic-toolbelt";
    header.append(label, modelBadge);

    const reply = document.createElement("p");
    reply.className = "reply-body";
    reply.textContent = result.reply;
    target.append(header, reply);
  } catch (error) {
    showError(target, error);
  } finally {
    setLoading(button, false);
  }
});

document.querySelector("#stock-send").addEventListener("click", async () => {
  const button = document.querySelector("#stock-send");
  const target = document.querySelector("#stock-result");
  target.classList.remove("error");
  setLoading(button, true, "Evaluando snapshots…");
  try {
    const sku = document.querySelector("#stock-sku")?.value || "CEM-50";
    const branch = document.querySelector("#stock-branch")?.value || "sede-norte";
    const quantity = Number(document.querySelector("#quantity").value);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      throw new Error("La cantidad solicitada debe ser mayor que cero.");
    }
    const query = new URLSearchParams({
      sku,
      requested_branch_id: branch,
      evaluated_at: "2026-10-08T15:00:00+00:00",
      requested_quantity: String(quantity),
    });
    const result = await request(`/v1/stock?${query}`);
    target.replaceChildren();

    const banner = document.createElement("div");
    banner.className = "fulfillment-banner";
    const summary = document.createElement("strong");
    summary.textContent = `${result.sku} en ${result.requested_branch_id}: ${result.local_available ?? "0"} unds locales firmes · Faltante local: ${result.shortfall ?? "0"}`;
    const statusBadge = document.createElement("span");
    const isSufficient = result.fulfillment_status === "sufficient";
    statusBadge.className = `stock-badge ${isSufficient ? "badge-fresh" : "badge-stale"}`;
    statusBadge.textContent = `CUMPLIMIENTO: ${(result.fulfillment_status || "observado").toUpperCase()}`;
    banner.append(summary, statusBadge);
    target.append(banner);

    for (const item of result.items) {
      const row = document.createElement("div");
      row.className = "stock-row";

      const name = document.createElement("span");
      name.textContent = `${item.origin_name} (${item.branch_id})`;

      const badges = document.createElement("div");
      badges.className = "stock-badges";

      const qtyBadge = document.createElement("span");
      qtyBadge.className = "stock-badge badge-kind";
      qtyBadge.textContent = `${item.quantity} unds · ${item.kind}`;

      const freshBadge = document.createElement("span");
      freshBadge.className = `stock-badge ${item.freshness === "fresh" ? "badge-fresh" : "badge-stale"}`;
      freshBadge.textContent = item.freshness === "fresh" ? "✓ FRESH (FIRME)" : `⚠ ${item.freshness.toUpperCase()} (${item.age || "vencido"})`;

      badges.append(qtyBadge, freshBadge);
      row.append(name, badges);
      target.append(row);
    }
  } catch (error) {
    showError(target, error);
  } finally {
    setLoading(button, false);
  }
});

document.querySelector("#quote-send").addEventListener("click", async () => {
  const button = document.querySelector("#quote-send");
  const target = document.querySelector("#quote-result");
  target.classList.remove("error");
  setLoading(button, true, "Calculando con Decimal…");
  try {
    const sku = document.querySelector("#quote-sku")?.value || "CEM-50";
    const qty = Number(document.querySelector("#quote-qty")?.value || 2);
    const discountRequested = Boolean(document.querySelector("#quote-discount")?.checked);
    if (!Number.isFinite(qty) || qty <= 0) {
      throw new Error("La cantidad a cotizar debe ser mayor que cero.");
    }

    const result = await request("/v1/quotes", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        tenant_id: "demo-video",
        request_id: `demo-${crypto.randomUUID()}`,
        lines: [{ query: sku, quantity: qty }],
        discount_requested: discountRequested,
      }),
    });

    if (result.outcome !== "draft_ready" || !result.quote) {
      throw new Error(result.message || "No se generó el borrador.");
    }

    const quote = result.quote;
    const line = quote.lines[0];
    target.replaceChildren();

    const header = document.createElement("div");
    header.className = "result-header";
    const label = document.createElement("strong");
    label.textContent = `ESTADO: ${quote.status} · VERSIÓN v${quote.version}`;
    const idBadge = document.createElement("span");
    idBadge.className = "stock-badge badge-fresh";
    idBadge.textContent = `ID: ${String(quote.id).slice(0, 8)}…`;
    header.append(label, idBadge);

    const total = document.createElement("div");
    total.className = "total";
    total.textContent = `$${new Intl.NumberFormat("es-CO").format(Number(quote.total))} ${quote.currency}`;

    const metaGrid = document.createElement("div");
    metaGrid.className = "quote-meta-grid";
    metaGrid.innerHTML = `
      <div><span class="metric-label">REFERENCIA</span><strong>${line.sku} · ${line.description}</strong></div>
      <div><span class="metric-label">CÁLCULO DECIMAL</span><strong>${line.quantity} ${line.unit} × $${new Intl.NumberFormat("es-CO").format(Number(line.unit_price))}</strong></div>
      <div><span class="metric-label">PROCEDENCIA</span><strong>${quote.source} (${quote.catalog_version})</strong></div>
    `;

    target.append(header, total, metaGrid);
  } catch (error) {
    showError(target, error);
  } finally {
    setLoading(button, false);
  }
});
