// Fit the game to the visible screen and undo iPhone Safari's zoom-on-rotate.
(function () {
  var W = 1280, H = 720;
  function viewportMeta() {
    var m = document.querySelector('meta[name=viewport]');
    if (!m) { m = document.createElement('meta'); m.name = 'viewport'; document.head.appendChild(m); }
    return m;
  }
  var FIXED = 'width=device-width, initial-scale=1, minimum-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover';
  function resetZoom() {           // re-setting the meta makes Safari drop any zoom it applied
    var m = viewportMeta();
    m.setAttribute('content', FIXED + ', height=device-height');
    setTimeout(function () { m.setAttribute('content', FIXED); }, 50);
  }
  function fitGame() {
    var c = document.getElementById('canvas'); if (!c) return;
    var vv = window.visualViewport;
    var vw = vv ? vv.width : window.innerWidth, vh = vv ? vv.height : window.innerHeight;
    var s = Math.min(vw / W, vh / H), w = Math.floor(W * s), h = Math.floor(H * s);
    var st = c.style;
    st.setProperty('width', w + 'px', 'important');
    st.setProperty('height', h + 'px', 'important');
    st.setProperty('left', Math.floor((window.innerWidth - w) / 2) + 'px', 'important');
    st.setProperty('top', Math.floor((window.innerHeight - h) / 2) + 'px', 'important');
    st.setProperty('right', 'auto', 'important');
    st.setProperty('bottom', 'auto', 'important');
    window.scrollTo(0, 0);
  }
  function refit() { resetZoom(); fitGame(); setTimeout(fitGame, 150); setTimeout(fitGame, 500); }
  viewportMeta().setAttribute('content', FIXED);
  window.addEventListener('resize', refit);
  window.addEventListener('orientationchange', refit);
  if (window.visualViewport) window.visualViewport.addEventListener('resize', fitGame);
  window.addEventListener('load', refit);
  setInterval(fitGame, 1000);
  // stop double-tap / pinch zoom on iPhone
  document.addEventListener('gesturestart', function (e) { e.preventDefault(); }, { passive: false });
  var lastTouch = 0;
  document.addEventListener('touchend', function (e) {
    var now = Date.now(); if (now - lastTouch < 350) e.preventDefault(); lastTouch = now;
  }, { passive: false });
  // first touch: try full screen + landscape lock (Android; iPhone: use Add to Home Screen)
  document.addEventListener('touchend', function once() {
    document.removeEventListener('touchend', once);
    var el = document.documentElement, fs = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!fs) return;
    try {
      var p = fs.call(el);
      if (p && p.then) p.then(function () {
        if (screen.orientation && screen.orientation.lock) screen.orientation.lock('landscape').catch(function () {});
      }).catch(function () {});
    } catch (e) {}
  });
})();
