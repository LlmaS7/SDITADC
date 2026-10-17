const fs=require('node:fs');
const path=require('node:path');
const dir=__dirname;
const assets=path.resolve(dir,'../../..','project/v0.3_preview/frontend/assets');
const mark=fs.readFileSync(path.join(assets,'logo-mark.svg'),'utf8');
const d=[...mark.matchAll(/<path fill="([^"]+)" d="([^"]+)"/g)].map(m=>m[2]);
const title='智能仓储协同调度系统';
function glyph(body,route,outline=false,engraved=false){
  let amber=d[1];
  if(engraved)amber=amber.split(/(?=M)/).filter(s=>!s.startsWith('M1325')&&!s.startsWith('M384')).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="95 124 1375 465" fill="none"><g fill-rule="evenodd"><path fill="${body}" ${outline?'stroke="#8d9aa5" stroke-width="14" stroke-linejoin="round"':''} d="${d[0]}"/><path fill="${route}" ${!engraved&&!outline?'stroke="#1c2024" stroke-width="8" paint-order="stroke fill" stroke-linejoin="round"':''} d="${amber}"/></g></svg>`;
}
const variants={
  a:glyph('#aeb7be','#e6b568'),
  b:glyph('#171b1f','#e6b568',true),
  d:glyph('#e6b568','#1c2024',false,true)
};
const stacked=fs.readFileSync(path.join(assets,'logo-stacked.svg'),'utf8');
const groups=[...stacked.matchAll(/<g fill-rule="evenodd">.*?<\/g>/g)].map(m=>m[0]);
variants.c=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="95 124 1375 650" fill="none">${variants.a.match(/<g.*<\/g>/)[0]}${groups[1].replace('#24292e','#aeb7be')}</svg>`;
for(const [id,svg]of Object.entries(variants))fs.writeFileSync(path.join(dir,`mark-${id}.svg`),svg);
const options=[
  {id:'a',name:'A · 无底嵌入',tag:'优先推荐',note:'去掉底板；银灰主体与琥珀路径直接融入顶栏，标题位置延续现在的习惯。',sub:'AWCS · 仓库运行总览'},
  {id:'b',name:'B · 深色铭牌',tag:'保留容器感',note:'保留深色边框，用细银灰描边勾出 AW；更偏工业控制台。',sub:'AWCS · 仓库运行总览'},
  {id:'c',name:'C · 品牌组合',tag:'更完整',note:'AW 图形与原版 AWCS 字标上下组合，以细分隔线与系统名称区分层次。',sub:'Agent-Assisted Warehouse Coordination System'},
  {id:'d',name:'D · 琥珀单色',tag:'更醒目',note:'以主题琥珀色统一图形，路径改成深色镂空；名称与 AWCS 合成一行。',sub:'仓库运行总览 / Warehouse Overview'}
];
const brand=o=>`<div class="brand ${o.id}"><span class="mark"><img src="mark-${o.id}.svg" alt="AWCS图形"></span>${o.id==='c'?'<i class="divider"></i>':''}<div class="words"><h2>${o.id==='d'?'<b>AWCS</b><span class="dot">·</span>':''}${title}</h2><p>${o.sub}</p></div></div>`;
const stats='<div class="stats"><span class="running">运行中</span><span>已完成 <b>1</b></span><span>执行中 <b>3</b></span><span>待处理 <b>5</b></span></div>';
const head=o=>`<header class="head">${brand(o)}${stats}</header>`;
const toolbar='<div class="toolbar"><span class="pause">暂停</span><span>速度</span><span class="speed">2×⌄</span><span class="spacer"></span><span class="control">AI 设置</span><span class="control">调试窗口 ↗</span></div>';
fs.writeFileSync(path.join(dir,'index.html'),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AWCS · 顶栏方案比较</title><style>
*{box-sizing:border-box}body{margin:0;background:#101214;color:#eef0f1;font:14px/1.5 'Segoe UI','Microsoft YaHei',sans-serif}button{font:inherit;cursor:pointer}main{max-width:1240px;margin:auto;padding:30px 28px 40px}h1{font-size:25px;margin:0 0 6px;font-weight:600}.intro{color:#99a3ab;margin:0 0 24px;font-size:13px}.label{display:flex;gap:12px;align-items:baseline;margin:0 0 9px}.label h3{font-size:16px;font-weight:600;margin:0}.tag{color:#e6b568;font-size:11px}.note{color:#98a2aa;font-size:12px;margin:9px 0 0}.option{margin:0 0 22px}.frame{border:1px solid #343b41;border-radius:5px;overflow:hidden}.head{height:78px;padding:0 24px;display:flex;align-items:center;justify-content:space-between;gap:20px;background:#1c2024;border-bottom:1px solid #343b41}.brand{display:flex;align-items:center;gap:15px;flex-shrink:0}.mark{display:grid;place-items:center;width:112px;height:46px;flex-shrink:0}.mark img{display:block;width:108px;height:37px;object-fit:contain}.words h2{font-size:21px;font-weight:650;letter-spacing:.5px;line-height:1.3;margin:0}.words p{font:12px/1.3 Consolas,'Microsoft YaHei',monospace;letter-spacing:.6px;color:#9ba6af;margin:5px 0 0}.b .mark{background:#252b30;border:1px solid #46515a;border-radius:4px}.b .mark img{width:98px;height:34px}.c .mark{width:108px;height:56px}.c .mark img{width:108px;height:52px}.divider{height:34px;width:1px;background:#475057;margin:0 3px}.c .words h2{font-size:20px}.c .words p{font:11px/1.3 'Segoe UI',sans-serif;letter-spacing:.25px}.d .mark{width:96px}.d .mark img{width:92px;height:32px}.d .words h2{font-size:20px;font-weight:600}.d .words h2 b{font-size:22px;letter-spacing:1px}.dot{color:#616b73;margin:0 10px}.d .words p{font:11px/1.3 'Segoe UI','Microsoft YaHei',sans-serif}.stats{display:flex;align-items:center;gap:24px;white-space:nowrap;color:#9faab3;font-size:12px}.stats b{font:600 17px Consolas,monospace;margin-left:9px;color:#eef0f1}.running{font-size:12px;background:#233a30;color:#9cd7b4;border:1px solid #456454;padding:4px 11px;border-radius:20px}.toolbar{height:48px;display:flex;align-items:center;gap:9px;background:#121416;padding:0 24px;font-size:11px;color:#abb2b8}.pause{background:#e6b568;color:#241b0b;padding:6px 12px;border-radius:4px;font-weight:600}.speed,.control{padding:6px 10px;background:#24292e;border:1px solid #3b4248;border-radius:4px;color:#dbe0e3}.spacer{flex:1}.choose{margin-left:auto;border:1px solid #424b53;color:#cbd3d9;background:#24292e;border-radius:4px;padding:3px 9px;font-size:11px}.choose:hover,.choose.active{border-color:#e6b568;color:#e6b568;background:#393023}.detail{margin-top:32px}.detail h3{font-size:18px;font-weight:600;margin:0 0 8px}.detail p{color:#98a2aa;font-size:12px}.full{position:relative;border:1px solid #343b41;border-radius:5px;overflow:hidden;container-type:inline-size}.full>img{display:block;width:100%;height:auto}.overlay{position:absolute;left:0;top:1.25cqw;width:100%;height:3.8086cqw;background:#1c2024}.overlay iframe{width:2048px;height:78px;border:0;transform-origin:0 0;display:block}.foot{color:#87929b;font-size:12px;margin:18px 0 0}@media(max-width:1050px){.stats{gap:12px}.head{padding:0 16px}.words h2{font-size:18px}.c .words p{font-size:10px}.mark{width:100px}.mark img{width:96px}.d .words h2{font-size:18px}.stats{font-size:11px}}@media(max-width:800px){main{padding:24px 16px}.frame{overflow:auto}.frame>.head,.frame>.toolbar{min-width:1000px}.intro{max-width:40em}}
</style><main><h1>AWCS · 去白底的四个方向</h1><p class="intro">保留已选 AW 轮廓，比较暗色适配与标题排版。下面均为局部粗预览；点击按钮可查看在你这张截图中的整体效果。</p><div id="comparisons">${options.map(o=>`<section class="option"><div class="label"><h3>${o.name}</h3><span class="tag">${o.tag}</span><button class="choose ${o.id==='a'?'active':''}" data-option="${o.id}">查看全界面</button></div><div class="frame">${head(o)}${toolbar}</div><p class="note">${o.note}</p></section>`).join('')}</div><section class="detail"><h3 id="detail-title">A · 无底嵌入 / 全界面预览</h3><p>背景沿用你的界面截图，仅用 HTML 覆盖顶栏；下方是对照画面。</p><div class="full"><img src="reference.png" alt="用户当前界面截图"><div class="overlay"><iframe title="所选方案的顶栏" src="header-a.html"></iframe></div></div></section><p class="foot">探索稿 · 2026-10-16 · 正式程序未修改。A / C 的银灰主体用深色细线分隔琥珀路径。</p></main><script>
const titles=${JSON.stringify(Object.fromEntries(options.map(o=>[o.id,o.name])))};
function resize(){const host=document.querySelector('.overlay');host.querySelector('iframe').style.transform='scale('+host.clientWidth/2048+')'}new ResizeObserver(resize).observe(document.querySelector('.full'));
for(const btn of document.querySelectorAll('[data-option]'))btn.onclick=()=>{document.querySelectorAll('[data-option]').forEach(b=>b.classList.toggle('active',b===btn));document.querySelector('iframe').src='header-'+btn.dataset.option+'.html';document.querySelector('#detail-title').textContent=titles[btn.dataset.option]+' / 全界面预览';};
</script></html>`);
// Standalone headers share the exact same CSS with the comparison page.
const html=fs.readFileSync(path.join(dir,'index.html'),'utf8'),css=html.match(/<style>([\s\S]*?)<\/style>/)[1];
for(const o of options)fs.writeFileSync(path.join(dir,`header-${o.id}.html`),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>${css}body{background:#1c2024}</style>${head(o)}</html>`);
fs.writeFileSync(path.join(dir,'README.md'),'# AWCS 顶栏无白底探索\n\n打开 index.html 比较 A/B/C/D 四个方向，并切换下方的完整界面预览。\n\n'+options.map(o=>`- ${o.name}：${o.note}`).join('\n')+'\n\n仅为 .temp HTML/CSS 与 SVG 探索；正式程序及已选原稿未修改。reference.png 是用户本次提供的截图原件。银灰和单色配色是预览变体，未替换生产素材。\n');
console.log('Created 4 SVG variants, 4 headers and interactive comparison page.');
