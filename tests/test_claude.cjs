const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/claude.js'),'utf8');
async function scenario(withImage, mime='image/png', draft='', nativeInsert=true) {
 let handler,sent=false,uploaded=false,received=[],inserted='';
 const label=s=>({getClientRects:()=>[{}],getAttribute:n=>n==='aria-label'?s:null,textContent:'',disabled:false});
 const copy=label('Copy');
 const reply={parentElement:null,getAttribute:()=>null,closest:()=>null,querySelector:()=>null,querySelectorAll:s=>s==='button'?[copy]:[],cloneNode:()=>({textContent:'Чотири.',querySelectorAll:()=>[]})};
 const form={textContent:'',querySelectorAll:()=>[]};
 const editor={...label(''),tagName:'DIV',innerText:draft,focus(){},closest:()=>form,replaceChildren(p){this.innerText=p.textContent;inserted=p.textContent},dispatchEvent(){}};
 const send={...label('Send message'),click(){sent=true}};
 const file={accept:'image/*',dispatchEvent(){uploaded=true;received=this.files;form.textContent=received.map(f=>f.name).join(' ')}};
 const doc={body:form,documentElement:{},getSelection:()=>({removeAllRanges(){},addRange(){}}),createRange:()=>({selectNodeContents(){},collapse(){}}),createElement:()=>({textContent:''}),execCommand(command,_,text){assert.equal(command,'insertText');if(!nativeInsert)return false;editor.innerText=text;inserted=text;return true},querySelector(selector){if(selector==='[data-testid="send-button"]')return send;return null},querySelectorAll(selector){
  if(selector.includes('[contenteditable'))return [editor];
  if(selector.includes('[data-is-streaming]'))return sent?[reply]:[];
  if(selector==='input[type="file"]')return [file];
  if(selector==='button,[role="button"]')return [send];
  return [];
 }};
 const ctx={window:{},document:doc,location:{origin:'https://claude.ai',pathname:'/chat/test'},getComputedStyle:()=>({visibility:'visible'}),atob:s=>Buffer.from(s,'base64').toString('binary'),Uint8Array,File:class{constructor(bytes,name,opts){this.name=name;this.type=opts.type}},DataTransfer:class{constructor(){this.files=[];this.items={add:f=>this.files.push(f)}}},Event:class{},InputEvent:class{},Date,setTimeout,clearTimeout,browser:{runtime:{sendMessage:()=>Promise.resolve(),onMessage:{addListener(f){handler=f}}}}};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 const result=await handler({type:'solve',id:'test',url:'https://claude.ai/chat/test',text:'Скільки буде два плюс два?',files:withImage?[{name:'MeetVoice-test.png',mime,data:'cG5n'}]:[]});
 if(mime==='audio/wav'||draft) {assert.ok(result.error);assert.equal(sent,false);return;}
 assert.equal(result.text,'Чотири.');assert.equal(sent,true);assert.equal(inserted,'Скільки буде два плюс два?');
 assert.equal(uploaded,withImage);assert.equal(received.length,withImage?1:0);
}
(async()=>{await scenario(false);await scenario(true);await scenario(false,'image/png','',false);await scenario(true,'audio/wav');await scenario(false,'image/png','My draft');console.log('PASS: Claude transcript, transcript+PNG, WAV rejection, draft protection')})().catch(e=>{console.error(e);process.exitCode=1});
