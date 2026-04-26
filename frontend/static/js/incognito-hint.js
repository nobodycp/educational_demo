/**
 * Best-effort private / incognito *hints* (no browser exposes a reliable boolean).
 *
 * Many Chromium builds report a much smaller `navigator.storage.estimate().quota` in
 * incognito than in a normal profile. A hard cut-off at ~1.1GB (`quota < 1.1e9` = private)
 * fails on newer Chrome (incognito can report 1.2–4GB). We combine `usage` / ratio
 * checks and treat `quota >= 5GB` as likely a non‑ephemeral profile.
 */
(function (global) {
  "use strict";

  function isMobileOrTablet() {
    var ua = navigator.userAgent || "";
    if (/Mobi|Android|iPhone|iPad|Tablet|SM-T|IEMobile|webOS|BlackBerry/i.test(ua)) {
      return true;
    }
    if (navigator.maxTouchPoints > 1 && /Mac OS X|Macintosh/.test(ua) && "ontouchend" in document) {
      return true;
    }
    return false;
  }

  function isDesktopChromium() {
    return !isMobileOrTablet() && !!global.chrome;
  }

  function isDesktopWebKitSafari() {
    var ua = navigator.userAgent || "";
    if (global.safari === undefined) {
      return false;
    }
    if (/Chrome\//.test(ua) || /Chromium\//.test(ua)) {
      return false;
    }
    return /Version\//.test(ua) && /Safari\//.test(ua);
  }

  /**
   * @param {number|undefined} usage
   * @param {number|undefined} quota
   */
  function storagePrivateHintFromQuotaUsage(usage, quota) {
    var q = typeof quota === "number" && !isNaN(quota) ? quota : 0;
    var u = typeof usage === "number" && !isNaN(usage) ? usage : 0;
    if (q <= 0) {
      return false;
    }
    if (q < 12e7) {
      return true;
    }
    if (isMobileOrTablet()) {
      return false;
    }
    if (!isDesktopChromium() && !isDesktopWebKitSafari()) {
      return false;
    }
    if (q >= 5e9) {
      return false;
    }
    if (q < 1.1e9) {
      return true;
    }
    if (u < 6e4 && u / Math.max(q, 1) < 1e-4) {
      return true;
    }
    return false;
  }

  function storageHintFromEstimate(est) {
    if (!est || typeof est !== "object") {
      return storagePrivateHintFromQuotaUsage(0, 0);
    }
    return storagePrivateHintFromQuotaUsage(est.usage, est.quota);
  }

  /**
   * @param {function(boolean): void} cb
   *   `true` = at least one heuristic suggests private / incognito (may be spoofed or wrong).
   */
  function detectIncognitoHint(cb) {
    if (typeof cb !== "function") {
      return;
    }
    try {
      try {
        global.localStorage.setItem("__edu_lab_ls", "1");
        global.localStorage.removeItem("__edu_lab_ls");
      } catch (eLs) {
        cb(true);
        return;
      }

      var checks = [];

      if (navigator.storage && navigator.storage.estimate) {
        checks.push(
          navigator.storage
            .estimate()
            .then(function (est) {
              return storageHintFromEstimate(est);
            })
            .catch(function () {
              return true;
            })
        );
      }

      if (global.webkitTemporaryStorage && global.webkitTemporaryStorage.queryUsageAndQuota) {
        checks.push(
          new Promise(function (resolve) {
            try {
              global.webkitTemporaryStorage.queryUsageAndQuota(
                function (usage, quota) {
                  resolve(storagePrivateHintFromQuotaUsage(usage, quota));
                },
                function () {
                  resolve(false);
                }
              );
            } catch (eWk) {
              resolve(false);
            }
          })
        );
      }

      if (global.indexedDB) {
        checks.push(
          new Promise(function (resolve) {
            var settled = false;
            var t = setTimeout(function () {
              if (!settled) {
                settled = true;
                resolve(false);
              }
            }, 800);
            var req;
            try {
              req = global.indexedDB.open("__edu_incognito_probe", 1);
            } catch (eIdb) {
              clearTimeout(t);
              resolve(true);
              return;
            }
            req.onupgradeneeded = function () {};
            req.onerror = function () {
              if (!settled) {
                settled = true;
                clearTimeout(t);
                resolve(true);
              }
            };
            req.onsuccess = function () {
              if (!settled) {
                settled = true;
                clearTimeout(t);
                try {
                  req.result.close();
                  global.indexedDB.deleteDatabase("__edu_incognito_probe");
                } catch (eClose) {}
                resolve(false);
              }
            };
          })
        );
      }

      if (!checks.length) {
        cb(false);
        return;
      }

      Promise.all(checks).then(function (results) {
        cb(results.some(Boolean));
      });
    } catch (e) {
      cb(false);
    }
  }

  global.EduLabIncognito = { detect: detectIncognitoHint };
})(
  typeof window !== "undefined" ? window : typeof globalThis !== "undefined" ? globalThis : this
);
