export function createState() {
  return { connected:false, botRunning:false, actionRunning:false, ready:false, logs:[], page:"overview", settings:null, history:[] };
}
export function appendLog(state, log) { return { ...state, logs:[...state.logs, log].slice(-1000) }; }
export function applyBackendState(state, update) {
  const next={...state,...update};
  next.canStartBot=Boolean(next.connected && next.ready && !next.botRunning && !next.actionRunning);
  return next;
}
