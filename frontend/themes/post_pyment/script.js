(function () {
  'use strict';

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
    initCvvTooltip();
  });
})();
