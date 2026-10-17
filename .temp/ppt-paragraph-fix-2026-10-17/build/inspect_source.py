from pathlib import Path
import json, zipfile, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
records=[]
with zipfile.ZipFile(ROOT/'source/原稿.pptx') as z:
    for n in range(1,12):
        doc=ET.fromstring(z.read(f'ppt/slides/slide{n}.xml'))
        for sp in doc.findall('p:cSld/p:spTree/p:sp',NS):
            tx=sp.find('p:txBody',NS)
            if tx is None: continue
            text=''.join(tx.itertext())
            text=''.join(t.text or '' for t in tx.findall('.//a:t',NS))
            if not text:continue
            nv=sp.find('p:nvSpPr/p:cNvPr',NS)
            xfrm=sp.find('p:spPr/a:xfrm',NS)
            off=xfrm.find('a:off',NS);ext=xfrm.find('a:ext',NS)
            run=tx.find('.//a:rPr',NS)
            body=tx.find('a:bodyPr',NS)
            ppr=tx.find('.//a:pPr',NS)
            records.append({'slide':n,'id':nv.get('id'),'name':nv.get('name'),'text':text,
              'box':{k:round(int(v)/9525,3) for k,v in {**off.attrib,**ext.attrib}.items()},
              'rPr':ET.tostring(run,encoding='unicode') if run is not None else None,
              'bodyPr':dict(body.attrib),'pPr':ET.tostring(ppr,encoding='unicode') if ppr is not None else None})
(ROOT/'build/source-shapes.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
for n in range(1,12):
    print('SLIDE',n)
    for r in records:
        if r['slide']==n:
            print(r['id'],r['name'],list(r['box'].values()),r['text'])
print('Sample formatting:',json.dumps(next(r for r in records if r['slide']==2 and r['box']['y']==475),ensure_ascii=False))
