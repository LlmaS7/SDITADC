import { Map2D } from './map2d.js';
import { Scene3D } from './scene3d.js';

const $ = id => document.getElementById(id);
const map2d=new Map2D($('map2d')), scene3d=new Scene3D($('scene3d'));
const robotColors=['#4bb4fc','#ffb354','#76d4ad'];
let state=null, receivedAt=0, connected=false, pending=0;
let selected=null, selectionInitialized=false, filter='all', taskSignature='', mapKey='';
let transient='', transientUntil=0, currentPositions={};
const finished=t=>t.status==='completed';
const idText=id=>'T'+String(id).padStart(3,'0');

function chosen() { return state?.tasks.find(t=>t.id===selected) || null; }
function filtered() { return (state?.tasks || []).filter(t=>filter==='all' || (filter==='completed' ? finished(t) : !finished(t))); }
function toast(value) { transient=value; transientUntil=performance.now()+4500; }

function controls() {
  if(!state) return;
  const busy=pending>0 || !connected;
  for(const id of ['pause','step','random','new-task','auto','retry','save','load','reset']) $(id).disabled=busy;
  $('speed').disabled=busy;
  $('pause').textContent=state.paused ? '继续' : '暂停';
  $('speed').value=String(state.speed);
  $('auto').textContent=state.auto ? '自动生成：开' : '自动生成：关';
  $('auto').setAttribute('aria-pressed',String(state.auto));
  const t=chosen();
  $('raise').disabled=busy || !t || finished(t) || t.priority===5;
  $('urgent').disabled=$('raise').disabled;
  $('cancel').disabled=busy || !t || !['pending','reserved','to_pickup'].includes(t.status);
}

function renderTasks() {
  if(!state) return;
  const list=filtered();
  if(!selectionInitialized) { selected=list[0]?.id ?? null; selectionInitialized=true; }
  if(selected!==null && !list.some(t=>t.id===selected)) selected=list[0]?.id ?? null;
  const signature=JSON.stringify([filter,selected,state.tick,list]);
  if(signature!==taskSignature) {
    taskSignature=signature;
    const scroll=$('tasks').scrollTop;
    const fragment=document.createDocumentFragment();
    for(const t of list) {
      const row=document.createElement('button'); row.className='task-card'+(t.id===selected?' selected':'');
      row.dataset.taskId=t.id; row.setAttribute('aria-label',`${idText(t.id)} ${t.label}`);
      const age=(t.completed_at ?? state.tick)-t.created_at;
      const warning=['pending','reserved'].includes(t.status) && age>=state.wait_warning;
      row.innerHTML=`<span class="task-top"><span class="task-id">${idText(t.id)} <span class="priority-tag${t.priority===5?' urgent':''}">${t.priority===5?'紧急':'等级 '+t.priority}</span></span><span class="task-owner">${t.label}${t.robot_id?' · R'+t.robot_id:''}</span></span><span class="task-route">取货点 ${String(t.pickup_number).padStart(2,'0')} → 配送点 D${t.delivery_number}</span><span class="task-age${warning?' warning':''}">已用时 ${age} 步${warning?' · 等待较久':''}</span>`;
      fragment.append(row);
    }
    if(!list.length) { const e=document.createElement('p'); e.className='empty'; e.textContent='当前筛选下没有任务'; fragment.append(e); }
    $('tasks').replaceChildren(fragment); $('tasks').scrollTop=scroll;
  }
  const t=chosen();
  $('detail-title').textContent=t ? `${idText(t.id)} · ${t.label}` : '选择一个任务';
  $('detail-route').textContent=t ? `取货点 ${t.pickup_number} → 配送点 D${t.delivery_number} · 抢占 ${t.preemptions} 次` : '点击任务查看其取送位置';
  $('detail-note').textContent=t?.status==='reserved' ? `R${t.robot_id} 完成当前搬运后接手` : t?.status==='pending' && t.priority===5 ? '暂无立即可用的机器人，等待安全接手' : t ? '取 / 送标记表示选中任务的位置' : '';
  scene3d.highlight(t); controls();
}

function accept(value) {
  if(state && value.generation===state.generation && value.revision<state.revision) return;
  const changedGeneration=state && value.generation!==state.generation;
  if(changedGeneration) { selected=null; selectionInitialized=false; taskSignature=''; }
  state=value; receivedAt=performance.now();
  const key=state.generation+':'+state.map.seed;
  if(key!==mapKey) {
    mapKey=key; map2d.setMap(state.map); scene3d.setMap(state.map);
    $('pickup').replaceChildren(...state.map.pickups.map((p,i)=>new Option(`取货点 ${i+1} · (${p})`,i+1)));
    $('delivery').replaceChildren(...state.map.deliveries.map((p,i)=>new Option(`配送点 D${i+1} · (${p})`,i+1)));
  }
  $('tick').textContent=String(state.tick).padStart(4,'0'); $('seed').textContent=state.map.seed;
  $('task-count').textContent=state.metrics.visible_total;
  $('completed-count').textContent=`完成 ${state.metrics.completed} / ${state.metrics.visible_total}`;
  $('avg-completion').innerHTML=state.metrics.avg_completion.toFixed(1)+' <small>步</small>';
  $('distance').innerHTML=state.metrics.distance+' <small>格</small>';
  $('waits').innerHTML=state.metrics.waits+' <small>步</small>';
  $('plan-ms').innerHTML=state.metrics.last_plan_ms.toFixed(1)+' <small>ms</small>';
  $('assignment-note').textContent=`本轮预计完成时间和 ${state.assignment.eta_sum ?? 0} 步；匹配代价不含未来冲突等待。`;
  $('robots').innerHTML=state.robots.map(r=>`<article class="robot-card"><h3><span style="color:${robotColors[r.id-1]}">R${r.id}</span><span>${r.label}</span></h3><p>${r.task_id?idText(r.task_id):'等待接单'}${r.next_task_id?' → '+idText(r.next_task_id):''}</p><p>完成 ${r.completed} · 移动 ${r.distance} 格${r.loaded?' · 已载货':''}</p></article>`).join('');
  renderTasks(); scene3d.update(state,chosen());
  $('mode-note').textContent=state.replaying ? '输入事件回放 · 三台机器人' : '普通场景 · 三台机器人';
}

async function poll() {
  try {
    const response=await fetch('./api/state',{cache:'no-store'});
    if(!response.ok) throw new Error('连接未就绪');
    const value=await response.json(); connected=true;
    if(!state || value.revision!==state.revision || value.generation!==state.generation) accept(value);
    controls();
  } catch(error) { connected=false; controls(); }
  finally { setTimeout(poll,connected?110:1000); }
}

async function command(operation,data={}) {
  if(!connected) { toast('尚未连接仿真，请稍后再试'); return false; }
  pending++; controls();
  try {
    const response=await fetch('./api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,data})});
    const result=await response.json();
    if(!response.ok || !result.ok) throw new Error(result.error || '操作未完成');
    accept(result.state); return true;
  } catch(error) { toast(error.message); return false; }
  finally { pending--; controls(); }
}

$('pause').onclick=()=>command('pause',{paused:!state.paused});
$('step').onclick=()=>command('step');
$('speed').onchange=()=>command('speed',{value:Number($('speed').value)});
$('random').onclick=()=>command('random');
$('auto').onclick=()=>command('auto',{enabled:!state.auto});
$('retry').onclick=()=>command('retry');
$('save').onclick=()=>command('save');
$('load').onclick=()=>command('load');
$('reset').onclick=()=>command('reset');
$('recenter').onclick=()=>scene3d.recenter();
$('raise').onclick=()=>{const t=chosen();if(t) command('priority',{task_id:t.id,priority:t.priority+1});};
$('urgent').onclick=()=>{const t=chosen();if(t) command('priority',{task_id:t.id,priority:5});};
$('cancel').onclick=()=>{const t=chosen();if(t) command('cancel',{task_id:t.id});};
$('clear-selection').onclick=()=>{selected=null;selectionInitialized=true;renderTasks();};
$('tasks').onclick=e=>{const row=e.target.closest('[data-task-id]');if(row){selected=Number(row.dataset.taskId);selectionInitialized=true;renderTasks();}};
document.querySelectorAll('[data-filter]').forEach(button=>{button.onclick=()=>{filter=button.dataset.filter;$('tasks').scrollTop=0;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===button));renderTasks();};});
$('new-task').onclick=async()=>{if(await command('pause',{paused:true})) $('task-dialog').showModal();};
$('close-dialog').onclick=$('back-dialog').onclick=()=>$('task-dialog').close();
$('task-form').onsubmit=async e=>{e.preventDefault();if(await command('add',{pickup:Number($('pickup').value),delivery:Number($('delivery').value),priority:Number($('priority').value)})) $('task-dialog').close();};
document.addEventListener('keydown',e=>{
  if($('task-dialog').open || ['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName) || pending || !connected) return;
  if(e.code==='Space'){e.preventDefault();$('pause').click();}
  else if(e.key.toLowerCase()==='n') $('step').click();
  else if(e.key.toLowerCase()==='a') $('random').click();
  else if(e.key.toLowerCase()==='r') $('retry').click();
  else if(e.key.toLowerCase()==='s') $('save').click();
});

function renderFrame() {
  if(state) {
    const alpha=state.paused || state.planning || !connected ? 1 : Math.min(1,(state.seconds_since_step+(performance.now()-receivedAt)/1000)*state.speed);
    currentPositions=Object.fromEntries(state.robots.map(r=>[r.id,[r.previous[0]+(r.position[0]-r.previous[0])*alpha,r.previous[1]+(r.position[1]-r.previous[1])*alpha]]));
    map2d.draw(state,currentPositions,chosen()); scene3d.draw(state,currentPositions);
    $('connection').textContent=!connected?'连接中断':state.planning?'规划中':state.paused?'已暂停':'运行中';
    $('connection').classList.toggle('offline',!connected);
    $('status-message').textContent=performance.now()<transientUntil?transient:!connected?'连接中断，画面保留最后状态':state.message;
  }
}
function animate() { renderFrame(); requestAnimationFrame(animate); }
window.previewDebug={inspect:()=>{renderFrame();return {ready:!!state, tick:state?.tick, viewTicks:[$('map2d').dataset.tick,$('scene3d').dataset.tick],...scene3d.inspect(), canvas2d:Object.entries(currentPositions).map(([id,p])=>({id:Number(id),x:p[0],y:p[1]})), taskIds:[...document.querySelectorAll('[data-task-id]')].map(e=>Number(e.dataset.taskId))};}};
poll(); animate();
