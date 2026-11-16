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
  // ---------------------------------------------------------------- full screen (phones/tablets)
  var root = document.documentElement;
  var reqFS = root.requestFullscreen || root.webkitRequestFullscreen;
  var touchy = ('ontouchstart' in window) || (window.matchMedia && matchMedia('(pointer: coarse)').matches);
  var standalone = navigator.standalone ||
    (window.matchMedia && matchMedia('(display-mode: fullscreen), (display-mode: standalone)').matches);
  function isFS() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
  function lockLandscape() {
    try { if (screen.orientation && screen.orientation.lock) screen.orientation.lock('landscape').catch(function () {}); } catch (e) {}
  }
  function goFS() {
    if (!reqFS || isFS()) return;
    try {
      var p = reqFS.call(root, { navigationUI: 'hide' });
      if (p && p.then) p.then(lockLandscape).catch(function () {}); else lockLandscape();
    } catch (e) {}
  }
  // Auto: every tap tries to go full screen (a tap is needed - browsers block it otherwise),
  // until the player leaves full screen on purpose; then only the button brings it back.
  var userLeft = false, wasFS = false;
  function autoFS() { if (touchy && !userLeft) goFS(); }
  document.addEventListener('touchend', autoFS, true);   // capture phase so pygbag can't swallow the tap
  document.addEventListener('pointerup', autoFS, true);

  // the [ ] button in the top-right corner (hidden while full screen)
  var css = document.createElement('style');
  css.textContent =
    '#fsbtn{position:fixed;z-index:9999;top:calc(env(safe-area-inset-top) + 8px);right:calc(env(safe-area-inset-right) + 8px);' +
    'width:46px;height:46px;border-radius:12px;border:2px solid #3c2823;background:rgba(255,248,235,.75);' +
    'font:bold 26px/42px sans-serif;color:#3c2823;text-align:center;display:none;touch-action:none;-webkit-user-select:none;user-select:none}' +
    '#fshint{position:fixed;z-index:10000;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.6)}' +
    '#fshint div{max-width:80%;padding:18px 22px;border-radius:14px;background:#fff8eb;color:#3c2823;font:17px/1.4 sans-serif;text-align:center}';
  document.head.appendChild(css);
  var btn = document.createElement('div'); btn.id = 'fsbtn'; btn.textContent = '⛶';
  var hint = document.createElement('div'); hint.id = 'fshint';
  hint.innerHTML = '<div><b>Full screen on iPhone</b><br>Safari can\'t hide its bars for games.<br>' +
    'Tap <b>Share</b> → <b>Add to Home Screen</b>, then open Chiikawa Smash from your home screen ' +
    '- it runs with no bars at all.<br><br><i>(tap to close)</i></div>';
  function onBtn(e) {
    e.preventDefault(); e.stopPropagation();
    if (reqFS) { userLeft = false; goFS(); } else hint.style.display = 'flex';
  }
  btn.addEventListener('touchend', onBtn, { passive: false });
  btn.addEventListener('click', onBtn);
  btn.addEventListener('touchstart', function (e) { e.stopPropagation(); }, { passive: true });
  hint.addEventListener('touchend', function (e) { e.preventDefault(); e.stopPropagation(); hint.style.display = 'none'; }, { passive: false });
  hint.addEventListener('click', function () { hint.style.display = 'none'; });
  function updateBtn() {
    var fs = isFS();
    if (wasFS && !fs) userLeft = true;      // they swiped/backed out of full screen on purpose
    wasFS = fs;
    btn.style.display = (touchy && !fs && !standalone) ? 'block' : 'none';
    refit();
  }
  document.addEventListener('fullscreenchange', updateBtn);
  document.addEventListener('webkitfullscreenchange', updateBtn);
  function addUI() { document.body.appendChild(btn); document.body.appendChild(hint); updateBtn(); }
  if (document.body) addUI(); else window.addEventListener('DOMContentLoaded', addUI);
})();
