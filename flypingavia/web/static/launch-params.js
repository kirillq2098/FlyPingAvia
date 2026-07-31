/**
 * BUG-02.3: Telegram Mini App launch-parameter extraction.
 * Independent of telegram-web-app.js — CDN/SDK failure must not block initData recovery.
 * Never logs parameter values (secrets). Safe for Huawei/EMUI WebView quirks.
 */
(function (root) {
  "use strict";

  var MAX_DECODE_PASSES = 2;

  function looksLikeInitData(s) {
    if (!s || typeof s !== "string") return false;
    if (s.indexOf("hash=") < 0) return false;
    return (
      s.indexOf("auth_date=") >= 0 ||
      s.indexOf("user=") >= 0 ||
      s.indexOf("query_id=") >= 0 ||
      s.indexOf("receiver=") >= 0 ||
      s.indexOf("chat=") >= 0
    );
  }

  function limitedDecode(input, maxPasses) {
    maxPasses = typeof maxPasses === "number" ? maxPasses : MAX_DECODE_PASSES;
    var cur = String(input || "");
    var passes = 0;
    var ok = true;
    while (passes < maxPasses) {
      if (cur.indexOf("%") < 0 && cur.indexOf("+") < 0) break;
      // Stop if it already looks like initData / query with raw separators.
      if (looksLikeInitData(cur) && cur.indexOf("tgWebAppData=") < 0) break;
      try {
        var next = decodeURIComponent(cur.replace(/\+/g, "%20"));
        passes += 1;
        if (next === cur) break;
        cur = next;
      } catch (e) {
        ok = false;
        break;
      }
    }
    return { value: cur, passes: passes, ok: ok };
  }

  function decodeKey(raw) {
    try {
      return decodeURIComponent(String(raw || "").replace(/\+/g, " "));
    } catch (e) {
      return String(raw || "");
    }
  }

  /**
   * Split query while keeping values that contain '=' (unlike SDK split('=')).
   * Also reassembles tgWebAppData when Huawei/EMUI partially decoded inner '&'.
   */
  function parseQueryKeepEquals(query) {
    var out = {};
    var lengths = {};
    var q = String(query || "").replace(/^\?/, "");
    if (!q) return { params: out, lengths: lengths };

    var parts = q.split("&");
    var i;
    for (i = 0; i < parts.length; i++) {
      var raw = parts[i];
      if (!raw) continue;
      var eq = raw.indexOf("=");
      var key;
      var val;
      if (eq < 0) {
        key = decodeKey(raw);
        val = "";
      } else {
        key = decodeKey(raw.slice(0, eq));
        val = raw.slice(eq + 1);
      }
      if (!key) continue;

      // Reassemble: unencoded initData fields leaked as sibling keys after partial decode.
      if (
        out.tgWebAppData &&
        !looksLikeInitData(out.tgWebAppData) &&
        (key === "user" ||
          key === "auth_date" ||
          key === "hash" ||
          key === "query_id" ||
          key === "signature" ||
          key === "chat" ||
          key === "chat_type" ||
          key === "chat_instance" ||
          key === "start_param" ||
          key === "receiver" ||
          key === "can_send_after")
      ) {
        out.tgWebAppData = out.tgWebAppData + "&" + key + "=" + val;
        lengths.tgWebAppData = out.tgWebAppData.length;
        continue;
      }

      // Prefer first non-empty; do not clobber a good tgWebAppData with empty.
      if (typeof out[key] === "undefined" || (!out[key] && val)) {
        out[key] = val;
        lengths[key] = val.length;
      }
    }
    return { params: out, lengths: lengths };
  }

  function normalizeFragmentToQuery(hash) {
    var h = String(hash || "");
    if (h.charAt(0) === "#") h = h.slice(1);
    if (!h) return { query: "", path: "", decodePasses: 0, decodeOk: true };

    // Whole-fragment may be percent-encoded (Huawei WebView): tgWebAppData%3D...
    var decoded = limitedDecode(h, MAX_DECODE_PASSES);
    h = decoded.value;

    var path = "";
    var query = h;
    // SPA: #/path?tgWebAppData=...  or  #path?tgWebAppData=...
    var qIdx = h.indexOf("?");
    if (qIdx >= 0) {
      path = h.slice(0, qIdx);
      query = h.slice(qIdx + 1);
    } else if (h.charAt(0) === "/") {
      // #/route without query
      path = h;
      query = "";
    } else if (h.indexOf("=") < 0) {
      path = h;
      query = "";
    }

    // Leading '?' already stripped by slice; also handle '#?tgWebAppData='
    if (query.charAt(0) === "?") query = query.slice(1);

    return {
      query: query,
      path: path,
      decodePasses: decoded.passes,
      decodeOk: decoded.ok,
    };
  }

  function finalizeInitValue(rawVal, decodePassesSoFar) {
    if (rawVal == null || rawVal === "") {
      return { value: "", passes: decodePassesSoFar, ok: true, source: "" };
    }
    var decoded = limitedDecode(String(rawVal), MAX_DECODE_PASSES);
    var value = decoded.value;
    var passes = decodePassesSoFar + decoded.passes;
    // One more pass if still encoded nested form
    if (!looksLikeInitData(value) && value.indexOf("%") >= 0) {
      var again = limitedDecode(value, 1);
      value = again.value;
      passes += again.passes;
    }
    if (!looksLikeInitData(value)) {
      return { value: "", passes: passes, ok: decoded.ok, source: "rejected" };
    }
    return { value: value, passes: passes, ok: decoded.ok, source: "ok" };
  }

  function extractFromRawQuery(query, decodePassesSoFar) {
    var parsed = parseQueryKeepEquals(query);
    var raw = parsed.params.tgWebAppData;
    if (typeof raw === "undefined" || raw === null || raw === "") {
      // Key itself may still be encoded in a flat string
      if (String(query).indexOf("tgWebAppData%") >= 0 || String(query).indexOf("tgWebAppData=") >= 0) {
        var decodedQ = limitedDecode(query, MAX_DECODE_PASSES);
        parsed = parseQueryKeepEquals(decodedQ.value);
        raw = parsed.params.tgWebAppData;
        decodePassesSoFar += decodedQ.passes;
      }
    }
    var fin = finalizeInitValue(raw, decodePassesSoFar || 0);
    return {
      initData: fin.value,
      passes: fin.passes,
      ok: fin.ok,
      params: parsed.params,
      lengths: parsed.lengths,
    };
  }

  /**
   * Extract initData from location-like hash + search.
   * Returns { initData, meta } where meta is safe for diagnostics.
   */
  function extractInitDataFromUrl(hash, search) {
    hash = hash == null ? "" : String(hash);
    search = search == null ? "" : String(search);

    var attempts = [];
    var best = "";
    var bestMeta = null;

    function consider(label, result) {
      attempts.push(label);
      if (result && result.initData && looksLikeInitData(result.initData)) {
        if (!best || result.initData.length > best.length) {
          best = result.initData;
          bestMeta = result;
          bestMeta.label = label;
        }
      }
      return result;
    }

    var fromHashNorm = normalizeFragmentToQuery(hash);
    consider(
      "hash",
      extractFromRawQuery(fromHashNorm.query, fromHashNorm.decodePasses)
    );

    // Raw hash without SPA split (entire fragment as query)
    var rawHash = hash.charAt(0) === "#" ? hash.slice(1) : hash;
    if (rawHash && rawHash !== fromHashNorm.query) {
      consider("hash_flat", extractFromRawQuery(rawHash, 0));
      var decFlat = limitedDecode(rawHash, MAX_DECODE_PASSES);
      consider("hash_decoded_flat", extractFromRawQuery(decFlat.value, decFlat.passes));
    }

    var searchRaw = search.charAt(0) === "?" ? search.slice(1) : search;
    consider("search", extractFromRawQuery(searchRaw, 0));
    if (searchRaw) {
      var decSearch = limitedDecode(searchRaw, MAX_DECODE_PASSES);
      consider("search_decoded", extractFromRawQuery(decSearch.value, decSearch.passes));
    }

    return {
      initData: best,
      meta: bestMeta,
      attempts: attempts,
      hashNorm: fromHashNorm,
    };
  }

  /** Safe diagnostics — names and lengths only, never values. */
  function diagnoseLaunchUrl(hash, search) {
    hash = hash == null ? "" : String(hash);
    search = search == null ? "" : String(search);

    var hashNorm = normalizeFragmentToQuery(hash);
    var hashParsed = parseQueryKeepEquals(hashNorm.query);
    // If empty params but hash long — try decode-all
    if (
      Object.keys(hashParsed.params).length === 0 &&
      hash.length > 1
    ) {
      var alt = limitedDecode(hash.charAt(0) === "#" ? hash.slice(1) : hash, MAX_DECODE_PASSES);
      var altNorm = normalizeFragmentToQuery("#" + alt.value);
      hashParsed = parseQueryKeepEquals(altNorm.query);
      hashNorm.decodePasses = alt.passes;
      hashNorm.decodeOk = alt.ok;
    }

    var searchRaw = search.charAt(0) === "?" ? search.slice(1) : search;
    var searchParsed = parseQueryKeepEquals(searchRaw);
    if (Object.keys(searchParsed.params).length === 0 && searchRaw) {
      var ds = limitedDecode(searchRaw, MAX_DECODE_PASSES);
      searchParsed = parseQueryKeepEquals(ds.value);
    }

    var extracted = extractInitDataFromUrl(hash, search);
    var hp = hashParsed.params;
    var sp = searchParsed.params;

    function flag(obj, key) {
      return typeof obj[key] !== "undefined" && obj[key] !== null && String(obj[key]).length > 0;
    }

    function names(obj) {
      return Object.keys(obj).filter(function (k) {
        return k && k.charAt(0) !== "_";
      });
    }

    function lenMap(lengths, keys) {
      var parts = [];
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        parts.push(k + ":" + (lengths[k] != null ? lengths[k] : 0));
      }
      return parts.join(",").slice(0, 200);
    }

    var hashNames = names(hp);
    var searchNames = names(sp);
    var rawTgLen = 0;
    if (flag(hp, "tgWebAppData")) rawTgLen = String(hp.tgWebAppData).length;
    else if (flag(sp, "tgWebAppData")) rawTgLen = String(sp.tgWebAppData).length;

    return {
      hash_params: hashNames.join(",").slice(0, 120),
      hash_param_lens: lenMap(hashParsed.lengths, hashNames),
      search_params: searchNames.join(",").slice(0, 120),
      search_param_lens: lenMap(searchParsed.lengths, searchNames),
      has_tgwebappdata: flag(hp, "tgWebAppData") || flag(sp, "tgWebAppData"),
      tgwebappdata_len: Math.min(rawTgLen, 100000),
      has_tgwebappversion: flag(hp, "tgWebAppVersion") || flag(sp, "tgWebAppVersion"),
      has_tgwebappplatform: flag(hp, "tgWebAppPlatform") || flag(sp, "tgWebAppPlatform"),
      has_tgwebapptheme: flag(hp, "tgWebAppThemeParams") || flag(sp, "tgWebAppThemeParams"),
      decode_ok: hashNorm.decodeOk !== false,
      decode_passes: extracted.meta ? extracted.meta.passes || 0 : hashNorm.decodePasses || 0,
      extract_ok: !!extracted.initData,
      extract_source: extracted.meta ? extracted.meta.label || "" : "",
      extract_len: extracted.initData ? extracted.initData.length : 0,
      spa_path: !!(hashNorm.path && hashNorm.path.indexOf("/") >= 0),
    };
  }

  var api = {
    MAX_DECODE_PASSES: MAX_DECODE_PASSES,
    looksLikeInitData: looksLikeInitData,
    limitedDecode: limitedDecode,
    extractInitDataFromUrl: extractInitDataFromUrl,
    diagnoseLaunchUrl: diagnoseLaunchUrl,
    parseQueryKeepEquals: parseQueryKeepEquals,
    normalizeFragmentToQuery: normalizeFragmentToQuery,
  };

  root.FlyPingLaunchParams = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
