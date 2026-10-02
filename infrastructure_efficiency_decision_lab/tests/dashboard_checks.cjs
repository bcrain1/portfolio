// Offline interaction logic checks. Run after python lab.py.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../output/dashboard.html'),'utf8');
const data=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script=html.match(/<\/script><script>([\s\S]*?)<\/script>/)[1];
const elements={},listeners={};for(const id of ['data','scenario','service','price','priceLabel','cost','costdetail','pooled','standard','bars','rows','decision','quality','export'])elements[id]={value:'',textContent:'',innerHTML:'',addEventListener:(e,fn)=>listeners[id+':'+e]=fn};
elements.data.textContent=data;elements.scenario.value='optimized';elements.service.value='all';elements.price.value='10';
const context={document:{getElementById:id=>elements[id]},Intl,JSON,console};vm.createContext(context);vm.runInContext(script,context);
let checked=0;for(const scenario of ['optimized','mix_only'])for(const service of ['all','batch','interactive','streaming'])for(const price of ['5','10','20']){elements.scenario.value=scenario;elements.service.value=service;elements.price.value=price;listeners['price:input']();assert(!/NaN|undefined|Infinity/.test(elements.cost.textContent+elements.pooled.textContent+elements.standard.textContent+elements.rows.innerHTML));assert.equal((elements.rows.innerHTML.match(/<tr>/g)||[]).length,service==='all'?3:1);if(scenario==='mix_only')assert(elements.decision.textContent.startsWith('Hold.'));checked++;}
console.log(`${checked} scenario/service/price combinations passed`);
