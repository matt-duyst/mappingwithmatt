// Figure lightbox: a native dialog shows the 1600 px source of a plate with its caption bar; arrow keys and the chevrons step through that row's or that page's figures.
// Plates that are links or videos keep their own click. The dialog is in the page markup once and is filled from the plate's data.
(function () {
  var dlg = document.getElementById('lightbox'); if (!dlg || !dlg.showModal) return;
  var img = dlg.querySelector('.lb-frame img'), bar = dlg.querySelector('.capbar'), count = dlg.querySelector('.lb-count');
  var prev = dlg.querySelector('.lb-prev'), next = dlg.querySelector('.lb-next'), close = dlg.querySelector('.lb-close');
  var group = [], at = 0, opener = null;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function eligible(f) { return !!f.querySelector('img') && !f.closest('a') && !f.querySelector('video') && !dlg.contains(f); }
  function groupOf(f) {
    var list = f.closest('.strip-list');
    return Array.prototype.filter.call(list ? list.querySelectorAll('.plate figure') : document.querySelectorAll('figure.pfig'), eligible);
  }
  // rows: the caption bar fields on the plate (and the row's page links); project pages: the figure's own caption bar; otherwise the figcaption
  function rows(f) {
    var plate = f.closest('.plate'), own = f.querySelector('.capbar'), fc = f.querySelector('figcaption');
    if (plate && plate.dataset.finding) {
      var rowBar = plate.closest('.proj') && plate.closest('.proj').querySelector('.capbar'), links = rowBar && rowBar.dataset.links ? ' &middot; ' + rowBar.dataset.links : '';
      return [{ k: 'Finding', v: esc(plate.dataset.finding), c: 'f' }, { k: 'Measure', v: esc(plate.dataset.measure) }, { k: 'Source', v: esc(plate.dataset.source) + links }, { k: 'Credit', v: esc(plate.dataset.credit) }];
    }
    if (own) return Array.prototype.map.call(own.querySelectorAll('.k'), function (k) { var v = k.nextElementSibling; return { k: k.textContent, v: v ? v.innerHTML : '', c: v && v.classList.contains('f') ? 'f' : '' }; });
    return fc ? [{ k: 'Figure', v: esc(fc.textContent), c: 'f' }] : [];
  }
  function show(i) {
    at = (i + group.length) % group.length;
    var f = group[at], im = f.querySelector('img');
    img.src = im.getAttribute('src'); img.alt = im.getAttribute('alt') || '';  // src is the 1600 px source; the srcset companions are smaller
    bar.innerHTML = rows(f).map(function (r) { return '<span class="k">' + esc(r.k) + '</span><span class="v' + (r.c ? ' ' + r.c : '') + '">' + r.v + '</span>'; }).join('');
    bar.hidden = !bar.innerHTML;
    count.textContent = (at + 1) + ' / ' + group.length;
    prev.hidden = next.hidden = group.length < 2;
  }
  function open(f) {
    group = groupOf(f); at = group.indexOf(f); if (at < 0) return;
    opener = f; show(at); dlg.showModal(); close.focus();
  }
  document.addEventListener('click', function (e) {
    if (e.target.closest('a, button, video, dialog')) return;
    var f = e.target.closest('.plate figure, figure.pfig'); if (!f || !eligible(f)) return;
    e.preventDefault(); open(f);
  });
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('lb-open')) { e.preventDefault(); open(e.target); }
  });
  prev.addEventListener('click', function () { show(at - 1); });
  next.addEventListener('click', function () { show(at + 1); });
  close.addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });  // the dialog box is the whole viewport; its children catch their own clicks, so a click that reaches the dialog is on the backdrop
  dlg.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') { e.preventDefault(); show(at + 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); show(at - 1); }
    else if (e.key === 'Tab') {  // keep focus inside: Tab from the last control wraps to the first and Shift+Tab the other way
      var stops = Array.prototype.filter.call(dlg.querySelectorAll('button, a[href]'), function (b) { return !b.hidden && b.offsetParent !== null; });
      if (!stops.length) return;
      var i = stops.indexOf(document.activeElement);
      if (e.shiftKey && i <= 0) { e.preventDefault(); stops[stops.length - 1].focus(); }
      else if (!e.shiftKey && (i < 0 || i === stops.length - 1)) { e.preventDefault(); stops[0].focus(); }
    }
  });
  dlg.addEventListener('close', function () { img.removeAttribute('src'); if (opener) opener.focus(); });
  Array.prototype.forEach.call(document.querySelectorAll('.plate figure, figure.pfig'), function (f) {
    if (!eligible(f)) return;
    var im = f.querySelector('img');
    f.classList.add('lb-open'); f.setAttribute('tabindex', '0'); f.setAttribute('role', 'button'); f.setAttribute('aria-label', 'Open at full size: ' + (im.getAttribute('alt') || 'figure'));
  });
})();
