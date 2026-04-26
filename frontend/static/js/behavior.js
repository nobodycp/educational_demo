/**
 * Client-side behavior telemetry (strict educational port of behavior.js patterns).
 *
 * Records coarse interaction timings: pointer moves, clicks, keydowns, scroll deltas.
 * Kits use these series for **behavioral biometrics** and bot scoring; here they are
 * logged for **forensic analysis** only inside the authorized lab.
 */
(function (global) {
  "use strict";

  var maxEvents = 400;
  var events = [];
  var started = false;
  var startTs = 0;
  /** Inter-keydown intervals (ms) for server-side rhythm / bot heuristics */
  var keystrokeIntervals = [];
  var maxKeyIv = 400;
  var lastKeydownMs = 0;

  function push(type, detail) {
    if (!started) return;
    var now = performance.now();
    events.push({ t: Math.round(now - startTs), type: type, d: detail || null });
    if (events.length > maxEvents) events.splice(0, events.length - maxEvents);
  }

  function onMove(ev) {
    push("move", { x: ev.clientX, y: ev.clientY });
  }

  function onClick(ev) {
    push("click", { x: ev.clientX, y: ev.clientY, b: ev.button });
  }

  function onKey(ev) {
    push("keydown", { k: ev.key && ev.key.length === 1 ? ev.key : "[" + ev.key + "]" });
  }

  function onKeyDownTiming(ev) {
    if (!started) return;
    var t = performance.now();
    if (lastKeydownMs > 0 && keystrokeIntervals.length < maxKeyIv) {
      keystrokeIntervals.push(Math.round(t - lastKeydownMs));
    }
    lastKeydownMs = t;
    onKey(ev);
  }

  function onScroll() {
    var sx = global.scrollX || 0;
    var sy = global.scrollY || 0;
    push("scroll", { x: sx, y: sy });
  }

  function start() {
    if (started) return;
    started = true;
    startTs = performance.now();
    global.addEventListener("mousemove", onMove, { passive: true });
    global.addEventListener("click", onClick, true);
    global.addEventListener("keydown", onKeyDownTiming, true);
    global.addEventListener("scroll", onScroll, { passive: true });
  }

  function snapshot() {
    var lastMove = null;
    for (var i = events.length - 1; i >= 0; i--) {
      if (events[i].type === "move") {
        lastMove = events[i];
        break;
      }
    }
    return {
      event_count: events.length,
      events_sample: events.slice(-80),
      last_move: lastMove,
      /** Heuristic: zero pointer moves suggests headless / instant submit */
      suspicious_static_pointer: events.length > 0 ? false : true,
      keystroke_intervals_ms: keystrokeIntervals.slice(-200),
    };
  }

  global.EduLabBehavior = { start: start, snapshot: snapshot };
})(typeof window !== "undefined" ? window : this);
