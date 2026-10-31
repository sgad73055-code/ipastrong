export const REPO='sgad73055-code/ipastrong';
export const WORKFLOW='manage-apps.yml';
export const RAW='https://raw.githubusercontent.com/'+REPO+'/refs/heads/main/ipastrong.json';
export const REPO_API='https://api.github.com/repos/'+REPO;
const pythonString=x=>x===undefined?'':x===null?'None':x===true?'True':x===false?'False':String(x);
export function identityText(app){return '['+['downloadURL','bundleIdentifier','name','_sourceURL'].map(k=>JSON.stringify(pythonString(app[k]))).join(', ')+']'}
export async function appId(app){const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(identityText(app)));return [...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,16)}
export function imageURL(value){try{const u=new URL(value);return u.protocol==='https:'?u.href:''}catch{return ''}}
export function sourceLabel(app){try{if(app._sourceURL==='local')return 'إضافة خاصة';const download=new URL(app.downloadURL);const channel=decodeURIComponent(download.pathname).match(/tg-ipa\/([^/]+)/);if(channel)return channel[1];const u=new URL(app._sourceURL||app.downloadURL);if(u.hostname==='raw.githubusercontent.com'||u.hostname==='github.com')return u.pathname.split('/').filter(Boolean)[0]||'GitHub';return u.hostname.replace(/^www\./,'')}catch{return 'المصدر'}}
export function findApps(apps,query){const q=query.trim().toLocaleLowerCase();if(!q)return apps;return apps.filter(a=>[a.name,a.bundleIdentifier,a.version,a.downloadURL,a._sourceURL,sourceLabel(a)].some(v=>String(v||'').toLocaleLowerCase().includes(q)))}
export function buildInputs({original,values,action,requestId,target=''}){
 const inputs={action,request_id:requestId,dry_run:false};
 if(action==='delete'){if(!target)throw Error('اختار التطبيق أولًا.');inputs.target=target;return inputs}
 if(!values.name.trim())throw Error('اكتب اسم التطبيق.');
 if(action==='edit'){if(!target)throw Error('معرّف التطبيق غير متوفر؛ حدّث المكتبة.');inputs.target=target}
 if(!original||values.name.trim()!==String(original.name||''))inputs.name=values.name.trim();
 for(const [key,field,clear] of [['description','localizedDescription','clear_description'],['icon','iconURL','clear_icon']]){
  const next=values[key].trim(),old=String(original?.[field]||'');
  if(!original||next!==old){if(next)inputs[key]=next;else if(original)inputs[clear]=true}
 }
 const url=values.url.trim();
 if(action==='add'&&!url)throw Error('حط رابط IPA مباشر للإضافة.');
 if(url&&(!imageURL(url)||new URL(url).username||new URL(url).password))throw Error('استخدم رابط تحميل HTTPS بدون بيانات دخول.');
 if(url&&(!original||url!==original.downloadURL))inputs.url=url;
 if(inputs.icon&&!inputs.icon.startsWith('data:image/')&&!imageURL(inputs.icon))throw Error('رابط الصورة لازم يبدأ بـhttps://.');
 if(action==='edit'&&!Object.keys(inputs).some(k=>!['action','request_id','target','dry_run'].includes(k)))throw Error('ما تغيّر أي حقل بعد.');
 if(new TextEncoder().encode(JSON.stringify({ref:'main',inputs})).length>60000)throw Error('التفاصيل طويلة؛ قلّل حجم الصورة أو طول الوصف.');
 return inputs;
}
export function operationMatches(apps,original,values,action){
 if(action==='delete')return !apps.some(a=>identityText(a)===identityText(original));
 const url=values.url.trim()||original?.downloadURL;
 return apps.some(a=>a.downloadURL===url&&a.name===values.name.trim()&&String(a.localizedDescription||'')===values.description.trim()&&(values.icon.startsWith('data:')||String(a.iconURL||'')===values.icon.trim()));
}
