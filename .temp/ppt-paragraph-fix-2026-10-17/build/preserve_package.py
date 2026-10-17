"""Apply only authored paragraph replacements to the original OPC package."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
NS={'p':P,'a':A}
ET.register_namespace('p',P);ET.register_namespace('a',A)
ET.register_namespace('r','http://schemas.openxmlformats.org/officeDocument/2006/relationships')
plan=json.loads((ROOT/'build/merge-plan.json').read_text(encoding='utf-8'))
ink_file=ROOT/'build/ink-measurements.json'
offsets={(g['slide'],g['name']):g['delta'][0] for g in json.loads(ink_file.read_text(encoding='utf-8'))} if ink_file.exists() else {}
src=ROOT/'source/原稿.pptx';candidate=ROOT/'build/artifact-candidate.pptx'
out=ROOT/'build/paragraph-candidate.pptx'
changes={}
with zipfile.ZipFile(src) as source,zipfile.ZipFile(candidate) as authored:
    for slide in sorted({g['slide'] for g in plan}):
        part=f'ppt/slides/slide{slide}.xml'
        source_xml=source.read(part).decode('utf-8')
        source_doc=ET.fromstring(source_xml);target_doc=ET.fromstring(authored.read(part))
        original_shapes={s.find('p:nvSpPr/p:cNvPr',NS).get('name'):s for s in source_doc.findall('p:cSld/p:spTree/p:sp',NS)}
        authored_shapes={s.find('p:nvSpPr/p:cNvPr',NS).get('name'):s for s in target_doc.findall('p:cSld/p:spTree/p:sp',NS)}
        for group in [g for g in plan if g['slide']==slide]:
            originals=[original_shapes[r['name']] for r in group['originals']]
            replacement=deepcopy(authored_shapes[group['name']])
            # Preserve source shape identity, complete geometry/style and original
            # character runs. The only geometry change is the united frame height.
            for tag in ['nvSpPr','spPr','style']:
                old=replacement.find('p:'+tag,NS)
                if old is not None:replacement.remove(old)
            replacement.insert(0,deepcopy(originals[0].find('p:nvSpPr',NS)))
            geometry=deepcopy(originals[0].find('p:spPr',NS))
            leading=offsets.get((slide,group['originals'][0]['name']),0)
            geometry.find('a:xfrm/a:off',NS).set('y',str(round((group['box']['y']-leading)*9525)))
            geometry.find('a:xfrm/a:ext',NS).set('cy',str(round((group['box']['cy']+leading)*9525)))
            replacement.insert(1,geometry)
            style=originals[0].find('p:style',NS)
            if style is not None:replacement.insert(2,deepcopy(style))
            tx=deepcopy(originals[0].find('p:txBody',NS))
            tx.find('a:bodyPr',NS).set('wrap','square')
            for old in tx.findall('a:p',NS):tx.remove(old)
            paragraph=ET.SubElement(tx,'{'+A+'}p')
            ppr=deepcopy(originals[0].find('p:txBody/a:p/a:pPr',NS))
            if ppr is None:ppr=ET.Element('{'+A+'}pPr')
            for tag in ['lnSpc','spcBef','spcAft']:
                child=ppr.find('a:'+tag,NS)
                if child is not None:ppr.remove(child)
            spacing=ET.Element('{'+A+'}lnSpc')
            ET.SubElement(spacing,'{'+A+'}spcPts',{'val':str(round(group['pitch']*75))})
            ppr.insert(0,spacing)
            paragraph.append(ppr)
            for i,old in enumerate(originals):
                old_p=old.find('p:txBody/a:p',NS)
                if i:
                    br=ET.SubElement(paragraph,'{'+A+'}br')
                    rpr=old_p.find('a:r/a:rPr',NS)
                    if rpr is not None:br.append(deepcopy(rpr))
                for child in old_p:
                    if child.tag in ['{'+A+'}r','{'+A+'}fld']:paragraph.append(deepcopy(child))
            end=originals[-1].find('p:txBody/a:p/a:endParaRPr',NS)
            if end is not None:paragraph.append(deepcopy(end))
            old_tx=replacement.find('p:txBody',NS)
            if old_tx is not None:replacement.remove(old_tx)
            replacement.append(tx)
            # Replace only the targeted <p:sp> strings; every other source byte
            # (including unchanged shapes inside edited slides) remains intact.
            for i,old in enumerate(originals):
                nv=old.find('p:nvSpPr/p:cNvPr',NS);shape_name=nv.get('name')
                matched=[m for m in re.finditer(r'<p:sp\b[\s\S]*?</p:sp>',source_xml) if re.search(r'\bname="'+re.escape(shape_name)+r'"',m.group())]
                if len(matched)!=1:raise RuntimeError('Ambiguous source shape: '+shape_name)
                text=ET.tostring(replacement,encoding='unicode') if i==0 else ''
                m=matched[0];source_xml=source_xml[:m.start()]+text+source_xml[m.end():]
            text=lambda element:''.join(t.text or '' for t in element.findall('.//a:t',NS))
            assert text(replacement)==''.join(text(s) for s in originals)
            assert len(tx.findall('a:p',NS))==1
            assert len(paragraph.findall('a:br',NS))==len(originals)-1
        ET.fromstring(source_xml)
        changes[part]=source_xml.encode('utf-8')
    with zipfile.ZipFile(out,'w') as final:
        for item in source.infolist():final.writestr(item,changes.get(item.filename,source.read(item.filename)))
with zipfile.ZipFile(src) as before,zipfile.ZipFile(out) as after:
    assert before.namelist()==after.namelist()
    changed=[n for n in before.namelist() if before.read(n)!=after.read(n)]
    assert sorted(changed)==sorted(changes)
report={'paragraphs':len(plan),'originalLineTextboxes':sum(len(g['originals']) for g in plan),
        'removedTextboxes':sum(len(g['originals'])-1 for g in plan),'changedParts':changed,
        'unchangedParts':len(before.namelist())-len(changed),'originalSha256':hashlib.sha256(src.read_bytes()).hexdigest()}
(ROOT/'build/structural-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
