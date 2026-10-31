import {REPO_API,WORKFLOW} from './model.mjs';
export class GitHubError extends Error{constructor(message,status){super(message);this.status=status}}
export class GitHub{
 #token='';
 constructor(fetcher=fetch){this.fetcher=fetcher}
 get connected(){return !!this.#token}
 disconnect(){this.#token=''}
 async request(path,{method='GET',body}={},token=this.#token){
  if(!token)throw new GitHubError('اربط GitHub حتى تقدر تحفظ.',401);
  // The caller chooses only fixed repository-relative routes. No arbitrary origins.
  if(!/^\/(?:actions\/(?:workflows\/manage-apps\.yml(?:\/dispatches|\/runs(?:\?.*)?)?|runs\/\d+))$/.test(path))throw Error('Unsupported GitHub route');
  let response;
  try{response=await this.fetcher(REPO_API+path,{method,headers:{'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'X-GitHub-Api-Version':'2026-03-10',...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store',redirect:'error',signal:AbortSignal.timeout(25000)})}
  catch{throw new GitHubError(method==='POST'?'انقطع الاتصال أثناء الإرسال. قد يكون الطلب وصل؛ تابع الحالة قبل أي محاولة ثانية.':'تعذّر الاتصال بـGitHub. تحقق من الإنترنت وحاول متابعة الحالة.',0)}
  if(!response.ok){
   const messages={401:'رمز الربط غير صحيح أو انتهت صلاحيته. اربطه مجددًا.',403:'GitHub رفض الطلب. تأكد أن الرمز محدد لمستودع ipastrong وصلاحية Actions هي Read and write، أو انتظر إذا وصلت لحد الطلبات.',404:'المستودع أو مسار الإدارة غير متاح لهذا الرمز.',422:'GitHub رفض بيانات العملية؛ حدّث اللوحة وتأكد من صلاحيات الرمز.'};
   throw new GitHubError(messages[response.status]||'تعذّر إكمال طلب GitHub (HTTP '+response.status+').',response.status);
  }
  if(response.status===204)return null;
  return response.json();
 }
 async connect(value){
  const token=value.trim();
  if(!/^github_pat_[A-Za-z0-9_]+$/.test(token))throw new GitHubError('استخدم Fine-grained token يبدأ بـgithub_pat_.',401);
  const workflow=await this.request('/actions/workflows/'+WORKFLOW,{},token);
  if(workflow.state!=='active')throw Error('أداة إدارة التطبيقات متوقفة في GitHub.');
  this.#token=token;
 }
 dispatch(inputs){return this.request('/actions/workflows/'+WORKFLOW+'/dispatches',{method:'POST',body:{ref:'main',inputs}})}
 async locate(pending){
  if(pending.runId)return this.request('/actions/runs/'+pending.runId);
  const result=await this.request('/actions/workflows/'+WORKFLOW+'/runs?event=workflow_dispatch&per_page=50&created='+encodeURIComponent('>='+new Date(pending.createdAt-60000).toISOString()));
  return result.workflow_runs?.find(r=>r.display_title==='Catalog · '+pending.requestId)||null;
 }
}
