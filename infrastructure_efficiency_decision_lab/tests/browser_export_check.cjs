// Optional real Chromium check, separate from the standard-library Python tests.
// Usage: node tests/browser_export_check.cjs <chrome executable> <QA output dir>
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
const {spawn}=require('child_process'),{pathToFileURL}=require('url');
const chrome=process.argv[2];if(!chrome)throw Error('Supply a Chromium executable');
const out=path.resolve(process.argv[3]||path.join(os.tmpdir(),'infra-export-qa-'+Date.now()));fs.mkdirSync(out,{recursive:true});
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'infra-browser-check-'));
const child=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let ws,id=0;const pending=new Map();
async function until(fn){for(let i=0;i<100;i++){const v=await fn();if(v)return v;await sleep(100)}throw Error('Timed out');}
async function send(method,params={},sessionId){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});}
(async()=>{try{
 const portFile=path.join(profile,'DevToolsActivePort');await until(()=>fs.existsSync(portFile));const [port,endpoint]=fs.readFileSync(portFile,'utf8').trim().split('\n');
 ws=new WebSocket('ws://127.0.0.1:'+port+endpoint);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:out});
 const {targetId}=await send('Target.createTarget',{url:pathToFileURL(path.resolve(__dirname,'../output/dashboard.html')).href});const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 await send('Page.enable',{},sessionId);await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1650,deviceScaleFactor:1,mobile:false},sessionId);
 await until(async()=>{const r=await send('Runtime.evaluate',{expression:"document.getElementById('cost')?.textContent",returnByValue:true},sessionId);return r.result?.value?.startsWith('$')});
 await send('Runtime.evaluate',{expression:"document.getElementById('export').click()"},sessionId);const csv=path.join(out,'modeled-comparison.csv');await until(()=>fs.existsSync(csv));
 const lines=fs.readFileSync(csv,'utf8').trim().split('\n'),parse=s=>JSON.parse('['+s+']'),headers=parse(lines[0]),rows=lines.slice(1).map(s=>Object.fromEntries(parse(s).map((v,i)=>[headers[i],v])));
 assert.equal(rows.length,3);for(const r of rows){assert.equal(r.synthetic,'true');assert.equal(r.accepted_hours,'165');assert.equal(r.input_hours,'168');assert.equal(r.excluded_hours,'3');assert(r.limitations.includes('no actual savings'));assert.equal(r.accepted_first_hour_utc,'2026-01-05T00:00:00+00:00');assert.equal(r.accepted_last_hour_utc_inclusive,'2026-01-11T23:00:00+00:00');}
 const interactive=rows.find(r=>r.service==='interactive');assert.equal(interactive.decision,'HOLD');assert.equal(interactive.latency_ok,'false');assert(interactive.hold_reasons.includes('latency_budget_breach'));assert.equal(rows.find(r=>r.service==='batch').decision,'CANDIDATE_FOR_CONTROLLED_TRIAL');
 await send('Runtime.evaluate',{expression:"document.getElementById('scenario').value='mix_only';document.getElementById('scenario').dispatchEvent(new Event('input'));document.getElementById('price').value='20';document.getElementById('price').dispatchEvent(new Event('input'));document.getElementById('export').click()"},sessionId);
 const second=csv;await until(()=>fs.readFileSync(second,'utf8').includes('\"mix_only\"'));const mix=fs.readFileSync(second,'utf8').trim().split('\n').slice(1).map(s=>Object.fromEntries(parse(s).map((v,i)=>[headers[i],v])));for(const r of mix){assert.equal(r.scenario,'mix_only');assert.equal(r.cpu_price_multiplier,'2');assert.equal(r.decision,'HOLD');assert(r.hold_reasons.includes('workload_mix_changed'));}
 console.log(JSON.stringify({status:'PASS',real_browser_downloads:2,rows_checked:6,qa_directory:out}));await send('Browser.close');
 }finally{if(ws)ws.close();child.kill();}})().catch(e=>{console.error(e);process.exitCode=1});
