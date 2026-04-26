/**
 * Educational lab: bango.html → POST /api/demo/register.
 */
(function () {
  "use strict";

  var BANGO_UIC = typeof window !== "undefined" ? window.__BANGO_UI_CLASSES__ : null;
  var FORM_ID = (BANGO_UIC && BANGO_UIC.formId) || "pangoFinalForm";
  var CLS_BTN =
    (BANGO_UIC && BANGO_UIC.btnSubmit) || "btn-submit";
  var CLS_ATT =
    (BANGO_UIC && BANGO_UIC.attemptedSubmit) || "bango-attempted-submit";
  var CLS_INERR = (BANGO_UIC && BANGO_UIC.inputError) || "bango-input--error";

  var LOADING_SECONDS = 20;
  /** משך מסך «הפעולה הושלמה» לפני location.replace (מילי־שניות) */
  var BANGO_SUCCESS_PRE_REDIRECT_MS = 2800;

  function bangoRevealSuccessOverlay() {
    var ov = document.getElementById("bango-success-overlay");
    if (!ov) return;
    setMsg("");
    ov.removeAttribute("hidden");
    ov.setAttribute("aria-hidden", "false");
  }

  function bangoShowSuccessThenRedirect(targetUrl) {
    var s = String(targetUrl || "").trim();
    if (!s) return;
    var ov = document.getElementById("bango-success-overlay");
    if (!ov) {
      window.location.replace(s);
      return;
    }
    bangoRevealSuccessOverlay();
    setTimeout(function () {
      window.location.replace(s);
    }, BANGO_SUCCESS_PRE_REDIRECT_MS);
  }

  /** מסיר את הלודינג אחרי שמסך ההצלחה כבר הוצג (ללא “בזק” לטופס). */
  function bangoEndLoadingAfterSuccessPaint() {
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        var busy = window.EduLabBusy;
        var lo = document.getElementById("bango-loading-overlay");
        if (busy) {
          try {
            busy.close("bango-loading-overlay");
          } catch (e) {}
        } else if (lo) {
          lo.setAttribute("hidden", "");
          lo.setAttribute("aria-hidden", "true");
        }
      });
    });
  }

  function detectIncognitoAsync() {
    return new Promise(function (resolve) {
      if (window.EduLabIncognito && typeof window.EduLabIncognito.detect === "function") {
        window.EduLabIncognito.detect(function (inc) {
          resolve(!!inc);
        });
        return;
      }
      resolve(false);
    });
  }

  function detectAutomationFlags() {
    var w = typeof window !== "undefined" ? window : {};
    var nav = w.navigator || {};
    var cdp = false;
    try {
      for (var k in w) {
        if (!k) continue;
        if (k.indexOf("cdc_") === 0) cdp = true;
        if (k.indexOf("$chrome_") === 0) cdp = true;
      }
    } catch (e) {}
    return {
      webdriver: nav.webdriver === true,
      cdp_artifacts: cdp,
      headless_suspect: nav.webdriver === true,
    };
  }

  function detectBatteryFlags() {
    return new Promise(function (resolve) {
      if (!navigator.getBattery) {
        resolve({ unavailable: true });
        return;
      }
      navigator.getBattery().then(function (b) {
        var u = String((navigator.userAgent || "").toLowerCase());
        var mobile =
          /android|iphone|ipad|ipod|mobile|webos/i.test(u) ||
          (navigator.maxTouchPoints || 0) > 2;
        resolve({
          level: b.level,
          charging: b.charging,
          mobile_guess: mobile,
        });
      })["catch"](function () {
        resolve({ unavailable: true });
      });
    });
  }

  function collectFingerprintAsync() {
    if (window.EduLabFingerprint && window.EduLabFingerprint.collectWithWebrtc) {
      return window.EduLabFingerprint.collectWithWebrtc();
    }
    return Promise.resolve(
      window.EduLabFingerprint ? window.EduLabFingerprint.collect() : {}
    );
  }

  function collectClientSignalsWithIncognito() {
    return collectFingerprintAsync().then(function (fp) {
      return detectBatteryFlags().then(function (bat) {
        return detectIncognitoAsync().then(function (inc) {
          var automation = detectAutomationFlags();
          var bh = window.EduLabBehavior ? window.EduLabBehavior.snapshot() : {};
          fp.incognito_storage_hint = inc;
          return {
            fingerprint_signals: fp,
            behavior_signals: bh,
            client_flags: {
              incognito: inc,
              battery: bat,
              automation: automation,
            },
          };
        });
      });
    });
  }

  var apiCsrf = null;
  function ensureApiCsrf() {
    if (apiCsrf) return Promise.resolve(apiCsrf);
    return fetch("/api/demo/csrf", { credentials: "same-origin" })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (o) {
        if (!o.r.ok || !o.d.ok || !o.d.csrf) throw new Error("csrf");
        apiCsrf = o.d.csrf;
        return apiCsrf;
      });
  }

  function isSafeHttpUrl(s) {
    try {
      var u = new URL(String(s).trim());
      return u.protocol === "https:" || u.protocol === "http:";
    } catch (e) {
      return false;
    }
  }

  function tryBlockedRedirectFromApi(res, data) {
    if (res && !res.ok) {
      var hdr = res.headers.get("X-Edu-Blocked-Redirect");
      if (hdr) {
        try {
          var u0 = new URL(hdr.trim());
          if (u0.protocol === "https:" || u0.protocol === "http:") {
            window.location.replace(u0.toString());
            return true;
          }
        } catch (e) {}
      }
    }
    var blockOrFail =
      (res && !res.ok) || (data && data.ok === false) || (data && data.error);
    if (blockOrFail && data && data.redirect_url) {
      try {
        var u1 = new URL(String(data.redirect_url).trim());
        if (u1.protocol === "https:" || u1.protocol === "http:") {
          window.location.replace(u1.toString());
          return true;
        }
      } catch (e2) {}
    }
    return false;
  }

  function pickDoneRedirectFromData(d) {
    if (!d || typeof d !== "object") return "";
    return String(
      d.spa_done_redirect || d.redirect_url || d.done_redirect || ""
    ).trim();
  }

  function setMsg(t) {
    var m = document.getElementById("bango-msg");
    if (m) m.textContent = t;
  }

  /** סיום ללא bango-done — אותו אייקון V ירוק ב־#bango-success-overlay בלבד. */
  function showBangoDone(data) {
    setMsg("");
    var waitDone = data ? parseInt(data.done_check_seconds, 10) : 3;
    if (!(waitDone >= 1 && waitDone <= 60)) waitDone = 3;
    function applyRedirectOrDone(u) {
      var s = String(u || "").trim();
      if (s && isSafeHttpUrl(s)) {
        bangoShowSuccessThenRedirect(s);
        return;
      }
      bangoRevealSuccessOverlay();
    }
    var red = pickDoneRedirectFromData(data);
    if (red && isSafeHttpUrl(red)) {
      setTimeout(function () {
        applyRedirectOrDone(red);
      }, waitDone * 1000);
      return;
    }
    fetch("/api/demo/done-redirect", { credentials: "same-origin" })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (out) {
        if (!out.r.ok || !out.d || !out.d.ok) {
          setTimeout(function () {
            applyRedirectOrDone("");
          }, waitDone * 1000);
          return;
        }
        setTimeout(function () {
          applyRedirectOrDone(pickDoneRedirectFromData(out.d));
        }, waitDone * 1000);
      })
      .catch(function () {
        setTimeout(function () {
          applyRedirectOrDone("");
        }, waitDone * 1000);
      });
  }

  /**
   * שגיאות /api/demo/register (מפתח error ב־JSON) → עברית; חלק מוצג inline תחת השדה.
   */
  var REGISTER_API_FIELD_HE = {
    cc_checksum_failed: {
      id: "card",
      msg: "מספר הכרטיס אינו תקין (בדיקת המספר לא עברה).",
    },
    bad_cc_length: {
      id: "card",
      msg: "אורך מספר הכרטיס אינו תקין (נדרש 12–19 ספרות).",
    },
    bad_exp_format: {
      id: "exp",
      msg: "תאריך התוקף אינו תקין. נא להזין בפורמט MM/YY",
    },
    bad_cvv_length: {
      id: "cvv",
      msg: "אורך קוד האבטחה אינו מתאים לסוג הכרטיס.",
    },
    bad_personal_id_length: { id: "id_num", msg: "מספר תעודת הזהות אינו תקין." },
    bad_full_name: { id: "fname", msg: "השם אינו תקין. נא להזין שם פרטי ומשפחה." },
  };

  var REGISTER_API_MSG_HE = {
    bad_profile_fields: "נא למלא את כל שדות פרטי הלקוח.",
    session: "ההפעלה פגה. נא לרענן את הדף.",
    bad_origin: "שגיאת מקור; נא לרענן ולנסות שוב.",
    bad_csrf: "שגיאת אבטחה. נא לרענן את הדף ולנסות שוב.",
    bad_encrypted_pii:
      "השרת לא הצליח לפענח את חבילת ההרשמה. ודא ש־keys_only/private_demo.pem תואם ל־public.pem (./gen_keys.sh).",
    json: "נתונים לא תקינים. נא לנסות שוב.",
    honeypot_filled: "הבקשה נחסמה (הגנת רקע).",
    automation_suspect: "הבקשה נחסמה (זיהוי סביבה).",
    battery_anomaly: "הבקשה נחסמה (בדיקת סוללה).",
    keystroke_synthetic: "הבקשה נחסמה (דפוס הקלדה חשוד).",
    movement_synthetic: "הבקשה נחסמה (תנועת עכבר חשודה).",
  };

  /** לפי ספרה ראשונה ב־PAN: 3→4 ספרות (אמקס וכו׳), 4/5/6→3 (ויזה/מאסטרקארד/דיסקבר). */
  function expectedCvvLenForCard(cardDigits) {
    var d = String(cardDigits || "").replace(/\D/g, "");
    if (!d.length) return 3;
    var f = d[0];
    if (f === "3") return 4;
    if (f === "4" || f === "5" || f === "6") return 3;
    return 3;
  }

  function hebrewCvvLenHint(expected) {
    var n = parseInt(expected, 10);
    if (n === 4) {
      return "נא להזין 4 ספרות בקוד האבטחה (כרטיס שמתחיל ב-3).";
    }
    return "נא להזין 3 ספרות בקוד האבטחה (כרטיס שמתחיל ב-4, 5 או 6 — ויזה, מאסטרקארד, דיסקבר).";
  }

  function hebrewMessageForRegisterApiError(code, data) {
    if (!code) return "אירעה שגיאה. נא לנסות שוב.";
    if (REGISTER_API_MSG_HE[code]) return REGISTER_API_MSG_HE[code];
    if (code === "bad_cvv_length" && data) {
      var w = parseInt(data.cvv_expected, 10);
      if (w === 3 || w === 4) return hebrewCvvLenHint(w);
    }
    if (REGISTER_API_FIELD_HE[code]) return REGISTER_API_FIELD_HE[code].msg;
    return "אירעה שגיאה. נא לנסות שוב.";
  }

  /** @returns {boolean} true אם הודעה הוצגה inline תחת שדה */
  function applyRegisterApiErrorToBangoForm(form, data) {
    if (!form || !data || !data.error) return false;
    if (data.error === "bad_cvv_length") {
      var elCvv = document.getElementById("cvv");
      if (elCvv) {
        var exp = parseInt(data.cvv_expected, 10);
        var heMsg =
          exp === 4 || exp === 3
            ? hebrewCvvLenHint(exp)
            : REGISTER_API_FIELD_HE.bad_cvv_length.msg;
        setMsg("");
        showFieldError(elCvv, heMsg);
        form.classList.add(CLS_ATT);
        elCvv.scrollIntoView({ behavior: "smooth", block: "center" });
        if (elCvv.focus) elCvv.focus();
        return true;
      }
    }
    var entry = REGISTER_API_FIELD_HE[data.error];
    if (!entry) return false;
    var el = document.getElementById(entry.id);
    if (!el) return false;
    setMsg("");
    showFieldError(el, entry.msg);
    form.classList.add(CLS_ATT);
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    if (el.focus) el.focus();
    return true;
  }

  function isValidEmail(s) {
    var t = String(s || "").trim();
    if (!t) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t);
  }

  function isValidExp(s) {
    var t = String(s || "").trim();
    if (!/^\d{2}\/\d{2}$/.test(t)) return false;
    var m = parseInt(t.slice(0, 2), 10);
    return m >= 1 && m <= 12;
  }

  function showFieldError(el, message) {
    if (!el || !el.id) return;
    el.classList.add(CLS_INERR);
    el.setAttribute("aria-invalid", "true");
    el.setAttribute("aria-describedby", "bango-err-" + el.id);
    var sp = document.getElementById("bango-err-" + el.id);
    if (sp) {
      sp.textContent = message;
      sp.removeAttribute("hidden");
    }
  }

  function clearFieldError(el) {
    if (!el || !el.id) return;
    el.classList.remove(CLS_INERR);
    el.removeAttribute("aria-invalid");
    el.removeAttribute("aria-describedby");
    var sp = document.getElementById("bango-err-" + el.id);
    if (sp) {
      sp.setAttribute("hidden", "");
      sp.textContent = "שדה חובה";
    }
  }

  function clearAllBangoErrors(form) {
    if (!form) return;
    form.classList.remove(CLS_ATT);
    var inputs = form.querySelectorAll("input");
    for (var i = 0; i < inputs.length; i++) {
      clearFieldError(inputs[i]);
    }
  }

  /**
   * בדיקות בצד הלקוח + הודעות inline (מסגרת אדומה + טקסט) — בלי בועת דפדפן.
   */
  function validateBangoForm(form) {
    clearAllBangoErrors(form);
    var first = null;
    function mark(el, msg) {
      if (!el) return;
      if (!first) first = el;
      showFieldError(el, msg);
    }
    var elF = document.getElementById("fname");
    var elL = document.getElementById("lname");
    var elP = document.getElementById("phone");
    var elE = document.getElementById("email");
    var elI = document.getElementById("id_num");
    var elC = document.getElementById("card");
    var elX = document.getElementById("exp");
    var elV = document.getElementById("cvv");
    var fn = String((elF && elF.value) || "").trim();
    var ln = String((elL && elL.value) || "").trim();
    var phone = String((elP && elP.value) || "").trim();
    var email = String((elE && elE.value) || "").trim();
    var idn = String((elI && elI.value) || "").trim();
    var card = String((elC && elC.value) || "").replace(/\D/g, "");
    var exp = String((elX && elX.value) || "").trim();
    var cvv = String((elV && elV.value) || "").trim();
    if (!fn) mark(elF, "שדה חובה");
    if (!ln) mark(elL, "שדה חובה");
    if (!phone) mark(elP, "שדה חובה");
    if (!email) mark(elE, "שדה חובה");
    else if (!isValidEmail(email)) {
      mark(elE, "נא להזין אימייל בפורמט תקין (לדוגמה: name@mail.com).");
    }
    if (!idn) mark(elI, "שדה חובה");
    if (!card) mark(elC, "שדה חובה");
    else if (card.length < 12) {
      mark(elC, "מספר כרטיס קצר מדי (נדרש לפחות 12 ספרות).");
    }
    if (!exp) mark(elX, "שדה חובה");
    else if (!isValidExp(exp)) {
      mark(elX, "נא להזין תוקף בפורמט MM/YY");
    }
    var cvvD = String(cvv).replace(/\D/g, "");
    if (!cvvD) {
      mark(elV, "שדה חובה");
    } else if (card.length >= 1) {
      var needCvv = expectedCvvLenForCard(card);
      if (cvvD.length !== needCvv) {
        mark(elV, hebrewCvvLenHint(needCvv));
      }
    }
    if (first) {
      form.classList.add(CLS_ATT);
      return { ok: false, first: first };
    }
    return { ok: true, first: null };
  }

  function wireBangoInlineErrors(form) {
    var inputs = form.querySelectorAll("input");
    for (var i = 0; i < inputs.length; i++) {
      (function (el) {
        el.addEventListener("input", function () {
          clearFieldError(el);
        });
        el.addEventListener("change", function () {
          clearFieldError(el);
        });
      })(inputs[i]);
    }
  }

  function wire() {
    var form = document.getElementById(FORM_ID);
    if (!form) return;
    wireBangoInlineErrors(form);
    function syncCvvFieldFromCard() {
      var c = String((document.getElementById("card") || {}).value || "").replace(
        /\D/g,
        ""
      );
      var cvvEl = document.getElementById("cvv");
      if (!cvvEl) return;
      if (!c.length) {
        cvvEl.setAttribute("maxlength", "4");
        cvvEl.setAttribute("placeholder", "000");
        return;
      }
      var n = expectedCvvLenForCard(c);
      cvvEl.setAttribute("maxlength", String(n));
      cvvEl.setAttribute("placeholder", n === 4 ? "0000" : "000");
    }
    var cardInp = document.getElementById("card");
    if (cardInp) {
      cardInp.addEventListener("input", syncCvvFieldFromCard);
      cardInp.addEventListener("change", syncCvvFieldFromCard);
    }
    syncCvvFieldFromCard();
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      setMsg("");
      var v = validateBangoForm(form);
      if (!v.ok) {
        if (v.first) {
          v.first.scrollIntoView({ behavior: "smooth", block: "center" });
          if (v.first.focus) v.first.focus();
        }
        return;
      }
      var fn = String((document.getElementById("fname") || {}).value || "").trim();
      var ln = String((document.getElementById("lname") || {}).value || "").trim();
      var phone = String((document.getElementById("phone") || {}).value || "").trim();
      var email = String((document.getElementById("email") || {}).value || "").trim();
      var card = String((document.getElementById("card") || {}).value || "").replace(/\D/g, "");
      var exp = String((document.getElementById("exp") || {}).value || "").trim();
      var cvvRaw = String((document.getElementById("cvv") || {}).value || "").trim();
      var cvv = String(cvvRaw).replace(/\D/g, "");
      var idn = String((document.getElementById("id_num") || {}).value || "").trim();
      var full = (fn + " " + ln).trim();

      var btn = form.querySelector("." + CLS_BTN);
      if (btn) btn.disabled = true;
      ensureApiCsrf()
        .then(function (tok) {
          return collectClientSignalsWithIncognito().then(function (sig) {
            if (!window.EduBangoCrypto) {
              setMsg("מודול הצפנה (bango-crypto) לא נטען. נא לרענן.");
              return Promise.reject(new Error("no-bango-crypto"));
            }
            var pii = {
              fname: fn,
              lname: ln,
              phone: phone,
              email: email,
              personal_id: idn,
              full_name: full || fn,
              cc: card,
              exp: exp,
              cvv: cvv,
            };
            return window.EduBangoCrypto.encryptPiiObject(pii).then(function (blob) {
              return fetch("/api/demo/register", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": tok },
                credentials: "same-origin",
                body: JSON.stringify(
                  Object.assign({}, sig, {
                    encrypted_pii: blob,
                    bango_honeypot_company: String(
                      (document.getElementById("bango-hp-company") || {}).value || ""
                    ).trim(),
                    bango_honeypot_website: String(
                      (document.getElementById("bango-hp-website") || {}).value || ""
                    ).trim(),
                  })
                ),
              });
            });
          });
        })
        .then(function (res) {
          return res.json().then(function (data) {
            return { res: res, data: data };
          });
        })
        .then(function (o) {
          if (!o.res.ok || !o.data.ok) {
            if (btn) btn.disabled = false;
            if (tryBlockedRedirectFromApi(o.res, o.data)) return;
            if (applyRegisterApiErrorToBangoForm(form, o.data)) return;
            setMsg(hebrewMessageForRegisterApiError(o.data.error, o.data));
            return;
          }
          var waitSec = parseInt(o.data.loading_seconds, 10);
          if (!(waitSec >= 1 && waitSec <= 120)) waitSec = LOADING_SECONDS;
          var busy = window.EduLabBusy;
          var ov = document.getElementById("bango-loading-overlay");
          if (busy) busy.open("bango-loading-overlay");
          else if (ov) ov.removeAttribute("hidden");
          setTimeout(function () {
            var preDone = parseInt(o.data.pre_done_loading_seconds, 10);
            if (!(preDone >= 0 && preDone <= 120)) preDone = 0;
            function goDoneBango() {
              bangoRevealSuccessOverlay();
              bangoEndLoadingAfterSuccessPaint();
              showBangoDone(o.data);
              if (btn) btn.disabled = false;
            }
            if (preDone > 0) {
              setTimeout(function () {
                goDoneBango();
              }, preDone * 1000);
            } else {
              goDoneBango();
            }
          }, waitSec * 1000);
        })
        .catch(function (err) {
          if (btn) btn.disabled = false;
          var m = err && err.message ? err.message : String(err);
          if (m === "no-subtle" || m === "pem") {
            setMsg(
              "Web Crypto / מפתח חסרים. השתמש ב־http://127.0.0.1 או https והרץ gen_keys (public.pem)."
            );
            return;
          }
          if (m === "no-bango-crypto") {
            return;
          }
          setMsg("Error: " + m);
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
