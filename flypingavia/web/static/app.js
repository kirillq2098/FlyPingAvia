(() => {
  // --- Crash-safe boot (WA-03) ---
  function setBoot(msg) {
    try {
      const el = document.getElementById("boot");
      if (el) el.textContent = String(msg || "");
    } catch (_) {}
  }

  window.addEventListener("error", (e) => {
    setBoot("JS error: " + (e && e.message ? e.message : "unknown"));
  });
  window.addEventListener("unhandledrejection", (e) => {
    const r = e && e.reason;
    setBoot("Promise error: " + (r && r.message ? r.message : String(r || "unknown")));
  });

  try {
    setBoot("JS loaded");

    const bootEl = document.getElementById("boot");
    if (bootEl) {
      setTimeout(() => {
        if (bootEl.textContent === "JS loaded") bootEl.textContent = "";
      }, 1200);
    }

    // Decorative plane — isolated, never blocks app
    (function startPlane() {
      const el = document.getElementById("plane");
      if (!el) return;
      const reduce =
        window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) {
        el.style.display = "none";
        return;
      }

      let x = 40 + Math.random() * 120;
      let y = 80 + Math.random() * 160;
      let angle = -20 + Math.random() * 40;
      let speed = 38;
      let last = performance.now();
      let nextTurn = last + 1800 + Math.random() * 2200;

      function bounds() {
        const pad = 28;
        return {
          minX: pad,
          minY: pad,
          maxX: Math.max(pad + 1, window.innerWidth - pad),
          maxY: Math.max(pad + 1, window.innerHeight - pad),
        };
      }

      function frame(now) {
        const dt = Math.min(0.05, (now - last) / 1000);
        last = now;
        const b = bounds();

        if (now >= nextTurn) {
          angle += -55 + Math.random() * 110;
          speed = 28 + Math.random() * 26;
          nextTurn = now + 1400 + Math.random() * 2600;
        }

        const rad = (angle * Math.PI) / 180;
        x += Math.cos(rad) * speed * dt;
        y += Math.sin(rad) * speed * dt;

        let bounced = false;
        if (x < b.minX) {
          x = b.minX;
          angle = 180 - angle;
          bounced = true;
        }
        if (x > b.maxX) {
          x = b.maxX;
          angle = 180 - angle;
          bounced = true;
        }
        if (y < b.minY) {
          y = b.minY;
          angle = -angle;
          bounced = true;
        }
        if (y > b.maxY) {
          y = b.maxY;
          angle = -angle;
          bounced = true;
        }
        if (bounced) nextTurn = now + 900 + Math.random() * 1200;

        const cx = window.innerWidth / 2;
        const cy = window.innerHeight / 2;
        const dx = cx - x;
        const dy = cy - y;
        const dist = Math.hypot(dx, dy) || 1;
        const pull = Math.min(0.55, dist / 900);
        const vx = Math.cos(rad) * speed + (dx / dist) * pull * 18;
        const vy = Math.sin(rad) * speed + (dy / dist) * pull * 18;
        const targetAngle = (Math.atan2(vy, vx) * 180) / Math.PI;
        let delta = targetAngle - angle;
        while (delta > 180) delta -= 360;
        while (delta < -180) delta += 360;
        angle += delta * Math.min(1, dt * 7);
        const bank = Math.max(-22, Math.min(22, -vy * 12));

        el.style.transform =
          "translate(" +
          x.toFixed(1) +
          "px," +
          y.toFixed(1) +
          "px) rotate(" +
          angle.toFixed(1) +
          "deg) rotate(" +
          bank.toFixed(1) +
          "deg)";

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
      health: null,
      me: null,
      uiStarted: false,
      themeListenerBound: false,
      formListenersBound: false,
      closingConfirmation: false,
    };
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => Array.prototype.slice.call(document.querySelectorAll(sel));

    function toast(text) {
      const el = $("#toast");
      if (!el) return;
      el.textContent = text;
      el.classList.remove("hidden");
      clearTimeout(toast._t);
      toast._t = setTimeout(() => el.classList.add("hidden"), 2800);
      haptic("light");
    }

    function haptic(type) {
      try {
        const tg = getTelegramWebApp();
        const hf = tg && tg.HapticFeedback;
        if (!hf) return;
        if (type === "success" && typeof hf.notificationOccurred === "function") {
          hf.notificationOccurred("success");
        } else if (type === "error" && typeof hf.notificationOccurred === "function") {
          hf.notificationOccurred("error");
        } else if (typeof hf.impactOccurred === "function") {
          hf.impactOccurred(type === "medium" ? "medium" : "light");
        }
      } catch (_) {}
    }

    function clearMainButton() {
      try {
        const tg = getTelegramWebApp();
        const mb = tg && tg.MainButton;
        if (!mb) return;
        if (state._mainBtnHandler && typeof mb.offClick === "function") {
          mb.offClick(state._mainBtnHandler);
        }
        state._mainBtnHandler = null;
        if (typeof mb.hide === "function") mb.hide();
      } catch (_) {}
    }

    function syncMainButton() {
      const tg = getTelegramWebApp();
      const mb = tg && tg.MainButton;
      if (!mb) return;
      const watchForm = $("#watch-form");
      const searchPanel = $("#panel-search");
      const show =
        searchPanel &&
        searchPanel.classList.contains("active") &&
        watchForm &&
        !watchForm.classList.contains("hidden");
      clearMainButton();
      if (!show) return;
      try {
        if (typeof mb.setText === "function") mb.setText("Создать подписку");
        if (typeof mb.show === "function") mb.show();
        state._mainBtnHandler = function () {
          const submit = $("#watch-submit");
          if (submit) submit.click();
        };
        if (typeof mb.onClick === "function") mb.onClick(state._mainBtnHandler);
      } catch (_) {}
    }

    function showUserChip(me) {
      const chip = $("#user-chip");
      if (!chip || !me) return;
      const name = me.first_name || me.username || "";
      const nameEl = $("#user-name");
      const av = $("#user-avatar");
      if (nameEl) nameEl.textContent = name || "FlyPing";
      if (av) {
        const initials = name
          ? String(name)
              .split(/\s+/)
              .map((p) => p[0])
              .join("")
              .slice(0, 2)
              .toUpperCase()
          : "FP";
        av.textContent = initials || "FP";
      }
      chip.classList.remove("hidden");
    }

    function setFieldError(id, message) {
      const err = $("#" + id + "-error");
      const field = err && err.closest ? err.closest(".field") : null;
      if (err) err.textContent = message || "";
      if (field) field.classList.toggle("invalid", !!message);
    }

    function escapeHtml(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function getTelegramWebApp() {
      try {
        return window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
      } catch (_) {
        return null;
      }
    }

    function getInitData() {
      const tg = getTelegramWebApp();
      return (tg && tg.initData) || "";
    }

    /** True when launched inside Telegram WebView (even before initData is ready). */
    function isInsideTelegramWebView() {
      const tg = getTelegramWebApp();
      if (tg) {
        if (tg.initData) return true;
        try {
          const unsafe = tg.initDataUnsafe;
          if (unsafe && (unsafe.user || unsafe.query_id || unsafe.hash)) return true;
        } catch (_) {}
        // Outside Telegram the SDK still loads; platform stays "unknown".
        const platform = String(tg.platform || "").toLowerCase();
        if (platform && platform !== "unknown") return true;
      }
      try {
        const hash = String(location.hash || "");
        if (hash.indexOf("tgWebAppData=") >= 0 || hash.indexOf("tgWebAppVersion=") >= 0) {
          return true;
        }
      } catch (_) {}
      try {
        if (/Telegram/i.test(String(navigator.userAgent || ""))) return true;
      } catch (_) {}
      return false;
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    /** Wait briefly for Telegram SDK to populate initData (CDN race / WebView). */
    async function waitForInitData(maxMs) {
      maxMs = typeof maxMs === "number" ? maxMs : 2500;
      const started = Date.now();
      let data = getInitData();
      if (data) return data;
      while (Date.now() - started < maxMs) {
        await sleep(50);
        data = getInitData();
        if (data) return data;
      }
      return getInitData();
    }

    function clearUserDataUi() {
      state.quote = null;
      state.me = null;
      const watches = $("#watches");
      if (watches) watches.innerHTML = "";
      const quote = $("#quote");
      if (quote) {
        quote.classList.add("hidden");
        quote.innerHTML = "";
      }
      const watchForm = $("#watch-form");
      if (watchForm) watchForm.classList.add("hidden");
      const chip = $("#user-chip");
      if (chip) chip.classList.add("hidden");
      hideLowThresholdWarn();
      setClosingConfirmation(false);
      clearMainButton();
    }

    function showAuthGate(title, message, botLink) {
      const gate = $("#auth-gate");
      document.body.classList.add("auth-locked");
      if (!gate) {
        toast(message || title);
        return;
      }
      const titleEl = $("#auth-title");
      const msgEl = $("#auth-message");
      const botBtn = $("#auth-bot-link");
      const siteLink = $("#auth-site-link");
      if (titleEl) titleEl.textContent = title || "FlyPing работает внутри Telegram";
      if (msgEl) {
        msgEl.textContent =
          message || "Откройте бота и нажмите кнопку «Открыть FlyPing».";
      }
      // Inside Telegram WebView never offer a bot deep-link loop.
      const allowBotLink = !!botLink && !isInsideTelegramWebView();
      if (botBtn) {
        if (allowBotLink) {
          botBtn.href = botLink;
          botBtn.classList.remove("hidden");
        } else {
          botBtn.classList.add("hidden");
          botBtn.removeAttribute("href");
        }
      }
      if (siteLink) {
        // Site link is browser-fallback helper; hide inside Telegram.
        if (isInsideTelegramWebView()) siteLink.classList.add("hidden");
        else siteLink.classList.remove("hidden");
      }
      gate.classList.remove("hidden");
      clearUserDataUi();
      clearMainButton();
    }

    function hideAuthGate() {
      const gate = $("#auth-gate");
      if (gate) gate.classList.add("hidden");
      document.body.classList.remove("auth-locked");
    }

    function applyTelegramTheme(tg) {
      if (!tg) return;
      const root = document.documentElement;
      const scheme =
        (tg.colorScheme ||
          (tg.themeParams && tg.themeParams.bg_color && isDarkHex(tg.themeParams.bg_color)
            ? "dark"
            : "light")) === "dark"
          ? "dark"
          : "light";
      root.setAttribute("data-tg-color-scheme", scheme);
      root.classList.toggle("theme-dark", scheme === "dark");
      try {
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", scheme === "dark" ? "#07111F" : "#F7F8FA");
      } catch (_) {}
      // Keep Telegram CSS vars for compatibility; brand tokens stay primary.
      const tp = tg.themeParams || {};
      const map = [
        ["--tg-bg-color", tp.bg_color, scheme === "dark" ? "#07111f" : "#f7f8fa"],
        ["--tg-text-color", tp.text_color, scheme === "dark" ? "#f4f7fb" : "#0a0b0d"],
        ["--tg-hint-color", tp.hint_color, scheme === "dark" ? "#8b95a7" : "#5c6570"],
        ["--tg-link-color", tp.link_color, "#0b4db8"],
        ["--tg-button-color", tp.button_color, "#0b4db8"],
        ["--tg-button-text-color", tp.button_text_color, "#ffffff"],
        ["--tg-secondary-bg-color", tp.secondary_bg_color, scheme === "dark" ? "#0d1829" : "#ffffff"],
        ["--tg-destructive-text-color", tp.destructive_text_color, "#c53030"],
      ];
      map.forEach((row) => {
        root.style.setProperty(row[0], row[1] || row[2]);
      });
    }

    function isDarkHex(hex) {
      try {
        const h = String(hex || "").replace("#", "");
        if (h.length < 6) return false;
        const r = parseInt(h.slice(0, 2), 16);
        const g = parseInt(h.slice(2, 4), 16);
        const b = parseInt(h.slice(4, 6), 16);
        return (r * 299 + g * 587 + b * 114) / 1000 < 128;
      } catch (_) {
        return false;
      }
    }

    function bindThemeListener(tg) {
      if (!tg || state.themeListenerBound || typeof tg.onEvent !== "function") return;
      tg.onEvent("themeChanged", () => applyTelegramTheme(tg));
      state.themeListenerBound = true;
    }

    function setClosingConfirmation(enabled) {
      const tg = getTelegramWebApp();
      if (!tg) return;
      try {
        if (enabled && !state.closingConfirmation && typeof tg.enableClosingConfirmation === "function") {
          tg.enableClosingConfirmation();
          state.closingConfirmation = true;
        } else if (!enabled && state.closingConfirmation && typeof tg.disableClosingConfirmation === "function") {
          tg.disableClosingConfirmation();
          state.closingConfirmation = false;
        }
      } catch (_) {}
    }

    function updateDirtyClosingConfirmation() {
      const origin = ($("#origin") && $("#origin").value.trim()) || "";
      const destination = ($("#destination") && $("#destination").value.trim()) || "";
      const depart = ($("#depart") && $("#depart").value) || "";
      const threshold = ($("#threshold") && $("#threshold").value) || "";
      const dirty =
        !!origin ||
        !!destination ||
        !!depart ||
        !!state.quote ||
        (threshold && Number(threshold) > 0);
      setClosingConfirmation(dirty);
    }

    async function apiFetch(path, options) {
      options = options || {};
      if (typeof path !== "string" || path.indexOf("/api/") !== 0) {
        throw new Error("apiFetch только для same-origin /api/...");
      }
      const headers = Object.assign({}, options.headers || {});
      if (options.body && !headers["Content-Type"] && !headers["content-type"]) {
        headers["Content-Type"] = "application/json";
      }
      const initData = getInitData();
      if (initData) {
        headers["Authorization"] = "tma " + initData;
      }
      const res = await fetch(path, {
        method: options.method || "GET",
        headers: headers,
        body: options.body,
      });
      let data = {};
      try {
        data = await res.json();
      } catch (_) {}
      if (res.status === 401) {
        const detail = data && data.detail;
        const code = detail && typeof detail === "object" ? detail.code : "";
        const message =
          detail && typeof detail === "object" && detail.message
            ? detail.message
            : typeof detail === "string"
              ? detail
              : "Сессия Telegram недоступна. Закройте и снова откройте приложение.";
        const botLink =
          state.health && state.health.telegram_bot_link
            ? state.health.telegram_bot_link
            : "";
        // Browser-only fallback: never show t.me loop when already in Telegram.
        const gateBotLink = isInsideTelegramWebView() ? "" : botLink;
        showAuthGate(
          code === "MISSING_INIT_DATA"
            ? "FlyPing работает внутри Telegram"
            : "Нужно открыть приложение заново",
          isInsideTelegramWebView()
            ? "Сессия Telegram недоступна. Закройте Mini App и откройте снова через кнопку бота."
            : message,
          gateBotLink
        );
        const err = new Error(message);
        err.status = 401;
        err.auth = true;
        if (detail && typeof detail === "object") err.detail = detail;
        throw err;
      }
      if (!res.ok) {
        const detail = data.detail;
        const err = new Error(
          typeof detail === "string"
            ? detail
            : (detail && detail.message) || data.message || "Ошибка " + res.status
        );
        err.status = res.status;
        if (detail && typeof detail === "object") err.detail = detail;
        throw err;
      }
      return data;
    }

    // Back-compat alias used by UI handlers
    const api = apiFetch;

    function money(v) {
      return Math.round(Number(v)).toLocaleString("ru-RU") + " ₽";
    }

    // TR-04: бизнес-таймзона продукта (не timezone устройства)
    let displayTimezone = "Europe/Moscow";

    function _partsInTz(dateObj, timeZone) {
      try {
        const fmt = new Intl.DateTimeFormat("en-GB", {
          timeZone: timeZone,
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        });
        const map = {};
        fmt.formatToParts(dateObj).forEach((p) => {
          if (p.type !== "literal") map[p.type] = p.value;
        });
        return {
          year: Number(map.year),
          month: Number(map.month),
          day: Number(map.day),
          hour: Number(map.hour),
          minute: Number(map.minute),
        };
      } catch (_) {
        return null;
      }
    }

    function _minutesWord(n) {
      const nAbs = Math.abs(n) % 100;
      const n1 = nAbs % 10;
      if (nAbs >= 11 && nAbs <= 14) return "минут";
      if (n1 === 1) return "минуту";
      if (n1 >= 2 && n1 <= 4) return "минуты";
      return "минут";
    }

    function _hoursWord(n) {
      const nAbs = Math.abs(n) % 100;
      const n1 = nAbs % 10;
      if (nAbs >= 11 && nAbs <= 14) return "часов";
      if (n1 === 1) return "час";
      if (n1 >= 2 && n1 <= 4) return "часа";
      return "часов";
    }

    const _MONTHS_GEN = [
      "января",
      "февраля",
      "марта",
      "апреля",
      "мая",
      "июня",
      "июля",
      "августа",
      "сентября",
      "октября",
      "ноября",
      "декабря",
    ];

    function formatLastChecked(iso, nowMs, timeZone) {
      if (iso == null || iso === "") return "Ещё не проверяли";
      const checked = new Date(iso);
      if (Number.isNaN(checked.getTime())) return "Ещё не проверяли";
      const tz = timeZone || displayTimezone || "Europe/Moscow";
      const now = new Date(nowMs != null ? nowMs : Date.now());
      let deltaMs = now.getTime() - checked.getTime();
      if (deltaMs < 0 && deltaMs > -120000) deltaMs = 0;
      if (deltaMs < -120000) {
        const far = _partsInTz(checked, tz);
        if (!far) return "Ещё не проверяли";
        const hh = String(far.hour).padStart(2, "0");
        const mm = String(far.minute).padStart(2, "0");
        return (
          "Проверено " +
          far.day +
          " " +
          _MONTHS_GEN[far.month - 1] +
          " в " +
          hh +
          ":" +
          mm
        );
      }
      const secs = deltaMs / 1000;
      if (secs < 60) return "Проверено только что";
      if (secs < 3600) {
        const m = Math.max(1, Math.floor(secs / 60));
        return "Проверено " + m + " " + _minutesWord(m) + " назад";
      }
      const localC = _partsInTz(checked, tz);
      const localN = _partsInTz(now, tz);
      if (!localC || !localN) return "Ещё не проверяли";
      const hh = String(localC.hour).padStart(2, "0");
      const mm = String(localC.minute).padStart(2, "0");
      const dayKey = (p) => p.year * 10000 + p.month * 100 + p.day;
      const todayKey = dayKey(localN);
      const checkedKey = dayKey(localC);
      const yest = new Date(Date.UTC(localN.year, localN.month - 1, localN.day));
      yest.setUTCDate(yest.getUTCDate() - 1);
      const yestKey =
        yest.getUTCFullYear() * 10000 +
        (yest.getUTCMonth() + 1) * 100 +
        yest.getUTCDate();
      if (secs < 12 * 3600 && checkedKey === todayKey) {
        const h = Math.max(1, Math.floor(secs / 3600));
        return "Проверено " + h + " " + _hoursWord(h) + " назад";
      }
      if (checkedKey === todayKey) return "Проверено сегодня в " + hh + ":" + mm;
      if (checkedKey === yestKey) return "Проверено вчера в " + hh + ":" + mm;
      return (
        "Проверено " +
        localC.day +
        " " +
        _MONTHS_GEN[localC.month - 1] +
        " в " +
        hh +
        ":" +
        mm
      );
    }

    function levelLabel(level) {
      if (level === "cheap") return ["cheap", "дёшево"];
      if (level === "expensive") return ["expensive", "дорого"];
      if (level === "normal") return ["normal", "обычно"];
      return ["", "нет оценки"];
    }

    function syncPaxUi() {
      const adultsEl = $("#adults-val");
      if (!adultsEl) return;
      adultsEl.textContent = String(state.adults);
      $("#children-val").textContent = String(state.children);
      $("#infants-val").textContent = String(state.infants);
    }

    function setTrip(trip) {
      state.trip = trip;
      $$(".trip-btn").forEach((b) =>
        b.classList.toggle("active", b.getAttribute("data-trip") === trip)
      );
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
      updateDirtyClosingConfirmation();
    }

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
        "Вы выбрали: " +
        thr +
        ". Дешёвая цена по текущим данным: до " +
        cheap +
        ". С таким порогом уведомление может долго не прийти.";
      box.classList.remove("hidden");
    }

    function renderQuote(q) {
      state.quote = q;
      const box = $("#quote");
      const lvl = levelLabel(q.level);
      const tripLabel = q.return_date ? "туда-обратно" : "в одну сторону";
      const dateBits = [];
      if (q.depart_date) dateBits.push(q.depart_date);
      if (q.return_date) dateBits.push("⇄ " + q.return_date);
      const originCode = escapeHtml(q.origin || "");
      const destCode = escapeHtml(q.destination || "");
      box.classList.remove("hidden");
      box.innerHTML =
        '<div class="route-row">' +
        '<div><div class="airport-code code">' +
        originCode +
        '</div><div class="city">' +
        escapeHtml(q.origin_name || q.origin) +
        "</div></div>" +
        '<div class="route-line" aria-hidden="true"></div>' +
        '<div style="text-align:right"><div class="airport-code code">' +
        destCode +
        '</div><div class="city">' +
        escapeHtml(q.destination_name || q.destination) +
        "</div></div>" +
        "</div>" +
        '<div class="meta mono">' +
        tripLabel +
        (dateBits.length ? " · " + escapeHtml(dateBits.join(" ")) : "") +
        "</div>" +
        '<div class="price-now">' +
        (q.price != null ? money(q.price) : "—") +
        "</div>" +
        (lvl[0]
          ? '<div class="level ' + lvl[0] + '">относительно рынка · ' + lvl[1] + "</div>"
          : "") +
        '<div class="meta">' +
        (q.origin_airport ? "вылет " + escapeHtml(q.origin_airport) : "") +
        (q.destination_airport ? " · прилёт " + escapeHtml(q.destination_airport) : "") +
        (q.transfers === 0
          ? " · прямой"
          : q.transfers != null
            ? " · пересадок: " + q.transfers
            : "") +
        (q.airline ? " · " + escapeHtml(q.airline) : "") +
        "</div>" +
        (q.airports_note ? '<div class="meta">' + escapeHtml(q.airports_note) + "</div>" : "") +
        '<div class="band">' +
        '<div class="band-row cheap"><span>дёшево</span><span>≤ ' +
        money(q.cheap_max) +
        "</span></div>" +
        '<div class="band-row typical"><span>обычно</span><span>~ ' +
        money(q.typical) +
        "</span></div>" +
        '<div class="band-row expensive"><span>дорого</span><span>≥ ' +
        money(q.expensive_min) +
        "</span></div>" +
        "</div>" +
        '<div style="margin-top:12px"><a class="btn ghost" href="' +
        escapeHtml(q.tickets_url) +
        '" target="_blank" rel="noopener">Смотреть билеты</a></div>';
      $("#watch-form").classList.remove("hidden");
      $("#threshold").value = Math.round(q.cheap_max || q.price || 0);
      updateDirtyClosingConfirmation();
      syncMainButton();
    }

    async function resolveHint(inputId, hintId) {
      const q = $(inputId).value.trim();
      const hint = $(hintId);
      if (q.length < 2) {
        hint.textContent = "";
        return;
      }
      try {
        const items = await api("/api/resolve?q=" + encodeURIComponent(q));
        if (!items.length) {
          hint.textContent = "не найдено";
          return;
        }
        const top = items[0];
        hint.textContent =
          top.airports.length > 1
            ? top.label + " · " + top.airports.length + " а/п → самый дешёвый"
            : top.label;
      } catch (_) {
        hint.textContent = "";
      }
    }

    function switchTab(name) {
      $$(".tab").forEach((b) => {
        const on = b.getAttribute("data-tab") === name;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      $$(".panel").forEach((p) =>
        p.classList.toggle("active", p.id === "panel-" + name)
      );
      if (name === "watches") {
        clearMainButton();
        loadWatches();
      } else {
        syncMainButton();
      }
    }

    function logoSvgTiny() {
      return (
        '<svg class="deco" viewBox="0 0 22 22" fill="none" aria-hidden="true">' +
        '<circle cx="4" cy="18" r="2.2" fill="#0B4DB8"/>' +
        '<path d="M5.8 16.4 C9 12.2, 13.2 7.4, 18.5 4.2" stroke="#0B4DB8" stroke-width="1.6" stroke-linecap="round" fill="none"/>' +
        '<circle cx="18.5" cy="4.2" r="2.2" fill="#0B4DB8" opacity="0.9"/>' +
        '<circle cx="18.5" cy="4.2" r="4.4" stroke="#0B4DB8" stroke-width="1" fill="none" opacity="0.35"/>' +
        "</svg>"
      );
    }

    async function loadWatches() {
      const box = $("#watches");
      if (!box) return;
      box.innerHTML =
        '<div class="skeleton" aria-busy="true" aria-label="Загрузка подписок">' +
        '<div class="skeleton-card"></div><div class="skeleton-card"></div>' +
        "</div>";
      try {
        const items = await api("/api/watches");
        if (!items.length) {
          box.innerHTML =
            '<div class="empty-state empty-onboarding">' +
            logoSvgTiny() +
            "<h2>Пока нет подписок</h2>" +
            '<p class="meta">Настройте поездку один раз — FlyPing будет проверять цену за вас.</p>' +
            '<button class="btn primary" type="button" data-empty-create="1">Создать подписку</button>' +
            "</div>";
          return;
        }
        box.innerHTML = items
          .map((w) => {
            const trip = w.return_date ? "туда-обратно" : "в одну сторону";
            const flex = Number(w.flexibility_days || 0);
            const flexLabel = flex > 0 ? " · гибкость ±" + flex + " дн." : "";
            const priceLine = w.last_price != null ? money(w.last_price) : null;
            const checkedLine = formatLastChecked(w.last_checked_at);
            const originCode = escapeHtml(w.origin || "");
            const destCode = escapeHtml(w.destination || "");
            return (
              '<article class="watch-card" data-id="' +
              w.id +
              '">' +
              '<div class="route-row">' +
              '<div><div class="airport-code code">' +
              originCode +
              '</div><div class="city">' +
              escapeHtml(w.origin_name || w.origin) +
              "</div></div>" +
              '<div class="route-line" aria-hidden="true"></div>' +
              '<div style="text-align:right"><div class="airport-code code">' +
              destCode +
              '</div><div class="city">' +
              escapeHtml(w.destination_name || w.destination) +
              "</div></div>" +
              "</div>" +
              '<div class="meta mono">' +
              trip +
              flexLabel +
              "</div>" +
              '<div class="threshold">порог ' +
              money(w.max_price) +
              "</div>" +
              (priceLine != null
                ? '<div class="price-line">сейчас: <span class="mono">' +
                  priceLine +
                  "</span>" +
                  (w.last_origin_airport
                    ? " · вылет " + escapeHtml(w.last_origin_airport)
                    : "") +
                  "</div>"
                : "") +
              '<div class="meta">' +
              escapeHtml(checkedLine) +
              "</div>" +
              '<div class="actions">' +
              '<a class="btn ghost" href="' +
              escapeHtml(w.tickets_url) +
              '" target="_blank" rel="noopener">Билеты</a>' +
              '<button class="btn ghost" data-share="' +
              w.id +
              '" type="button">Поделиться</button>' +
              '<button class="btn ghost" data-del="' +
              w.id +
              '" type="button" aria-label="Удалить подписку">Удалить</button>' +
              "</div>" +
              "</article>"
            );
          })
          .join("");
      } catch (err) {
        if (err && err.auth) return;
        box.innerHTML =
          '<div class="error-state">' +
          "<h2>Не удалось загрузить</h2>" +
          '<p class="meta">' +
          escapeHtml(err.message || "Попробуйте ещё раз") +
          "</p>" +
          '<button class="btn primary" type="button" data-retry-watches="1">Повторить</button>' +
          "</div>";
      }
    }

    function syncFlexUi() {
      $$(".flex-btn").forEach((b) => {
        b.classList.toggle(
          "active",
          Number(b.getAttribute("data-flex")) === state.flexibilityDays
        );
      });
      const hint = $("#flex-hint");
      if (!hint) return;
      if (!state.flexibilityDays) {
        hint.textContent = "Ищем только выбранную дату вылета.";
      } else if (state.trip === "round") {
        hint.textContent =
          "Обе даты сдвигаются вместе (±" +
          state.flexibilityDays +
          " дн.), длительность поездки сохраняется.";
      } else {
        hint.textContent =
          "Ищем билеты в окне ±" + state.flexibilityDays + " дня вокруг выбранной даты.";
      }
    }

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

    function bindUiOnce() {
      if (state.formListenersBound) return;
      state.formListenersBound = true;

      $$(".tab").forEach((btn) =>
        btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")))
      );

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
        updateDirtyClosingConfirmation();
      });
      $("#destination").addEventListener("input", () => {
        clearTimeout(destTimer);
        destTimer = setTimeout(
          () => resolveHint("#destination", "#destination-hint"),
          280
        );
        updateDirtyClosingConfirmation();
      });
      $("#depart").addEventListener("change", () => {
        state.depart = $("#depart").value || "";
        if (state.trip === "round" && state.depart && !state.returnDate) {
          const d = new Date(state.depart + "T12:00:00");
          d.setDate(d.getDate() + 7);
          state.returnDate = d.toISOString().slice(0, 10);
          $("#return").value = state.returnDate;
        }
        updateDirtyClosingConfirmation();
      });
      $("#return").addEventListener("change", () => {
        state.returnDate = $("#return").value || "";
        updateDirtyClosingConfirmation();
      });
      const thresholdEl = $("#threshold");
      if (thresholdEl) {
        thresholdEl.addEventListener("input", updateDirtyClosingConfirmation);
      }

      $("#search-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = $("#search-btn");
        state.origin = $("#origin").value.trim();
        state.destination = $("#destination").value.trim();
        state.depart = $("#depart").value || "";
        state.returnDate = state.trip === "round" ? $("#return").value || "" : "";
        setFieldError("origin", state.origin ? "" : "Укажите город или код аэропорта");
        setFieldError("destination", state.destination ? "" : "Укажите город или код аэропорта");
        if (!state.origin || !state.destination) {
          haptic("error");
          return;
        }
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
          haptic("success");
        } catch (err) {
          if (!(err && err.auth)) {
            toast(err.message);
            haptic("error");
          }
        } finally {
          btn.disabled = false;
          btn.textContent = "Показать вилку цен";
        }
      });

      $$("[data-preset]").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (!state.quote) return;
          const key = btn.getAttribute("data-preset");
          $("#threshold").value = Math.round(
            state.quote[key === "cheap" ? "cheap_max" : "typical"] || 0
          );
          hideLowThresholdWarn();
          updateDirtyClosingConfirmation();
        });
      });

      $$(".flex-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.flexibilityDays = Number(btn.getAttribute("data-flex")) || 0;
          syncFlexUi();
          hideLowThresholdWarn();
        });
      });

      $("#watch-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!state.quote) return;
        const threshold = Math.round(Number($("#threshold").value));
        if (!Number.isFinite(threshold) || threshold < 1) {
          setFieldError("threshold", "Введите порог числом, например 12000");
          toast("Введите порог числом, например 12000");
          haptic("error");
          return;
        }
        setFieldError("threshold", "");
        hideLowThresholdWarn();
        try {
          await createWatch(threshold, false);
          toast("Подписка создана");
          setClosingConfirmation(false);
          haptic("success");
          clearMainButton();
          switchTab("watches");
        } catch (err) {
          if (err && err.detail && err.detail.code === "LOW_THRESHOLD_CONFIRMATION_REQUIRED") {
            showLowThresholdWarn(err.detail);
            return;
          }
          if (!(err && err.auth)) {
            toast(err.message);
            haptic("error");
          }
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
            setClosingConfirmation(false);
            haptic("success");
            clearMainButton();
            switchTab("watches");
          } catch (err) {
            if (!(err && err.auth)) toast(err.message);
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
        const retry =
          e.target && e.target.closest && e.target.closest("[data-retry-watches]");
        if (retry) {
          loadWatches();
          return;
        }
        const createBtn = e.target && e.target.closest && e.target.closest("[data-empty-create]");
        if (createBtn) {
          switchTab("search");
          return;
        }
        const shareId = e.target && e.target.getAttribute("data-share");
        if (shareId) {
          try {
            const data = await api("/api/watches/" + shareId + "/share", { method: "POST" });
            const url = data && data.url ? String(data.url) : "";
            if (!url) {
              toast("Не удалось создать ссылку");
              return;
            }
            const sharePage =
              "https://t.me/share/url?url=" +
              encodeURIComponent(url) +
              "&text=" +
              encodeURIComponent("Следи за ценой на эту поездку в FlyPing");
            const box = document.createElement("div");
            box.className = "share-modal";
            box.innerHTML =
              '<div class="share-modal-card">' +
              "<h3>Ссылка готова</h3>" +
              '<p class="meta mono" id="share-url-text"></p>' +
              '<div class="btn-row">' +
              '<a class="btn primary" id="share-send" href="' +
              sharePage +
              '" target="_blank" rel="noopener">Отправить</a>' +
              '<button class="btn ghost" type="button" id="share-close">Закрыть</button>' +
              "</div></div>";
            document.body.appendChild(box);
            const urlEl = box.querySelector("#share-url-text");
            if (urlEl) urlEl.textContent = url;
            const close = () => {
              if (box.parentNode) box.parentNode.removeChild(box);
            };
            const closeBtn = box.querySelector("#share-close");
            if (closeBtn) closeBtn.addEventListener("click", close);
            box.addEventListener("click", (ev) => {
              if (ev.target === box) close();
            });
          } catch (err) {
            if (!(err && err.auth)) toast(err.message);
          }
          return;
        }
        const id = e.target && e.target.getAttribute("data-del");
        if (!id) return;
        try {
          await api("/api/watches/" + id, { method: "DELETE" });
          toast("Удалено");
          loadWatches();
        } catch (err) {
          if (!(err && err.auth)) toast(err.message);
        }
      });

      $("#refresh-watches").addEventListener("click", loadWatches);
      syncPaxUi();
      syncFlexUi();
    }

    async function bootstrapTelegramApp() {
      if (state.uiStarted) return;
      setBoot("Boot…");

      let health = null;
      try {
        health = await fetch("/api/health").then((r) => r.json());
      } catch (_) {
        health = null;
      }
      state.health = health;
      if (health && health.display_timezone) {
        displayTimezone = health.display_timezone;
      }

      const appEnv = (health && health.app_env) || "production";
      const tg = getTelegramWebApp();
      const insideTelegram = isInsideTelegramWebView();
      // Give Telegram WebView time to populate initData before browser fallback.
      let initData = getInitData();
      if (!initData && insideTelegram) {
        setBoot("Telegram…");
        initData = await waitForInitData(2500);
      }
      const botLink = health && health.telegram_bot_link ? health.telegram_bot_link : "";

      if (tg) {
        try {
          if (typeof tg.ready === "function") tg.ready();
          if (typeof tg.expand === "function") tg.expand();
        } catch (_) {}
        applyTelegramTheme(tg);
        bindThemeListener(tg);
      }

      if (!initData && appEnv === "production") {
        if (insideTelegram) {
          // Already in Telegram but no initData — do not redirect to bot.
          showAuthGate(
            "Не удалось получить сессию Telegram",
            "Закройте Mini App и откройте снова через кнопку «Открыть FlyPing» или Menu.",
            ""
          );
          setBoot("Нет initData");
          return;
        }
        // Browser fallback only (no Telegram WebApp context).
        showAuthGate(
          "FlyPing работает внутри Telegram",
          "Откройте бота и нажмите кнопку «Открыть FlyPing».",
          botLink
        );
        setBoot("Нужен Telegram");
        return;
      }

      try {
        const me = await apiFetch("/api/me");
        state.me = me;
        hideAuthGate();
        bindUiOnce();
        showUserChip(me);
        state.uiStarted = true;
        const name = (me && me.first_name) || (me && me.username) || "";
        setBoot(name ? "Привет, " + name : "Готово");
        setTimeout(() => setBoot(""), 1500);
        syncMainButton();
      } catch (err) {
        if (!(err && err.auth)) {
          showAuthGate(
            "Не удалось войти",
            (err && err.message) ||
              "Закройте и снова откройте приложение через Telegram.",
            insideTelegram ? "" : botLink
          );
        }
        setBoot("Auth");
      }
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", bootstrapTelegramApp, { once: true });
    } else {
      bootstrapTelegramApp();
    }
  } catch (err) {
    setBoot("Ошибка UI: " + (err && err.message ? err.message : String(err)));
  }
})();
