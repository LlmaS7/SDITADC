import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve(import.meta.dirname,'..');
process.on('uncaughtException',error=>{console.error(error.message);console.error((error.stack||'').split('\n').filter(line=>line.includes('merge_paragraphs.mjs')).join('\n'));process.exit(1);});
const runtime='C:/Users/25489/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES=runtime+'/node/node_modules';
const {PresentationFile,FileBlob}=await import(pathToFileURL(runtime+'/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs').href);
const records=JSON.parse(await fs.readFile(path.join(root,'build/source-shapes.json'),'utf8'));
const range=(a,b)=>Array.from({length:b-a+1},(_,i)=>`v2-${a+i}`);
const definitions=[
 [2,range(13,14)],[2,range(17,19)],[2,range(21,23)],
 [3,range(34,36)],[3,range(38,40)],
 [4,range(52,54)],[4,range(55,56)],[4,range(61,63)],[4,range(64,65)],[4,range(70,72)],[4,range(73,74)],
 [5,range(84,87)],[5,range(90,93)],
 [6,range(104,109)],
 [7,range(135,136)],[7,range(138,140)],
 [8,range(149,151)],[8,range(153,154)]
];
const p=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'source/原稿.pptx')));
const inspected=(await p.inspect({kind:'shape,textbox,table,image',maxChars:1000000})).ndjson;
await fs.writeFile(path.join(root,'build/imported-inspect.ndjson'),inspected);
const anchors=inspected.split('\n').filter(Boolean).map(line=>JSON.parse(line));
const plan=[];
for(const [slideNo,names]of definitions){
 const originals=names.map(name=>records.find(r=>r.slide===slideNo&&r.name===name));
 if(originals.some(r=>!r))throw Error('Missing original text shape');
 const slide=p.slides.items[slideNo-1],first=originals[0],last=originals.at(-1),box=first.box;
 const pitch=originals[1].box.y-box.y;
 if(originals.some((r,i)=>r.box.x!==box.x||r.box.cx!==box.cx||Math.abs(r.box.y-box.y-i*pitch)>.01||r.rPr!==first.rPr))throw Error('Nonuniform paragraph group: '+names);
 const name=`paragraph-fix-${slideNo}-${first.name}`;
 const shape=slide.shapes.add({geometry:'textbox',name,position:{left:box.x,top:box.y,width:box.cx,height:last.box.y+last.box.cy-box.y},fill:'none',line:{fill:'none',width:0}});
 // Author a single editable text frame. The packaging pass restores the exact
 // source run formatting and uses soft breaks within one semantic paragraph.
 shape.text=originals.map(r=>r.text).join('\n');
 const size=Number(first.rPr.match(/sz="(\d+)"/)[1])/75;
 const color='#'+first.rPr.match(/srgbClr val="([A-Fa-f0-9]+)"/)[1];
 const font=first.rPr.match(/typeface="([^"]+)"/)[1];
 shape.text.style={typeface:font,fontSize:size,color,bold:false,wrap:'square',autoFit:'none',verticalAlignment:'top',insets:0,lineSpacing:pitch/size};
 for(const original of originals){
   const target=slide.shapes.items.find(s=>s.name===original.name);
   if(!target)throw Error('Imported shape name missing: '+original.name);
   const anchor=anchors.find(a=>a.name===original.name&&a.slideIndex===slideNo-1&&a.id?.startsWith('sh/'));
   if(!anchor)throw Error('Missing canonical shape anchor for '+original.name);
   p.delete([anchor.id]);
 }
 plan.push({slide:slideNo,name,originals,pitch,box:{x:box.x,y:box.y,cx:box.cx,cy:last.box.y+last.box.cy-box.y}});
}
await fs.writeFile(path.join(root,'build/merge-plan.json'),JSON.stringify(plan,null,2));
await(await PresentationFile.exportPptx(p)).save(path.join(root,'build/artifact-candidate.pptx'));
console.log(JSON.stringify({paragraphs:plan.length,oldTextboxes:plan.reduce((n,g)=>n+g.originals.length,0),affectedSlides:[...new Set(plan.map(g=>g.slide))]}));
