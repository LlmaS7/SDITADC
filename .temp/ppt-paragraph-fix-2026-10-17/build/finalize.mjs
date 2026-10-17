import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
process.on('uncaughtException',error=>{console.error(error.message);console.error((error.stack||'').split('\n').filter(s=>s.includes('finalize.mjs')).join('\n'));process.exit(1);});
const workspaceDir=path.resolve(import.meta.dirname,'..');
const skill='C:/Users/25489/.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations';
const runtime='C:/Users/25489/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES=runtime+'/node/node_modules';
const {finalizePresentation}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs').href);
const candidatePath=path.join(workspaceDir,'build/paragraph-candidate.pptx');
const sourcePath=path.join(workspaceDir,'source/原稿.pptx');
const sha=async file=>crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
const finalPath=path.join(workspaceDir,'output',process.argv[2]||'奉行主权平等_课堂演讲_精排版_文本框修复.pptx');
const result=await finalizePresentation({
 workspaceDir,candidatePath,finalPath,
 pythonExecutable:runtime+'/python/python.exe',
 integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',
 layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--require-native-table-slide','9'],
 explicitTotalSlideCount:11,requiredNativeTableOwnerSlides:[9],requiredNativeChartOwnerSlides:[],
 fontPolicy:{basis:'reference',families:['Microsoft YaHei','STZhongsong','Georgia'],referencePath:sourcePath,referenceSha256:await sha(sourcePath)},
 verifyArtifactToolImport:true,
 receiptPath:path.join(workspaceDir,'build',path.basename(finalPath)+'.validation.json')
});
if(await sha(finalPath)!==await sha(candidatePath))throw Error('Final differs from the native-rendered draft');
console.log(JSON.stringify({file:result.finalPath,bytes:result.byteCount,sha256:await sha(finalPath)}));
