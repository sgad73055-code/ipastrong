import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {appId,identityText,findApps,buildInputs,operationMatches,imageURL,sourceLabel,REPO_API} from './model.mjs';
import {GitHub} from './github.mjs';
const app={name:'بيكرام — تجربة',bundleIdentifier:'com.test',_sourceURL:'https://example.org/feed',version:'1',downloadURL:'https://example.org/a.ipa',iconURL:'https://example.org/a.png',localizedDescription:'الوصف'};
const vals={name:app.name,description:app.localizedDescription,icon:app.iconURL,url:app.downloadURL};
const args={original:app,values:vals,action:'edit',requestId:'request-fixture-123',target:'123456789abcdef0'};
test('IDs exactly match Python with Arabic and distinguish shared URLs',async()=>{
 const expected=execFileSync('python3',['-c','import json,hashlib,sys;a=json.loads(sys.argv[1]);s=json.dumps([str(a.get(k,"")) for k in ("downloadURL","bundleIdentifier","name","_sourceURL")],ensure_ascii=False);print(hashlib.sha256(s.encode()).hexdigest()[:16])',JSON.stringify(app)],{encoding:'utf8'}).trim();
 assert.equal(await appId(app),expected);assert.notEqual(await appId(app),await appId({...app,name:'Another'}));assert.match(identityText(app),/, /);
});
test('search is case-insensitive and includes version and source channel',()=>{
 const a={...app,name:'Beegram',downloadURL:'https://fastsign.dev/tg-ipa/ipa-dark/app.ipa',_sourceURL:'local'};
 assert.equal(findApps([a],'beE').length,1);assert.equal(findApps([a],'IPA-DARK').length,1);assert.equal(findApps([a],'1').length,1);assert.equal(sourceLabel({...a,_sourceURL:''}),'ipa-dark');assert.equal(findApps([a],'none').length,0);
});
test('edit sends only changed fields and allows clearing description and icon',()=>{
 const i=buildInputs({...args,values:{...vals,name:'New'}});assert.equal(i.name,'New');assert.equal(i.description,undefined);assert.equal(i.url,undefined);assert.equal(i.icon,undefined);
 const clear=buildInputs({...args,values:{...vals,description:'',icon:''}});assert.equal(clear.clear_description,true);assert.equal(clear.clear_icon,true);
 assert.throws(()=>buildInputs(args),/ما تغيّر/);
});
test('delete targets the exact selected ID; add needs an HTTPS IPA URL',()=>{
 assert.deepEqual(buildInputs({action:'delete',target:'abc',requestId:'req'}),{action:'delete',target:'abc',request_id:'req',dry_run:false});
 assert.throws(()=>buildInputs({action:'delete',requestId:'req'}));
 assert.throws(()=>buildInputs({action:'add',values:{...vals,url:''},requestId:'req'}));
 assert.throws(()=>buildInputs({action:'add',values:{...vals,url:'javascript:alert(1)'},requestId:'req'}));
 assert.throws(()=>buildInputs({action:'add',values:{...vals,url:'https://user:secret@example.org/a.ipa'},requestId:'req'}));
});
test('oversized input is blocked before dispatch',()=>{assert.throws(()=>buildInputs({...args,values:{...vals,description:'ع'.repeat(50000)}}),/طويلة/)});
test('image preview accepts HTTPS only and final state comparison is exact',()=>{
 assert.equal(imageURL('javascript:alert(1)'),'');assert.equal(imageURL('http://example.org/a.png'),'');assert.equal(operationMatches([app],app,vals,'edit'),true);assert.equal(operationMatches([app],app,{...vals,name:'New'},'edit'),false);assert.equal(operationMatches([app],app,null,'delete'),false);assert.equal(operationMatches([],app,null,'delete'),true);
});
const response=(status,data)=>({status,ok:status>=200&&status<300,json:async()=>data});
test('connect is read-only, secret sent only in auth header to fixed GitHub origin',async()=>{
 const calls=[],api=new GitHub(async(url,options)=>{calls.push({url,options});return response(200,{state:'active'})});
 await api.connect('github_pat_fixture');assert.equal(calls.length,1);assert.equal(calls[0].options.method,'GET');assert.equal(calls[0].url,REPO_API+'/actions/workflows/manage-apps.yml');assert.equal(calls[0].options.headers.Authorization,'Bearer github_pat_fixture');assert.equal(calls[0].options.body,undefined);assert(!JSON.stringify(api).includes('fixture'));api.disconnect();assert.equal(api.connected,false);await assert.rejects(()=>api.dispatch({action:'edit'}));
});
test('dispatch supports the documented run-id response and legacy 204',async()=>{
 for(const status of [200,204]){const calls=[],api=new GitHub(async(url,options)=>{calls.push({url,options});return options.method==='GET'?response(200,{state:'active'}):response(status,{workflow_run_id:123})});await api.connect('github_pat_fixture');const result=await api.dispatch({action:'edit',request_id:'req'});assert.equal(calls[1].options.method,'POST');assert.equal(JSON.parse(calls[1].options.body).ref,'main');assert.equal(calls[1].options.headers.Authorization,'Bearer github_pat_fixture');assert.equal(status===204?result:result.workflow_run_id,status===204?null:123)}
});
test('unknown dispatch completion is not retried; unauthorized paths rejected',async()=>{
 let count=0;const api=new GitHub(async(_,o)=>{if(o.method==='GET')return response(200,{state:'active'});count++;throw Error('offline')});await api.connect('github_pat_fixture');await assert.rejects(()=>api.dispatch({action:'edit'}),/قد يكون الطلب وصل/);assert.equal(count,1);await assert.rejects(()=>api.request('https://other.test'));await assert.rejects(()=>api.request('/contents/ipastrong.json',{method:'PUT'}));
});
test('legacy polling selects the exact request, never another user run',async()=>{
 const api=new GitHub(async(url)=>url.endsWith('manage-apps.yml')?response(200,{state:'active'}):response(200,{workflow_runs:[{id:1,display_title:'Catalog · another'},{id:2,display_title:'Catalog · req'}]}));await api.connect('github_pat_fixture');assert.equal((await api.locate({runId:null,requestId:'req',createdAt:Date.now()})).id,2);
});
test('credential is never persisted; no third-party executable scripts',()=>{
 const js=readFileSync(new URL('./app.mjs',import.meta.url),'utf8'),html=readFileSync(new URL('./index.html',import.meta.url),'utf8');assert(!/localStorage\.setItem\([^\n]*(?:token|credential)/.test(js));assert(!html.includes('script src="https:'));assert(html.includes("script-src 'self'"));assert(html.includes('type="password"'));
});
