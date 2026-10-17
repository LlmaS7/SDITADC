const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=__dirname;
const server=http.createServer((req,res)=>{
  const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const target=path.resolve(root,'.'+(name==='/'?'/index.html':name));
  if(!target.startsWith(root+path.sep)||!fs.existsSync(target)||!fs.statSync(target).isFile()){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',({'.html':'text/html; charset=utf-8','.svg':'image/svg+xml','.png':'image/png'})[path.extname(target)]||'text/plain; charset=utf-8');
  res.setHeader('Cache-Control','no-store');fs.createReadStream(target).pipe(res);
});
server.listen(0,'127.0.0.1',()=>console.log('http://127.0.0.1:'+server.address().port));
setTimeout(()=>server.close(),20*60*1000).unref();
