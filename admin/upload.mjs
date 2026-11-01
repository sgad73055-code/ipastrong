import {checkFile,remoteFilename,uploadURL,uploadFile,probePublic,isPackageURL,progressState} from './gitlab-upload.mjs?v=2';
const $=id=>document.getElementById(id);let file=null,busy=false,request=null,target=null,wake=null,stallTimer=null,lastProgress=0,lastBytes=0;
const key='ipastrong-gitlab-upload-target-v1';
function remember(){try{sessionStorage.setItem(key,JSON.stringify({url:target}))}catch{}}
function error(text){$('uploadError').textContent=text;$('uploadError').hidden=false}
function controls(disabled){$('uploadButton').disabled=disabled;$('ipaFile').disabled=disabled;$('remoteName').disabled=disabled;$('deployToken').disabled=disabled}
$('ipaFile').onchange=()=>{if(busy)return;file=$('ipaFile').files[0]||null;$('fileInfo').hidden=!file;if(file){$('fileInfo').textContent=file.name+' · '+(file.size/1024**3).toFixed(2)+' GiB';$('remoteName').value=remoteFilename(file.name)}};
function showResult(title,text){$('resultSection').hidden=false;$('resultTitle').textContent=title;$('resultText').textContent=text;$('downloadURL').value=target||'';$('copyLink').disabled=true}
async function verify(){if(!target)return;$('verifyLink').disabled=true;$('copyLink').disabled=true;$('visibilityHelp').hidden=true;try{const result=await probePublic(target);$('resultText').textContent=result.reason;$('resultSection').classList.toggle('success',result.ready);$('resultTitle').textContent=result.ready?'الرابط المباشر جاهز ✓':'الملف يحتاج فحص الوصول';$('copyLink').disabled=!result.ready;$('visibilityHelp').hidden=result.ready||result.network}catch{error('تعذّر فحص الرابط. حاول مجددًا.')}finally{$('verifyLink').disabled=false}}
$('uploadForm').onsubmit=async e=>{
 e.preventDefault();if(busy)return;$('uploadError').hidden=true;
 const token=$('deployToken').value.trim();if(!token){error('الصق رمز Deploy token أولًا.');return}
 busy=true;controls(true);$('resultSection').hidden=true;$('progressSection').hidden=true;
 try{
  await checkFile(file);
  target=uploadURL($('remoteName').value.trim(),new Date().toISOString().replace(/[^0-9]/g,'').slice(0,14)+'-'+crypto.randomUUID().slice(0,8));remember();
  $('progressSection').hidden=false;$('progress').value=0;$('progressTitle').textContent='جارٍ الرفع إلى GitLab…';$('progressText').textContent='بدء الاتصال…';$('cancelUpload').hidden=false;
  try{wake=await navigator.wakeLock?.request('screen')}catch{}
  lastProgress=Date.now();lastBytes=0;
  stallTimer=setInterval(()=>{if(busy&&Date.now()-lastProgress>=90000){$('progressTitle').textContent='ما وصل تقدّم جديد من المتصفح…';$('progressText').textContent='التقدّم متوقف منذ '+Math.floor((Date.now()-lastProgress)/60000)+' دقيقة. استلام الملف غير مؤكد؛ لا تعيد الرفع تلقائيًا.'}},15000);
  request=uploadFile({file,url:target,token,onProgress:(loaded,total)=>{if(loaded>lastBytes){lastProgress=Date.now();lastBytes=loaded}const progress=progressState(loaded,total);$('progress').value=progress.percent;$('progressTitle').textContent=progress.title;$('progressText').textContent=progress.percent.toFixed(1)+'% · '+(progress.sent/1024**3).toFixed(2)+' / '+(progress.total/1024**3).toFixed(2)+' GiB'}});
  await request.promise;$('progressTitle').textContent='GitLab أكد استلام الملف ✓';$('progress').value=100;$('progressText').textContent='١٠٠٪ — GitLab أكد استلام الملف.';$('deployToken').value='';showResult('تم رفع الملف؛ نفحص الرابط…','نختبر التنزيل بدون رمز، حتى يشتغل عند المشتركين.');await verify();
 }catch(err){error(err.message);if(target&&err.uncertain)showResult('حالة الرفع غير مؤكدة','افحص نفس الرابط أولًا. ما راح نعيد إرسال الملف تلقائيًا.');}
 finally{clearInterval(stallTimer);stallTimer=null;busy=false;controls(false);$('cancelUpload').hidden=true;request=null;try{await wake?.release()}catch{}wake=null}
};
$('cancelUpload').onclick=()=>{if(request&&confirm('توقف إرسال الملف؟ الرفع ما يستأنف من نفس المكان.'))request.abort()};$('verifyLink').onclick=verify;$('copyLink').onclick=async()=>{try{await navigator.clipboard.writeText(target);$('copyLink').textContent='تم نسخ الرابط ✓'}catch{$('downloadURL').focus();$('downloadURL').select();error('اضغط مطولًا على الرابط وانسخه يدويًا.')}};
window.addEventListener('beforeunload',e=>{if(busy){e.preventDefault();e.returnValue=''}});
try{const saved=JSON.parse(sessionStorage.getItem(key)||'null');if(isPackageURL(saved?.url)){target=saved.url;showResult('عندك رابط رفع سابق','اضغط فحص الرابط قبل إعادة رفع نفس الملف.')}}catch{}
