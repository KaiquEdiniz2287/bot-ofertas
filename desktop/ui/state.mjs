export function createState() {
  return {
    connected:false, botRunning:false, actionRunning:false, ready:false, logs:[], page:"overview",
    settings:null, history:[], whatsappStatus:"DISCONNECTED", whatsappAccount:"", whatsappQr:"",
    whatsappGroups:[], pending:[], pauseUntil:null, nextCycleAt:null, whatsappRetryAt:null,
    whatsappRetryAttempt:0, whatsappRetryMax:5, browserInstalled:false, mlSessionDetected:false,
    cycleIntervalMinutes:0, postSpacingSeconds:0, currentAction:null, sessionActions:{},
  };
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

export function startSessionAction(state, key, label, message) {
  return {...state,currentAction:{key,label,status:"running",message,startedAt:Date.now(),finishedAt:null}};
}

export function finishSessionAction(state, key, succeeded, message) {
  const current=state.currentAction?.key===key?state.currentAction:{key,label:key,startedAt:Date.now()};
  return {
    ...state,
    currentAction:{...current,status:succeeded?"success":"error",message,finishedAt:Date.now()},
    sessionActions:succeeded?{...state.sessionActions,[key]:true}:state.sessionActions,
  };
}
