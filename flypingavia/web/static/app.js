(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try { tg.setHeaderColor("#071821"); tg.setBackgroundColor("#071821"); } catch (_) {}
  }

  const state = {
    quote: null,
    origin: "",
    destination: "",
    depart: "",
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  function toast(text) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2600);
  }

  function authHeaders() {
    const headers = { "Content-Type": "application/json" };
    const initData = tg?.initData || "";
    if (initData) headers["X-Telegram-Init-Data"] = initData;
    return headers;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || `Ошибка ${res.status}`);
    return data;
  }

  function money(v) {
    return `${Math.round(Number(v)).toLocaleString("ru-RU")} ₽`;
  }

  function levelLabel(level) {
    if (level === "cheap") return ["cheap", "дёшево"];
    if (level === "expensive") return ["expensive", "дорого"];
    if (level === "normal") return ["normal", "обычно"];
    return ["", "нет оценки"];
  }

  function renderQuote(q) {
    state.quote = q;
    const box = $("#quote");
    const [cls, label] = levelLabel(q.level);
    box.classList.remove("hidden");
    box.innerHTML = `
      <h2>${q.origin_name} → ${q.destination_name}</h2>
      <div class="price-now">${q.price != null ? money(q.price) : "—"}</div>
      <div class="level ${cls}">● сейчас ${label}</div>
      <div class="meta">
        ${q.origin_airport ? `вылет ${q.origin_airport}` : ""}
        ${q.destination_airport ? ` · прилёт ${q.destination_airport}` : ""}
        ${q.transfers == 0 ? " · прямой" : q.transfers != null ? ` · пересадок: ${q.transfers}` : ""}
      </div>
      ${q.airports_note ? `<div class="meta">${q.airports_note}</div>` : ""}
      <div class="band">
        <div class="band-row cheap"><span>🟢 дёшево</span><span>≤ ${money(q.cheap_max)}</span></div>
        <div class="band-row typical"><span>🟡 обычно</span><span>~ ${money(q.typical)}</span></div>
        <div class="band-row expensive"><span>🔴 дорого</span><span>≥ ${money(q.expensive_min)}</span></div>
      </div>
      <div class="actions" style="margin-top:12px;display:grid">
        <a class="btn ghost" href="${q.tickets_url}" target="_blank" rel="noopener">Смотреть билеты</a>
      </div>
    `;
    $("#watch-form").classList.remove("hidden");
    $("#threshold").value = Math.round(q.cheap_max || q.price || 0);
  }

  async function resolveHint(inputId, hintId) {
    const q = $(inputId).value.trim();
    const hint = $(hintId);
    if (q.length < 2) { hint.textContent = ""; return; }
    try {
      const items = await api(`/api/resolve?q=${encodeURIComponent(q)}`);
      if (!items.length) { hint.textContent = "не найдено"; return; }
      const top = items[0];
      hint.textContent = top.airports.length > 1
        ? `${top.label} · ${top.airports.length} а/п → самый дешёвый`
        : top.label;
    } catch {
      hint.textContent = "";
    }
  }

  function switchTab(name) {
    $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
    if (name === "watches") loadWatches();
  }

  async function loadWatches() {
    const box = $("#watches");
    box.innerHTML = `<div class="meta">Загрузка…</div>`;
    try {
      const items = await api("/api/watches");
      if (!items.length) {
        box.innerHTML = `<div class="quote"><h2>Пока пусто</h2><p class="meta">Соберите маршрут на вкладке «Поиск» и нажмите «Следить».</p></div>`;
        return;
      }
      box.innerHTML = items.map((w) => `
        <article class="watch-card" data-id="${w.id}">
          <h3>${w.origin_name || w.origin} → ${w.destination_name || w.destination}</h3>
          <div class="meta mono">#${w.id} · порог ${money(w.max_price)}</div>
          <div class="meta">сейчас: ${w.last_price != null ? money(w.last_price) : "ещё не проверяли"}
            ${w.last_origin_airport ? ` · вылет ${w.last_origin_airport}` : ""}
          </div>
          <div class="actions">
            <a class="btn ghost" href="${w.tickets_url}" target="_blank" rel="noopener">Билеты</a>
            <button class="btn ghost" data-del="${w.id}" type="button">Удалить</button>
          </div>
        </article>
      `).join("");
    } catch (err) {
      box.innerHTML = `<div class="quote"><h2>Не удалось загрузить</h2><p class="meta">${err.message}</p></div>`;
    }
  }

  $$(".tab").forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

  let originTimer, destTimer;
  $("#origin").addEventListener("input", () => {
    clearTimeout(originTimer);
    originTimer = setTimeout(() => resolveHint("#origin", "#origin-hint"), 280);
  });
  $("#destination").addEventListener("input", () => {
    clearTimeout(destTimer);
    destTimer = setTimeout(() => resolveHint("#destination", "#destination-hint"), 280);
  });

  $("#search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#search-btn");
    state.origin = $("#origin").value.trim();
    state.destination = $("#destination").value.trim();
    state.depart = $("#depart").value || "";
    btn.disabled = true;
    btn.textContent = "Считаем…";
    try {
      const params = new URLSearchParams({
        origin: state.origin,
        destination: state.destination,
      });
      if (state.depart) params.set("depart_date", state.depart);
      const q = await api(`/api/quote?${params}`);
      renderQuote(q);
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Показать вилку цен";
    }
  });

  $$("[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!state.quote) return;
      const key = btn.dataset.preset;
      $("#threshold").value = Math.round(state.quote[key === "cheap" ? "cheap_max" : "typical"] || 0);
    });
  });

  $("#watch-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.quote) return;
    try {
      const body = {
        origin: state.quote.origin,
        destination: state.quote.destination,
        max_price: Number($("#threshold").value),
        depart_date: state.depart || null,
      };
      await api("/api/watches", { method: "POST", body: JSON.stringify(body) });
      toast("Подписка создана");
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      switchTab("watches");
    } catch (err) {
      toast(err.message);
    }
  });

  $("#watches").addEventListener("click", async (e) => {
    const id = e.target?.dataset?.del;
    if (!id) return;
    try {
      await api(`/api/watches/${id}`, { method: "DELETE" });
      toast("Удалено");
      loadWatches();
    } catch (err) {
      toast(err.message);
    }
  });

  $("#refresh-watches").addEventListener("click", loadWatches);

  // Прогрев /me — сразу покажет проблему с auth
  api("/api/me").catch((err) => {
    if (!tg?.initData) {
      toast("Откройте из Telegram или задайте WEBAPP_DEV_USER_ID");
    } else {
      toast(err.message);
    }
  });
})();
