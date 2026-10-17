// Trace the approved reference into self-contained SVG paths; no image generation.
// Run with the existing local Playwright package; the reference PNG stays intact.
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('C:/Users/25489/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright');
const root = path.resolve(__dirname, '../../project/v0.3_preview/frontend/assets');
function simplify(points, tolerance = 1) {
  if (points.length < 3) return points;
  const a = points[0], b = points.at(-1), dx = b[0]-a[0], dy = b[1]-a[1];
  let far = 0, at = 0;
  for (let i=1;i<points.length-1;i++) {
    const p=points[i], t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
    const d=Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
    if(d>far){far=d;at=i;}
  }
  return far>tolerance ? [...simplify(points.slice(0,at+1),tolerance).slice(0,-1),...simplify(points.slice(at),tolerance)] : [a,b];
}
function trace(pixels, width, height, box, amberOnly=false, tolerance=1) {
  const [x0,y0,x1,y1]=box, w=x1-x0, h=y1-y0, mask=new Uint8Array(w*h);
  for(let y=0;y<h;y++) for(let x=0;x<w;x++) {
    const i=((y+y0)*width+x+x0)*4, r=pixels[i],g=pixels[i+1],b=pixels[i+2];
    const amber=r>145&&g>85&&b<190&&r-b>50&&r>g;
    mask[y*w+x]=amberOnly ? amber : amber || Math.max(r,g,b)<145;
  }
  const edges=new Map(), stride=w+1;
  const add=(ax,ay,bx,by)=>{const a=ay*stride+ax,b=by*stride+bx;if(!edges.has(a))edges.set(a,[]);edges.get(a).push(b);};
  const on=(x,y)=>x>=0&&x<w&&y>=0&&y<h&&mask[y*w+x];
  for(let y=0;y<h;y++) for(let x=0;x<w;x++) if(on(x,y)) {
    if(!on(x,y-1))add(x,y,x+1,y);
    if(!on(x+1,y))add(x+1,y,x+1,y+1);
    if(!on(x,y+1))add(x+1,y+1,x,y+1);
    if(!on(x-1,y))add(x,y+1,x,y);
  }
  const paths=[];
  while(edges.size) {
    const start=edges.keys().next().value; let key=start; const points=[];
    do {
      points.push([key%stride+x0,Math.floor(key/stride)+y0]);
      const next=edges.get(key); if(!next)break;
      const dest=next.pop(); if(!next.length)edges.delete(key); key=dest;
    }while(key!==start);
    const area=points.reduce((n,p,i)=>{const q=points[(i+1)%points.length];return n+p[0]*q[1]-q[0]*p[1];},0)/2;
    if(Math.abs(area)<12)continue;
    // Split the closed polygon at its farthest vertex for stable simplification.
    let far=1;for(let i=2;i<points.length;i++)if(Math.hypot(points[i][0]-points[0][0],points[i][1]-points[0][1])>Math.hypot(points[far][0]-points[0][0],points[far][1]-points[0][1]))far=i;
    const pts=[...simplify(points.slice(0,far+1),tolerance).slice(0,-1),...simplify([...points.slice(far),points[0]],tolerance).slice(0,-1)];
    paths.push('M'+pts.map(p=>p.join(' ')).join('L')+'Z');
  }
  return paths.join('');
}
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage();
    const src='data:image/png;base64,'+fs.readFileSync(path.join(__dirname,'05-selected-awcs.png')).toString('base64');
    const data=await page.evaluate(async src=>{const img=new Image();img.src=src;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);return {w:c.width,h:c.height,p:[...ctx.getImageData(0,0,c.width,c.height).data]};},src);
    const groups={};
    for(const [name,box] of Object.entries({mark:[95,124,1470,589],word:[280,605,1225,765],names:[198,775,1340,936]})) {
      groups[name]=`<g fill-rule="evenodd"><path fill="#24292e" d="${trace(data.p,data.w,data.h,box,false,name==='mark'?3:1)}"/>`;
      if(name==='mark')groups[name]+=`<path fill="#e6b568" d="${trace(data.p,data.w,data.h,box,true,3)}"/>`;
      groups[name]+='</g>';
    }
    const svg=(view,title,body)=>`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${view}" fill="none"><title>${title}</title>${body}</svg>\n`;
    const title='AWCS · 智能仓储协同调度系统';
    fs.writeFileSync(path.join(root,'logo-mark.svg'),svg('95 124 1375 465',title,groups.mark));
    fs.writeFileSync(path.join(root,'logo-stacked.svg'),svg('0 0 1536 1024',title,'<rect width="1536" height="1024" fill="#fff"/>'+groups.mark+groups.word+groups.names));
    fs.writeFileSync(path.join(root,'logo.svg'),svg('0 0 1440 420',title,'<rect width="1440" height="420" fill="#fff"/>'+`<g transform="translate(24 67) scale(.39)">${groups.mark}</g><g transform="translate(465 -249) scale(.59)">${groups.word}</g><g transform="translate(476 -270) scale(.64)">${groups.names}</g>`));
    fs.writeFileSync(path.join(root,'logo-icon.svg'),svg('0 0 64 64','AWCS','<rect width="64" height="64" rx="8" fill="#fff"/>'+`<g transform="translate(-1 10) scale(.043)">${groups.mark}</g><g transform="translate(4 18) scale(.037)">${groups.word}</g>`));
    fs.writeFileSync(path.join(__dirname,'05-selected-awcs.svg'),fs.readFileSync(path.join(root,'logo-stacked.svg')));
    const vector='data:image/svg+xml;base64,'+fs.readFileSync(path.join(root,'logo-stacked.svg')).toString('base64');
    const fidelity=await page.evaluate(async({src,vector})=>{
      async function raster(url){const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=1536;c.height=1024;const ctx=c.getContext('2d');ctx.drawImage(img,0,0,1536,1024);return ctx.getImageData(0,0,1536,1024).data;}
      const a=await raster(src),b=await raster(vector),counts={ink:[0,0],amber:[0,0]};
      const amber=(p,i)=>p[i]>145&&p[i+1]>85&&p[i+2]<190&&p[i]-p[i+2]>50&&p[i]>p[i+1];
      for(let i=0;i<a.length;i+=4){const aa=amber(a,i),ba=amber(b,i),ai=aa||Math.max(a[i],a[i+1],a[i+2])<145,bi=ba||Math.max(b[i],b[i+1],b[i+2])<145;
        counts.ink[0]+=ai&&bi;counts.ink[1]+=ai||bi;counts.amber[0]+=aa&&ba;counts.amber[1]+=aa||ba;
      }
      return {inkIntersectionOverUnion:counts.ink[0]/counts.ink[1],amberIntersectionOverUnion:counts.amber[0]/counts.amber[1],method:'Binary ink and amber mask overlap at original 1536x1024 resolution; colors normalized, emblem paths simplified within three source pixels to remove raster edge noise, lettering within one pixel.'};
    },{src,vector});
    fs.writeFileSync(path.join(__dirname,'vector-fidelity.json'),JSON.stringify(fidelity,null,2)+'\n');
    if(fidelity.inkIntersectionOverUnion<.98||fidelity.amberIntersectionOverUnion<.95)throw Error('Reference fidelity below expected threshold: '+JSON.stringify(fidelity));
    console.log(JSON.stringify({source:[data.w,data.h],outputs:['logo-mark.svg','logo-stacked.svg','logo.svg','logo-icon.svg'],bytes:Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,v.length]))}));
    console.log(JSON.stringify(fidelity));
  } finally {await browser.close();}
})();
