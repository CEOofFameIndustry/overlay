const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/content.js'),'utf8');
async function scenario(count) {
 let handler,uploaded=false,sent=false,filesReceived=[];
 const rect=()=>[{}];
 const reply={querySelector(){return null},cloneNode(){return {querySelectorAll(){return []},textContent:'Відповідь.'}},querySelectorAll(){return [{getAttribute(n){return n==='aria-label'?'Copy':null},innerText:''}]}};
 const editor={innerText:'',getClientRects:rect,closest(){return null},contains(){return false}};
 const send={getClientRects:rect,getAttribute(n){return n==='aria-label'?'Send message':null},innerText:'',click(){sent=true},disabled:false};
 const closes=Array.from({length:count},(_,i)=>({getClientRects:rect,getAttribute(n){return n==='aria-label'?'close MeetVoice-...'+i:null},innerText:'',click(){}}));
 const input={accept:'*',multiple:true,dispatchEvent(){uploaded=true;filesReceived=this.files},matches(){return true}};
 const doc={documentElement:{},body:{innerText:'WAV\nMeetVoice-...truncated'},images:[],querySelectorAll(selector){
  if(selector.includes('[contenteditable'))return [editor];
  if(selector==='model-response')return sent?[{},reply]:[{}];
  if(selector==='input[type="file"]')return [input];
  if(selector==='button,[role=button]' || selector==='button,[role="button"]')return [send,...uploaded?closes:[]];
  if(selector==="[aria-label],[title]")return uploaded?closes:[];
  return [];
 }};
 const ctx={window:{},document:doc,location:{origin:'https://gemini.google.com',pathname:'/app/test'},getComputedStyle(){return {visibility:'visible'}},atob:s=>Buffer.from(s,'base64').toString('binary'),Uint8Array,File:class{constructor(bytes,name,opts){this.name=name;this.type=opts.type}},DataTransfer:class{constructor(){this.files=[];this.items={add:f=>this.files.push(f)}}},Event:class{},Date,setTimeout,clearTimeout,browser:{runtime:{sendMessage(){return Promise.resolve()},onMessage:{addListener(f){handler=f}}}}};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 const files=[{name:'MeetVoice-test.wav',mime:'audio/wav',data:'d2F2'}];if(count===2)files.push({name:'MeetVoice-test.png',mime:'image/png',data:'cG5n'});
 const result=await handler({type:'solve',id:'test',url:'https://gemini.google.com/app/test',files});
 assert.equal(result.text,'Відповідь.');assert.equal(sent,true);assert.equal(filesReceived.length,count);
 assert.equal(filesReceived[0].type,'audio/wav');
}
(async()=>{await scenario(1);await scenario(2);console.log('PASS: audio and audio+screenshot upload, truncated-name close-button confirmation, final answer')})().catch(e=>{console.error(e);process.exitCode=1});
