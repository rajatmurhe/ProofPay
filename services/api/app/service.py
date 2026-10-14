import hashlib, json, os
from sqlalchemy import select
from .db import Job, Message, Event, MessageEvent, Relationship, Audit
from .parser import gate, extract

def rows(s,model,owner):return list(s.scalars(select(model).where(model.owner==owner)))
def amount(d, role=None):
    values=[a for a in d['amounts'] if a['role']==role] if role else [a for a in d['amounts'] if a['role']!='balance']
    return values[0] if len(values)==1 else None

def context_compatible(a,b):
    return all(not a.get(k) or not b.get(k) or a[k]==b[k] for k in ['issuer','instrument_last4']) and (a['instrument_type']==b['instrument_type'] or 'unknown' in [a['instrument_type'],b['instrument_type']])
def reconcile(s,event,owner):
    a=event.data
    for other in rows(s,Event,owner):
        if event.id==other.id:continue
        b=other.data
        if not context_compatible(a,b):continue
        ma,mb=amount(a),amount(b)
        same_money=bool(ma and mb and ma['minor']==mb['minor'] and ma['currency']==mb['currency'] and ma['currency'])
        same_ref=any(a.get(k) and a.get(k)==b.get(k) for k in (['refund_ref'] if a['subtype']=='refund' else ['transaction_ref']))
        same_kind=a['subtype']==b['subtype'] and a['message_type']==b['message_type']
        if same_ref and same_kind:
            safe=same_money and a.get('merchant')==b.get('merchant') and (a['event_date']==b['event_date'] or a['subtype']=='refund') and (a['status']==b['status'] or a['subtype']=='refund' and {a['status'],b['status']} <= {'initiated','pending','successful'})
            status='accepted' if safe else 'suggested'
            s.add(Relationship(owner=owner,left_id=other.id,right_id=event.id,kind='duplicate',status=status,reason='Matching reference and compatible facts' if safe else 'Reference matches but critical evidence conflicts'))
            if not safe:
                for row in [event,other]:
                    d=dict(row.data);d['conflicts']=list(set(d['conflicts']+['Same reference has conflicting evidence']));d['quality']='needs review';row.data=d
        elif same_kind and same_money and a.get('merchant') and a['merchant']==b['merchant'] and a['event_date']==b['event_date'] and not (a.get('transaction_ref') and b.get('transaction_ref') and a['transaction_ref']!=b['transaction_ref']):
            s.add(Relationship(owner=owner,left_id=other.id,right_id=event.id,kind='duplicate',status='suggested',reason='Similar amount, merchant and date; insufficient reference evidence'))
        if {a['subtype'],b['subtype']}=={'purchase','refund'}:
            purchase,refund=(other,event) if a['subtype']=='refund' else (event,other)
            p,r=purchase.data,refund.data
            pa,ra=amount(p,'purchase'),amount(r,'refund')
            if not pa or not ra or pa['currency']!=ra['currency'] or not pa['currency']:continue
            if p.get('order_ref') and p['order_ref']==r.get('order_ref'):
                s.add(Relationship(owner=owner,left_id=purchase.id,right_id=refund.id,kind='refund',status='accepted',reason='Explicit shared order reference; currency and instrument compatible'))
            elif p.get('merchant') and p['merchant']==r.get('merchant') and ra['minor']<=pa['minor']:
                s.add(Relationship(owner=owner,left_id=purchase.id,right_id=refund.id,kind='refund',status='suggested',reason='Merchant and amount compatible; original purchase reference missing'))

def quarantine_ambiguous_refund_links(s,owner):
    """Do not apply one refund to multiple distinct purchases with a reused order ID."""
    s.flush()
    events=rows(s,Event,owner);parent={e.id:e.id for e in events}
    def root(x):
        while parent[x]!=x:x=parent[x]
        return x
    links=rows(s,Relationship,owner)
    for r in links:
        if r.kind=='duplicate' and r.status=='accepted':parent[root(r.right_id)]=root(r.left_id)
    groups={}
    for r in links:
        if r.kind=='refund' and r.status=='accepted':groups.setdefault(root(r.right_id),[]).append(r)
    for links in groups.values():
        if len({root(r.left_id) for r in links})>1:
            for r in links:r.status='suggested';r.reason='Order reference matches multiple distinct purchases; choose the original purchase'

def import_batch(s,messages,owner,mode='rules'):
    job=Job(owner=owner,status='processing',counts={});s.add(job);s.commit()
    counts={k:0 for k in ['processed','retained','irrelevant','otp','unresolved','reimported','failed','provider_failures']}
    try:
        for message in messages:
            counts['processed']+=1
            relevance=gate(message.body)
            if relevance!='relevant':counts['unresolved' if relevance=='uncertain' else relevance]+=1;continue
            fingerprint=hashlib.sha256((owner+'\0'+message.source+'\0'+(message.source_id or '')+'\0'+message.body).encode()).hexdigest()
            if s.scalar(select(Message).where(Message.owner==owner,Message.fingerprint==fingerprint)):
                counts['reimported']+=1;continue
            try:
                with s.begin_nested():
                    events=extract(message.body, 'fixture' if mode=='fixture' else 'rules')
                    if mode=='live' and any(e.quality=='unresolved' for e in events):
                        from .provider import augment
                        events,failed=augment(message.body,events);counts['provider_failures']+=int(failed)
                    if not events:counts['unresolved']+=1;continue
                    msg=Message(owner=owner,fingerprint=fingerprint,source=message.source,received_at=message.received_at.isoformat() if message.received_at else None,job_id=job.id,evidence=[x.model_dump(mode='json') for e in events for x in e.evidence],mode=events[0].mode)
                    s.add(msg);s.flush()
                    for data in events:
                        event=Event(owner=owner,data=data.model_dump(mode='json'));s.add(event);s.flush()
                        s.add(MessageEvent(message_id=msg.id,event_id=event.id));reconcile(s,event,owner)
                    quarantine_ambiguous_refund_links(s,owner)
                    counts['retained']+=1
            except Exception:
                # Do not log exception representations: provider/validation errors may contain input.
                counts['failed']+=1
            job.counts=dict(counts);s.commit()
        job.status='partial' if counts['failed'] or counts['provider_failures'] else 'completed';job.counts=counts;s.commit()
    except Exception:
        s.rollback();job=s.get(Job,job.id);job.status='failed';job.counts=counts;s.commit()
    return {'id':job.id,'status':job.status,'counts':counts}

def projection(s,owner):
    events=rows(s,Event,owner);relations=rows(s,Relationship,owner);byid={e.id:e for e in events};parent={e.id:e.id for e in events}
    def root(x):
        while parent[x]!=x:x=parent[x]
        return x
    for r in relations:
        if r.kind=='duplicate' and r.status=='accepted' and r.left_id in parent and r.right_id in parent:parent[root(r.right_id)]=root(r.left_id)
    groups={}
    for e in events:groups.setdefault(root(e.id),[]).append(e)
    out=[]
    for key,group in groups.items():
        # Completed refund supersedes initiation; other conflicting evidence never silently wins.
        winner=next((e for e in group if e.data['subtype']=='refund' and e.data['status']=='successful'),group[0])
        d=dict(winner.data);d['id']=key;d['member_ids']=[e.id for e in group]
        d['conflicts']=sorted({c for e in group for c in e.data['conflicts']})
        if d['conflicts']:d['quality']='needs review'
        mids=list(s.scalars(select(MessageEvent.message_id).where(MessageEvent.event_id.in_(d['member_ids']))))
        msgs=list(s.scalars(select(Message).where(Message.owner==owner,Message.id.in_(mids)))) if mids else []
        d['sources']=[{'id':m.id,'source':m.source,'received_at':m.received_at,'job_id':m.job_id,'mode':m.mode,'evidence':m.evidence} for m in msgs]
        d['relationships']=[{'id':r.id,'left_id':r.left_id,'right_id':r.right_id,'kind':r.kind,'status':r.status,'reason':r.reason} for r in relations if r.left_id in d['member_ids'] or r.right_id in d['member_ids']]
        d['corrections']=[{'id':a.id,'created_at':a.created_at,**a.data} for a in rows(s,Audit,owner) if a.event_id in d['member_ids']]
        out.append(d)
    canonical={member:e for e in out for member in e['member_ids']}
    for e in out:
        if e['subtype']!='purchase':continue
        refunds={canonical[r.right_id]['id']:canonical[r.right_id] for r in relations if r.kind=='refund' and r.status=='accepted' and r.left_id in e['member_ids'] and r.right_id in canonical}
        p=amount(e,'purchase');cur=p['currency'] if p else None
        e['received_refund_minor']=sum(a['minor'] for r in refunds.values() if r['status']=='successful' and (a:=amount(r,'refund')) and a['currency']==cur)
        e['pending_refund_minor']=sum(a['minor'] for r in refunds.values() if r['status'] in ['pending','initiated'] and (a:=amount(r,'refund')) and a['currency']==cur)
        e['net_minor']=p['minor']-e['received_refund_minor'] if p else None
        if e['net_minor'] is not None and e['net_minor']<0:e['conflicts'].append('Linked refunds exceed purchase');e['quality']='needs review'
    return out

def metrics(events):
    totals={}
    for e in events:
        if e.get('mode')=='live':continue
        a=amount(e)
        if not a or not a['currency']:continue
        t=totals.setdefault(a['currency'],{'purchase':0,'net_purchase':0,'refund_received':0,'refund_pending':0,'bills':0,'cash_in':0,'cash_out':0})
        if e['subtype']=='purchase' and e['status']=='successful':t['purchase']+=a['minor'];t['net_purchase']+=e.get('net_minor',a['minor'])
        if e['subtype']=='refund':
            if e['status']=='successful':t['refund_received']+=a['minor']
            elif e['status'] in ['pending','initiated']:t['refund_pending']+=a['minor']
        if e['status']=='successful' and e['financial_effect'] in ['account inflow','account outflow']:t['cash_in' if e['financial_effect']=='account inflow' else 'cash_out']+=a['minor']
    for e in events:
        a=amount(e,'total due')
        if a and a['currency'] and e['subtype']=='bill':totals.setdefault(a['currency'],{'purchase':0,'net_purchase':0,'refund_received':0,'refund_pending':0,'bills':0,'cash_in':0,'cash_out':0})['bills']+=a['minor']
    return {'currencies':totals,'needs_review':sum(e['quality']!='validated' or any(r['status']=='suggested' for r in e['relationships']) for e in events),'records':len(events),'coverage':'Based on imported messages. This is not a complete account statement.'}
