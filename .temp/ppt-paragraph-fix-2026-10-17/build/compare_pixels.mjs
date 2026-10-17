import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire('C:/Users/25489/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/package.json');
const sharp=require('sharp');
const root=path.resolve(import.meta.dirname,'..');
const plan=JSON.parse(await fs.readFile(path.join(root,'build/merge-plan.json'),'utf8'));
const report=[];
for(let slide=1;slide<=11;slide++){
 const filename=`幻灯片${slide}.PNG`;
 const before=await sharp(path.join(root,'before',filename)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const after=await sharp(path.join(root,'after',filename)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const {width,height,channels}=before.info;
 if(width!==after.info.width||height!==after.info.height)throw Error('Slide dimensions changed');
 const boxes=plan.filter(g=>g.slide===slide).map(g=>g.box);
 let changed=0,outside=0,maxDelta=0,minX=width,minY=height,maxX=-1,maxY=-1;
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const i=(y*width+x)*channels;let delta=0;
   for(let c=0;c<3;c++)delta=Math.max(delta,Math.abs(before.data[i+c]-after.data[i+c]));
   if(delta){changed++;maxDelta=Math.max(maxDelta,delta);minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);
     if(!boxes.some(b=>x>=b.x-2&&x<=b.x+b.cx+2&&y>=b.y-2&&y<=b.y+b.cy+2))outside++;
   }
 }
 if(outside)throw Error(`Unrelated pixels changed on slide ${slide}: ${outside}`);
 report.push({slide,changedPixels:changed,changedRatio:changed/(width*height),outsideParagraphRegions:outside,bbox:changed?[minX,minY,maxX,maxY]:null});
}
await fs.writeFile(path.join(root,'build/pixel-comparison.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
