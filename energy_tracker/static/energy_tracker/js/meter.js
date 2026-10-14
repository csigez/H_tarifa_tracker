// Rolls the hero meter digits up from zero on load, like a real register settling.
(function () {
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function animateValue(el) {
    var target = parseFloat(el.dataset.target || "0");
    var suffix = el.dataset.suffix || "";

    if (reduceMotion || !target) {
      el.textContent = Math.round(target).toLocaleString() + suffix;
      return;
    }

    var duration = 900;
    var start = null;

    function step(timestamp) {
      if (start === null) start = timestamp;
      var elapsed = timestamp - start;
      var progress = Math.min(elapsed / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var current = Math.round(target * eased);
      el.textContent = current.toLocaleString() + suffix;
      if (progress < 1) {
        requestAnimationFrame(step);
      }
    }

    requestAnimationFrame(step);
  }

  function animateGauge(el) {
    var target = parseFloat(el.dataset.target || "0");
    requestAnimationFrame(function () {
      el.style.width = target + "%";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-roll]").forEach(animateValue);
    document.querySelectorAll("[data-gauge]").forEach(animateGauge);

    var navToggle = document.querySelector(".nav-toggle");
    var navLinks = document.querySelector(".nav-links");
    if (navToggle && navLinks) {
      navToggle.addEventListener("click", function () {
        navLinks.classList.toggle("is-open");
      });
    }

    document.querySelectorAll(".message .dismiss").forEach(function (btn) {
      btn.addEventListener("click", function () {
        btn.closest(".message").remove();
      });
    });
  });
})();
