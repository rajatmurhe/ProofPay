'use client';
import {useEffect,useRef,useState} from 'react';
import {Mail,ShieldCheck} from 'lucide-react';
import {api,json,RequestError} from '../lib/api';
import {useAuth} from './auth-gate';
type GmailStatus={configured:boolean;connected:boolean;email:string|null;last_success_at?:string|null};
type ImportResult={after:string;before:string;fetched:number;counts:Record<string,number>;unsupported_content_skipped:number;more_available:boolean;next_cursor:string|null};
type ImportTask={id:string;status:'queued'|'running'|'complete'|'failed'|'cancelled';attempts:number;result:ImportResult|null;error:string|null};
function localDate(date:Date){return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`}
export function GmailConnector({onImported}:{onImported:()=>Promise<void>}){
 const {demo}=useAuth();
 const [status,setStatus]=useState<GmailStatus|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[consent,setConsent]=useState(false),[cursor,setCursor]=useState<string|null>(null),[task,setTask]=useState<ImportTask|null>(null);
 const [after,setAfter]=useState(()=>localDate(new Date(Date.now()-14*86400000))),[before,setBefore]=useState(()=>localDate(new Date(Date.now()+86400000)));
 const imported=useRef(onImported);imported.current=onImported;
 const pending=task?.status==='queued'||task?.status==='running';
 async function refresh(){setStatus(await api('/connectors/gmail/status'))}
 useEffect(()=>{
  if(demo)return;
  let active=true;
  Promise.all([api('/connectors/gmail/status'),api('/connectors/gmail/imports/latest')]).then(([s,t])=>{if(active){setStatus(s);if(t?.status==='queued'||t?.status==='running')setTask(t)}}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[demo]);
 useEffect(()=>{
  if(!pending||!task)return;
  let active=true;let timer:ReturnType<typeof setTimeout>;
  async function poll(){
   try{
    const next:ImportTask=await api('/connectors/gmail/imports/'+task!.id);
    if(!active)return;
    if(next.status==='complete'&&next.result){
     const r=next.result;
     setNotice(`Emails checked: ${r.fetched}. Financial messages saved: ${r.counts.retained||0}. Already imported: ${r.counts.reimported||0}. Emails without supported text: ${r.unsupported_content_skipped||0}.${r.counts.failed?` Messages needing another attempt: ${r.counts.failed}.`:""}${r.more_available?' More emails match this range. Import the next batch to continue.':''}`);
     setAfter(r.after);setBefore(r.before);setCursor(r.next_cursor||null);setConsent(false);setError('');
     await imported.current();if(active)await refresh();
    }else if(next.status==='failed'||next.status==='cancelled'){setError(next.error||'Import stopped. Check your connection and try again.');setConsent(false)}
    else timer=setTimeout(poll,2000);
    if(active)setTask(next);
   }catch(e){if(active){setError(e instanceof Error?e.message:'Unable to check import progress');if(e instanceof RequestError&&e.status===404)setTask(null);else timer=setTimeout(poll,5000)}}
  }
  timer=setTimeout(poll,1000);
  return()=>{active=false;clearTimeout(timer)};
 },[pending,task?.id]);
 if(demo)return null;
 return <section className="panel import-card spaced gmail-card" aria-label="Gmail connection">
  <div className="section-icon"><Mail size={24}/></div><h2>Import from Gmail</h2>
  <p>Connect your own mailbox and choose a date range. Imported emails use local processing. ProofPay keeps financial facts and masked evidence, and skips unrelated content.</p>
  {error&&<div role="alert" className="alert error">{error}</div>}{notice&&<div role="status" className="alert success">{notice}</div>}
  {pending&&<div role="status" className="alert">{task?.status==='queued'?'Your import is queued. It will start when the import service is available.':'Checking your emails. You can keep using ProofPay while this runs.'}{task?.error&&` ${task.error}`} Keep signed in until it finishes.</div>}
  {status?.connected?<>
   <div className="gmail-account"><ShieldCheck size={18}/><strong>{status.email}</strong><span className="badge green">Connected · read only</span></div>
   {status.last_success_at&&<small>Last successful import: {new Date(status.last_success_at).toLocaleString()}</small>}
   <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');setNotice('');try{setTask(await api('/connectors/gmail/imports',json({after,before,limit:20,consent,cursor})));setConsent(false)}catch(e){setError(e instanceof Error?e.message:'Email import could not start')}finally{setBusy(false)}}}>
    <div className="gmail-dates">
     <label>From<input aria-label="Gmail import from" type="date" required disabled={pending} value={after} onChange={e=>{setAfter(e.target.value);setCursor(null);setConsent(false)}}/></label>
     <label>Before<input aria-label="Gmail import before" type="date" required disabled={pending} min={after} value={before} onChange={e=>{setBefore(e.target.value);setCursor(null);setConsent(false)}}/></label>
    </div>
    <small>Choose up to 31 days. Each import checks up to 20 matching emails. Dates use India time (IST). The Before date is excluded.</small>
    <label className="consent-checkbox"><input type="checkbox" disabled={pending} checked={consent} onChange={e=>setConsent(e.target.checked)}/>I agree to read matching emails in this date range for financial extraction.</label>
    <div className="button-row"><button className="primary" disabled={busy||pending||!consent||!status.configured}>{pending?'Import in progress…':busy?'Starting…':cursor?'Import next matching emails':'Import financial emails'}</button>
     <button type="button" className="secondary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const r=await api('/connectors/gmail/connection',{method:'DELETE'});await refresh();setTask(null);setCursor(null);setConsent(false);setNotice(r.provider_revoked?'Gmail disconnected. Previously imported records stay in your workspace.':'Disconnected locally. Google access revocation could not be confirmed. Remove ProofPay from your Google Account permissions.')}catch(e){setError(e instanceof Error?e.message:'Unable to disconnect')}finally{setBusy(false)}}}>Disconnect Gmail</button>
    </div>
   </form>
  </>:status?.configured?<>
   <p className="gmail-scope">Google will request read access to email. ProofPay cannot send, edit, or delete your emails.</p>
   <button className="primary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const r=await api('/connectors/gmail/connect',{method:'POST'});const url=new URL(r.url);if(url.origin!=='https://accounts.google.com')throw Error('Connection address is invalid');window.location.assign(r.url)}catch(e){setError(e instanceof Error?e.message:'Unable to connect');setBusy(false)}}}>Connect Gmail</button>
  </>:<div className="gmail-setup"><strong>{status?'Google setup required':'Checking connection setup…'}</strong><p>{status?'An administrator must configure Google OAuth before Gmail can connect. You can continue importing EML files or pasted messages.':''}</p></div>}
 </section>;
}
