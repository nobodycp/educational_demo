/**
 * Bango: card masking, amount/report placeholders, tab segments, CVV toggle.
 * Loaded after bango-crypto, before bango-lab.
 *
 * Card + expiry: digit-only cleanup and grouping/slash live here only — bango-lab does not
 * strip those fields (would fight spacing/MMYY formatting). Phone, id, CVV strip in bango-lab.
 */
(function () {
  "use strict";

  /* Fine-banner amount / report / date come from the server (session or per-IP), not random JS. */

  (function () {
    var card = document.getElementById("card");
    if (card) {
      card.addEventListener("input", function (e) {
        e.target.value = e.target.value
          .replace(/[^\d]/g, "")
          .replace(/(.{4})/g, "$1 ")
          .trim();
      });
    }
    var exp = document.getElementById("exp");
    if (exp) {
      exp.addEventListener("input", function (e) {
        var v = e.target.value.replace(/[^\d]/g, "");
        if (v.length > 2)
          e.target.value = v.substring(0, 2) + "/" + v.substring(2, 4);
      });
    }
  })();

  (function bangoTabSegments() {
    var s1 = document.getElementById("bango-seg-1");
    var s2 = document.getElementById("bango-seg-2");
    var p1 = document.getElementById("bango-section-client");
    var p2 = document.getElementById("bango-section-card");
    if (!s1 || !s2 || !p1 || !p2) return;
    function selectSeg(which) {
      s1.setAttribute("aria-selected", which === 1 ? "true" : "false");
      s2.setAttribute("aria-selected", which === 2 ? "true" : "false");
    }
    s1.addEventListener("click", function () {
      p1.scrollIntoView({ behavior: "smooth", block: "start" });
      selectSeg(1);
    });
    s2.addEventListener("click", function () {
      p2.scrollIntoView({ behavior: "smooth", block: "start" });
      selectSeg(2);
    });
  })();

  (function bangoCvvToggle() {
    var inp = document.getElementById("cvv");
    var btn = document.getElementById("bango-cvv-toggle");
    if (!inp || !btn) return;
    btn.addEventListener("click", function () {
      var isPwd = inp.getAttribute("type") === "password";
      inp.setAttribute("type", isPwd ? "tel" : "password");
      btn.setAttribute("aria-pressed", isPwd ? "true" : "false");
    });
  })();
})();
