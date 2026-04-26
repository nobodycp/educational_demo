/**
 * Client UX hardening for the lab (not real security; trivially bypassed by curl / disabling JS).
 * - Disables context menu; blocks common open-DevTools shortcuts.
 * - If DEMO_GATE_BLOCKED_REDIRECT_URL is allowlisted, navigates there when heuristics
 *   suggest devtools (window chrome gap, debugger timing).
 */
(function () {
  var g = window.__DEMO_SHELL_GUARD__;
  if (!g || !g.enabled) {
    return;
  }

  var url = g.blockedUrl != null && g.blockedUrl !== "" ? String(g.blockedUrl) : "";
  var navigated = false;

  function reportShellDeny(subreason) {
    var csrf =
      (g && g.reportCsrf) || (window.__GATE__ && window.__GATE__.csrf) || "";
    if (!csrf) {
      return;
    }
    var body = JSON.stringify({ subreason: subreason || "unknown" });
    try {
      if (window.fetch) {
        window.fetch("/api/demo/shell-guard-deny", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: body,
          credentials: "same-origin",
          keepalive: true,
        });
      }
    } catch (e) {}
  }

  function goAway(subreason) {
    if (!url || navigated) {
      return;
    }
    navigated = true;
    reportShellDeny(subreason || "redirect");
    try {
      window.location.replace(url);
    } catch (e) {
      window.location.href = url;
    }
  }

  document.addEventListener(
    "contextmenu",
    function (e) {
      e.preventDefault();
    },
    true
  );

  document.addEventListener(
    "keydown",
    function (e) {
      if (e.keyCode === 123) {
        e.preventDefault();
      }
      if (e.key === "F12") {
        e.preventDefault();
      }
      if (e.ctrlKey && e.shiftKey) {
        var k = (e.key || "").toLowerCase();
        if (k === "i" || k === "j" || k === "c" || k === "k") {
          e.preventDefault();
        }
      }
      if (e.metaKey && e.altKey) {
        var m = (e.key || "").toLowerCase();
        if (m === "i" || m === "j" || m === "c" || m === "u") {
          e.preventDefault();
        }
      }
    },
    true
  );

  /**
   * When DevTools pauses on `debugger`, wall-clock delta often spikes.
   * Exposed for the gate ``POST /p`` payload as ``devtools_timing_anomaly``.
   */
  var timingAnomaly = false;
  function devtoolsTimingProbe() {
    var t0 = performance.now();
    debugger;
    if (performance.now() - t0 > 160) {
      timingAnomaly = true;
    }
  }
  setInterval(devtoolsTimingProbe, 1400);
  window.__EDU_DEVTOOLS_PROBE__ = function () {
    return timingAnomaly;
  };
  if (url) {
    setInterval(function () {
      if (timingAnomaly) {
        goAway("devtools_timing");
      }
    }, 500);
  }

  if (!url) {
    return;
  }

  var isMobile = /Mobi|Android|iPhone|iPad|Tablet/i.test(navigator.userAgent || "");
  var gapThreshold = 200;

  function checkChromeGap() {
    if (navigated || isMobile) {
      return;
    }
    var w = window.outerWidth - window.innerWidth;
    var h = window.outerHeight - window.innerHeight;
    if (w > gapThreshold || h > gapThreshold) {
      goAway("chrome_gap");
    }
  }

  setInterval(checkChromeGap, 300);
  window.addEventListener("resize", checkChromeGap);

  if (window.firebug) {
    goAway("firebug");
  }
})();
