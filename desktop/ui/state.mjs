export function createState() {
  return { connected:false, botRunning:false, actionRunning:false, ready:false, logs:[], page:"overview", settings:null, history:[] };
}
export function appendLog(state, log) {
  const logs=[...state.logs], last=logs.at(-1);
  if(last && last.level===log.level && last.source===log.source && last.message===log.message){
    logs[logs.length-1]={...log,count:(last.count||1)+1};
  }else logs.push(log);
  return { ...state, logs:logs.slice(-1000) };
}
export function applyBackendState(state, update) {
  const next={...state,...update};
  next.canStartBot=Boolean(next.connected && next.ready && !next.botRunning && !next.actionRunning);
  return next;
}
