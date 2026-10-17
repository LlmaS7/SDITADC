import fs from 'node:fs/promises';import path from 'node:path';import {createRequire} from 'node:module';
const sharp=createRequire('C:/Users/25489/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/package.json')('sharp');
const root=path.resolve(import.meta.dirname,'..'),plan=JSON.parse(await fs.readFile(path.join(root,'build/merge-plan.json'),'utf8'));
const cache=new Map();
async function get(which,slide){const key=which+slide;if(!cache.has(key))cache.set(key,await sharp(path.join(root,which,`幻灯片${slide}.PNG`)).ensureAlpha().raw().toBuffer({resolveWithObject:true}));return cache.get(key);}
function bbox(image,box){let top=9999,bottom=-1,left=9999,right=-1;for(let y=Math.floor(box.y);y<Math.ceil(box.y+box.cy);y++)for(let x=Math.floor(box.x);x<Math.ceil(box.x+box.cx);x++){const i=(y*image.info.width+x)*4;if(Math.max(Math.abs(image.data[i]-245),Math.abs(image.data[i+1]-242),Math.abs(image.data[i+2]-233))>50){top=Math.min(top,y);bottom=Math.max(bottom,y);left=Math.min(left,x);right=Math.max(right,x);}}return [left,top,right,bottom];}
const measurements=[];
for(const g of plan){const before=await get('before',g.slide),after=await get('after',g.slide);const lines=g.originals.map(r=>({source:bbox(before,r.box),after:bbox(after,{...r.box,cy:g.pitch})}));measurements.push({slide:g.slide,name:g.originals[0].name,lines,delta:lines.map(l=>l.after[1]-l.source[1])});}
await fs.writeFile(path.join(root,'build/ink-measurements.json'),JSON.stringify(measurements,null,2));console.log(JSON.stringify(measurements));
