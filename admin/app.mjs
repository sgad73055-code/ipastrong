import {RAW,REPO,findApps,imageURL,sourceLabel,appId,buildInputs,operationMatches} from './model.mjs';
import {GitHub} from './github.mjs?v=2';
const $=id=>document.getElementById(id),form=$('editForm'),api=new GitHub();
const state={apps:[],filtered:[],limit:48,selected:null,selectedId:'',imageData:'',dirty:false,busy:false,loading:false,pending:null,polling:false};
const pendingKey='ipastrong-manager-pending-v1';
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function editorNotice(text){$('editNotice').textContent=text;$('editNotice').hidden=!text;}
function toast(text){if($('editor').open)editorNotice(text);$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,7000)}
function savePending(value){state.pending=value;try{if(value)localStorage.setItem(pendingKey,JSON.stringify(value));else localStorage.removeItem(pendingKey)}catch{}}
function readPending(){try{const p=JSON.parse(localStorage.getItem(pendingKey)||'null');if(p&&/^[-a-z0-9]{10,60}$/i.test(p.requestId)&&Number.isFinite(p.createdAt)&&['edit','delete','add'].includes(p.action)&&(p.runId===null||Number.isSafeInteger(p.runId))&&!p.finished)return p}catch{}return null}
function setStatus(title,text,{kind='',runId=null,resume=false,dismiss=false}={}){$('pending').hidden=false;$('pending').className='status-box '+kind;$('pendingTitle').textContent=title;$('pendingText').textContent=text;$('resume').hidden=!resume;$('dismissPending').hidden=!dismiss;$('runLink').hidden=!runId;if(runId)$('runLink').href='https://github.com/'+REPO+'/actions/runs/'+runId}
function setConnected(){const connected=api.connected;$('connect').classList.toggle('connected',connected);$('connectionLabel').textContent=connected?'GitHub مربوط':'ربط GitHub';$('authSetup').hidden=connected;$('authConnected').hidden=!connected}
function openAuth(){setConnected();$('authError').hidden=true;$('auth').showModal()}
$('connect').onclick=openAuth;$('closeAuth').onclick=()=>$('auth').close();$('disconnect').onclick=()=>{api.disconnect();setConnected();toast('تم فصل GitHub من هذه الصفحة.')};
$('authForm').onsubmit=async e=>{e.preventDefault();$('authSubmit').disabled=true;$('authError').hidden=true;try{await api.connect($('token').value);$('token').value='';setConnected();$('auth').close();toast('تم الربط. صلاحية الكتابة تتأكد عند أول حفظ.');if(state.pending&&!state.polling)pollPending()}catch(err){$('authError').textContent=err.message;$('authError').hidden=false}finally{$('authSubmit').disabled=false}};
async function loadCatalog({quiet=false}={}){
 if(state.loading)return false;state.loading=true;$('refresh').disabled=true;
 if(!quiet&&!state.apps.length){$('grid').replaceChildren();for(let i=0;i<9;i++){const skeleton=document.createElement('div');skeleton.className='skeleton';$('grid').append(skeleton)}}
 try{
  const response=await fetch(RAW+'?t='+Date.now(),{cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(60000)});
  if(!response.ok)throw Error();const data=await response.json();
  if(!Array.isArray(data.apps)||!data.apps.length)throw Error();
  state.apps=data.apps.filter(a=>a&&typeof a==='object'&&typeof a.downloadURL==='string'&&typeof a.name==='string');
  $('total').textContent=state.apps.length.toLocaleString('ar-IQ');$('loadedAt').textContent='آخر جلب: '+new Date().toLocaleTimeString('ar-IQ',{hour:'2-digit',minute:'2-digit'});render();return true;
 }catch{
  if(state.apps.length){toast('تعذّر تحديث المكتبة؛ المعروض هو آخر نسخة جلبتها.');$('loadedAt').textContent='النسخة المعروضة قديمة — أعد التحديث'}else{$('grid').replaceChildren();$('results').textContent='تعذّر تحميل التطبيقات';$('empty').hidden=false;$('emptyTitle').textContent='المكتبة ما تحمّلت';$('emptyText').textContent='تحقق من اتصالك واضغط إعادة المحاولة.';$('retry').hidden=false}
  return false;
 }finally{state.loading=false;$('refresh').disabled=false}
}
function appImage(app){const img=document.createElement('img');img.src=imageURL(app.iconURL)||'../source-icon.jpeg';img.alt='';img.loading='lazy';img.referrerPolicy='no-referrer';img.onerror=()=>{const fallback=document.createElement('div');fallback.className='fallback';fallback.textContent=String(app.name||'S')[0];img.replaceWith(fallback)};return img}
function render(){
 state.filtered=findApps(state.apps,$('search').value);$('results').textContent=state.filtered.length.toLocaleString('ar-IQ')+' نتيجة';$('grid').replaceChildren();$('empty').hidden=state.filtered.length>0;$('emptyTitle').textContent='ماكو نتائج';$('emptyText').textContent='جرّب اسمًا ثانيًا أو جزءًا من الاسم.';$('retry').hidden=true;
 for(const app of state.filtered.slice(0,state.limit)){
  const card=document.createElement('button');card.className='card';card.type='button';const info=document.createElement('div');info.className='info';const name=document.createElement('div');name.className='app-name';name.textContent=app.name;const meta=document.createElement('div');meta.className='app-info';const version=document.createElement('span');version.className='version';version.textContent='v'+(app.version||'—');const source=document.createElement('span');source.className='source-label';source.textContent='· '+sourceLabel(app);meta.append(version,source);const edit=document.createElement('div');edit.className='edit-label';edit.textContent='تعديل التفاصيل ←';info.append(name,meta,edit);card.append(appImage(app),info);card.onclick=()=>openEditor(app);$('grid').append(card);
 }
 $('more').hidden=state.limit>=state.filtered.length;
}
$('search').oninput=()=>{state.limit=48;clearTimeout(render.timer);render.timer=setTimeout(render,100)};$('more').onclick=()=>{state.limit+=48;render()};$('refresh').onclick=()=>loadCatalog();$('retry').onclick=()=>loadCatalog();$('add').onclick=()=>openEditor(null);
async function openEditor(app){if(state.busy)return;editorNotice('');state.selected=app;state.selectedId='';state.imageData='';state.dirty=false;$('imageFile').value='';$('imageNote').textContent='تكدر تختار صورة من جهازك أو تلصق رابطها.';for(const [key,field] of [['name','name'],['description','localizedDescription'],['icon','iconURL'],['url','downloadURL']])form.elements[key].value=app?.[field]||'';$('modeLabel').textContent=app?'تعديل التطبيق':'إضافة جديدة';$('editTitle').textContent=app?.name||'تطبيق جديد';$('editMeta').textContent=app?'v'+app.version+' · '+app.bundleIdentifier:'نقرأ الإصدار ومعرّف الحزمة تلقائيًا من ملف IPA.';$('sourceInfo').hidden=!app;$('sourceInfo').textContent=app?'المصدر: '+sourceLabel(app)+' · '+app.downloadURL:'';$('editIcon').src=imageURL(app?.iconURL)||'../source-icon.jpeg';$('delete').hidden=!app;$('urlOptional').textContent=app?'اختياري للتبديل':'مطلوب';form.elements.url.required=!app;$('save').textContent=app?'حفظ على GitHub ←':'إضافة إلى السورس ←';$('save').disabled=false;$('editor').showModal();if(app){try{const id=await appId(app);if(state.selected===app)state.selectedId=id}catch{editorNotice('تعذّر تحديد التطبيق. أغلق النافذة وحدّث المكتبة ثم جرّب مجددًا.');}}}
function closeEditor(){if(state.dirty&&!confirm('تطلع بدون حفظ التعديلات؟'))return;$('editor').close();state.dirty=false} $('closeEditor').onclick=closeEditor;$('editor').addEventListener('cancel',e=>{e.preventDefault();closeEditor()});form.oninput=()=>state.dirty=true;
form.elements.icon.oninput=()=>{state.dirty=true;state.imageData='';$('imageFile').value='';$('imageNote').textContent='راح تُستخدم الصورة من هذا الرابط.';$('editIcon').src=imageURL(form.elements.icon.value)||'../source-icon.jpeg'};
$('editIcon').onerror=()=>{$('editIcon').onerror=null;$('editIcon').src='../source-icon.jpeg'};
$('imageFile').onchange=async e=>{
 const file=e.target.files[0];if(!file)return;if(!file.type.startsWith('image/')||file.size>20*1024*1024){toast('اختار صورة بحجم أقل من 20 ميغابايت.');return}
 $('save').disabled=true;
 try{
  const blobURL=URL.createObjectURL(file),image=new Image();try{await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;image.src=blobURL})}finally{URL.revokeObjectURL(blobURL)}
  const canvas=document.createElement('canvas');let data;
  for(const size of [256,192,128]){canvas.width=size;canvas.height=size;const ctx=canvas.getContext('2d');ctx.fillStyle='#ffffff';ctx.fillRect(0,0,size,size);const scale=Math.min(size/image.naturalWidth,size/image.naturalHeight),w=image.naturalWidth*scale,h=image.naturalHeight*scale;ctx.drawImage(image,(size-w)/2,(size-h)/2,w,h);data=canvas.toDataURL('image/jpeg',0.78);if(data.length<43000)break}
  if(data.length>=43000)throw Error();state.imageData=data;state.dirty=true;$('editIcon').src=data;form.elements.icon.value='';$('imageNote').textContent='✓ تم اختيار الصورة. تُنشر ضمن سورسك العام عند الحفظ.';
 }catch{toast('ما قدرت أقرأ الصورة. جرّب JPEG أو PNG.')}finally{$('save').disabled=false}
};
form.addEventListener('invalid',e=>{editorNotice('راجع حقل '+(e.target.name==='icon'?'رابط الصورة':e.target.name==='url'?'رابط تحميل IPA':'اسم التطبيق')+': '+e.target.validationMessage);},true);
function values(){return {name:form.elements.name.value,description:form.elements.description.value,icon:state.imageData||form.elements.icon.value,url:form.elements.url.value}}
function ensureWriteReady(){if(state.pending){toast('عندك عملية سابقة. أغلق نافذة التعديل واضغط متابعة الحالة أعلى المكتبة قبل إرسال تعديل جديد.');return false}if(!api.connected){openAuth();return false}return true}
form.onsubmit=async e=>{e.preventDefault();if(state.busy||!ensureWriteReady())return;editorNotice('جارٍ تجهيز التعديل…');try{const input=buildInputs({original:state.selected,values:values(),action:state.selected?'edit':'add',target:state.selectedId,requestId:crypto.randomUUID()});await sendOperation(input,state.selected,values())}catch(err){toast(err.message)}};
$('delete').onclick=()=>{if(!ensureWriteReady())return;$('deleteName').textContent=state.selected?.name||'';$('confirmDelete').showModal()};$('cancelDelete').onclick=$('cancelDeleteTop').onclick=()=>$('confirmDelete').close();$('confirmDeleteButton').onclick=async()=>{if(state.busy)return;try{const inputs=buildInputs({action:'delete',target:state.selectedId,requestId:crypto.randomUUID()});$('confirmDelete').close();await sendOperation(inputs,state.selected,null)}catch(err){toast(err.message)}};
async function sendOperation(inputs,original,expected){
 if(state.busy||state.pending)return;state.busy=true;$('save').disabled=true;editorNotice('جارٍ إرسال التعديل إلى GitHub…');
 const pending={requestId:inputs.request_id,runId:null,createdAt:Date.now(),action:inputs.action};savePending(pending);
 setStatus('جارٍ إرسال التعديل…','انتظر؛ ما نعتبر العملية محفوظة إلا بعد تأكيد GitHub.');
 try{
  const result=await api.dispatch(inputs);const id=Number(result?.workflow_run_id||result?.id);if(Number.isSafeInteger(id)&&id>0){pending.runId=id;savePending(pending)}
  state.dirty=false;$('editor').close();await pollPending({original,expected});
 }catch(err){
  if(err.status>=400&&err.status<500){savePending(null);setStatus('ما انحفظ التعديل',err.message,{kind:'error',dismiss:true})}
  else{state.dirty=false;$('editor').close();setStatus('نحتاج نتأكد من حالة الطلب',err.message+' ما راح نعيد إرساله تلقائيًا.',{resume:true})}
  toast(err.message);
 }finally{state.busy=false;$('save').disabled=false}
}
async function pollPending({original=null,expected=null}={}){
 if(!state.pending||state.polling)return;if(!api.connected){openAuth();return}state.polling=true;$('resume').disabled=true;
 const started=Date.now();
 try{
  while(state.pending&&Date.now()-started<30*60*1000){
   const current=state.pending,run=await api.locate(current);
   if(!run){setStatus('بانتظار تأكيد GitHub…','الطلب بعده ما ظهر بقائمة التشغيل. ما ترسله مرة ثانية.');await wait(5000);continue}
   if(!current.runId){current.runId=run.id;savePending(current)}
   if(run.status!=='completed'){setStatus(run.status==='in_progress'?'جارٍ فحص وحفظ التعديل…':'التعديل بانتظار دوره…','قد يأخذ دقيقة أو أكثر. تقدر تبقي الصفحة مفتوحة؛ إذا طلعت، اضغط متابعة الحالة من ترجع.',{runId:run.id});await wait(5000);continue}
   if(run.conclusion!=='success'){savePending(null);setStatus('العملية ما اكتملت','GitHub أعاد: '+String(run.conclusion)+'. افتح تفاصيل العملية لمعرفة السبب؛ لم نعد إرسالها.',{kind:'error',runId:run.id,dismiss:true});return}
   savePending(null);setStatus('تم الحفظ على GitHub ✓',current.action==='delete'?'تم حذف التطبيق من السورس.':'تم حفظ التغيير بالسورس. حدّث المصدر بتطبيق التوقيع حتى يظهر عندك.',{kind:'success',runId:run.id,dismiss:true});
   const loaded=await loadCatalog({quiet:true});if(!loaded||(expected&&original&&!operationMatches(state.apps,original,expected,current.action))){$('loadedAt').textContent='الحفظ نجح؛ اضغط تحديث إذا بعدك تشوف البيانات القديمة.'}
   toast('تم الحفظ على GitHub ✓');return;
  }
  setStatus('العملية أخذت وقتًا أطول','تابع حالتها من الرابط أو اضغط متابعة الحالة. ما راح نرسل طلب ثاني.',{runId:state.pending?.runId,resume:true});
 }catch(err){setStatus('توقفت متابعة الحالة',err.message+' تقدر تتابع نفس الطلب بدون إعادة إرساله.',{runId:state.pending?.runId,resume:true});}
 finally{state.polling=false;$('resume').disabled=false}
}
$('resume').onclick=()=>pollPending();$('dismissPending').onclick=()=>{if(!state.pending)$('pending').hidden=true};
window.addEventListener('beforeunload',e=>{if(state.dirty||state.busy){e.preventDefault();e.returnValue=''}});
state.pending=readPending();if(state.pending)setStatus('عندك عملية سابقة','اربط GitHub واضغط متابعة الحالة حتى نعرف نتيجتها.',{runId:state.pending.runId,resume:true});
setConnected();loadCatalog();
