import csv, io, json, re
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from .schema import InputMessage

MAX_BYTES=2*1024*1024
class ImportErrorSafe(ValueError):pass
def parse_upload(name,data):
    if len(data)>MAX_BYTES:raise ImportErrorSafe('File exceeds 2 MB limit')
    ext=name.rsplit('.',1)[-1].lower()
    try:
        if ext=='eml':
            msg=BytesParser(policy=policy.default).parsebytes(data)
            if not msg.get('From') or not msg.get('Date'):raise ValueError()
            part=msg.get_body(preferencelist=('plain',))
            if not part:raise ImportErrorSafe('Email must contain text/plain; HTML and attachments are not processed')
            body=part.get_content()
            # Quoted replies and forwarded history are excluded, not treated as new events.
            body=re.split(r'(?m)^On .+wrote:|^-----Original Message-----',body)[0]
            body='\n'.join(x for x in body.splitlines() if not x.lstrip().startswith('>'))
            return [InputMessage(source='email',body=body,source_id=msg.get('Message-ID'),received_at=parsedate_to_datetime(msg['Date']))]
        text=data.decode('utf-8-sig')
        if '\x00' in text:raise ValueError()
        if ext=='json':raw=json.loads(text)
        elif ext=='csv':raw=list(csv.DictReader(io.StringIO(text)))
        else:raise ImportErrorSafe('Supported types: SMS JSON, CSV, and text/plain EML')
        if not isinstance(raw,list) or not 1<=len(raw)<=200:raise ValueError()
        return [InputMessage.model_validate({k:v for k,v in x.items() if v!=''}) for x in raw]
    except ImportErrorSafe:raise
    except Exception:raise ImportErrorSafe('Invalid file content or message schema') from None
