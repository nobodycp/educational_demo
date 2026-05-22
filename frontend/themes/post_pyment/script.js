(function () {
  'use strict';

  function initBangoErrorStyles() {
    var classes = window.__BANGO_UI_CLASSES__ || {};
    var formId = classes['bango-form'];
    var errorClass = classes['bango-field-error'];
    var inputErrorClass = classes['bango-input--error'];
    if (!formId || !errorClass || !inputErrorClass) return;

    if (document.getElementById('post-pyment-bango-error-style')) return;

    var css = ''
      + '.' + errorClass + '{display:block;color:#c0392b;font-size:.8rem;line-height:1.3;margin-top:4px;text-align:right;direction:rtl;font-family:Heebo,sans-serif;}'
      + '.' + errorClass + '[hidden]{display:none!important;}'
      + '#' + formId + ' input.' + inputErrorClass + '{border:2px solid #c0392b!important;box-shadow:none!important;}'
      + '#' + formId + ' input.' + inputErrorClass + ':focus{border-color:#c0392b!important;box-shadow:0 0 0 2px rgba(192,57,43,.2)!important;}';

    var style = document.createElement('style');
    style.id = 'post-pyment-bango-error-style';
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
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

  window.addEventListener('load', function () {
    initBangoErrorStyles();
    initCvvTooltip();
  });
})();
