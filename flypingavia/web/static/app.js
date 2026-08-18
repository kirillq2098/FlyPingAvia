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
      cachedInitData: "",
      bootStartedAt: 0,
      bootstrapInFlight: false,
      lateInitArmed: false,
      bootState: "SDK_LOADING",
      themeListenerBound: false,
      formListenersBound: false,
      closingConfirmation: false,
      createIdempotencyKey: null,
      _submitT2: null,
      _submitT10: null,
      _quoteLoadT2: null,
      _quoteLoadT8: null,
      quoteSeq: 0,
      quoteAbort: null,
      quoteDebounceTimer: null,
      quoteInFlight: false,
    };
    // WA-04 hotfix: единый submit lock (не debounce).
    let isSubmitting = false;
    const CREATE_WATCH_TIMEOUT_MS = 25000;
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
      // WA-04 hotfix: только внутренняя кнопка формы — MainButton скрыт
      // (стабильнее в Telegram Web / Desktop / Android / iOS).
      clearMainButton();
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

    /**
     * BUG-02.2 launch diagnostics / initData recovery.
     * Auth remains Authorization: tma <initData> (no JWT/cookie).
     * initDataUnsafe is diagnostic only — never sent to the API.
     */
    const BOOT_STATES = {
      SDK_LOADING: "SDK_LOADING",
      SDK_READY: "SDK_READY",
      INIT_DATA_WAITING: "INIT_DATA_WAITING",
      INIT_DATA_FOUND: "INIT_DATA_FOUND",
      AUTH_VALIDATING: "AUTH_VALIDATING",
      AUTH_SUCCESS: "AUTH_SUCCESS",
      AUTH_FAILED: "AUTH_FAILED",
      NOT_TELEGRAM: "NOT_TELEGRAM",
    };

    function setBootState(next) {
      state.bootState = next;
      try {
        window.__FLYPING_BOOT_STATE__ = next;
      } catch (_) {}
    }

    function rememberInitData(data) {
      const LP = window.FlyPingLaunchParams;
      const ok =
        data &&
        typeof data === "string" &&
        ((LP && LP.looksLikeInitData(data)) || data.indexOf("hash=") >= 0);
      if (ok) {
        // Never overwrite a good cache with empty.
        state.cachedInitData = data;
        try {
          sessionStorage.setItem("__flyping__initData", data);
        } catch (_) {}
        return data;
      }
      return state.cachedInitData || "";
    }

    function readInitDataFromUrlFallback() {
      try {
        const LP = window.FlyPingLaunchParams;
        if (!LP || typeof LP.extractInitDataFromUrl !== "function") return "";
        const result = LP.extractInitDataFromUrl(location.hash || "", location.search || "");
        return (result && result.initData) || "";
      } catch (_) {}
      return "";
    }

    function readInitDataFromTelegramStorage() {
      try {
        const ours = sessionStorage.getItem("__flyping__initData");
        if (ours && ours.indexOf("hash=") >= 0) return ours;
      } catch (_) {}
      try {
        const raw = sessionStorage.getItem("__telegram__initParams");
        if (!raw) return "";
        const params = JSON.parse(raw);
        if (params && typeof params.tgWebAppData === "string" && params.tgWebAppData) {
          return params.tgWebAppData;
        }
      } catch (_) {}
      try {
        const params =
          window.Telegram &&
          window.Telegram.WebView &&
          window.Telegram.WebView.initParams;
        if (params && typeof params.tgWebAppData === "string" && params.tgWebAppData) {
          return params.tgWebAppData;
        }
      } catch (_) {}
      return "";
    }

    function getInitData() {
      if (state.cachedInitData) return state.cachedInitData;
      try {
        if (window.__FLYPING_PRESERVED_INIT__) {
          const preserved = rememberInitData(String(window.__FLYPING_PRESERVED_INIT__));
          if (preserved) return preserved;
        }
      } catch (_) {}
      const tg = getTelegramWebApp();
      const fromSdk = (tg && tg.initData) || "";
      if (fromSdk) {
        const kept = rememberInitData(fromSdk);
        if (kept) return kept;
      }
      // BUG-02.3: do not depend on SDK for launch params (Huawei: SDK sees hash, initData empty).
      const fromUrl = readInitDataFromUrlFallback();
      if (fromUrl) return rememberInitData(fromUrl);
      const fromStore = readInitDataFromTelegramStorage();
      if (fromStore) return rememberInitData(fromStore);
      return "";
    }

    // Backward-compatible aliases used by older contract tests.
    function readInitDataFromLocationHash() {
      try {
        const LP = window.FlyPingLaunchParams;
        if (!LP) return "";
        const r = LP.extractInitDataFromUrl(location.hash || "", "");
        return (r && r.initData) || "";
      } catch (_) {}
      return "";
    }

    function readInitDataFromLocationSearch() {
      try {
        const LP = window.FlyPingLaunchParams;
        if (!LP) return "";
        const r = LP.extractInitDataFromUrl("", location.search || "");
        return (r && r.initData) || "";
      } catch (_) {}
      return "";
    }

    function collectLaunchSignals() {
      const tg = getTelegramWebApp();
      let unsafeKeys = [];
      let unsafeHasUser = false;
      try {
        const unsafe = tg && tg.initDataUnsafe;
        if (unsafe && typeof unsafe === "object") {
          unsafeKeys = Object.keys(unsafe).slice(0, 20);
          unsafeHasUser = !!(unsafe.user && (unsafe.user.id || unsafe.user.id === 0));
        }
      } catch (_) {}
      let hash = "";
      let search = "";
      try {
        hash = String(location.hash || "");
        search = String(location.search || "");
      } catch (_) {}
      let launchDiag = {};
      try {
        const LP = window.FlyPingLaunchParams;
        if (LP && typeof LP.diagnoseLaunchUrl === "function") {
          launchDiag = LP.diagnoseLaunchUrl(hash, search) || {};
        }
      } catch (_) {}
      const platform = tg ? String(tg.platform || "unknown") : "";
      const hasProxy = typeof window.TelegramWebviewProxy !== "undefined";
      const sdkInitLen = tg && tg.initData ? String(tg.initData).length : 0;
      return {
        has_telegram: !!(window.Telegram),
        has_webapp: !!tg,
        platform: platform.slice(0, 32),
        // Local SDK is primary; true only if we had to recover without CDN (compat field).
        sdk_fallback: !!window.__FLYPING_SDK_FALLBACK__ || !!(window.__FLYPING_BOOT__ && window.__FLYPING_BOOT__.localSdk),
        asset: (window.__FLYPING_BOOT__ && window.__FLYPING_BOOT__.asset) || "",
        unsafe_keys: unsafeKeys.join(",").slice(0, 120),
        unsafe_has_user: unsafeHasUser,
        hash_present: hash.length > 1,
        hash_len: Math.min(hash.length, 100000),
        hash_params: String(launchDiag.hash_params || "").slice(0, 120),
        hash_param_lens: String(launchDiag.hash_param_lens || "").slice(0, 200),
        search_present: search.length > 1,
        search_len: Math.min(search.length, 100000),
        search_params: String(launchDiag.search_params || "").slice(0, 120),
        search_param_lens: String(launchDiag.search_param_lens || "").slice(0, 200),
        has_tgwebappdata: !!launchDiag.has_tgwebappdata,
        tgwebappdata_len: Number(launchDiag.tgwebappdata_len) || 0,
        has_tgwebappversion: !!launchDiag.has_tgwebappversion,
        has_tgwebappplatform: !!launchDiag.has_tgwebappplatform,
        has_tgwebapptheme: !!launchDiag.has_tgwebapptheme,
        decode_ok: launchDiag.decode_ok !== false,
        decode_passes: Number(launchDiag.decode_passes) || 0,
        extract_ok: !!launchDiag.extract_ok,
        extract_source: String(launchDiag.extract_source || "").slice(0, 32),
        extract_len: Number(launchDiag.extract_len) || 0,
        spa_path: !!launchDiag.spa_path,
        sdk_init_len: Math.min(sdkInitLen, 100000),
        storage_present: !!readInitDataFromTelegramStorage(),
        href_len: Math.min(String(location.href || "").length, 100000),
        path: String(location.pathname || "").slice(0, 64),
        origin: String(location.origin || "").slice(0, 64),
        referrer_origin: (function () {
          try {
            if (!document.referrer) return "";
            return String(new URL(document.referrer).origin).slice(0, 64);
          } catch (_) {
            return "";
          }
        })(),
        has_webview_proxy: hasProxy,
        nav_type: (function () {
          try {
            const entries = performance.getEntriesByType && performance.getEntriesByType("navigation");
            if (entries && entries[0] && entries[0].type) return String(entries[0].type).slice(0, 32);
          } catch (_) {}
          return "";
        })(),
      };
    }

    /**
     * Real Mini App / WebApp context — NOT User-Agent alone.
     * Telegram UA + empty platform/initData usually means in-app browser via url= button.
     */
    function isTelegramMiniAppContext() {
      if (getInitData()) return true;
      const tg = getTelegramWebApp();
      if (!tg) {
        // Hash/search may still carry launch params before SDK is ready.
        try {
          const LP = window.FlyPingLaunchParams;
          if (LP) {
            const d = LP.diagnoseLaunchUrl(location.hash || "", location.search || "");
            if (d && (d.has_tgwebappdata || d.has_tgwebappplatform || d.has_tgwebappversion)) {
              return true;
            }
          }
        } catch (_) {}
        return false;
      }
      try {
        const unsafe = tg.initDataUnsafe;
        if (unsafe && (unsafe.user || unsafe.query_id || unsafe.auth_date || unsafe.hash)) {
          return true;
        }
      } catch (_) {}
      const platform = String(tg.platform || "").toLowerCase();
      if (platform && platform !== "unknown") return true;
      try {
        const hash = String(location.hash || "");
        const search = String(location.search || "");
        if (hash.indexOf("tgWebApp") >= 0 || search.indexOf("tgWebApp") >= 0) return true;
        if (hash.indexOf("tgWebApp") < 0 && (hash.indexOf("%") >= 0 || search.indexOf("%") >= 0)) {
          const LP = window.FlyPingLaunchParams;
          if (LP) {
            const d = LP.diagnoseLaunchUrl(hash, search);
            if (d && (d.has_tgwebappdata || d.has_tgwebappplatform || d.has_tgwebapptheme)) {
              return true;
            }
          }
        }
      } catch (_) {}
      if (typeof window.TelegramWebviewProxy !== "undefined") return true;
      return false;
    }

    // Backward-compatible name used across UI helpers.
    function isInsideTelegramWebView() {
      return isTelegramMiniAppContext();
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async function waitForTelegramSdk(maxMs) {
      maxMs = typeof maxMs === "number" ? maxMs : 3000;
      setBootState(BOOT_STATES.SDK_LOADING);
      const started = Date.now();
      while (Date.now() - started < maxMs) {
        if (getTelegramWebApp()) {
          setBootState(BOOT_STATES.SDK_READY);
          return true;
        }
        await sleep(50);
      }
      const ok = !!getTelegramWebApp();
      if (ok) setBootState(BOOT_STATES.SDK_READY);
      return ok;
    }

    function signalTelegramReady() {
      const tg = getTelegramWebApp();
      if (!tg) return null;
      try {
        if (typeof tg.ready === "function") {
          tg.ready();
          try {
            if (window.FlyPingDiag) {
              window.FlyPingDiag.markReady();
              window.FlyPingDiag.emit("telegram_ready_called");
            }
          } catch (_) {}
        }
      } catch (_) {}
      try {
        if (typeof tg.expand === "function") {
          tg.expand();
          try {
            if (window.FlyPingDiag) {
              window.FlyPingDiag.markExpand();
              window.FlyPingDiag.emit("telegram_expand_called");
            }
          } catch (_) {}
        }
      } catch (_) {}
      return tg;
    }

    function reportDiag(stage, extra) {
      try {
        if (window.FlyPingDiag && typeof window.FlyPingDiag.emit === "function") {
          const init = getInitData();
          const signals = collectLaunchSignals();
          const payload = Object.assign(
            {
              boot_state: String(state.bootState || "").slice(0, 32),
              has_init_data: !!init,
              init_data_len: init ? init.length : 0,
              has_cached_init: !!state.cachedInitData,
              inside_telegram: isTelegramMiniAppContext(),
              ui_started: !!state.uiStarted,
              storage_present: !!readInitDataFromTelegramStorage(),
            },
            signals
          );
          if (extra && typeof extra === "object") {
            if (extra.http_status != null) payload.http_status = Number(extra.http_status) || 0;
            if (extra.endpoint) payload.endpoint = String(extra.endpoint).slice(0, 64);
            if (extra.error_code) payload.error_code = String(extra.error_code).slice(0, 64);
            if (extra.detail) payload.detail = String(extra.detail).slice(0, 200);
          }
          window.FlyPingDiag.emit(stage, payload);
          return;
        }
      } catch (_) {}
      // Fallback if diag-session.js missing
      try {
        const init = getInitData();
        const signals = collectLaunchSignals();
        const payload = Object.assign(
          {
            stage: String(stage || "unknown").slice(0, 64),
            boot_state: String(state.bootState || "").slice(0, 32),
            has_init_data: !!init,
            init_data_len: init ? init.length : 0,
            has_cached_init: !!state.cachedInitData,
            inside_telegram: isTelegramMiniAppContext(),
            ui_started: !!state.uiStarted,
            elapsed_ms: state.bootStartedAt ? Date.now() - state.bootStartedAt : 0,
            session_id:
              (window.__FLYPING_BOOT__ && window.__FLYPING_BOOT__.session_id) || "",
          },
          signals
        );
        if (extra && typeof extra === "object") {
          if (extra.http_status != null) payload.http_status = Number(extra.http_status) || 0;
          if (extra.endpoint) payload.endpoint = String(extra.endpoint).slice(0, 64);
          if (extra.error_code) payload.error_code = String(extra.error_code).slice(0, 64);
        }
        fetch("/api/diag/miniapp-bootstrap", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Diag-Session": payload.session_id || "",
          },
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(function () {});
      } catch (_) {}
    }

    async function waitForInitData(maxMs) {
      maxMs = typeof maxMs === "number" ? maxMs : 12000;
      setBootState(BOOT_STATES.INIT_DATA_WAITING);
      let data = getInitData();
      if (data) {
        setBootState(BOOT_STATES.INIT_DATA_FOUND);
        return data;
      }
      return new Promise(function (resolve) {
        var done = false;
        var started = Date.now();
        function finish(value) {
          if (done) return;
          done = true;
          try {
            window.removeEventListener("hashchange", onHash);
            window.removeEventListener("popstate", onHash);
          } catch (_) {}
          try {
            clearInterval(timer);
          } catch (_) {}
          var finalValue = value || getInitData() || "";
          if (finalValue) setBootState(BOOT_STATES.INIT_DATA_FOUND);
          resolve(finalValue);
        }
        function onHash() {
          var d = getInitData();
          if (d) finish(d);
        }
        window.addEventListener("hashchange", onHash);
        window.addEventListener("popstate", onHash);
        var timer = setInterval(function () {
          var d = getInitData();
          if (d) {
            finish(d);
            return;
          }
          if (Date.now() - started >= maxMs) finish("");
        }, 50);
      });
    }

    function armLateInitDataResume() {
      if (state.lateInitArmed) return;
      state.lateInitArmed = true;
      function maybeResume(reason) {
        if (state.uiStarted || state.bootstrapInFlight) return;
        if (!getInitData()) return;
        reportDiag("late_resume_" + reason);
        bootstrapTelegramApp({ fromLateResume: true });
      }
      window.addEventListener("hashchange", function () {
        maybeResume("hashchange");
      });
      window.addEventListener("popstate", function () {
        maybeResume("popstate");
      });
      document.addEventListener("visibilitychange", function () {
        if (!document.hidden) maybeResume("visibility");
      });
      window.addEventListener("pageshow", function () {
        maybeResume("pageshow");
      });
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

    function showAuthGate(title, message, botLink, options) {
      options = options || {};
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
      const retryBtn = $("#auth-retry");
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
      if (retryBtn) {
        if (options.showRetry) {
          retryBtn.classList.remove("hidden");
          if (!retryBtn.dataset.bound) {
            retryBtn.dataset.bound = "1";
            retryBtn.addEventListener("click", function () {
              retryBtn.disabled = true;
              hideAuthGate();
              setBoot("Повтор…");
              bootstrapTelegramApp({ manualRetry: true }).finally(function () {
                retryBtn.disabled = false;
              });
            });
          }
        } else {
          retryBtn.classList.add("hidden");
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
      const retryBtn = $("#auth-retry");
      if (retryBtn) retryBtn.classList.add("hidden");
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
      try {
        const sid =
          (window.FlyPingDiag && window.FlyPingDiag.sessionId && window.FlyPingDiag.sessionId()) ||
          (window.__FLYPING_BOOT__ && window.__FLYPING_BOOT__.session_id) ||
          "";
        if (sid) headers["X-Diag-Session"] = String(sid).slice(0, 64);
      } catch (_) {}
      const controller = new AbortController();
      const timeoutMs = Number(options.timeoutMs) || 0;
      let timer = null;
      if (timeoutMs > 0) {
        timer = setTimeout(function () {
          try {
            controller.abort();
          } catch (_) {}
        }, timeoutMs);
      }
      if (options.signal) {
        if (options.signal.aborted) {
          if (timer) clearTimeout(timer);
          const err = new Error("aborted");
          err.aborted = true;
          throw err;
        }
        options.signal.addEventListener(
          "abort",
          function () {
            try {
              controller.abort();
            } catch (_) {}
          },
          { once: true }
        );
      }
      let res;
      try {
        res = await fetch(path, {
          method: options.method || "GET",
          headers: headers,
          body: options.body,
          signal: controller.signal,
        });
      } catch (fetchErr) {
        if (timer) clearTimeout(timer);
        const aborted =
          (fetchErr && fetchErr.name === "AbortError") ||
          (typeof DOMException !== "undefined" && fetchErr instanceof DOMException);
        if (aborted) {
          if (options.signal && options.signal.aborted) {
            const err = new Error("aborted");
            err.aborted = true;
            throw err;
          }
          if (timeoutMs > 0) {
            const err = new Error("Превышено время ожидания ответа сервера");
            err.timeout = true;
            err.status = 0;
            throw err;
          }
        }
        throw fetchErr;
      }
      if (timer) clearTimeout(timer);
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
              : "Данные запуска Telegram отклонены сервером.";
        const botLink =
          state.health && state.health.telegram_bot_link
            ? state.health.telegram_bot_link
            : "";
        const gateBotLink = isInsideTelegramWebView() ? "" : botLink;
        const missing = code === "MISSING_INIT_DATA";
        showAuthGate(
          missing
            ? "Не удалось получить данные запуска Telegram"
            : "Данные запуска Telegram отклонены",
          isInsideTelegramWebView()
            ? missing
              ? "Закройте окно и откройте снова через кнопку «Открыть FlyPing» или Menu в боте."
              : "Подпись initData не прошла проверку. Закройте Mini App и откройте снова через кнопку бота."
            : message,
          gateBotLink,
          { showRetry: isInsideTelegramWebView() }
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
      if (level === "cheap") return ["cheap", "выгодная"];
      if (level === "expensive") return ["expensive", "высокая"];
      if (level === "normal") return ["normal", "средняя"];
      return ["", "нет оценки"];
    }

    function hideQuoteLoading() {
      const box = $("#quote-loading");
      if (box) box.classList.add("hidden");
      if (state._quoteLoadT2) {
        clearTimeout(state._quoteLoadT2);
        state._quoteLoadT2 = null;
      }
      if (state._quoteLoadT8) {
        clearTimeout(state._quoteLoadT8);
        state._quoteLoadT8 = null;
      }
    }

    function showQuoteLoading() {
      const box = $("#quote-loading");
      const text = $("#quote-loading-text");
      if (!box) return;
      box.classList.remove("hidden");
      if (text) text.textContent = "Анализируем стоимость билетов…";
      if (state._quoteLoadT2) clearTimeout(state._quoteLoadT2);
      if (state._quoteLoadT8) clearTimeout(state._quoteLoadT8);
      state._quoteLoadT2 = setTimeout(function () {
        if (text && !box.classList.contains("hidden")) {
          text.textContent = "Сравниваем доступные варианты…";
        }
      }, 2000);
      state._quoteLoadT8 = setTimeout(function () {
        if (text && !box.classList.contains("hidden")) {
          text.textContent =
            "Поиск занимает немного больше времени. Можно продолжить заполнение формы.";
        }
      }, 8000);
    }

    function formatComputedAt(iso) {
      if (!iso) return "";
      try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return "";
        return (
          d.toLocaleString("ru-RU", {
            day: "numeric",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          }) || ""
        );
      } catch (_) {
        return "";
      }
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
        ". Выгодная цена по текущим данным: до " +
        cheap +
        ". С таким порогом уведомление может долго не прийти.";
      box.classList.remove("hidden");
    }

    function renderQuote(q, opts) {
      opts = opts || {};
      state.quote = q;
      hideQuoteLoading();
      const box = $("#quote");
      const tripLabel = q.return_date ? "туда-обратно" : "в одну сторону";
      const dateBits = [];
      if (q.depart_date) dateBits.push(q.depart_date);
      if (q.return_date) dateBits.push("⇄ " + q.return_date);
      const originCode = escapeHtml(q.origin || "");
      const destCode = escapeHtml(q.destination || "");
      const isLive = !!q.is_live;
      const isEstimate = !isLive || q.price_source === "travelpayouts_estimate";
      const title =
        q.partial
          ? "Предварительный ориентир"
          : q.stale || opts.updating
            ? "Ориентир по стоимости"
            : q.title || (isLive ? "Минимальная цена сейчас" : "Оценка стоимости");
      const statusBits = [];
      if (q.partial) statusBits.push("Предварительный ориентир — уточняем гибкие даты");
      else if (opts.updating || q.refreshing) statusBits.push("Обновляем данные…");
      else if (q.stale) statusBits.push("Показаны сохранённые данные");
      else if (q.cached) statusBits.push("Ориентир обновлён");
      if (isLive && !isEstimate) statusBits.push("Живой поиск");
      if (isEstimate) {
        statusBits.push("По данным Travelpayouts");
        statusBits.push("Фактическая цена на Aviasales может отличаться");
      }
      const computed = formatComputedAt(q.updated_at || q.computed_at);
      if (computed) statusBits.push("расчёт: " + computed);
      box.classList.remove("hidden");
      box.innerHTML =
        '<h2 class="quote-title">' +
        escapeHtml(title) +
        "</h2>" +
        (statusBits.length
          ? '<p class="quote-status">' + escapeHtml(statusBits.join(" · ")) + "</p>"
          : "") +
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
        (q.price != null ? (isEstimate ? "~ " : "") + money(q.price) : "—") +
        "</div>" +
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
        '<div style="margin-top:12px" class="btn-row">' +
        '<a class="btn ghost" href="' +
        escapeHtml(q.tickets_url) +
        '" target="_blank" rel="noopener">Смотреть билеты</a>' +
        (q.partial || q.status === "timeout" || (!q.price && !q.cheap_max)
          ? '<button type="button" class="btn ghost" id="quote-retry">Повторить расчёт</button>'
          : "") +
        "</div>";
      $("#watch-form").classList.remove("hidden");
      const thresholdInput = $("#threshold");
      const recommended = Math.round(q.cheap_max || q.price || 0);
      if (thresholdInput) {
        if (!opts.keepThreshold) {
          thresholdInput.value = "";
        }
        thresholdInput.placeholder =
          recommended > 0
            ? "Например, " + money(recommended)
            : "Введите желаемую цену";
      }
      if (!opts.keepThreshold) {
        hideLowThresholdWarn();
      }
      updateDirtyClosingConfirmation();
      syncMainButton();
      const retry = $("#quote-retry");
      if (retry) {
        retry.addEventListener("click", function () {
          requestQuote({ refresh: true, force: true });
        });
      }
    }

    function renderQuoteTimeoutFallback() {
      hideQuoteLoading();
      const box = $("#quote");
      if (!box) return;
      box.classList.remove("hidden");
      box.innerHTML =
        '<h2 class="quote-title">Ориентир по стоимости</h2>' +
        '<p class="meta">Не удалось быстро рассчитать ориентир. Подписку всё равно можно создать — укажите порог вручную.</p>' +
        '<div class="btn-row" style="margin-top:12px">' +
        '<button type="button" class="btn primary" id="quote-retry">Повторить расчёт</button>' +
        "</div>";
      $("#watch-form").classList.remove("hidden");
      const thr = $("#threshold");
      if (thr) {
        if (!thr.value) thr.value = "";
        if (!thr.placeholder) thr.placeholder = "Введите желаемую цену";
      }
      const retry = $("#quote-retry");
      if (retry) {
        retry.addEventListener("click", function () {
          requestQuote({ refresh: true, force: true });
        });
      }
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

    async function createWatch(threshold, confirmLow, idempotencyKey) {
      const q = state.quote || {};
      const headers = {};
      if (idempotencyKey) {
        headers["Idempotency-Key"] = String(idempotencyKey);
      }
      const body = {
        origin: q.origin,
        destination: q.destination,
        max_price: threshold,
        depart_date: state.depart || null,
        return_date: state.returnDate || null,
        adults: state.adults,
        children: state.children,
        infants: state.infants,
        confirm_low_threshold: !!confirmLow,
        flexibility_days: state.flexibilityDays || 0,
      };
      // Снимок рынка с уже показанного quote — без повторного search на сервере.
      if (q.cheap_max != null && q.typical != null) {
        body.market_cheap_max = Number(q.cheap_max);
        body.market_typical = Number(q.typical);
        if (q.expensive_min != null) {
          body.market_expensive_min = Number(q.expensive_min);
        }
      }
      return api("/api/watches", {
        method: "POST",
        headers: headers,
        body: JSON.stringify(body),
        timeoutMs: CREATE_WATCH_TIMEOUT_MS,
      });
    }

    function newIdempotencyKey() {
      try {
        if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
          return crypto.randomUUID();
        }
      } catch (_) {}
      return (
        "w-" +
        Date.now().toString(36) +
        "-" +
        Math.random().toString(36).slice(2, 10)
      );
    }

    function ensureCreateIdempotencyKey() {
      if (!state.createIdempotencyKey) {
        state.createIdempotencyKey = newIdempotencyKey();
      }
      return state.createIdempotencyKey;
    }

    function clearCreateIdempotencyKey() {
      state.createIdempotencyKey = null;
    }

    function clearSubmitProgressTimers() {
      if (state._submitT2) {
        clearTimeout(state._submitT2);
        state._submitT2 = null;
      }
      if (state._submitT10) {
        clearTimeout(state._submitT10);
        state._submitT10 = null;
      }
    }

    function setSubmitUi(busy) {
      const btn = $("#watch-submit");
      const confirmBtn = $("#low-threshold-confirm");
      const editBtn = $("#low-threshold-edit");
      const progress = $("#watch-submit-progress");
      clearSubmitProgressTimers();
      if (btn) {
        btn.disabled = !!busy;
        btn.classList.toggle("is-loading", !!busy);
        btn.setAttribute("aria-busy", busy ? "true" : "false");
        btn.textContent = busy ? "Создаём подписку…" : "Создать подписку";
      }
      if (confirmBtn) {
        confirmBtn.disabled = !!busy;
        confirmBtn.classList.toggle("is-loading", !!busy);
        if (busy) {
          confirmBtn.textContent = "Создаём подписку…";
        } else {
          confirmBtn.textContent = "Сохранить всё равно";
        }
      }
      if (editBtn) editBtn.disabled = !!busy;
      if (progress) {
        if (!busy) {
          progress.classList.add("hidden");
          progress.textContent = "";
        } else {
          progress.classList.add("hidden");
          progress.textContent = "";
          state._submitT2 = setTimeout(function () {
            if (!isSubmitting || !progress) return;
            progress.classList.remove("hidden");
            progress.textContent =
              "Сохраняем и подключаем отслеживание. Это может занять несколько секунд.";
          }, 2000);
          state._submitT10 = setTimeout(function () {
            if (!isSubmitting || !progress) return;
            progress.classList.remove("hidden");
            progress.textContent =
              "Подписка всё ещё создаётся. Не закрывайте окно.";
          }, 10000);
        }
      }
      clearMainButton();
    }

    function shouldWarnLowThresholdLocal(threshold) {
      const q = state.quote;
      if (!q) return false;
      const cheap = Number(q.cheap_max);
      if (!Number.isFinite(threshold) || threshold <= 0) return false;
      if (!Number.isFinite(cheap) || cheap <= 0) return false;
      return threshold < cheap;
    }

    function resetWatchFormAfterSuccess() {
      hideLowThresholdWarn();
      state.quote = null;
      const quote = $("#quote");
      if (quote) {
        quote.classList.add("hidden");
        quote.innerHTML = "";
      }
      const form = $("#watch-form");
      if (form) form.classList.add("hidden");
      const thr = $("#threshold");
      if (thr) thr.value = "";
      clearCreateIdempotencyKey();
      clearMainButton();
    }

    function watchMatchesPendingCreate(w, threshold) {
      if (!w || !state.quote) return false;
      const origin = String(state.quote.origin || "").toUpperCase();
      const dest = String(state.quote.destination || "").toUpperCase();
      if (String(w.origin || "").toUpperCase() !== origin) return false;
      if (String(w.destination || "").toUpperCase() !== dest) return false;
      if (Math.round(Number(w.max_price)) !== Math.round(Number(threshold))) return false;
      if (Number(w.flexibility_days || 0) !== Number(state.flexibilityDays || 0)) return false;
      const dep = state.depart || null;
      const ret = state.returnDate || null;
      const wDep = w.depart_date || null;
      const wRet = w.return_date || null;
      if (dep !== wDep) return false;
      if (ret !== wRet) return false;
      return true;
    }

    async function recoverAfterCreateTimeout(threshold) {
      try {
        const items = await api("/api/watches");
        if (!Array.isArray(items)) return null;
        for (let i = 0; i < items.length; i++) {
          if (watchMatchesPendingCreate(items[i], threshold)) {
            return items[i];
          }
        }
      } catch (_) {}
      return null;
    }

    async function finishCreateSuccess() {
      hideLowThresholdWarn();
      toast("Подписка создана");
      setClosingConfirmation(false);
      haptic("success");
      resetWatchFormAfterSuccess();
      switchTab("watches");
      // Разблокируем только после навигации на список.
      isSubmitting = false;
      setSubmitUi(false);
    }

    async function submitWatchForm(confirmLow) {
      if (isSubmitting) return;
      if (!state.quote) return;
      const threshold = Math.round(Number($("#threshold").value));
      if (!Number.isFinite(threshold) || threshold < 1) {
        setFieldError("threshold", "Укажите цену, при которой вам сообщить");
        toast("Укажите цену, при которой вам сообщить");
        haptic("error");
        return;
      }
      setFieldError("threshold", "");

      // Мгновенная локальная проверка низкого порога по уже загруженному quote.
      if (!confirmLow && shouldWarnLowThresholdLocal(threshold)) {
        showLowThresholdWarn({
          threshold: threshold,
          cheap_max: state.quote.cheap_max,
          typical: state.quote.typical,
        });
        return;
      }

      isSubmitting = true;
      setSubmitUi(true);
      const key = ensureCreateIdempotencyKey();
      try {
        await createWatch(threshold, !!confirmLow, key);
        await finishCreateSuccess();
      } catch (err) {
        if (err && err.timeout) {
          const found = await recoverAfterCreateTimeout(threshold);
          if (found) {
            await finishCreateSuccess();
            return;
          }
          toast(
            "Не удалось подтвердить создание. Откройте «Мои подписки» — не нажимайте повторно сразу."
          );
          haptic("error");
          // Ключ сохраняем: повтор использует тот же Idempotency-Key.
          isSubmitting = false;
          setSubmitUi(false);
          return;
        }
        if (err && err.detail && err.detail.code === "LOW_THRESHOLD_CONFIRMATION_REQUIRED") {
          showLowThresholdWarn(err.detail);
          isSubmitting = false;
          setSubmitUi(false);
          return;
        }
        if (!(err && err.auth)) {
          toast(err.message || "Не удалось создать подписку");
          haptic("error");
        }
        isSubmitting = false;
        setSubmitUi(false);
      }
    }

    // Экспорт для единообразного вызова (форма / confirm / тесты).
    window.submitWatchForm = submitWatchForm;

    function scheduleQuoteRefresh() {
      if (state.quoteDebounceTimer) clearTimeout(state.quoteDebounceTimer);
      state.quoteDebounceTimer = setTimeout(function () {
        state.quoteDebounceTimer = null;
        const origin = ($("#origin") && $("#origin").value.trim()) || "";
        const dest = ($("#destination") && $("#destination").value.trim()) || "";
        if (!origin || !dest) return;
        if (state.trip === "round") {
          const ret = ($("#return") && $("#return").value) || "";
          if (!ret) return;
        }
        // Only auto-refresh if user already has a quote card open.
        if (!$("#quote") || $("#quote").classList.contains("hidden")) return;
        requestQuote({ refresh: true });
      }, 550);
    }

    async function requestQuote(opts) {
      opts = opts || {};
      const btn = $("#search-btn");
      state.origin = ($("#origin") && $("#origin").value.trim()) || "";
      state.destination = ($("#destination") && $("#destination").value.trim()) || "";
      state.depart = ($("#depart") && $("#depart").value) || "";
      state.returnDate =
        state.trip === "round" ? (($("#return") && $("#return").value) || "") : "";
      setFieldError("origin", state.origin ? "" : "Укажите город или код аэропорта");
      setFieldError(
        "destination",
        state.destination ? "" : "Укажите город или код аэропорта"
      );
      if (!state.origin || !state.destination) {
        if (opts.force) haptic("error");
        return;
      }
      if (state.trip === "round" && !state.returnDate) {
        if (opts.force) toast("Укажите дату возврата");
        return;
      }

      if (state.quoteAbort) {
        try {
          state.quoteAbort.abort();
        } catch (_) {}
      }
      const seq = ++state.quoteSeq;
      const controller = new AbortController();
      state.quoteAbort = controller;

      if (!opts.silent) {
        showQuoteLoading();
        if (btn) {
          btn.disabled = true;
          btn.textContent = "Формируем ориентир по стоимости…";
        }
      }

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
        if (opts.refresh) params.set("refresh", "1");
        const q = await api("/api/quote?" + params.toString(), {
          timeoutMs: 22000,
          signal: controller.signal,
        });
        if (seq !== state.quoteSeq) return;
        if (!q || (q.price == null && q.cheap_max == null)) {
          renderQuoteTimeoutFallback();
          haptic("error");
          return;
        }
        renderQuote(q, { keepThreshold: !!opts.keepThreshold, updating: false });
        haptic("success");
        // Stale-while-revalidate: show cached, then refresh once in background.
        if (q.stale && q.refreshing && !opts.refresh) {
          renderQuote(q, { keepThreshold: true, updating: true });
          requestQuote({ refresh: true, silent: true, keepThreshold: true });
        }
      } catch (err) {
        if (seq !== state.quoteSeq) return;
        if (err && err.aborted) return;
        if (err && err.timeout) {
          renderQuoteTimeoutFallback();
          haptic("error");
          return;
        }
        if (!(err && err.auth)) {
          toast(err.message || "Не удалось рассчитать ориентир");
          haptic("error");
        }
      } finally {
        if (seq === state.quoteSeq) {
          hideQuoteLoading();
          if (btn) {
            btn.disabled = false;
            btn.textContent = "Показать ориентир по стоимости";
          }
        }
      }
    }

    window.requestQuote = requestQuote;

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
        await requestQuote({ force: true });
      });

      $$(".flex-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.flexibilityDays = Number(btn.getAttribute("data-flex")) || 0;
          syncFlexUi();
          hideLowThresholdWarn();
          // Debounced re-quote when route already filled and quote was shown.
          scheduleQuoteRefresh();
        });
      });

      $("#watch-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        await submitWatchForm(false);
      });

      const confirmBtn = $("#low-threshold-confirm");
      if (confirmBtn) {
        confirmBtn.addEventListener("click", async () => {
          await submitWatchForm(true);
        });
      }

      const editBtn = $("#low-threshold-edit");
      if (editBtn) {
        editBtn.addEventListener("click", () => {
          if (isSubmitting) return;
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

    const JS_ASSET_BUILD = "0.3.0-thresholdfix1";

    function detectAssetMismatch() {
      try {
        const htmlAsset =
          (window.__FLYPING_BOOT__ && window.__FLYPING_BOOT__.asset) || "";
        if (htmlAsset && htmlAsset !== JS_ASSET_BUILD) {
          reportDiag("asset_mismatch");
          return true;
        }
      } catch (_) {}
      return false;
    }

    async function bootstrapTelegramApp(options) {
      options = options || {};
      if (state.uiStarted) return;
      if (state.bootstrapInFlight && !options.fromLateResume && !options.manualRetry) {
        return;
      }
      state.bootstrapInFlight = true;
      if (!state.bootStartedAt) state.bootStartedAt = Date.now();
      setBoot("Boot…");
      detectAssetMismatch();
      // Prefer URL launch params even before SDK (Huawei: SDK initData empty).
      try {
        reportDiag("location_snapshot");
        reportDiag("launch_parser_start");
        const early = readInitDataFromUrlFallback();
        if (early) {
          rememberInitData(early);
          reportDiag("initdata_from_url");
        }
        reportDiag("launch_parser_result");
        const tgSnap = getTelegramWebApp();
        if (tgSnap && tgSnap.initData) reportDiag("initdata_from_sdk");
        if (readInitDataFromTelegramStorage()) reportDiag("initdata_from_storage");
      } catch (_) {}
      reportDiag("bootstrap_start");

      const sdkOk = await waitForTelegramSdk(3000);
      if (!sdkOk) {
        // SDK missing is non-fatal if URL already has initData.
        if (!getInitData()) {
          setBootState(BOOT_STATES.AUTH_FAILED);
          state.bootstrapInFlight = false;
          reportDiag("sdk_missing");
          showAuthGate(
            "Не удалось загрузить Telegram SDK",
            "Проверьте сеть и нажмите «Повторить».",
            "",
            { showRetry: true }
          );
          setBoot("Нет SDK");
          return;
        }
        reportDiag("sdk_missing_but_url_init");
      }

      // Signal ready as early as possible (before waiting for late hash / initData).
      const tgEarly = signalTelegramReady();
      if (tgEarly) {
        applyTelegramTheme(tgEarly);
        bindThemeListener(tgEarly);
      }
      armLateInitDataResume();

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
      const botLink = health && health.telegram_bot_link ? health.telegram_bot_link : "";
      const miniAppCtx = isTelegramMiniAppContext();
      let launchMode = "external_browser";
      try {
        launchMode =
          (window.FlyPingDiag && window.FlyPingDiag.detectLaunchMode()) ||
          (miniAppCtx ? "telegram_browser" : "external_browser");
      } catch (_) {}

      let initData = getInitData();
      if (!initData && miniAppCtx) {
        setBoot("Telegram…");
        reportDiag("wait_init_data_start");
        reportDiag("wait_init_data");
        initData = await waitForInitData(12000);
      }

      if (!initData && appEnv === "production") {
        state.bootstrapInFlight = false;
        // Direct open of https://app.flyping.ru/ or Telegram in-app browser without tgWebAppData
        // is not a "lost Mini App session" — guide user back to the bot web_app button.
        if (launchMode === "telegram_browser" || launchMode === "external_browser" || !getInitData()) {
          const isBrowserLike =
            launchMode !== "valid_miniapp" &&
            !(window.FlyPingLaunchParams &&
              window.FlyPingLaunchParams.diagnoseLaunchUrl &&
              window.FlyPingLaunchParams.diagnoseLaunchUrl(location.hash || "", location.search || "")
                .has_tgwebappdata);
          if (isBrowserLike || !miniAppCtx) {
            setBootState(BOOT_STATES.NOT_TELEGRAM);
            reportDiag("missing_init_data");
            showAuthGate(
              launchMode === "external_browser"
                ? "FlyPing работает внутри Telegram"
                : "Вы открыли FlyPing как обычную ссылку",
              launchMode === "external_browser"
                ? "Откройте бота и нажмите кнопку «Открыть FlyPing»."
                : "Вернитесь в чат с ботом и нажмите кнопку «Открыть FlyPing».",
              launchMode === "external_browser" ? botLink : "",
              { showRetry: false }
            );
            setBoot("Нужен web_app");
            return;
          }
        }
        if (miniAppCtx) {
          setBootState(BOOT_STATES.AUTH_FAILED);
          reportDiag("missing_init_data");
          showAuthGate(
            "Не удалось получить данные запуска Telegram",
            "Нажмите «Повторить» или закройте окно и откройте снова через кнопку «Открыть FlyPing» или Menu в боте (не обычную ссылку).",
            "",
            { showRetry: true }
          );
          setBoot("Нет initData");
          return;
        }
        setBootState(BOOT_STATES.NOT_TELEGRAM);
        reportDiag("need_telegram");
        showAuthGate(
          "FlyPing работает внутри Telegram",
          "Откройте бота и нажмите кнопку «Открыть FlyPing».",
          botLink
        );
        setBoot("Нужен Telegram");
        return;
      }

      setBootState(BOOT_STATES.AUTH_VALIDATING);
      try {
        reportDiag("api_me_start", { endpoint: "/api/me" });
        const me = await apiFetch("/api/me");
        state.me = me;
        hideAuthGate();
        bindUiOnce();
        showUserChip(me);
        state.uiStarted = true;
        state.bootstrapInFlight = false;
        setBootState(BOOT_STATES.AUTH_SUCCESS);
        reportDiag("api_me_ok", { endpoint: "/api/me", http_status: 200 });
        reportDiag("bootstrap_success", { endpoint: "/api/me", http_status: 200 });
        const name = (me && me.first_name) || (me && me.username) || "";
        setBoot(name ? "Привет, " + name : "Готово");
        setTimeout(() => setBoot(""), 1500);
        syncMainButton();
      } catch (err) {
        state.bootstrapInFlight = false;
        setBootState(BOOT_STATES.AUTH_FAILED);
        const networkFail = !(err && err.status) && !(err && err.auth);
        reportDiag(networkFail ? "network_fail" : "api_me_error", {
          endpoint: "/api/me",
          http_status: (err && err.status) || 0,
          error_code:
            (err && err.detail && err.detail.code) ||
            (err && err.auth ? "auth" : networkFail ? "network" : "error"),
        });
        if (!networkFail) {
          reportDiag("api_me_fail", {
            endpoint: "/api/me",
            http_status: (err && err.status) || 0,
            error_code:
              (err && err.detail && err.detail.code) ||
              (err && err.auth ? "auth" : "error"),
          });
        }
        if (networkFail) {
          showAuthGate(
            "Нет связи с сервером",
            "Проверьте интернет и нажмите «Повторить».",
            "",
            { showRetry: true }
          );
        } else if (!(err && err.auth)) {
          showAuthGate(
            "Не удалось войти",
            (err && err.message) ||
              "Закройте и снова откройте приложение через Telegram.",
            miniAppCtx ? "" : botLink,
            { showRetry: !!miniAppCtx }
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
