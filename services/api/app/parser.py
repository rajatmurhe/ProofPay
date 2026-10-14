"""Conservative English financial parser. No input logging or retained bodies."""
import re, hashlib
from decimal import Decimal, InvalidOperation
from datetime import date
from .schema import EventData, Money, Evidence

MONEY=re.compile(r'(?P<currency>INR|Rs\.?|₹|USD|\$|EUR|€)\s*(?P<n>\d[\d,]*(?:\.\d{1,2})?)(?!\d|\.\d)',re.I)
MAP={'amazon':('Amazon','Shopping'),'swiggy':('Swiggy','Food & dining'),'zomato':('Zomato','Food & dining'),'bigbasket':('BigBasket','Groceries'),'uber':('Uber','Transport'),'netflix':('Netflix','Subscriptions'),'bescom':('BESCOM','Utilities'),'apollo':('Apollo','Health'),'metro':('Metro','Transport')}
INTERMEDIARIES=['Razorpay','PhonePe','Amazon Pay','Paytm']
def mask(s):
    s=re.sub(r'(?i)((?:otp|pin|verification code|password)\s*(?:is|:|=)?\s*)\S+',r'\1[redacted]',s)
    s=re.sub(r'\b[\w.+-]+@[\w.-]+\b','[masked address]',s)
    s=re.sub(r'\b\d{5,}\b',lambda m:'••••'+m[0][-4:],s)
    s=re.sub(r'\b(?:\d[ -]?){12,19}\b',lambda m:'••••'+re.sub(r'\D','',m[0])[-4:],s)
    return s

def gate(text):
    low=text.lower()
    if re.search(r'\botp\b|one.time.password|verification code|authentication code',low): return 'otp'
    strong=re.search(r'debited|credited|spent|refund|cashback|credit card|a/c|account.*(?:balance|transfer)|emi\b|payment.*(?:failed|declined|unsuccessful|successful|received)|transaction.*(?:failed|declined|unsuccessful|successful)|minimum due|total due',low)
    offer=re.search(r'offer|discount|\d+% off|reward points',low) and (MONEY.search(text) or 'card' in low or 'reward points' in low)
    if (strong and (MONEY.search(text) or re.search(r'reward points|account (?:blocked|frozen|closed)',low))) or offer: return 'relevant'
    # Second in-memory assessment requires both an explicit amount and financial action.
    if MONEY.search(text) and re.search(r'paid|purchase|bought|transfer|bill|received|sent',low): return 'relevant'
    if re.search(r'bank|payment|transaction|money|rupees|refund|paisa|bhej',low): return 'uncertain'
    return 'irrelevant'

def extract(text, mode='rules'):
    parts=re.split(r'\n\s*(?:EVENT:|•)|\s*\|\|\s*',text)
    return [parse(p,mode) for p in parts if p.strip() and gate(p)=='relevant']

def parse(text,mode='rules'):
    low=text.lower(); e=EventData(mode=mode)
    def has(p): return bool(re.search(p,low))
    if has('refund'):
        e.message_type='Refund'; e.subtype='refund'
        e.status='successful' if has('credited|received|completed') else 'initiated' if has('initiated') else 'pending'
    elif has('minimum due|total due|statement.*due'):
        e.message_type='Credit Card Bill';e.subtype='bill';e.status='pending'
    elif has('failed|declined|unsuccessful'):
        e.message_type='Failed Transaction';e.subtype='failed payment';e.status='failed'
    elif has(r'\bemi\b'):
        e.message_type='EMI';e.subtype='instalment';e.status='successful' if has('debited|paid') else 'pending'
    elif has('cashback|reward points'):
        e.message_type='Cashback/Reward';e.subtype='reward';e.benefit_type='points' if has('points') else 'cashback';e.status='successful' if has('credited|received') else 'pending'
    elif has('offer|discount|% off'):
        e.message_type='Offer/Promotion';e.subtype='offer';e.status='unknown';e.benefit_type='discount'
    elif has('(?:card|bill).*payment|payment.*(?:card|bill)|transferred|transfer to|transfer from'):
        e.message_type='Payment';e.subtype='card repayment' if has('card') else 'transfer';e.status='successful' if has('successful|credited|debited|paid|received|transferred') else 'unknown'
    elif has(r'debited|spent|paid|purchase|credited|received|\bdebit hua\b'):
        e.message_type='Transaction';e.subtype='credit' if has('credited|received') and not has('debited|spent|paid|purchase') else 'purchase';e.status='successful'
    if has('reversed|reversal'):e.status='reversed'
    if has('pending') and e.status=='successful': e.status='pending'
    if has('credit card'):e.instrument_type='credit card'
    elif has('debit card'):e.instrument_type='debit card'
    elif has(r'a/c|bank account|account (?:ending|xx|\d)'):e.instrument_type='bank account'
    elif has('wallet'):e.instrument_type='wallet'
    elif has('loan'):e.instrument_type='loan'
    e.rail='UPI' if has('upi') else 'card' if has('card') else 'netbanking' if has('netbanking') else 'wallet' if has('wallet') else 'unknown'
    last=re.search(r'(?:ending(?: in)?|[xX*]{2,}|a/c\s*)\s*(\d{4})(?!\d)',text)
    if last:e.instrument_last4=last[1]
    issuer=re.search(r'\b(HDFC|ICICI|SBI|Axis|Kotak|IDFC|Federal)\b',text,re.I)
    if issuer:e.issuer=issuer[1].upper()
    # Last four is deliberately not a resolved account identifier.
    m=re.search(r'(?:\bat\s+|merchant:\s*)([A-Za-z][A-Za-z0-9 &.\-]{1,45}?)(?=\s+(?:on|via|using|with|ref|order|txn|UPI)\b|[;\n]|$)',text,re.I)
    if m:
        e.merchant_original=mask(m[1].strip());e.merchant=e.merchant_original
        for intermediary in INTERMEDIARIES:
            if intermediary.lower() in e.merchant.lower():e.intermediary=intermediary;e.merchant=None;break
        if e.merchant:
            for k,(name,cat) in MAP.items():
                if e.merchant.lower()==k:e.merchant=name;e.category=cat;e.enrichment='curated-demo-map-v1';break
    for intermediary in INTERMEDIARIES:
        if intermediary.lower() in low:e.intermediary=intermediary
    for field,pat in [('transaction_ref',r'(?:txn|transaction|upi)\s*(?:ref(?:erence)?|id)[: #]*([A-Za-z0-9-]{3,40})'),('order_ref',r'order\s*(?:ref|id)?[: #]*([A-Za-z0-9-]{3,40})'),('refund_ref',r'refund\s*(?:ref|id)[: #]*([A-Za-z0-9-]{3,40})')]:
        match=re.search(pat,text,re.I)
        if match:setattr(e,field,('ref-'+hashlib.sha256(match[1].encode()).hexdigest()[:24]) if re.search(r'\d{5,}',match[1]) else match[1])
    for field,pat in [('due_date',r'due(?: date)?(?: on| by)?[: ]+(\d{4}-\d{2}-\d{2})'),('expiry_date',r'(?:expires?|valid until)[: ]+(\d{4}-\d{2}-\d{2})'),('event_date',r'\bon\s+(\d{4}-\d{2}-\d{2})')]:
        match=re.search(pat,text,re.I)
        if match:
            try:setattr(e,field,date.fromisoformat(match[1]))
            except ValueError:e.validation.append('Invalid '+field)
    if e.event_date:e.date_precision='day'
    default={'Refund':'refund','Credit Card Bill':'total due','Offer/Promotion':'threshold','Cashback/Reward':'reward','Payment':'payment','EMI':'emi','Transaction':'purchase'}.get(e.message_type,'unknown')
    for m in MONEY.finditer(text):
        before=low[max(0,m.start()-25):m.start()];role=default
        if re.search(r'(?:avl|available|closing|account)?\s*bal(?:ance)?[: .]*$',before):role='balance'
        elif re.search(r'min(?:imum)?(?: amount)? due[: ]*$',before):role='minimum due'
        elif re.search(r'total(?: amount)? due[: ]*$',before):role='total due'
        elif re.search(r'discount[: ]*$',before):role='discount'
        cur=m['currency'].upper();cur='INR' if cur in ['RS','RS.','₹','INR'] else 'EUR' if cur=='€' else None if cur=='$' else cur
        if ',' in m['n'] and not re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?',m['n']):
            e.validation.append('Invalid amount grouping');continue
        try:minor=int(Decimal(m['n'].replace(',',''))*100)
        except InvalidOperation:continue
        e.amounts.append(Money(role=role,minor=minor,currency=cur,evidence=m[0]))
    # Bare amounts are not assigned INR; absence is made explicit.
    if e.message_type in ['Offer/Promotion','Credit Card Bill'] or e.benefit_type=='points':e.financial_effect='non-monetary'
    elif e.status in ['successful','reversed']:
        credit=e.message_type in ['Refund','Cashback/Reward'] or e.subtype=='credit' or (e.subtype=='card repayment' and has('credited|received'))
        e.direction='credit' if credit else 'debit'
        e.financial_effect=('card liability decrease' if credit else 'card liability increase') if e.instrument_type=='credit card' else ('account inflow' if credit else 'account outflow') if e.instrument_type in ['bank account','debit card','wallet'] else 'unknown'
    if e.message_type=='Failed Transaction' and has('debited'):
        e.conflicts.append('Failure notice also reports a debit; cashflow unresolved')
    critical=[a for a in e.amounts if a.role!='balance']
    if not critical and e.benefit_type!='points':e.missing_fields.append('amount')
    if any(a.currency is None for a in critical):e.missing_fields.append('currency')
    if not e.event_date and e.message_type not in ['Credit Card Bill','Offer/Promotion']:e.missing_fields.append('event_date')
    if e.message_type=='Credit Card Bill' and not e.due_date:e.missing_fields.append('due_date')
    if e.subtype=='purchase' and not e.merchant:e.missing_fields.append('merchant')
    if len([a for a in critical if a.role==default])>1:e.conflicts.append('Multiple amounts for the same role')
    # A visible monetary token that cannot be parsed must never imply completeness.
    if re.search(r'(?:INR|Rs\.?|₹|USD|\$|EUR|€)\s*\d',text,re.I) and not e.amounts:
        e.validation.append('Amount format needs review')
    if e.status=='unknown' and e.message_type not in ['Offer/Promotion','Other']:e.missing_fields.append('status')
    if e.message_type=='Other':e.missing_fields.append('event_subtype')
    for field in ['merchant_original','issuer','instrument_last4','transaction_ref','order_ref','refund_ref','event_date','due_date','expiry_date']:
        v=getattr(e,field)
        if v is not None:e.evidence.append(Evidence(field=field,value=str(v),excerpt=str(v)))
    e.evidence.extend(Evidence(field='amount:'+a.role,value=str(a.minor),excerpt=a.evidence) for a in e.amounts)
    e.quality='needs review' if e.missing_fields or e.conflicts or e.validation else 'validated'
    if not critical and e.message_type=='Other':e.quality='unresolved'
    e.validation.append('Only explicit amount tokens accepted; no received-date substitution')
    return e
