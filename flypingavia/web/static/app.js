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

    (function flyPlane() {
      const el = document.getElementById("plane");
      if (!el) return;
      const size = 36;
      const pad = 12;
      let x = pad + Math.random() * Math.max(40, window.innerWidth - size - pad * 2);
      let y = pad + 24 + Math.random() * Math.max(40, window.innerHeight * 0.45);
      let vx = (0.8 + Math.random() * 1.2) * (Math.random() < 0.5 ? -1 : 1);
      let vy = (Math.random() - 0.5) * 1.2;
      let angle = 0;
      let nextTurn = 0;
      let last = performance.now();

      function bounds() {
        return {
          minX: pad,
          maxX: Math.max(pad + 1, window.innerWidth - size - pad),
          minY: pad + 8,
          maxY: Math.max(pad + 9, window.innerHeight - size - pad - 24),
        };
      }

      function clampSpeed() {
        const speed = Math.hypot(vx, vy) || 1;
        const target = 1.0 + Math.random() * 1.4;
        const desired = Math.max(0.85, Math.min(2.4, speed));
        const mix = 0.35;
        const s = desired * (1 - mix) + target * mix;
        vx = (vx / speed) * s;
        vy = (vy / speed) * s;
      }

      function wander(t) {
        if (t < nextTurn) return;
        nextTurn = t + 700 + Math.random() * 1800;
        // лёгкий поворот «по кругу»
        const turn = (Math.random() < 0.55 ? 1 : -1) * (0.35 + Math.random() * 0.9);
        const nx = vx * Math.cos(turn) - vy * Math.sin(turn);
        const ny = vx * Math.sin(turn) + vy * Math.cos(turn);
        vx = nx + (Math.random() - 0.5) * 0.4;
        vy = ny + (Math.random() - 0.5) * 0.4;
        clampSpeed();
      }

      function steerInside(b) {
        const margin = 56;
        const cx = (b.minX + b.maxX) / 2;
        const cy = (b.minY + b.maxY) / 2;
        if (x < b.minX + margin) vx += 0.12;
        if (x > b.maxX - margin) vx -= 0.12;
        if (y < b.minY + margin) vy += 0.12;
        if (y > b.maxY - margin) vy -= 0.12;
        // мягко тянем к центру, чтобы кружил по экрану
        vx += (cx - x) * 0.00035;
        vy += (cy - y) * 0.00035;
      }

      function bounce(b) {
        if (x < b.minX) { x = b.minX; vx = Math.abs(vx) + 0.15; }
        if (x > b.maxX) { x = b.maxX; vx = -Math.abs(vx) - 0.15; }
        if (y < b.minY) { y = b.minY; vy = Math.abs(vy) + 0.15; }
        if (y > b.maxY) { y = b.maxY; vy = -Math.abs(vy) - 0.15; }
      }

      function frame(now) {
        const dt = Math.min(0.05, (now - last) / 1000);
        last = now;
        const b = bounds();
        wander(now);
        steerInside(b);

        x += vx * dt * 60;
        y += vy * dt * 60;
        bounce(b);

        const speed = Math.hypot(vx, vy) || 1;
        if (speed > 2.6) { vx *= 2.4 / speed; vy *= 2.4 / speed; }
        if (speed < 0.7) { vx *= 0.9 / speed; vy *= 0.9 / speed; }

        const targetAngle = Math.atan2(vy, vx) * 180 / Math.PI;
        let delta = targetAngle - angle;
        while (delta > 180) delta -= 360;
        while (delta < -180) delta += 360;
        angle += delta * Math.min(1, dt * 7);
        const bank = Math.max(-22, Math.min(22, -vy * 12));

        el.style.transform =
          "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px) rotate(" +
          angle.toFixed(1) + "deg) rotate(" + bank.toFixed(1) + "deg)";

        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);

      document.addEventListener("visibilitychange", () => {
        el.style.opacity = document.hidden ? "0" : "0.7";
      });
      window.addEventListener("resize", () => {
        const b = bounds();
        x = Math.min(b.maxX, Math.max(b.minX, x));
        y = Math.min(b.maxY, Math.max(b.minY, y));
      });
    })();

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
      flexibilityDays: 0,
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
        const err = new Error(
          typeof detail === "string"
            ? detail
            : (detail && detail.message) || data.message || ("Ошибка " + res.status)
        );
        err.status = res.status;
        if (detail && typeof detail === "object") err.detail = detail;
        throw err;
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
      const dateBits = [];
      if (q.depart_date) dateBits.push(q.depart_date);
      if (q.return_date) dateBits.push("⇄ " + q.return_date);
      box.classList.remove("hidden");
      box.innerHTML =
        "<h2>" + q.origin_name + " → " + q.destination_name + "</h2>" +
        "<div class=\"meta\">" + tripLabel + (dateBits.length ? " · " + dateBits.join(" ") : "") + "</div>" +
        "<div class=\"price-now\">" + (q.price != null ? money(q.price) : "—") + "</div>" +
        (lvl[0]
          ? ("<div class=\"level " + lvl[0] + "\">относительно рынка · " + lvl[1] + "</div>")
          : "") +
        "<div class=\"meta\">" +
          (q.origin_airport ? ("вылет " + q.origin_airport) : "") +
          (q.destination_airport ? (" · прилёт " + q.destination_airport) : "") +
          (q.transfers === 0 ? " · прямой" : (q.transfers != null ? (" · пересадок: " + q.transfers) : "")) +
          (q.airline ? (" · " + q.airline) : "") +
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
          const flex = Number(w.flexibility_days || 0);
          const flexLabel = flex > 0 ? (" · гибкость ±" + flex + " дн.") : "";
          return (
            "<article class=\"watch-card\" data-id=\"" + w.id + "\">" +
              "<h3>" + (w.origin_name || w.origin) + " → " + (w.destination_name || w.destination) + "</h3>" +
              "<div class=\"meta\">" + trip + flexLabel + "</div>" +
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
        params.set("flexibility_days", String(state.flexibilityDays || 0));
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
        hideLowThresholdWarn();
      });
    });

    function hideLowThresholdWarn() {
      const box = $("#low-threshold-warn");
      if (box) box.classList.add("hidden");
    }

    function showLowThresholdWarn(detail) {
      const box = $("#low-threshold-warn");
      const text = $("#low-threshold-text");
      if (!box || !text) return;
      const thr = money(detail.threshold);
      const cheap = money(detail.cheap_max);
      text.textContent =
        "Вы выбрали: " + thr + ". Дешёвая цена по текущим данным: до " + cheap +
        ". С таким порогом уведомление может долго не прийти.";
      box.classList.remove("hidden");
    }

    function syncFlexUi() {
      $$(".flex-btn").forEach((b) => {
        b.classList.toggle("active", Number(b.getAttribute("data-flex")) === state.flexibilityDays);
      });
      const hint = $("#flex-hint");
      if (!hint) return;
      if (!state.flexibilityDays) {
        hint.textContent = "Ищем только выбранную дату вылета.";
      } else if (state.trip === "round") {
        hint.textContent =
          "Обе даты сдвигаются вместе (±" + state.flexibilityDays +
          " дн.), длительность поездки сохраняется.";
      } else {
        hint.textContent = "Ищем билеты в окне ±" + state.flexibilityDays + " дня вокруг выбранной даты.";
      }
    }

    $$(".flex-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.flexibilityDays = Number(btn.getAttribute("data-flex")) || 0;
        syncFlexUi();
        hideLowThresholdWarn();
      });
    });
    syncFlexUi();

    async function createWatch(threshold, confirmLow) {
      return api("/api/watches", {
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
          confirm_low_threshold: !!confirmLow,
          flexibility_days: state.flexibilityDays || 0,
        }),
      });
    }

    $("#watch-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!state.quote) return;
      const threshold = Math.round(Number($("#threshold").value));
      if (!Number.isFinite(threshold) || threshold < 1) {
        toast("Введите порог числом, например 12000");
        return;
      }
      hideLowThresholdWarn();
      try {
        await createWatch(threshold, false);
        toast("Подписка создана");
        if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        switchTab("watches");
      } catch (err) {
        if (
          err.status === 409 &&
          err.detail &&
          err.detail.code === "LOW_THRESHOLD_CONFIRMATION_REQUIRED"
        ) {
          showLowThresholdWarn(err.detail);
          return;
        }
        toast(err.message);
      }
    });

    const confirmBtn = $("#low-threshold-confirm");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", async () => {
        if (!state.quote) return;
        const threshold = Math.round(Number($("#threshold").value));
        try {
          await createWatch(threshold, true);
          hideLowThresholdWarn();
          toast("Подписка создана");
          if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          switchTab("watches");
        } catch (err) {
          toast(err.message);
        }
      });
    }

    const editBtn = $("#low-threshold-edit");
    if (editBtn) {
      editBtn.addEventListener("click", () => {
        hideLowThresholdWarn();
        const input = $("#threshold");
        if (input) {
          input.focus();
          input.select();
        }
      });
    }

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
