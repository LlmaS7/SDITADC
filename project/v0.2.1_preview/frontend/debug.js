import { SimulationClient, focusMainWindow } from './client.js';

const $=id=>document.getElementById(id);
let state=null,mapKey='',transient='',transientUntil=0,seedTouched=false;
const note=message=>{transient=message;transientUntil=performance.now()+4500;};
const client=new SimulationClient({onState:accept,onStatus:controls,onError:note});
const taskName=id=>id===null?'—':'T'+String(id).padStart(3,'0');

function controls() {
  if(!state) return;
  const busy=client.pending>0 || !client.connected;
  for(const id of ['pause','step','random','new-task','auto','save','load','retry','reset']) $(id).disabled=busy;
  $('speed').disabled=busy;$('pause').textContent=state.paused?'继续':'暂停';$('speed').value=String(state.speed);
  $('auto').textContent=state.auto?'自动生成：开':'自动生成：关';$('auto').setAttribute('aria-pressed',String(state.auto));
  $('connection').textContent=!client.connected?'连接中断':state.planning?'规划中':state.paused?'已暂停':'运行中';
  $('connection').classList.toggle('offline',!client.connected);
}
function accept(value,previous) {
  state=value;
  if(previous && value.generation!==previous.generation) {
    $('task-dialog').close();seedTouched=false;
  }
  const key=state.generation+':'+state.map.seed;
  if(key!==mapKey) {
    mapKey=key;
    $('pickup').replaceChildren(...state.map.pickups.map((p,i)=>new Option(`取货点 ${i+1} · (${p})`,i+1)));
    $('delivery').replaceChildren(...state.map.deliveries.map((p,i)=>new Option(`配送点 D${i+1} · (${p})`,i+1)));
  }
  const m=state.metrics;
  const fields={tick:state.tick,seed:state.map.seed,'map-size':`${state.map.width} × ${state.map.height}`,generation:state.generation,revision:state.revision,'visible-total':m.visible_total,'record-total':m.total,replaying:state.replaying?'开':'关','plan-ms':`${m.last_plan_ms.toFixed(1)} ms`,'cbs-nodes':m.cbs_nodes,plans:m.plans,recoveries:m.recovery_attempts,distance:`${m.distance} 格`,waits:`${m.waits} 步`,'avg-completion':`${m.avg_completion.toFixed(1)} 步`,preemptions:`${m.preemptions} 次`};
  Object.entries(fields).forEach(([id,value])=>$(id).textContent=value);
  if(!seedTouched) $('reset-seed').value=state.map.seed;
  $('assignment-note').textContent=`本轮预计完成时间和：${state.assignment.eta_sum ?? 0} 步。代价不含未来插单及路径冲突等待。`;
  $('robot-data').innerHTML=state.robots.map(r=>`<tr><td>R${r.id}</td><td>(${r.position})</td><td>${r.label}</td><td>${taskName(r.task_id)}</td><td>${taskName(r.next_task_id)}</td><td>${Math.max(0,r.path.length-1)}</td><td>${r.loaded?'是':'否'}</td></tr>`).join('');
  controls();
}
$('pause').onclick=()=>client.command('pause',{paused:!state.paused});
$('step').onclick=()=>client.command('step');
$('speed').onchange=()=>client.command('speed',{value:Number($('speed').value)});
$('random').onclick=()=>client.command('random');
$('auto').onclick=()=>client.command('auto',{enabled:!state.auto});
$('save').onclick=()=>client.command('save');
$('load').onclick=()=>client.command('load');
$('retry').onclick=()=>client.command('retry');
$('reset-seed').oninput=()=>seedTouched=true;
$('reset').onclick=()=>{
  const input=$('reset-seed');
  if(!input.checkValidity() || input.value==='') {input.reportValidity();note('请输入合法的地图种子');return;}
  client.command('reset',{seed:Number(input.value)});
};
$('focus-main').onclick=async()=>{try{await focusMainWindow();}catch(e){note(e.message);}};
$('new-task').onclick=async()=>{if(await client.command('pause',{paused:true})) $('task-dialog').showModal();};
$('close-dialog').onclick=$('back-dialog').onclick=()=>$('task-dialog').close();
$('task-form').onsubmit=async e=>{e.preventDefault();if(await client.command('add',{pickup:Number($('pickup').value),delivery:Number($('delivery').value),priority:Number($('priority').value)})) $('task-dialog').close();};
document.addEventListener('keydown',e=>{
  if($('task-dialog').open || ['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName) || client.pending || !client.connected || e.ctrlKey || e.altKey || e.metaKey) return;
  const actions={n:'step',a:'random',r:'retry',s:'save'};
  if(e.code==='Space') {e.preventDefault();$('pause').click();}
  else if(actions[e.key.toLowerCase()]) $(actions[e.key.toLowerCase()]).click();
});
setInterval(()=>{if(state) $('status-message').textContent=performance.now()<transientUntil?transient:!client.connected?'连接中断，等待恢复':state.message;},120);
window.debugInspect=()=>({ready:!!state,tick:state?.tick,seed:state?.map.seed,generation:state?.generation,revision:state?.revision,paused:state?.paused,auto:state?.auto,taskIds:state?.tasks.map(t=>t.id) || []});
client.poll();
