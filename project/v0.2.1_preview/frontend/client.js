/** Shared read/command transport. Both windows talk to one simulation. */
export class SimulationClient {
  constructor({onState=()=>{},onStatus=()=>{},onError=()=>{}}={}) {
    this.state=null;this.connected=false;this.pending=0;this.receivedAt=0;
    this.onState=onState;this.onStatus=onStatus;this.onError=onError;this.stopped=false;
  }
  accept(value) {
    // Revision also increases across resets, so late replies cannot rewind a view.
    if(this.state && value.revision<this.state.revision) return;
    const previous=this.state;this.state=value;this.receivedAt=performance.now();
    this.onState(value,previous);
  }
  async poll() {
    if(this.stopped) return;
    try {
      const response=await fetch('./api/state',{cache:'no-store'});
      if(!response.ok) throw new Error('连接未就绪');
      const value=await response.json();this.connected=true;
      if(!this.state || value.revision!==this.state.revision) this.accept(value);
    } catch(error) {this.connected=false;}
    finally {this.onStatus();if(!this.stopped) setTimeout(()=>this.poll(),this.connected?110:1000);}
  }
  async command(operation,data={}) {
    if(!this.connected) {this.onError('尚未连接仿真，请稍后再试');return false;}
    this.pending++;this.onStatus();
    try {
      const response=await fetch('./api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,data})});
      const result=await response.json();
      if(!response.ok || !result.ok) throw new Error(result.error || '操作未完成');
      this.accept(result.state);return true;
    } catch(error) {this.onError(error.message);return false;}
    finally {this.pending--;this.onStatus();}
  }
}

export async function openDebugWindow() {
  if(window.pywebview?.api?.open_debug) return window.pywebview.api.open_debug();
  const child=window.open('./debug.html','sditadc-debug','width=900,height=800');
  if(!child) throw new Error('调试窗口被拦截，请允许本机页面打开窗口');
  return {ok:true};
}

export async function focusMainWindow() {
  if(window.pywebview?.api?.focus_main) return window.pywebview.api.focus_main();
  if(window.opener && !window.opener.closed) window.opener.focus();
  else window.open('./','sditadc-main');
  return {ok:true};
}
