/**
 * BUG-02.5: safe Mini App diagnostic session tracer.
 * Does not change auth/parser/HMAC. Never sends initData values / secrets.
 */
(function (root) {
  "use strict";

  function uuid() {
    try {
      if (root.crypto && typeof root.crypto.randomUUID === "function") {
        return root.crypto.randomUUID();
      }
      var a = new Uint8Array(16);
      root.crypto.getRandomValues(a);
      a[6] = (a[6] & 0x0f) | 0x40;
      a[8] = (a[8] & 0x3f) | 0x80;
      var h = [];
      for (var i = 0; i < a.length; i++) h.push(("0" + a[i].toString(16)).slice(-2));
      return (
        h.slice(0, 4).join("") +
        "-" +
        h.slice(4, 6).join("") +
        "-" +
        h.slice(6, 8).join("") +
        "-" +
        h.slice(8, 10).join("") +
        "-" +
        h.slice(10).join("")
      );
    } catch (e) {
      return "s" + String(Date.now()) + Math.random().toString(16).slice(2, 10);
    }
  }

  var boot = root.__FLYPING_BOOT__ || (root.__FLYPING_BOOT__ = {});
  if (!boot.session_id) boot.session_id = uuid();
  if (!boot.t) boot.t = Date.now();
  if (!boot.asset) boot.asset = "0.3.0-thresholdfix1";
  boot.scriptStartedAt = boot.scriptStartedAt || Date.now();
  boot.initialHrefLen = boot.initialHrefLen || 0;
  try {
    boot.initialHrefLen = String(location.href || "").length;
  } catch (e) {}

  function elapsed() {
    return Date.now() - (boot.scriptStartedAt || boot.t || Date.now());
  }

  function storageOk(which) {
    try {
      var s = which === "local" ? localStorage : sessionStorage;
      var k = "__flyping_diag_probe__";
      s.setItem(k, "1");
      s.removeItem(k);
      return true;
    } catch (e) {
      return false;
    }
  }

  function refParts() {
    try {
      if (!document.referrer) return { origin: "", path: "" };
      var u = new URL(document.referrer);
      return { origin: String(u.origin).slice(0, 64), path: String(u.pathname).slice(0, 64) };
    } catch (e) {
      return { origin: "", path: "" };
    }
  }

  function uaData() {
    var out = { present: false, brands: "", platform: "" };
    try {
      var uad = navigator.userAgentData;
      if (!uad) return out;
      out.present = true;
      if (uad.brands && uad.brands.length) {
        out.brands = uad.brands
          .map(function (b) {
            return String(b.brand || "") + ":" + String(b.version || "");
          })
          .join(",")
          .slice(0, 120);
      }
      out.platform = String(uad.platform || "").slice(0, 64);
    } catch (e) {}
    return out;
  }

  function launchSnapshot() {
    var hash = "";
    var search = "";
    try {
      hash = String(location.hash || "");
      search = String(location.search || "");
    } catch (e) {}
    var diag = {};
    try {
      if (root.FlyPingLaunchParams && root.FlyPingLaunchParams.diagnoseLaunchUrl) {
        diag = root.FlyPingLaunchParams.diagnoseLaunchUrl(hash, search) || {};
      }
    } catch (e) {}
    var ref = refParts();
    var hrefLen = 0;
    try {
      hrefLen = String(location.href || "").length;
    } catch (e) {}
    return {
      origin: String(location.origin || "").slice(0, 64),
      path: String(location.pathname || "").slice(0, 64),
      hash_present: hash.length > 1,
      hash_len: Math.min(hash.length, 100000),
      search_present: search.length > 1,
      search_len: Math.min(search.length, 100000),
      hash_params: String(diag.hash_params || "").slice(0, 120),
      hash_param_lens: String(diag.hash_param_lens || "").slice(0, 200),
      search_params: String(diag.search_params || "").slice(0, 120),
      search_param_lens: String(diag.search_param_lens || "").slice(0, 200),
      has_tgwebappdata: !!diag.has_tgwebappdata,
      tgwebappdata_len: Number(diag.tgwebappdata_len) || 0,
      has_tgwebappversion: !!diag.has_tgwebappversion,
      has_tgwebappplatform: !!diag.has_tgwebappplatform,
      has_tgwebapptheme: !!diag.has_tgwebapptheme,
      decode_ok: diag.decode_ok !== false,
      decode_passes: Number(diag.decode_passes) || 0,
      extract_ok: !!diag.extract_ok,
      extract_source: String(diag.extract_source || "").slice(0, 32),
      extract_len: Number(diag.extract_len) || 0,
      spa_path: !!diag.spa_path,
      href_len: Math.min(hrefLen, 100000),
      referrer_origin: ref.origin,
      referrer_path: ref.path,
      url_changed: hrefLen !== boot.initialHrefLen,
    };
  }

  function telegramSnapshot() {
    var tg = null;
    try {
      tg = root.Telegram && root.Telegram.WebApp;
    } catch (e) {}
    var unsafeKeys = [];
    var unsafeHasUser = false;
    try {
      if (tg && tg.initDataUnsafe && typeof tg.initDataUnsafe === "object") {
        unsafeKeys = Object.keys(tg.initDataUnsafe).slice(0, 20);
        unsafeHasUser = !!(tg.initDataUnsafe.user && (tg.initDataUnsafe.user.id || tg.initDataUnsafe.user.id === 0));
      }
    } catch (e) {}
    var initLen = 0;
    try {
      initLen = tg && tg.initData ? String(tg.initData).length : 0;
    } catch (e) {}
    return {
      has_telegram: !!(root.Telegram),
      has_webapp: !!tg,
      has_telegram_webview: !!(root.Telegram && root.Telegram.WebView),
      has_webview_proxy: typeof root.TelegramWebviewProxy !== "undefined",
      sdk_init_len: Math.min(initLen, 100000),
      has_init_data: initLen > 0,
      init_data_len: Math.min(initLen, 100000),
      unsafe_keys: unsafeKeys.join(",").slice(0, 120),
      unsafe_has_user: unsafeHasUser,
      webapp_version: tg ? String(tg.version || "").slice(0, 16) : "",
      platform: tg ? String(tg.platform || "").slice(0, 32) : "",
      color_scheme: tg ? String(tg.colorScheme || "").slice(0, 16) : "",
      is_expanded: !!(tg && tg.isExpanded),
      viewport_height: tg && tg.viewportHeight ? Math.round(Number(tg.viewportHeight) || 0) : 0,
      viewport_stable_height: tg && tg.viewportStableHeight ? Math.round(Number(tg.viewportStableHeight) || 0) : 0,
      ready_called: !!boot.readyCalled,
      expand_called: !!boot.expandCalled,
      sdk_source: boot.localSdk ? "local" : boot.sdkCdn ? "cdn" : "local",
      sdk_fallback: !!boot.localSdk || !!root.__FLYPING_SDK_FALLBACK__,
    };
  }

  function deviceSnapshot() {
    var uad = uaData();
    var langs = "";
    try {
      langs = (navigator.languages || []).slice(0, 5).join(",").slice(0, 120);
    } catch (e) {}
    var navType = "";
    try {
      var entries = performance.getEntriesByType && performance.getEntriesByType("navigation");
      if (entries && entries[0] && entries[0].type) navType = String(entries[0].type).slice(0, 32);
    } catch (e) {}
    var tz = "";
    try {
      tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch (e) {}
    return {
      ua: String(navigator.userAgent || "").slice(0, 240),
      nav_platform: String(navigator.platform || "").slice(0, 64),
      nav_vendor: String(navigator.vendor || "").slice(0, 64),
      language: String(navigator.language || "").slice(0, 32),
      languages: langs,
      ua_data_present: uad.present,
      ua_brands: uad.brands,
      ua_platform: uad.platform,
      screen_w: (screen && screen.width) || 0,
      screen_h: (screen && screen.height) || 0,
      dpr: Number(window.devicePixelRatio) || 0,
      timezone: tz.slice(0, 64),
      cookie_enabled: !!navigator.cookieEnabled,
      local_storage_ok: storageOk("local"),
      session_storage_ok: storageOk("session"),
      nav_type: navType,
      visibility: String(document.visibilityState || "").slice(0, 32),
      ready_state: String(document.readyState || "").slice(0, 32),
      online: navigator.onLine !== false,
    };
  }

  function detectLaunchMode() {
    var snap = launchSnapshot();
    var tg = telegramSnapshot();
    if (snap.has_tgwebappdata || tg.has_init_data || snap.extract_ok) return "valid_miniapp";
    if (tg.has_webapp || tg.has_webview_proxy || /Telegram/i.test(String(navigator.userAgent || ""))) {
      return "telegram_browser";
    }
    return "external_browser";
  }

  function emit(event, extra) {
    try {
      var payload = Object.assign(
        {
          session_id: boot.session_id,
          event: String(event || "unknown").slice(0, 64),
          stage: String(event || "unknown").slice(0, 64),
          asset: String(boot.asset || "").slice(0, 32),
          elapsed_ms: elapsed(),
          launch_mode: detectLaunchMode(),
        },
        launchSnapshot(),
        telegramSnapshot(),
        deviceSnapshot(),
        extra && typeof extra === "object" ? extra : {}
      );
      // Never include secrets even if caller passes them.
      delete payload.initData;
      delete payload.init_data;
      delete payload.authorization;
      delete payload.Authorization;
      fetch("/api/diag/miniapp-bootstrap", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Diag-Session": boot.session_id,
        },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function () {});
    } catch (e) {}
  }

  function bindLifecycle() {
    try {
      window.addEventListener("pageshow", function () {
        emit("pageshow");
      });
      document.addEventListener("visibilitychange", function () {
        emit("visibilitychange");
      });
      window.addEventListener("focus", function () {
        emit("focus");
      });
      window.addEventListener("hashchange", function () {
        emit("hashchange");
      });
      window.addEventListener("popstate", function () {
        emit("popstate");
      });
      window.addEventListener("error", function (ev) {
        emit("unhandled_error", {
          detail: String((ev && ev.message) || "error").slice(0, 200),
        });
      });
      window.addEventListener("unhandledrejection", function (ev) {
        var msg = "";
        try {
          msg = String((ev && ev.reason && (ev.reason.message || ev.reason)) || "rejection");
        } catch (e) {
          msg = "rejection";
        }
        emit("unhandled_rejection", { detail: msg.slice(0, 200) });
      });
    } catch (e) {}
  }

  var api = {
    sessionId: function () {
      return boot.session_id;
    },
    emit: emit,
    detectLaunchMode: detectLaunchMode,
    launchSnapshot: launchSnapshot,
    markReady: function () {
      boot.readyCalled = true;
    },
    markExpand: function () {
      boot.expandCalled = true;
    },
    bindLifecycle: bindLifecycle,
  };

  root.FlyPingDiag = api;
  emit("html_loaded");
  bindLifecycle();
})(typeof window !== "undefined" ? window : globalThis);
