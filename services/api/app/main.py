import os, json, csv, io
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, delete
from .schema import Batch, Correction, LinkInput, LinkAction, EventData
from .db import Session, Event, Message, Job, MessageEvent, Relationship, Audit
from .service import import_batch, projection, metrics, rows, amount
from .adapters import parse_upload, ImportErrorSafe, MAX_BYTES
from .parser import mask

app=FastAPI(title='ProofPay',version='0.1.0')
OWNER=os.getenv('LOCAL_OWNER','local-demo')
MODE=os.getenv('PROCESSING_MODE','rules')
WEB_ORIGIN=os.getenv('LOCAL_WEB_ORIGIN','http://127.0.0.1:3017')
if MODE not in ['rules','fixture','live']:raise RuntimeError('PROCESSING_MODE must be rules, fixture, or live')
@app.exception_handler(RequestValidationError)
async def invalid(request,exc):return JSONResponse(status_code=422,content={'detail':'Invalid request schema; input content is never returned'})
@app.middleware('http')
async def local_guard(request:Request,call_next):
    # Browser CSRF guard; application intentionally has no internet authentication.
    origin=request.headers.get('origin')
    if origin and origin not in [WEB_ORIGIN,'http://127.0.0.1:3000','http://localhost:3000','http://127.0.0.1:8017','http://127.0.0.1:3017','http://localhost:3017']:return JSONResponse(status_code=403,content={'detail':'Origin not allowed'})
    length=request.headers.get('content-length')
    if length and (not length.isdigit() or int(length)>11*1024*1024):return JSONResponse(status_code=413,content={'detail':'Request too large'})
    if request.method in ['POST','PATCH','PUT']:
        chunks=[];total=0
        async for chunk in request.stream():
            total+=len(chunk)
            if total>11*1024*1024:return JSONResponse(status_code=413,content={'detail':'Request too large'})
            chunks.append(chunk)
        request._body=b''.join(chunks)
    try:return await call_next(request)
    except Exception:return JSONResponse(status_code=500,content={'detail':'Processing failed; message content omitted'})
@app.get('/health')
def health():return {'status':'ok','mode':MODE,'single_user':True,'live_configured':bool(os.getenv('AI_BASE_URL') and os.getenv('AI_MODEL') and os.getenv('AI_API_KEY'))}
@app.post('/imports')
def imports(batch:Batch):
    with Session() as s:return import_batch(s,batch.messages,OWNER,MODE)
@app.post('/imports/files')
async def files(files:list[UploadFile]=File(...)):
    if len(files)>5:raise HTTPException(400,'Maximum 5 files')
    messages=[]
    for file in files:
        data=await file.read(MAX_BYTES+1)
        try:messages.extend(parse_upload(file.filename or '',data))
        except ImportErrorSafe as exc:raise HTTPException(400,str(exc)) from None
        finally:await file.close()
    if len(messages)>200:raise HTTPException(400,'Maximum 200 messages per batch')
    with Session() as s:return import_batch(s,messages,OWNER,MODE)
@app.post('/demo')
def demo(stage:str='all'):
    raw=json.loads((Path(__file__).resolve().parents[3]/'data/synthetic/demo.json').read_text())
    if stage=='purchase':raw=raw[:2]
    elif stage=='initiated':raw=raw[2:3]
    elif stage=='received':raw=raw[3:4]
    elif stage!='all':raise HTTPException(400,'Unknown demo stage')
    with Session() as s:return import_batch(s,Batch(messages=raw).messages,OWNER,'fixture')
@app.get('/jobs')
def jobs():
    with Session() as s:return [{'id':j.id,'status':j.status,'counts':j.counts,'created_at':j.created_at} for j in rows(s,Job,OWNER)][::-1]
@app.get('/events')
def events():
    with Session() as s:return projection(s,OWNER)
@app.get('/metrics')
def dashboard():
    with Session() as s:return metrics(projection(s,OWNER))
@app.patch('/events/{event_id}')
def correct(event_id:str,correction:Correction):
    with Session() as s:
        e=s.get(Event,event_id)
        if not e or e.owner!=OWNER:raise HTTPException(404,'Record not found')
        d=dict(e.data);old=d.get(correction.field);value=mask(correction.value)
        d[correction.field]=value
        try:validated=EventData.model_validate(d)
        except Exception:raise HTTPException(422,'Invalid correction value') from None
        d=validated.model_dump(mode='json');d['missing_fields']=[x for x in d['missing_fields'] if x!=correction.field]
        # A user correction remains explicitly reviewed; it never creates observed source evidence.
        d['quality']='needs review' if d['missing_fields'] or d['conflicts'] else 'validated'
        group=next((x for x in projection(s,OWNER) if event_id in x['member_ids']),None)
        for member_id in (group['member_ids'] if group else [event_id]):
            member=s.get(Event,member_id);md=dict(member.data);md[correction.field]=d[correction.field];md['missing_fields']=[x for x in md['missing_fields'] if x!=correction.field];md['quality']='needs review' if md['missing_fields'] or md['conflicts'] else 'validated';member.data=md
        s.add(Audit(owner=OWNER,event_id=event_id,data={'field':correction.field,'before':old,'after':value,'reason':mask(correction.reason),'origin':'user correction'}));s.commit()
        return {'ok':True}
@app.post('/relationships')
def link(payload:LinkInput):
    with Session() as s:
        left,right=s.get(Event,payload.left_id),s.get(Event,payload.right_id)
        if not left or not right or left.owner!=OWNER or right.owner!=OWNER:raise HTTPException(404,'Record not found')
        if left.id==right.id:raise HTTPException(400,'Cannot link a record to itself')
        if payload.kind=='refund' and (left.data['subtype']!='purchase' or right.data['subtype']!='refund'):raise HTTPException(400,'Select a purchase and a refund')
        if payload.kind=='duplicate' and left.data['subtype']!=right.data['subtype']:raise HTTPException(400,'Incompatible event types')
        r=Relationship(owner=OWNER,**payload.model_dump(),status='suggested',reason='User proposed relationship');s.add(r);s.commit();return {'id':r.id}
@app.patch('/relationships/{link_id}')
def change_link(link_id:str,payload:LinkAction):
    with Session() as s:
        r=s.get(Relationship,link_id)
        if not r or r.owner!=OWNER:raise HTTPException(404,'Relationship not found')
        if payload.status=='accepted':
            left,right=s.get(Event,r.left_id),s.get(Event,r.right_id)
            a,b=amount(left.data),amount(right.data)
            if not a or not b or not a['currency'] or a['currency']!=b['currency']:raise HTTPException(400,'Link requires explicit matching currency')
            if r.kind=='duplicate' and (left.data['subtype']!=right.data['subtype'] or a['minor']!=b['minor']):raise HTTPException(400,'Conflicting amounts or types cannot be merged')
            if r.kind=='refund':
                others=[x for x in rows(s,Relationship,OWNER) if x.kind=='refund' and x.status=='accepted' and x.right_id==r.right_id and x.left_id!=r.left_id]
                if others:raise HTTPException(400,'Undo the existing purchase link first')
        old=r.status;r.status=payload.status;s.add(Audit(owner=OWNER,event_id=r.left_id,data={'relationship_id':r.id,'before':old,'after':r.status,'origin':'user correction'}));s.commit();return {'ok':True}
@app.get('/export')
def export(format:str='json'):
    with Session() as s:records=projection(s,OWNER)
    fields=['id','merchant','message_type','status','event_date','quality','mode']
    if format=='json':return records
    if format!='csv':raise HTTPException(400,'Use json or csv')
    out=io.StringIO();writer=csv.writer(out);writer.writerow(fields+['amount_minor','currency'])
    def safe(v):
        v='' if v is None else str(v)
        return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r')) else v
    for e in records:
        a=amount(e);writer.writerow([safe(e.get(f)) for f in fields]+[a['minor'] if a else '',a['currency'] if a else ''])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="proofpay-activity.csv"'})
@app.delete('/data')
def erase():
    with Session() as s:
        ids=[e.id for e in rows(s,Event,OWNER)]
        s.execute(delete(MessageEvent).where(MessageEvent.event_id.in_(ids)))
        for model in [Audit,Relationship,Event,Message,Job]:s.execute(delete(model).where(model.owner==OWNER))
        s.commit()
    return {'deleted':True}

@app.get("/evaluation")
def evaluation_report():
    path=Path(__file__).resolve().parents[3]/"evaluation/report-test-rules.json"
    if not path.exists(): raise HTTPException(404,"Held-out evaluation has not been run yet")
    data=json.loads(path.read_text())
    return {k:v for k,v in data.items() if k!="failure_examples"}
