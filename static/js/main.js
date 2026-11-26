/* Small touches used on every page. */
(function () {
  "use strict";

  // 1. Cards and sections fade in when they scroll into view.
  //    IntersectionObserver tells us when an element becomes visible.
  //    Skipped for people who asked their system for reduced motion.
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const targets = document.querySelectorAll(
    ".postcard, .guide-card, .info-card, .flight-pass, .trip-ticket, .stat-card, .step-icon"
  );
  if (!reduceMotion && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);   // animate only once
        }
      });
    }, { rootMargin: "0px 0px -40px 0px" });
    targets.forEach((el) => {
      // Elements already on screen when the page opens are shown immediately.
      if (el.getBoundingClientRect().top < window.innerHeight) return;
      el.classList.add("reveal");
      observer.observe(el);
    });
  }

  // 2. Success / info messages close themselves after 6 seconds.
  //    Errors and warnings stay until the user closes them.
  document.querySelectorAll(".flash-stack .alert-success, .flash-stack .alert-info").forEach((alert) => {
    setTimeout(() => {
      if (window.bootstrap && document.body.contains(alert)) bootstrap.Alert.getOrCreateInstance(alert).close();
    }, 6000);
  });
})();
