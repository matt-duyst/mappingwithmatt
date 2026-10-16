// Shared by the five project pages
(function () {
  // Cross-document view transition: the first figure takes the hero-figure name the main page gave the clicked plate, and gives it back when the transition ends
  window.addEventListener('pagereveal', function (e) {
    if (!e.viewTransition) return;
    var media = document.querySelector('#hero-figure img, #hero-figure video');
    if (!media) return;
    media.style.viewTransitionName = 'hero-figure';
    e.viewTransition.finished.then(function () { media.style.viewTransitionName = ''; }, function () { media.style.viewTransitionName = ''; });
  });
})();
// Before-and-after swipe: the handle position is one custom property on the stage, moved by pointer drag or arrow keys
document.addEventListener('DOMContentLoaded', function () {  // this file loads from the head, before the figures exist
  Array.prototype.forEach.call(document.querySelectorAll('.swipe-stage'), function (stage) {
    var handle = stage.querySelector('.swipe-handle'), pos = 50;
    function set(p) { pos = Math.max(0, Math.min(100, p)); stage.style.setProperty('--pos', pos.toFixed(1) + '%'); handle.setAttribute('aria-valuenow', Math.round(pos)); }
    function fromEvent(e) { var r = stage.getBoundingClientRect(); set(100 * (e.clientX - r.left) / r.width); }
    stage.addEventListener('pointerdown', function (e) { if (e.button !== 0) return; e.preventDefault(); stage.setPointerCapture(e.pointerId); fromEvent(e); handle.focus({ preventScroll: true }); });
    stage.addEventListener('pointermove', function (e) { if (e.buttons & 1) fromEvent(e); });
    handle.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { e.preventDefault(); set(pos - 2); }
      else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); set(pos + 2); }
      else if (e.key === 'Home') { e.preventDefault(); set(0); } else if (e.key === 'End') { e.preventDefault(); set(100); }
    });
  });
});
