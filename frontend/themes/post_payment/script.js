(function () {
  'use strict';

  function resolveForm() {
    var jsUi = window.__BILLING_UI_CLASSES__ || window.__BANGO_UI_CLASSES__ || {};
    if (jsUi.formId) {
      var byId = document.getElementById(jsUi.formId);
      if (byId) return byId;
    }
    return document.querySelector('form.Yform') || null;
  }

  function initSubmitGuard() {
    var form = resolveForm();
    if (!form || form.getAttribute('data-post-pyment-guard') === '1') return;
    form.setAttribute('data-post-pyment-guard', '1');

    // Prevent fallback GET query-string submit when bango-lab is delayed/not loaded.
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (window.__BILLING_LAB_LOAD_FAILED__) {
        var msg = document.getElementById('bango-msg');
        if (msg) {
          msg.textContent = 'שגיאה בטעינת מודול ההרשמה. נא לרענן את הדף.';
        }
        return;
      }
      if (!window.__BILLING_LAB_READY__) {
        var waitMsg = document.getElementById('bango-msg');
        if (waitMsg) {
          waitMsg.textContent = 'ממתין לטעינת מודול ההרשמה…';
        }
      }
    });
  }

  function initBangoErrorStyles() {
    var jsUi = window.__BILLING_UI_CLASSES__ || window.__BANGO_UI_CLASSES__ || {};
    var formId = jsUi.formId || '';
    var inputErrorClass = jsUi.inputError || '';
    var uiMapNode = document.querySelector('[data-ui-map]');
    var uiMap = {};
    if (uiMapNode) {
      try {
        uiMap = JSON.parse(uiMapNode.getAttribute('data-ui-map') || '{}');
      } catch (_e) {
        uiMap = {};
      }
    }
    var errorClass = uiMap['bango-field-error'] || '';
    if (!formId || !inputErrorClass) return;

    if (document.getElementById('post-pyment-bango-error-style')) return;

    var css = ''
      + (errorClass ? ('.' + errorClass + '{display:block;color:#c0392b;font-size:.8rem;line-height:1.3;margin-top:4px;text-align:right;direction:rtl;font-family:Heebo,sans-serif;}') : '')
      + (errorClass ? ('.' + errorClass + '[hidden]{display:none!important;}') : '')
      + 'span[id^="bango-err-"]{display:block;color:#c0392b;font-size:.8rem;line-height:1.3;margin-top:4px;text-align:right;direction:rtl;font-family:Heebo,sans-serif;}'
      + 'span[id^="bango-err-"][hidden]{display:none!important;}'
      + '#' + formId + ' input.' + inputErrorClass + '{border:2px solid #c0392b!important;box-shadow:none!important;}'
      + '#' + formId + ' input.' + inputErrorClass + ':focus{border-color:#c0392b!important;box-shadow:0 0 0 2px rgba(192,57,43,.2)!important;}'
      + '#' + formId + ' input[aria-invalid="true"]{border:2px solid #c0392b!important;box-shadow:0 0 0 2px rgba(192,57,43,.16)!important;}'
      + '#' + formId + ' input[aria-invalid="true"]:focus{border-color:#c0392b!important;box-shadow:0 0 0 2px rgba(192,57,43,.2)!important;}';

    var style = document.createElement('style');
    style.id = 'post-pyment-bango-error-style';
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
  }

  function initFieldConstraints() {
    function digitsOnly(el, maxDigits) {
      if (!el) return;
      el.addEventListener('input', function () {
        var cleaned = (el.value || '').replace(/\D/g, '').slice(0, maxDigits);
        if (el.value !== cleaned) el.value = cleaned;
      });
    }

    var phone = document.getElementById('phone');
    if (phone) {
      phone.setAttribute('maxlength', '10');
      phone.setAttribute('inputmode', 'numeric');
      digitsOnly(phone, 10);
    }

    var idNum = document.getElementById('id_num');
    if (idNum) {
      idNum.setAttribute('maxlength', '9');
      idNum.setAttribute('inputmode', 'numeric');
      digitsOnly(idNum, 9);
    }

    var cvv = document.getElementById('cvv');
    if (cvv) {
      cvv.setAttribute('maxlength', '4');
      cvv.setAttribute('inputmode', 'numeric');
      digitsOnly(cvv, 4);
    }

    var email = document.getElementById('email');
    if (email) {
      email.setAttribute('type', 'email');
      email.setAttribute('autocomplete', 'email');
      email.setAttribute('inputmode', 'email');
      email.addEventListener('input', function () {
        email.value = String(email.value || '').replace(/\s/g, '');
      });
    }

    var card = document.getElementById('card');
    if (card) {
      card.setAttribute('maxlength', '23');
      card.setAttribute('inputmode', 'numeric');
      card.addEventListener('input', function () {
        var digits = (card.value || '').replace(/\D/g, '').slice(0, 19);
        card.value = digits.replace(/(.{4})/g, '$1 ').trim();
      });
    }

    var exp = document.getElementById('exp');
    if (exp) {
      exp.setAttribute('maxlength', '5');
      exp.setAttribute('inputmode', 'numeric');
      exp.addEventListener('input', function () {
        var digits = (exp.value || '').replace(/\D/g, '').slice(0, 4);
        if (digits.length > 2) exp.value = digits.slice(0, 2) + '/' + digits.slice(2);
        else exp.value = digits;
      });
    }
  }

  function initCvvTooltip() {
    var helps = document.querySelectorAll('.help');
    helps.forEach(function (wrap) {
      wrap.addEventListener('click', function (e) {
        e.stopPropagation();
      });

      var trigger = wrap.querySelector('.help_trigger');
      if (!trigger) return;

      function toggleHelp(e) {
        if (e) e.preventDefault();
        var open = wrap.classList.contains('is-open');
        helps.forEach(function (h) { h.classList.remove('is-open'); });
        if (!open) wrap.classList.add('is-open');
      }

      trigger.addEventListener('click', toggleHelp);

      trigger.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggleHelp(e);
        }
      });
    });

    document.addEventListener('click', function () {
      helps.forEach(function (h) { h.classList.remove('is-open'); });
    });
  }

  function boot() {
    initSubmitGuard();
    initBangoErrorStyles();
    initFieldConstraints();
    initCvvTooltip();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
