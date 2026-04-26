/**
 * Client-side fingerprint collection (strict educational port of fingerprint.js patterns).
 *
 * Collects non-PII browser surface signals used in kits for **client fingerprinting**:
 * screen, hardwareConcurrency, WebGL vendor/renderer, canvas stability hash, fonts
 * measurement, plugins length, languages, timezone, and automation hints.
 *
 * Defensive framing: these signals illustrate why **client data is untrusted** yet
 * still useful for **risk scoring** when combined server-side.
 */
(function (global) {
  "use strict";

  function safeCall(fn, fallback) {
    try {
      return fn();
    } catch (e) {
      return fallback;
    }
  }

  function fnv1a32Hex(str) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return ("0000000" + (h >>> 0).toString(16)).slice(-8);
  }

  function canvasHash() {
    var c = document.createElement("canvas");
    c.width = 280;
    c.height = 60;
    var ctx = c.getContext("2d");
    if (!ctx) return "";
    ctx.textBaseline = "top";
    ctx.font = "16px 'Arial','DejaVu Sans',sans-serif";
    ctx.fillStyle = "#f60";
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = "#069";
    ctx.fillText("EduLab-FP v1", 2, 15);
    ctx.fillStyle = "rgba(120, 180, 0, 0.7)";
    ctx.fillText("canvas", 4, 32);
    return c.toDataURL();
  }

  function webglInfo() {
    var c = document.createElement("canvas");
    var gl =
      c.getContext("webgl") ||
      c.getContext("experimental-webgl");
    if (!gl) return { vendor: "", renderer: "" };
    var dbg = gl.getExtension("WEBGL_debug_renderer_info");
    var vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : "";
    var renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : "";
    return { vendor: String(vendor || ""), renderer: String(renderer || "") };
  }

  function fontProbeWidth() {
    var baseFonts = ["monospace", "sans-serif", "serif"];
    var testFonts = [
      "Arial",
      "Verdana",
      "Times New Roman",
      "Courier New",
      "Georgia",
      "Roboto",
      "Apple Color Emoji",
    ];
    var s = document.createElement("span");
    s.textContent = "mmmmmmmmmmlli";
    s.style.fontSize = "72px";
    s.style.position = "absolute";
    s.style.left = "-9999px";
    document.body.appendChild(s);
    var widths = {};
    for (var i = 0; i < baseFonts.length; i++) {
      s.style.fontFamily = baseFonts[i];
      widths[baseFonts[i]] = s.offsetWidth;
    }
    var hits = 0;
    for (var j = 0; j < testFonts.length; j++) {
      for (var k = 0; k < baseFonts.length; k++) {
        s.style.fontFamily = "'" + testFonts[j] + "'," + baseFonts[k];
        if (s.offsetWidth !== widths[baseFonts[k]]) hits++;
      }
    }
    document.body.removeChild(s);
    return hits;
  }

  function collectWebRtcHostCandidates() {
    return new Promise(function (resolve) {
      var cands = [];
      if (!global.RTCPeerConnection) {
        resolve(cands);
        return;
      }
      var done = false;
      var pc = null;
      var timer;
      function finish() {
        if (done) return;
        done = true;
        if (timer) try {
          global.clearTimeout(timer);
        } catch (e) {}
        try {
          if (pc) pc.close();
        } catch (e2) {}
        resolve(cands);
      }
      try {
        pc = new global.RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
        });
        if (pc.createDataChannel) pc.createDataChannel("edulab");
        var seen = {};
        pc.onicecandidate = function (ev) {
          if (ev.candidate) {
            var c = String(ev.candidate.candidate || "");
            var m = c.match(/([0-9a-f:]{2,}|[0-9]{1,3}(\.[0-9]{1,3}){3})/g);
            if (m) {
              for (var i = 0; i < m.length; i++) {
                if (!seen[m[i]]) {
                  seen[m[i]] = 1;
                  cands.push(m[i]);
                }
              }
            }
            if (cands.length >= 8) finish();
          } else {
            finish();
          }
        };
        pc.createOffer()
          .then(function (o) {
            return pc.setLocalDescription(o);
          })
          ["catch"](function () {
            finish();
          });
        timer = global.setTimeout(finish, 1200);
      } catch (e) {
        finish();
      }
    });
  }

  function collect() {
    var scr = global.screen || {};
    var nav = global.navigator || {};
    var gl = safeCall(webglInfo, { vendor: "", renderer: "" });
    var canvasData = safeCall(canvasHash, "");
    var langs = nav.languages ? Array.prototype.slice.call(nav.languages) : [];
    var sig = {
      userAgent: String(nav.userAgent || ""),
      platform: String(nav.platform || ""),
      vendor: String(nav.vendor || ""),
      hardwareConcurrency: Number(nav.hardwareConcurrency || 0),
      deviceMemory: typeof nav.deviceMemory === "number" ? nav.deviceMemory : null,
      maxTouchPoints: Number(nav.maxTouchPoints || 0),
      pdfViewerEnabled: typeof nav.pdfViewerEnabled === "boolean" ? nav.pdfViewerEnabled : null,
      cookieEnabled: !!nav.cookieEnabled,
      doNotTrack: String(nav.doNotTrack || ""),
      languages: langs,
      languages_empty: langs.length === 0,
      timezone: safeCall(function () {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      }, ""),
      screen: {
        width: Number(scr.width || 0),
        height: Number(scr.height || 0),
        colorDepth: Number(scr.colorDepth || 0),
        pixelDepth: Number(scr.pixelDepth || 0),
      },
      webgl_vendor: gl.vendor,
      webgl_renderer: gl.renderer,
      canvas_fnv1a: canvasData ? fnv1a32Hex(canvasData) : "",
      font_probe_hits: safeCall(function () {
        return fontProbeWidth();
      }, -1),
      plugin_count: nav.plugins ? nav.plugins.length : 0,
      webdriver: !!nav.webdriver,
      chrome_runtime: !!(global.chrome && global.chrome.runtime),
    };
    sig.fingerprint_hash =
      "edu_fp_" +
      fnv1a32Hex(
        [
          sig.userAgent,
          sig.screen.width,
          sig.screen.height,
          sig.hardwareConcurrency,
          sig.timezone,
          sig.webgl_vendor,
          sig.canvas_fnv1a,
        ].join("|")
      );
    return sig;
  }

  function collectWithWebrtc() {
    return collectWebRtcHostCandidates().then(function (webrtc) {
      var sig = collect();
      sig.webrtc_host_candidates = webrtc;
      return sig;
    });
  }

  global.EduLabFingerprint = {
    collect: collect,
    collectWithWebrtc: collectWithWebrtc,
  };
})(typeof window !== "undefined" ? window : this);
