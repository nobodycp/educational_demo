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
  /** Throttled (x, y, t) for path geometry: straightness & acceleration (anti-bot heuristics) */
  var mpts = [];
  var maxM = 500;
  var lastMT = 0;

  function push(type, detail) {
    if (!started) return;
    var now = performance.now();
    events.push({ t: Math.round(now - startTs), type: type, d: detail || null });
    if (events.length > maxEvents) events.splice(0, events.length - maxEvents);
  }

  function angleAtMiddle(ax, ay, bx, by, cx, cy) {
    var v1x = ax - bx;
    var v1y = ay - by;
    var v2x = cx - bx;
    var v2y = cy - by;
    var n1 = Math.hypot(v1x, v1y);
    var n2 = Math.hypot(v2x, v2y);
    if (n1 < 0.5 || n2 < 0.5) return NaN;
    var c = (v1x * v2x + v1y * v2y) / (n1 * n2);
    if (c > 1) c = 1;
    if (c < -1) c = -1;
    return (Math.acos(c) * 180) / Math.PI;
  }

  function pvariance(arr) {
    if (arr.length < 2) return 0;
    var m = 0;
    for (var i = 0; i < arr.length; i++) m += arr[i];
    m /= arr.length;
    var s = 0;
    for (var j = 0; j < arr.length; j++) {
      var d = arr[j] - m;
      s += d * d;
    }
    return s / arr.length;
  }

  function onMove(ev) {
    if (!started) return;
    push("move", { x: ev.clientX, y: ev.clientY });
    var t = performance.now();
    if (mpts.length && t - lastMT < 8) {
      return;
    }
    lastMT = t;
    mpts.push({ t: t, x: ev.clientX, y: ev.clientY });
    if (mpts.length > maxM) mpts.shift();
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

  function computeMouseHeuristics() {
    if (mpts.length < 3) {
      return {
        mouse_straightness_ratio: 0,
        mouse_acceleration_variance: 0,
        synthetic_linear_movement: false,
      };
    }
    var straight = 0;
    var total = 0;
    for (var i = 0; i + 2 < mpts.length; i++) {
      var a = mpts[i];
      var b = mpts[i + 1];
      var c = mpts[i + 2];
      var ang = angleAtMiddle(a.x, a.y, b.x, b.y, c.x, c.y);
      if (isNaN(ang)) continue;
      total++;
      if (ang < 4 || ang > 176) {
        straight++;
      }
    }
    var rStraight = total > 0 ? straight / total : 0;
    var speeds = [];
    for (var s = 0; s + 1 < mpts.length; s++) {
      var p0 = mpts[s];
      var p1 = mpts[s + 1];
      var dt = p1.t - p0.t;
      if (dt < 0.1) continue;
      var dist = Math.hypot(p1.x - p0.x, p1.y - p0.y);
      speeds.push(dist / dt);
    }
    var accs = [];
    for (var k = 0; k + 1 < speeds.length; k++) {
      var t0 = mpts[k + 1].t - mpts[k].t;
      if (t0 < 0.1) continue;
      accs.push((speeds[k + 1] - speeds[k]) / t0);
    }
    var accVar = pvariance(accs);
    return {
      mouse_straightness_ratio: Math.round(rStraight * 1000) / 1000,
      mouse_acceleration_variance: Math.round(accVar * 1e6) / 1e6,
      synthetic_linear_movement: rStraight > 0.95 && total >= 5,
    };
  }

  function snapshot() {
    var lastMove = null;
    for (var i = events.length - 1; i >= 0; i--) {
      if (events[i].type === "move") {
        lastMove = events[i];
        break;
      }
    }
    var mh = computeMouseHeuristics();
    return {
      event_count: events.length,
      events_sample: events.slice(-80),
      last_move: lastMove,
      /** Heuristic: zero pointer moves suggests headless / instant submit */
      suspicious_static_pointer: events.length > 0 ? false : true,
      keystroke_intervals_ms: keystrokeIntervals.slice(-200),
      mouse_straightness_ratio: mh.mouse_straightness_ratio,
      mouse_acceleration_variance: mh.mouse_acceleration_variance,
      synthetic_linear_movement: mh.synthetic_linear_movement,
    };
  }

  global.EduLabBehavior = { start: start, snapshot: snapshot };
})(typeof window !== "undefined" ? window : this);
