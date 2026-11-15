// Online play bridge for Chiikawa Smash (browser build).
// Python (pygbag) calls window.SmashNet.* with plain strings; PeerJS does the WebRTC work.
// Room code "1234" -> PeerJS id "chiikawa-smash-1234" on the free PeerJS cloud server.
window.SmashNet = (function () {
  var PREFIX = "chiikawa-smash-";
  // Relay (TURN) for friends on different networks / mobile data. Paste your Metered Open Relay
  // credentials URL here (free account): "https://YOURAPP.metered.live/api/v1/turn/credentials?apiKey=YOURKEY"
  var TURN_API = "";
  // ...or fixed credentials from a TURN dashboard (e.g. ExpressTURN free plan): fill in all three.
  var TURN_URL = "free.expressturn.com:3478";        // e.g. "relay1.expressturn.com:3478"  (shown in your dashboard)
  var TURN_USER = "000000002110153387";
  var TURN_PASS = "kHNH6xcZ4fv+wUs7a7B0QNpGt34=";
  var iceServers = TURN_URL ? [
    { urls: ["turn:" + TURN_URL, "turn:" + TURN_URL + "?transport=tcp"], username: TURN_USER, credential: TURN_PASS }
  ] : null;
  function withIce(cb) {
    if (!TURN_API || iceServers) { cb(); return; }
    fetch(TURN_API).then(function (r) { return r.json(); })
      .then(function (list) { iceServers = list; cb(); })
      .catch(function () { cb(); });           // relay unavailable: still try direct
  }
  var peer = null, conns = {}, hostConn = null, inbox = [], state = "idle", err = "";

  function push(from, data) {
    if (typeof data !== "string") { try { data = JSON.stringify(data); } catch (e) { return; } }
    inbox.push([from, data]);
    if (inbox.length > 2000) inbox.splice(0, inbox.length - 2000);   // never grow without limit
  }
  function wire(c, isHostSide) {
    c.on("open", function () {
      conns[c.peer] = c;
      if (isHostSide) push(c.peer, '{"t":"_open"}');
      else { hostConn = c; state = "ready"; }
    });
    c.on("data", function (d) { push(c.peer, d); });
    c.on("close", function () {
      delete conns[c.peer];
      push(c.peer, '{"t":"_close"}');
      if (!isHostSide) state = "closed";
    });
    c.on("error", function (e) { err = String(e); });
  }
  function make(id) {
    if (typeof Peer === "undefined") { state = "error"; err = "PeerJS didn't load (no internet?)"; return null; }
    var opts = { debug: 0 };
    if (iceServers) opts.config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }].concat(iceServers) };
    var p = id ? new Peer(id, opts) : new Peer(opts);
    p.on("error", function (e) {
      err = (e && e.type) || String(e);
      if (err === "unavailable-id") state = "taken";
      else if (err === "peer-unavailable") state = "nohost";
      else if (state !== "ready") state = "error";
    });
    p.on("disconnected", function () { try { p.reconnect(); } catch (e) {} });  // keep the room listed
    return p;
  }
  function reset() {
    for (var k in conns) { try { conns[k].close(); } catch (e) {} }
    conns = {}; hostConn = null; inbox = []; err = "";
    if (peer) { try { peer.destroy(); } catch (e) {} }
    peer = null; state = "idle";
  }
  return {
    host: function (code) {
      reset(); state = "connecting";
      withIce(function () {
        peer = make(PREFIX + code); if (!peer) return;
        peer.on("open", function () { state = "ready"; });
        peer.on("connection", function (c) { wire(c, true); });
      });
    },
    join: function (code) {
      reset(); state = "connecting";
      withIce(function () {
        peer = make(null); if (!peer) return;
        peer.on("open", function () {
          var c = peer.connect(PREFIX + code, { reliable: false, serialization: "raw" });
          wire(c, false);
          // room exists but no direct route (different networks, no relay): report it instead of hanging
          setTimeout(function () { if (state === "connecting") { state = err === "peer-unavailable" ? "nohost" : "noroute"; } }, 15000);
        });
      });
    },
    send: function (to, text) {
      var c = to ? conns[to] : hostConn;
      if (c && c.open) { try { c.send(text); } catch (e) {} }
    },
    broadcast: function (text) {
      for (var k in conns) { var c = conns[k]; if (c.open) { try { c.send(text); } catch (e) {} } }
    },
    poll: function () { var out = JSON.stringify(inbox); inbox = []; return out; },
    status: function () { return state; },
    error: function () { return err; },
    close: function () { reset(); }
  };
})();
