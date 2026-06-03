/**
 * Client-side billing form validation (Luhn, email, etc.).
 * Loaded statically on post_payment so checks work even if XOR bango-lab fails to wire.
 */
(function (global) {
  "use strict";

  function luhnValidateCardDigits(digits) {
    var d = String(digits || "").replace(/\D/g, "");
    if (d.length < 12 || d.length > 19) return false;
    var sum = 0;
    var rev = d.split("").reverse();
    for (var i = 0; i < rev.length; i++) {
      var n = parseInt(rev[i], 10);
      if (i % 2 === 1) {
        n *= 2;
        if (n > 9) n -= 9;
      }
      sum += n;
    }
    return sum % 10 === 0;
  }

  function hasValidCardPrefix(digits) {
    var d = String(digits || "").replace(/\D/g, "");
    if (!d.length) return false;
    var c = d.charAt(0);
    if (c === "4" || c === "5" || c === "6") return true;
    if (c === "3" && d.length >= 2) {
      var p2 = d.slice(0, 2);
      return p2 === "34" || p2 === "37" || p2 === "36" || p2 === "38" || p2 === "39";
    }
    return false;
  }

  /** Visa/MC/Discover = 16; Amex = 15; unknown prefix up to 19. */
  function expectedCardDigitLength(digits) {
    var d = String(digits || "").replace(/\D/g, "");
    if (!d.length) return 16;
    if (d.charAt(0) === "3" && d.length >= 2) {
      var p2 = d.slice(0, 2);
      if (p2 === "34" || p2 === "37") return 15;
    }
    if (d.charAt(0) === "4" || d.charAt(0) === "5" || d.charAt(0) === "6") return 16;
    return 19;
  }

  function formatCardInputValue(raw) {
    var digits = String(raw || "").replace(/\D/g, "");
    digits = digits.slice(0, expectedCardDigitLength(digits));
    return digits.replace(/(.{4})/g, "$1 ").trim();
  }

  var COMMON_EMAIL_TLDS = {
    com: 1, net: 1, org: 1, edu: 1, gov: 1, mil: 1, int: 1, info: 1, biz: 1, name: 1,
    pro: 1, co: 1, io: 1, me: 1, tv: 1, cc: 1, us: 1, uk: 1, de: 1, fr: 1, il: 1,
    ru: 1, cn: 1, in: 1, au: 1, ca: 1, eu: 1, app: 1, dev: 1, ai: 1,
  };

  var IL_EMAIL_SLD = { co: 1, org: 1, ac: 1, gov: 1, muni: 1, idf: 1, k12: 1 };

  function isValidEmail(s) {
    var t = String(s || "").trim();
    if (!t || t.length > 254) return false;
    var at = t.lastIndexOf("@");
    if (at < 1 || at >= t.length - 3) return false;
    var local = t.slice(0, at);
    var host = t.slice(at + 1).toLowerCase();
    if (!local || !host || host.indexOf("..") >= 0 || local.indexOf("..") >= 0) return false;
    if (!/^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+$/.test(local)) return false;
    if (local.charAt(0) === "." || local.charAt(local.length - 1) === ".") return false;

    var labels = host.split(".");
    if (labels.length < 2) return false;
    for (var i = 0; i < labels.length; i++) {
      var lab = labels[i];
      if (!lab || lab.length > 63) return false;
      if (!/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(lab)) return false;
    }

    var tld = labels[labels.length - 1];
    if (tld === "il" && labels.length >= 2 && IL_EMAIL_SLD[labels[labels.length - 2]]) {
      return true;
    }
    if (COMMON_EMAIL_TLDS[tld]) return true;
    if (tld.length === 2 && /^[a-z]{2}$/.test(tld)) return true;
    return false;
  }

  function isValidName(s) {
    var t = String(s || "").trim();
    if (t.length < 2) return false;
    return /^[A-Za-z\u0590-\u05FF\s]+$/.test(t);
  }

  function isValidIsraeliPhone(s) {
    var t = String(s || "").replace(/\D/g, "");
    if (t.length !== 10) return false;
    return /^(050|051|052|053|054|055|058)/.test(t);
  }

  function isValidIsraeliId(s) {
    var t = String(s || "").replace(/\D/g, "");
    return t.length === 9 && /^\d{9}$/.test(t);
  }

  function checkCardExp(s) {
    var t = String(s || "").trim();
    if (!/^\d{2}\/\d{2}$/.test(t)) return { ok: false, code: "format" };
    var m = parseInt(t.slice(0, 2), 10);
    var y2 = parseInt(t.slice(3, 5), 10);
    if (m < 1 || m > 12) return { ok: false, code: "bad_month" };
    var y = 2000 + y2;
    var now = new Date();
    var expIdx = y * 12 + m;
    var curIdx = now.getFullYear() * 12 + (now.getMonth() + 1);
    if (expIdx < curIdx) return { ok: false, code: "expired" };
    if (expIdx > (now.getFullYear() + 15) * 12 + (now.getMonth() + 1)) {
      return { ok: false, code: "too_far" };
    }
    return { ok: true };
  }

  function expectedCvvLenForCard(cardDigits) {
    var d = String(cardDigits || "").replace(/\D/g, "");
    if (d.length >= 2 && d.slice(0, 2) === "34") return 4;
    if (d.length >= 2 && d.slice(0, 2) === "37") return 4;
    return 3;
  }

  function resolveInputErrorClass() {
    var jsUi = global.__BILLING_UI_CLASSES__ || global.__BANGO_UI_CLASSES__ || {};
    return jsUi.inputError || "bango-input--error";
  }

  function showFieldError(el, message, inputErrorClass) {
    if (!el || !el.id) return;
    var cls = inputErrorClass || resolveInputErrorClass();
    el.classList.add(cls);
    el.setAttribute("aria-invalid", "true");
    el.setAttribute("aria-describedby", "bango-err-" + el.id);
    var sp = document.getElementById("bango-err-" + el.id);
    if (sp) {
      sp.textContent = message;
      sp.removeAttribute("hidden");
    }
  }

  function clearFieldError(el, inputErrorClass) {
    if (!el || !el.id) return;
    var cls = inputErrorClass || resolveInputErrorClass();
    el.classList.remove(cls);
    el.removeAttribute("aria-invalid");
    el.removeAttribute("aria-describedby");
    var sp = document.getElementById("bango-err-" + el.id);
    if (sp) {
      sp.setAttribute("hidden", "");
      sp.textContent = "שדה חובה";
    }
  }

  function validateForm(form, opts) {
    opts = opts || {};
    var inputErrorClass = opts.inputErrorClass || resolveInputErrorClass();
    var attemptedClass =
      opts.attemptedClass ||
      ((global.__BILLING_UI_CLASSES__ || global.__BANGO_UI_CLASSES__ || {}).attemptedSubmit ||
        "bango-attempted-submit");

    if (!form) return { ok: false, first: null };

    var inputs = form.querySelectorAll("input");
    for (var i = 0; i < inputs.length; i++) clearFieldError(inputs[i], inputErrorClass);

    var first = null;
    function mark(el, msg) {
      if (!el) return;
      if (!first) first = el;
      showFieldError(el, msg, inputErrorClass);
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
    var cvvD = String((elV && elV.value) || "").replace(/\D/g, "");

    if (!fn) mark(elF, "שדה חובה");
    else if (!isValidName(fn)) mark(elF, "שם פרטי חייב להכיל אותיות בלבד (לפחות 2 תווים).");
    if (!ln) mark(elL, "שדה חובה");
    else if (!isValidName(ln)) mark(elL, "שם משפחה חייב להכיל אותיות בלבד (לפחות 2 תווים).");
    if (!phone) mark(elP, "שדה חובה");
    else if (!isValidIsraeliPhone(phone)) {
      mark(elP, "מספר טלפון לא תקין. יש להזין 10 ספרות המתחילות ב-050, 051, 052, 053, 054, 055 או 058.");
    }
    if (!email) mark(elE, "שדה חובה");
    else if (!isValidEmail(email)) {
      mark(elE, "נא להזין אימייל בפורמט תקין (לדוגמה: name@mail.com).");
    }
    if (!idn) mark(elI, "שדה חובה");
    else if (!isValidIsraeliId(idn)) mark(elI, "מספר תעודת זהות חייב להכיל 9 ספרות בדיוק.");
    if (!card) mark(elC, "שדה חובה");
    else if (card.length < 12 || card.length > 19) {
      mark(elC, "מספר כרטיס חייב להכיל 12–19 ספרות בלבד.");
    } else if (!hasValidCardPrefix(card)) {
      mark(elC, "מספר כרטיס אינו תקין (סוג כרטיס לא נתמך).");
    } else if (!luhnValidateCardDigits(card)) {
      mark(elC, "מספר כרטיס אינו תקין (בדיקת ספרת ביקורת נכשלה).");
    }
    if (!exp) mark(elX, "שדה חובה");
    else {
      var expR = checkCardExp(exp);
      if (!expR.ok) {
        var expMsg = "נא להזין תוקף בפורמט MM/YY";
        if (expR.code === "expired") expMsg = "תוקף הכרטיס פג (נא להזין תאריך עתידי).";
        else if (expR.code === "too_far") expMsg = "תוקף הכרטיס רחוק מדי (לא תקין).";
        else if (expR.code === "bad_month") expMsg = "תאריך התוקף אינו תקין או פג — נא לבדוק שוב.";
        mark(elX, expMsg);
      }
    }
    if (!cvvD) mark(elV, "שדה חובה");
    else if (!/^\d{3,4}$/.test(cvvD)) mark(elV, "קוד CVV חייב להכיל ספרות בלבד.");
    else if (card.length >= 1) {
      var needCvv = expectedCvvLenForCard(card);
      if (cvvD.length !== needCvv) {
        mark(elV, needCvv === 4 ? "קוד CVV חייב להכיל 4 ספרות (Amex)." : "קוד CVV חייב להכיל 3 ספרות.");
      }
    }

    if (first) {
      form.classList.add(attemptedClass);
      return { ok: false, first: first };
    }
    form.classList.remove(attemptedClass);
    return { ok: true, first: null };
  }

  global.BillingFormValidate = {
    luhnValidateCardDigits: luhnValidateCardDigits,
    hasValidCardPrefix: hasValidCardPrefix,
    expectedCardDigitLength: expectedCardDigitLength,
    formatCardInputValue: formatCardInputValue,
    isValidEmail: isValidEmail,
    validateForm: validateForm,
    showFieldError: showFieldError,
    clearFieldError: clearFieldError,
  };
})(typeof window !== "undefined" ? window : this);
