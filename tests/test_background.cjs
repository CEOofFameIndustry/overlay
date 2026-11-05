const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/background.js'),'utf8');
async function scenario(url, text, files, mismatched=false) {
 let nativeHandler,listener,selectedAdapter,request;
 const sent=[];
 const port={postMessage:m=>sent.push(m),onMessage:{addListener:f=>nativeHandler=f},onDisconnect:{addListener(){}}};
 const ctx={URL,TextDecoder,Uint8Array,atob:s=>Buffer.from(s,'base64').toString('binary'),fetch:async file=>({ok:true,text:async()=>{selectedAdapter=file;return '// adapter'}}),browser:{runtime:{getURL:f=>f,connectNative:()=>port,onMessage:{addListener:f=>listener=f}},storage:{local:{get:async()=>({target:url}),set:async()=>{}}},tabs:{query:async()=>[{id:42,url}],executeScript:async()=>{},sendMessage:async(id,data)=>{request=data;return {text:'Отримано'}}}}};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 await new Promise(setImmediate);
 assert.equal((await listener({action:'status'})).target,url);
 const payload=Buffer.from(JSON.stringify({target:mismatched?'https://claude.ai/chat/different':url,text,files})).toString('base64');
 nativeHandler({type:'image-start',id:'test'});nativeHandler({type:'image-chunk',id:'test',data:payload});nativeHandler({type:'image-end',id:'test'});
 await new Promise(setImmediate);
 if(mismatched){assert.equal(request,undefined);assert.ok(sent.some(m=>m.type==='error'));return;}
 assert.equal(request.text,text);assert.equal(request.files.length,files.length);
 assert.equal(selectedAdapter,url.includes('claude.ai')?'claude.js':'content.js');
 assert.ok(sent.some(m=>m.type==='answer'&&m.text==='Отримано'));
}
(async()=>{await scenario('https://claude.ai/chat/test','Українська: ґ ї є і',[]);await scenario('https://gemini.google.com/u/1/app/test','',[{mime:'audio/wav',data:'d2F2'}]);await scenario('https://claude.ai/chat/test','Питання',[],true);console.log('PASS: provider routing, UTF-8 transcript, Gemini WAV, destination change rejection')})().catch(e=>{console.error(e);process.exitCode=1});
