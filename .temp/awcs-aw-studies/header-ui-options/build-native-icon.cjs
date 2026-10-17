// Rasterize the approved SVG glyph directly; pack PNG frames into a Windows ICO.
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('C:/Users/25489/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright');
const assets=path.resolve(__dirname,'../../../project/v0.3_preview/frontend/assets');
const output=path.resolve(__dirname,'../../../project/v0.3_preview/output/native');
fs.mkdirSync(output,{recursive:true});
const mark=fs.readFileSync(path.join(assets,'logo-mark.svg'),'utf8');
const group=mark.match(/<g fill-rule="evenodd">.*?<\/g>/)[0];
// Square canvas with transparent margins, keeping the original wide AW proportions.
const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><title>AW logo</title><svg x="8" y="87.418" width="240" height="81.164" viewBox="95 124 1375 465">${group}</svg></svg>\n`;
fs.writeFileSync(path.join(assets,'app-icon.svg'),svg);
const sizes=[16,20,24,32,40,48,64,128,256];
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage(),frames=[];
    for(const size of sizes){
      const base64=await page.evaluate(async({svg,size})=>{
        const img=new Image();img.src='data:image/svg+xml;base64,'+btoa(svg);await img.decode();
        const canvas=document.createElement('canvas');canvas.width=canvas.height=size;
        const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,size,size);
        return canvas.toDataURL('image/png').split(',')[1];
      },{svg,size});
      const png=Buffer.from(base64,'base64');frames.push(png);
      fs.writeFileSync(path.join(output,`app-icon-${size}.png`),png);
      if(size===256)fs.writeFileSync(path.join(assets,'app-icon.png'),png);
    }
    const header=Buffer.alloc(6+16*sizes.length);header.writeUInt16LE(1,2);header.writeUInt16LE(sizes.length,4);
    let offset=header.length;
    frames.forEach((png,i)=>{const base=6+16*i,size=sizes[i];header[base]=header[base+1]=size===256?0:size;header.writeUInt16LE(1,base+4);header.writeUInt16LE(32,base+6);header.writeUInt32LE(png.length,base+8);header.writeUInt32LE(offset,base+12);offset+=png.length;});
    fs.writeFileSync(path.join(assets,'app-icon.ico'),Buffer.concat([header,...frames]));
    fs.writeFileSync(path.join(output,'icon-preview.html'),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>AW native icon</title><style>body{background:#1c2024;color:#eef0f1;font:14px 'Segoe UI',sans-serif;padding:24px}.sizes{display:flex;align-items:center;gap:28px}.sample{display:grid;justify-items:center;gap:12px}img{display:block}.large{margin-top:24px}</style><h2>AW · 原生窗口与任务栏图标</h2><p>透明底，仅图形；各尺寸按实际像素显示。</p><div class="sizes">${sizes.slice(0,-1).map(size=>`<div class="sample"><img src="app-icon-${size}.png" width="${size}" height="${size}"><span>${size}px</span></div>`).join('')}</div>`);
    // Export a self-contained proof sheet in the same rendering session.
    const rows=frames.slice(0,-1).map((png,i)=>`<div style="display:grid;justify-items:center;gap:12px"><img width="${sizes[i]}" height="${sizes[i]}" src="data:image/png;base64,${png.toString('base64')}"><span>${sizes[i]}px</span></div>`).join('');
    await page.setViewportSize({width:1000,height:280});
    await page.setContent(`<body style="margin:0;padding:32px;background:#1c2024;color:#eef0f1;font:14px Segoe UI,sans-serif"><h2 style="margin:0 0 20px">AW · Windows icon sizes</h2><div style="display:flex;gap:28px;align-items:center">${rows}</div></body>`);
    await page.evaluate(()=>Promise.all([...document.images].map(img=>img.decode())));
    await page.screenshot({path:path.join(output,'icon-sizes.png')});
    console.log(JSON.stringify({sizes,bytes:offset,visibleText:false,asset:'frontend/assets/app-icon.ico'}));
  }finally{await browser.close();}
})();
