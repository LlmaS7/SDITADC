async (page)=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1280,height:1100});
  await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode())));
  const detail=await page.locator('.detail').boundingBox();
  await page.screenshot({path:'comparison.png',clip:{x:0,y:0,width:1280,height:Math.ceil(detail.y-16)}});
  const gaps=await page.locator('#comparisons .head').evaluateAll(headers=>headers.map(h=>({brand:h.querySelector('.brand').getBoundingClientRect().right,stats:h.querySelector('.stats').getBoundingClientRect().left})));
  if(gaps.some(g=>g.brand+12>g.stats))throw Error('Header overlaps');
  for(const id of ['a','b','c','d']){
    await page.locator(`[data-option="${id}"]`).click();
    const frame=page.frameLocator('iframe');
    await frame.locator(`.brand.${id}`).waitFor();
    await frame.locator('img').evaluate(i=>i.decode());
    await page.locator('.full').screenshot({path:`context-${id}.png`});
    await page.locator(`#comparisons .brand.${id}`).screenshot({path:`brand-${id}.png`});
  }
  if(errors.length)throw Error(errors.join('; '));
  return {options:4,comparison:'comparison.png',context:['context-a.png','context-b.png','context-c.png','context-d.png'],errors};
}
