(() => {
  const boot = document.getElementById("boot");
  function setBoot(text) {
    if (boot) boot.textContent = text;
  }

  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      try {
        if (tg.setHeaderColor) tg.setHeaderColor("#071821");
        if (tg.setBackgroundColor) tg.setBackgroundColor("#071821");
      } catch (_) {}
      setBoot(tg.initData ? "Telegram ✓" : "Открыто без initData");
    } else {
      setBoot("Браузерный режим");
    }

    const state = {
      quote: null,
      origin: "",
      destination: "",
      depart: "",
      returnDate: "",
      trip: "oneway",
      adults: 1,
      children: 0,
      infants: 0,
    };
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => Array.prototype.slice.call(document.querySelectorAll(sel));

    function toast(text) {
      const el = $("#toast");
      el.textContent = text;
      el.classList.remove("hidden");
      clearTimeout(toast._t);
      toast._t = setTimeout(() => el.classList.add("hidden"), 2800);
    }

    function authHeaders() {
      const headers = { "Content-Type": "application/json" };
      const initData = (tg && tg.initData) || "";
      if (initData) headers["X-Telegram-Init-Data"] = initData;
      return headers;
    }

    async function api(path, options) {
      options = options || {};
      const res = await fetch(path, {
        method: options.method || "GET",
        headers: Object.assign({}, authHeaders(), options.headers || {}),
        body: options.body,
      });
      let data = {};
      try { data = await res.json(); } catch (_) {}
      if (!res.ok) {
        const detail = data.detail;
        const msg = typeof detail === "string" ? detail : (data.message || ("Ошибка " + res.status));
        throw new Error(msg);
      }
      return data;
    }

    function money(v) {
      return Math.round(Number(v)).toLocaleString("ru-RU") + " ₽";
    }

    function levelLabel(level) {
      if (level === "cheap") return ["cheap", "дёшево"];
      if (level === "expensive") return ["expensive", "дорого"];
      if (level === "normal") return ["normal", "обычно"];
      return ["", "нет оценки"];
    }

    function paxLabel(q) {
      const parts = ["взр. " + (q.adults || 1)];
      if (q.children) parts.push("дет. " + q.children);
      if (q.infants) parts.push("мл. " + q.infants);
      return parts.join(", ");
    }

    // passengers UI hidden for now
    function syncPaxUi() {
      const adultsEl = $("#adults-val");
      if (!adultsEl) return;
      adultsEl.textContent = String(state.adults);
      $("#children-val").textContent = String(state.children);
      $("#infants-val").textContent = String(state.infants);
    }

    function setTrip(trip) {
      state.trip = trip;
      $$(".trip-btn").forEach((b) => b.classList.toggle("active", b.getAttribute("data-trip") === trip));
      $("#return-field").classList.toggle("hidden", trip !== "round");
      if (trip !== "round") {
        state.returnDate = "";
        $("#return").value = "";
      } else if (!state.returnDate && state.depart) {
        const d = new Date(state.depart + "T12:00:00");
        d.setDate(d.getDate() + 7);
        state.returnDate = d.toISOString().slice(0, 10);
        $("#return").value = state.returnDate;
      }
    }

    function renderQuote(q) {
      state.quote = q;
      const box = $("#quote");
      const lvl = levelLabel(q.level);
      const tripLabel = q.return_date ? "туда-обратно" : "в одну сторону";
      box.classList.remove("hidden");
      box.innerHTML =
        "<h2>" + q.origin_name + " → " + q.destination_name + "</h2>" +
        "<div class=\"meta\">" + tripLabel + "</div>" +
        "<div class=\"price-now\">" + (q.price != null ? money(q.price) : "—") + "</div>" +
        "<div class=\"level " + lvl[0] + "\">● сейчас " + lvl[1] + "</div>" +
        (q.source === "live_search" ? "<div class=\"meta\">живой поиск</div>" : "") +
        "<div class=\"meta\">" +
          (q.origin_airport ? ("вылет " + q.origin_airport) : "") +
          (q.destination_airport ? (" · прилёт " + q.destination_airport) : "") +
          (q.transfers === 0 ? " · прямой" : (q.transfers != null ? (" · пересадок: " + q.transfers) : "")) +
        "</div>" +
        (q.airports_note ? ("<div class=\"meta\">" + q.airports_note + "</div>") : "") +
        "<div class=\"band\">" +
          "<div class=\"band-row cheap\"><span>🟢 дёшево</span><span>≤ " + money(q.cheap_max) + "</span></div>" +
          "<div class=\"band-row typical\"><span>🟡 обычно</span><span>~ " + money(q.typical) + "</span></div>" +
          "<div class=\"band-row expensive\"><span>🔴 дорого</span><span>≥ " + money(q.expensive_min) + "</span></div>" +
        "</div>" +
        "<div style=\"margin-top:12px\"><a class=\"btn ghost\" href=\"" + q.tickets_url + "\" target=\"_blank\" rel=\"noopener\">Смотреть билеты</a></div>";
      $("#watch-form").classList.remove("hidden");
      $("#threshold").value = Math.round(q.cheap_max || q.price || 0);
    }

    async function resolveHint(inputId, hintId) {
      const q = $(inputId).value.trim();
      const hint = $(hintId);
      if (q.length < 2) { hint.textContent = ""; return; }
      try {
        const items = await api("/api/resolve?q=" + encodeURIComponent(q));
        if (!items.length) { hint.textContent = "не найдено"; return; }
        const top = items[0];
        hint.textContent = top.airports.length > 1
          ? (top.label + " · " + top.airports.length + " а/п → самый дешёвый")
          : top.label;
      } catch (_) {
        hint.textContent = "";
      }
    }

    function switchTab(name) {
      $$(".tab").forEach((b) => b.classList.toggle("active", b.getAttribute("data-tab") === name));
      $$(".panel").forEach((p) => p.classList.toggle("active", p.id === ("panel-" + name)));
      if (name === "watches") loadWatches();
    }

    async function loadWatches() {
      const box = $("#watches");
      box.innerHTML = "<div class=\"meta\">Загрузка…</div>";
      try {
        const items = await api("/api/watches");
        if (!items.length) {
          box.innerHTML = "<div class=\"quote\"><h2>Пока пусто</h2><p class=\"meta\">Соберите маршрут на вкладке «Поиск».</p></div>";
          return;
        }
        box.innerHTML = items.map((w) => {
          const trip = w.return_date ? "туда-обратно" : "в одну сторону";
          return (
            "<article class=\"watch-card\" data-id=\"" + w.id + "\">" +
              "<h3>" + (w.origin_name || w.origin) + " → " + (w.destination_name || w.destination) + "</h3>" +
              "<div class=\"meta\">" + trip + "</div>" +
              "<div class=\"meta mono\">#" + w.id + " · порог " + money(w.max_price) + "</div>" +
              "<div class=\"meta\">сейчас: " + (w.last_price != null ? money(w.last_price) : "ещё не проверяли") +
                (w.last_origin_airport ? (" · вылет " + w.last_origin_airport) : "") + "</div>" +
              "<div class=\"actions\">" +
                "<a class=\"btn ghost\" href=\"" + w.tickets_url + "\" target=\"_blank\" rel=\"noopener\">Билеты</a>" +
                "<button class=\"btn ghost\" data-del=\"" + w.id + "\" type=\"button\">Удалить</button>" +
              "</div>" +
            "</article>"
          );
        }).join("");
      } catch (err) {
        box.innerHTML = "<div class=\"quote\"><h2>Не удалось загрузить</h2><p class=\"meta\">" + err.message + "</p></div>";
      }
    }

    $$(".tab").forEach((btn) => btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab"))));

    $$(".trip-btn").forEach((btn) => {
      btn.addEventListener("click", () => setTrip(btn.getAttribute("data-trip")));
    });

    $$("[data-pax]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const field = btn.getAttribute("data-pax");
        const delta = Number(btn.getAttribute("data-delta"));
        if (field === "adults") {
          state.adults = Math.max(1, Math.min(9, state.adults + delta));
          if (state.infants > state.adults) state.infants = state.adults;
        } else if (field === "children") {
          state.children = Math.max(0, Math.min(9, state.children + delta));
        } else if (field === "infants") {
          state.infants = Math.max(0, Math.min(state.adults, state.infants + delta));
        }
        syncPaxUi();
      });
    });

    let originTimer, destTimer;
    $("#origin").addEventListener("input", () => {
      clearTimeout(originTimer);
      originTimer = setTimeout(() => resolveHint("#origin", "#origin-hint"), 280);
    });
    $("#destination").addEventListener("input", () => {
      clearTimeout(destTimer);
      destTimer = setTimeout(() => resolveHint("#destination", "#destination-hint"), 280);
    });
    $("#depart").addEventListener("change", () => {
      state.depart = $("#depart").value || "";
      if (state.trip === "round" && state.depart && !state.returnDate) {
        const d = new Date(state.depart + "T12:00:00");
        d.setDate(d.getDate() + 7);
        state.returnDate = d.toISOString().slice(0, 10);
        $("#return").value = state.returnDate;
      }
    });
    $("#return").addEventListener("change", () => {
      state.returnDate = $("#return").value || "";
    });

    $("#search-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = $("#search-btn");
      state.origin = $("#origin").value.trim();
      state.destination = $("#destination").value.trim();
      state.depart = $("#depart").value || "";
      state.returnDate = state.trip === "round" ? ($("#return").value || "") : "";
      if (state.trip === "round" && !state.returnDate) {
        toast("Укажите дату возврата");
        return;
      }
      btn.disabled = true;
      btn.textContent = "Считаем…";
      try {
        const params = new URLSearchParams({
          origin: state.origin,
          destination: state.destination,
          adults: String(state.adults),
          children: String(state.children),
          infants: String(state.infants),
        });
        if (state.depart) params.set("depart_date", state.depart);
        if (state.returnDate) params.set("return_date", state.returnDate);
        const q = await api("/api/quote?" + params.toString());
        renderQuote(q);
        if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
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
        const key = btn.getAttribute("data-preset");
        $("#threshold").value = Math.round(state.quote[key === "cheap" ? "cheap_max" : "typical"] || 0);
      });
    });

    $("#watch-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!state.quote) return;
      const threshold = Math.round(Number($("#threshold").value));
      if (!Number.isFinite(threshold) || threshold < 1) {
        toast("Введите порог числом, например 12000");
        return;
      }
      try {
        await api("/api/watches", {
          method: "POST",
          body: JSON.stringify({
            origin: state.quote.origin,
            destination: state.quote.destination,
            max_price: threshold,
            depart_date: state.depart || null,
            return_date: state.returnDate || null,
            adults: state.adults,
            children: state.children,
            infants: state.infants,
          }),
        });
        toast("Подписка создана");
        if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        switchTab("watches");
      } catch (err) {
        toast(err.message);
      }
    });

    $("#watches").addEventListener("click", async (e) => {
      const id = e.target && e.target.getAttribute("data-del");
      if (!id) return;
      try {
        await api("/api/watches/" + id, { method: "DELETE" });
        toast("Удалено");
        loadWatches();
      } catch (err) {
        toast(err.message);
      }
    });

    $("#refresh-watches").addEventListener("click", loadWatches);
    syncPaxUi();

    api("/api/me").then(() => setBoot("Готово")).catch((err) => {
      setBoot("Auth: " + err.message);
      toast(err.message);
    });
  } catch (err) {
    setBoot("Ошибка UI: " + (err && err.message ? err.message : String(err)));
  }
})();
