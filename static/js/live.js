/* Live score push client.
 * Connects to ws://host/ws/live/ for real-time updates.
 * If WebSockets are unavailable (serverless deploy), falls back to polling
 * the rate-limited /scorecard/api/live/ endpoint every 45s.
 *
 * Usage: FZLive.connect(payload => renderMatches(payload.matches));
 * payload = {type:'live_score_update', matches:[...], note:'...'}
 */
window.FZLive = (function () {
  let ws = null;
  let onMessage = null;
  let retries = 0;
  let pollTimer = null;

  function connect(cb) {
    if (cb) onMessage = cb;
    stopPolling();
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    try {
      ws = new WebSocket(proto + '://' + location.host + '/ws/live/');
    } catch (e) {
      startPolling();
      return;
    }
    ws.onopen = function () { retries = 0; stopPolling(); };
    ws.onmessage = function (e) {
      try {
        const d = JSON.parse(e.data);
        if (d && d.type === 'live_score_update' && onMessage) onMessage(d);
      } catch (_) {}
    };
    ws.onclose = function () {
      retries += 1;
      if (retries > 2) { startPolling(); return; }   // serverless? poll instead
      setTimeout(function () { connect(onMessage); }, 5000);
    };
    ws.onerror = function () { try { ws.close(); } catch (_) {} };
  }

  function startPolling() {
    if (pollTimer) return;
    poll();
    pollTimer = setInterval(poll, 45000);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  function poll() {
    fetch('/scorecard/api/live/')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d && d.matches && onMessage) {
          onMessage({ type: 'live_score_update', matches: d.matches, note: d.note });
        }
      })
      .catch(function () {});
  }

  return { connect: connect };
})();
