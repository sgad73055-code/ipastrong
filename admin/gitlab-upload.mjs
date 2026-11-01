export const PROJECT_ID=88351948;
export const PACKAGE_ROOT='https://gitlab.com/api/v4/projects/'+PROJECT_ID+'/packages/generic/ipa-strong/';
export const MAX_BYTES=5000000000;
export function remoteFilename(name){let base=String(name).replace(/\.ipa$/i,'').replace(/[^A-Za-z0-9_.-]+/g,'-').replace(/^\.+|^-+|-+$/g,'').slice(0,110);if(!base)base='application';return base+'.ipa'}
export function uploadURL(filename,version){if(!/^[A-Za-z0-9][A-Za-z0-9_.-]*\.ipa$/.test(filename)||filename.includes('..')||filename.length>120)throw Error('اسم الملف لازم يكون بالإنكليزي وينتهي بـ.ipa، وبدون فراغات.');if(!/^[a-z0-9-]{10,80}$/.test(version))throw Error('Invalid upload version');return PACKAGE_ROOT+encodeURIComponent(version)+'/'+encodeURIComponent(filename)}
export function isPackageURL(url){try{const parsed=new URL(url);return !parsed.search&&!parsed.hash&&!parsed.username&&!parsed.password&&url.startsWith(PACKAGE_ROOT)&&/^[a-z0-9-]{10,80}\/[A-Za-z0-9][A-Za-z0-9_.-]*\.ipa$/.test(url.slice(PACKAGE_ROOT.length))}catch{return false}}
export async function checkFile(file){if(!file||!file.name.toLowerCase().endsWith('.ipa'))throw Error('اختار ملف ينتهي بـ.ipa.');if(!file.size||file.size>MAX_BYTES)throw Error('حجم الملف لازم يكون أكبر من صفر وأقل من ٥ GB.');const prefix=new Uint8Array(await file.slice(0,4).arrayBuffer());if(prefix.length!==4||prefix[0]!==80||prefix[1]!==75||!((prefix[2]===3&&prefix[3]===4)||(prefix[2]===5&&prefix[3]===6)))throw Error('الملف مو أرشيف IPA/ZIP. تأكد اختاريت الملف الصحيح.')}
export function uploadFile({file,url,token,onProgress=()=>{},makeXHR=()=>new XMLHttpRequest()}){
 if(!isPackageURL(url))throw Error('Upload target must be the selected GitLab project');
 if(!token||/[\r\n]/.test(token))throw Error('الصق رمز Deploy token الخاص بالمشروع.');
 const xhr=makeXHR();
 const promise=new Promise((resolve,reject)=>{
  xhr.open('PUT',url,true);xhr.timeout=3*60*60*1000;xhr.withCredentials=false;
  xhr.setRequestHeader('DEPLOY-TOKEN',token);xhr.setRequestHeader('Content-Type','application/octet-stream');
  xhr.upload.onprogress=e=>onProgress(e.loaded,e.lengthComputable?e.total:file.size);
  xhr.onload=()=>{
   if(xhr.status===201){resolve({url,status:201});return}
   const messages={400:'GitLab رفض الملف أو اسم الحزمة.',401:'رمز GitLab غير صحيح أو انتهت صلاحيته.',403:'الرمز ما عنده صلاحية write_package_registry، أو حسابك يحتاج توثيق.',404:'المشروع غير متاح للرمز أو Package Registry غير مفعّل.',409:'هذا الملف موجود مسبقًا؛ افحص رابط العملية السابقة.',413:'GitLab رفض حجم الملف؛ تجاوز حد الرفع المتاح.',429:'وصلت لحد الطلبات. انتظر قبل محاولة جديدة.'};
   const error=new Error(messages[xhr.status]||'فشل الرفع: HTTP '+xhr.status);error.uncertain=xhr.status>=500||xhr.status===0;reject(error);
  };
  xhr.onerror=()=>{const e=new Error('انقطع الاتصال أثناء الرفع. افحص الرابط قبل ما تعيد الرفع؛ ممكن GitLab استلم الملف.');e.uncertain=true;reject(e)};
  xhr.ontimeout=()=>{const e=new Error('انتهت مهلة الرفع. افحص الرابط قبل محاولة ثانية.');e.uncertain=true;reject(e)};
  xhr.onabort=()=>{const e=new Error('توقف الإرسال. افحص الرابط إذا كان الرفع واصل للنهاية.');e.uncertain=true;reject(e)};
  // Passing File directly avoids loading a multi-gigabyte IPA into JavaScript memory.
  xhr.send(file);
 });
 return {promise,abort:()=>xhr.abort()};
}
export async function probePublic(url,fetcher=fetch){
 if(!isPackageURL(url))throw Error('Invalid public download target');
 let response;
 try{response=await fetcher.call(globalThis,url,{method:'GET',headers:{Range:'bytes=0-3'},credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(30000)})}catch{return {ready:false,reason:'تعذّر فحص الرابط من المتصفح. ممكن الاتصال أو سياسة CORS؛ افتح الرابط بنافذة خاصة للتأكد.',network:true}}
 if(!response.ok||!response.body){try{await response.body?.cancel()}catch{}return {ready:false,reason:'الرابط ما رجّع ملفًا عامًا (HTTP '+response.status+'). تأكد من إعدادات الوصول.'}}
 const reader=response.body.getReader(),bytes=[];
 try{while(bytes.length<4){const {value,done}=await reader.read();if(done)break;for(const byte of value){bytes.push(byte);if(bytes.length===4)break}}}finally{try{await reader.cancel()}catch{}}
 const zip=bytes.length===4&&bytes[0]===80&&bytes[1]===75&&((bytes[2]===3&&bytes[3]===4)||(bytes[2]===5&&bytes[3]===6));
 return {ready:zip,reason:zip?'الرابط رجّع الملف مباشرة، بدون تسجيل دخول.':'الرابط رجّع صفحة أو ملفًا مختلفًا؛ ما نعتمده للسورس بعد.'};
}
