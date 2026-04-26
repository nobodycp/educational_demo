/**
 * Tiny helpers for reusable glass overlays + shared `.lab-spinner` (see `static/surface/`).
 *
 * Usage:
 *   EduLabBusy.open("my-overlay-id");
 *   EduLabBusy.setText("my-overlay-id", "Please wait…");
 *   EduLabBusy.close("my-overlay-id");
 */
(function (global) {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function textNode(overlayId) {
    var root = byId(overlayId);
    if (!root) return null;
    return root.querySelector(".lab-glass-overlay__text");
  }

  global.EduLabBusy = {
    open: function (overlayId) {
      var el = byId(overlayId);
      if (!el) return;
      el.removeAttribute("hidden");
      el.setAttribute("aria-busy", "true");
      el.setAttribute("aria-hidden", "false");
    },

    close: function (overlayId) {
      var el = byId(overlayId);
      if (!el) return;
      el.setAttribute("hidden", "");
      el.removeAttribute("aria-busy");
      el.setAttribute("aria-hidden", "true");
    },

    /** Sets the caption under the spinner inside the overlay panel. */
    setText: function (overlayId, message) {
      var t = textNode(overlayId);
      if (t) t.textContent = message || "";
    },
  };
})(typeof window !== "undefined" ? window : this);
