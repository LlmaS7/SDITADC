import {api} from './settings.js';
const $=id=>document.getElementById(id);
const names={get_status:'查询业务状态',get_locations:'查询作业点',create_tasks:'创建任务',raise_task_priorities:'提升优先级',cancel_tasks:'取消任务',get_metrics:'查询业务指标'};
const outcomes={applied:'已生效',no_change:'无需改变',rejected:'未能执行',not_executed:'未执行'};
export class Chat {
  constructor(options){
    Object.assign(this,options);this.cursor=0;this.rows=new Map();this.busy=false;this.submitting=false;this.request=null;this.ready=false;
    this.settings.onChange=v=>this.configure(v);
    $('chat-send').onclick=()=>this.send();$('chat-stop').onclick=()=>api('stop',{request_id:this.request}).catch(e=>this.notice(e.message));
    $('chat-clear').onclick=()=>api('clear',{}).catch(e=>this.notice(e.message));$('chat-unlink').onclick=()=>this.unlink();
    $('chat-input').oninput=()=>this.controls();$('chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!$('chat-send').disabled)this.send();}};
    this.settings.refresh().catch(()=>{});this.poll();
  }
  configure(v){this.ready=v.has_key&&!!v.model;$('ai-status').textContent=v.has_key?(v.model?`${v.model} · ${v.verified?'已验证':'未验证'}`:'请选择模型'):'先配置 DeepSeek，即可使用';this.controls();}
  controls(){$('chat-send').disabled=this.busy||this.submitting||!this.ready||!this.state()||!$('chat-input').value.trim();$('chat-stop').disabled=!this.busy;}
  updateAssociation(){const id=this.selected();$('chat-association').textContent=id?`当前关联：T${String(id).padStart(3,'0')}`:'未关联任务';$('chat-unlink').disabled=!id;this.controls();}
  append(className,text){const p=document.createElement('div');p.className=className;p.textContent=text;$('chat-messages').append(p);return p;}
  notice(text){this.append('chat-notice',text);}
  async send(){const state=this.state();if(!state||this.busy||this.submitting)return;const text=$('chat-input').value.trim();if(!text)return;this.busy=true;this.submitting=true;this.controls();try{await api('messages',{text,task_id:this.selected(),generation:state.generation});if($('chat-input').value.trim()===text)$('chat-input').value='';}catch(e){this.busy=false;this.notice(e.message);}finally{this.submitting=false;this.controls();}}
  row(e){let row=this.rows.get(e.request_id);if(!row){const article=document.createElement('article');article.className='chat-reply';const progress=document.createElement('p');progress.className='subtle';const text=document.createElement('div');text.className='chat-text';const results=document.createElement('div');results.className='chat-results';article.append(progress,text,results);$('chat-messages').append(article);row={article,progress,text,results,generation:e.generation};this.rows.set(e.request_id,row);}return row;}
  event(e){
    if(e.kind==='clear'){$('chat-messages').replaceChildren();this.rows.clear();return;}
    if(e.kind==='context'){this.notice(e.message);return;}
    if(e.kind==='start'){
      this.settings.value&&(this.settings.value.request_id=e.request_id);this.request=e.request_id;
      if(e.job==='message'){document.querySelector('.chat-welcome')?.remove();this.append('chat-user',e.text);const row=this.row(e);row.progress.textContent='正在处理…';}
      else this.settings.message(e.job==='models'?'正在获取模型…':'正在测试连接与只读工具…');
      return;
    }
    this.settings.event(e);
    const row=this.rows.get(e.request_id);
    if(e.kind==='text'&&row)row.text.textContent+=e.text;
    if(e.kind==='progress'&&row)row.progress.textContent=names[e.tool]||'正在处理业务请求';
    if(e.kind==='result'&&row){
      row.progress.textContent='业务结果已返回';
      if(e.result.error){const p=document.createElement('p');p.className='result-error';p.textContent=e.result.error;row.results.append(p);}
      for(const item of e.result.actions||[]){const card=document.createElement('div');card.className='result-card '+(item.outcome==='applied'?'success':'');const title=document.createElement('strong');title.textContent=`${names[e.tool]||'业务操作'} · ${outcomes[item.outcome]||item.outcome}`;card.append(title);
        if(item.task_id){const b=document.createElement('button');b.className='text-button task-link';b.textContent=item.task_id;b.onclick=()=>this.select(Number(item.task_id.slice(1)),e.generation);card.append(b);}
        if(item.pickup_label&&item.delivery_name){const route=document.createElement('p');route.textContent=`${item.pickup_label} → ${item.delivery_name}`;card.append(route);}
        const detail=document.createElement('p');detail.textContent=[item.phase_label,item.assigned_robot,item.priority?`等级 ${item.priority}`:'',item.reason].filter(Boolean).join(' · ');card.append(detail);row.results.append(card);}
    }
    if(['notice','error'].includes(e.kind)){if(row){const p=document.createElement('p');p.className=e.kind==='error'?'result-error':'chat-notice';p.textContent=e.message;row.article.append(p);}else if(!e.request_id)this.notice(e.message);}
    if(e.kind==='done'&&row)row.progress.textContent='本轮处理结束 · 操作以结果卡为准';
  }
  async poll(){try{const v=await api('events?after='+this.cursor);const area=$('chat-messages');const nearBottom=area.scrollHeight-area.scrollTop-area.clientHeight<70;for(const e of v.events)this.event(e);if(v.gap)this.notice('部分旧消息已超出本次显示缓存；当前任务以任务列表为准');this.cursor=v.cursor;this.busy=v.busy;this.request=v.request_id;this.settings.status(v);if(nearBottom)area.scrollTop=area.scrollHeight;this.controls();if(v.events.some(e=>['done','context'].includes(e.kind)))this.settings.refresh().catch(()=>{});}catch{this.controls();}finally{setTimeout(()=>this.poll(),180);}}
}
