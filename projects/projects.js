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
