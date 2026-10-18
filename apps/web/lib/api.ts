let csrfToken='';
export function setCsrfToken(value:string){csrfToken=value}
export class RequestError extends Error{constructor(message:string,public status:number){super(message)}}
export class SessionExpired extends Error{}
export async function api(path:string,options?:RequestInit){
 const headers=new Headers(options?.headers);
 if(options?.method&&!['GET','HEAD','OPTIONS'].includes(options.method.toUpperCase())&&csrfToken)headers.set('X-CSRF-Token',csrfToken);
 let response:Response;
 try{response=await fetch('/api'+path,{...options,headers,credentials:'same-origin',cache:'no-store'})}catch{throw Error('Unable to connect to ProofPay. Check the service and try again.')}
 if(!response.ok){
  let message=response.status>=500?'The request was interrupted. Please try again.':'The request could not be completed.';
  try{const detail=(await response.json()).detail;if(typeof detail==='string')message=detail}catch{}
  if(response.status===401&&path!=='/auth/login'){window.dispatchEvent(new Event('proofpay-session-expired'));throw new SessionExpired('Please sign in again.')}
  throw new RequestError(message,response.status);
 }
 return response.json();
}
export const json=(body:unknown,method='POST')=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
