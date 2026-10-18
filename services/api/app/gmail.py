"""Explicit Gmail OAuth/import flow. All Google URLs are fixed, tokens encrypted."""
import base64
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete, update
from .db import Session, OAuthState, GmailConnection, User, AuthSession, uid, now as db_now
from .schema import GmailImport, InputMessage
from .service import import_batch
from . import security

router = APIRouter(prefix='/connectors/gmail', tags=['Gmail'])
SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
REVOKE_URL = 'https://oauth2.googleapis.com/revoke'
API_URL = 'https://gmail.googleapis.com/gmail/v1/users/me'
MAX_RESPONSE = 1024 * 1024


def config():
    client_id = os.getenv('GOOGLE_CLIENT_ID', '')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '')
    key = os.getenv('CONNECTOR_ENCRYPTION_KEY', '')
    if not all([client_id, client_secret, key]):
        raise HTTPException(503, 'Gmail needs administrator setup before it can connect.')
    try:
        cipher = Fernet(key.encode())
    except Exception:
        raise HTTPException(503, 'Gmail connection storage needs administrator setup.') from None
    return client_id, client_secret, cipher


def require_account(request):
    if security.AUTH_MODE != 'authenticated' or not request.state.user:
        raise HTTPException(403, 'Sign in to a private account before connecting Gmail.')


def google(method, url, **kwargs):
    """Bounded response reader; no redirects, logging or reflected provider errors."""
    with httpx.Client(timeout=10.0, follow_redirects=False) as client:
        with client.stream(method, url, **kwargs) as response:
            response.raise_for_status()
            chunks = bytearray()
            for chunk in response.iter_bytes():
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE:
                    raise ValueError('Provider response exceeded size budget')
            return json.loads(chunks) if chunks else {}


def validate_tokens(data, previous=None):
    if not isinstance(data, dict) or data.get('token_type', '').lower() != 'bearer':
        raise ValueError('Invalid token response')
    access = data.get('access_token')
    if not isinstance(access, str) or not 1 <= len(access) <= 4096:
        raise ValueError('Invalid access token')
    if SCOPE not in data.get('scope', (previous or {}).get('scope', '')).split():
        raise ValueError('Required scope not granted')
    expires = int(data.get('expires_in', 0))
    if not 1 <= expires <= 86400:
        raise ValueError('Invalid expiry')
    refresh = data.get('refresh_token', (previous or {}).get('refresh_token'))
    if refresh is not None and (not isinstance(refresh, str) or len(refresh) > 8192):
        raise ValueError('Invalid refresh token')
    return {'access_token': access, 'refresh_token': refresh, 'scope': SCOPE}, int(time.time()) + expires


@router.get('/status')
def status(request: Request):
    require_account(request)
    try:
        config(); configured = True
    except HTTPException:
        configured = False
    with Session() as s:
        connection = s.get(GmailConnection, request.state.user.id)
        return {'configured': configured, 'connected': bool(connection), 'email': connection.email if connection else None, 'scope': 'Read email only', 'live_verified': bool(connection), 'last_success_at': connection.last_success_at if connection else None}


@router.post('/connect')
def connect(request: Request):
    require_account(request)
    client_id, _, cipher = config()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    with Session() as s:
        security.throttle(s, 'gmail-connect:' + request.state.user.id, 10)
        s.execute(delete(OAuthState).where(OAuthState.expires_at <= int(time.time())))
        account=s.scalar(select(User).where(User.id==request.state.user.id).with_for_update())
        s.add(OAuthState(state_hash=security.digest(state), user_id=request.state.user.id, connection_epoch=account.gmail_epoch, session_hash=request.state.session.token_hash, verifier_encrypted=cipher.encrypt(verifier.encode()).decode(), expires_at=int(time.time()) + 600))
        s.commit()
    query = urlencode({'client_id': client_id, 'redirect_uri': security.APP_ORIGIN + '/api/connectors/gmail/callback', 'response_type': 'code', 'scope': SCOPE, 'state': state, 'access_type': 'offline', 'prompt': 'consent', 'code_challenge': challenge, 'code_challenge_method': 'S256'})
    return {'url': 'https://accounts.google.com/o/oauth2/v2/auth?' + query}


@router.get('/callback')
def callback(request: Request, state: str = '', code: str = '', error: str = ''):
    require_account(request)
    if not state or len(state) > 100 or len(code) > 4096:
        raise HTTPException(400, 'The Gmail connection request is invalid or expired.')
    client_id, client_secret, cipher = config()
    with Session() as s:
        record = s.get(OAuthState, security.digest(state))
        if not record or record.user_id != request.state.user.id or record.session_hash != request.state.session.token_hash or record.expires_at <= int(time.time()):
            raise HTTPException(400, 'The Gmail connection request is invalid or expired.')
        epoch=record.connection_epoch
        verifier = cipher.decrypt(record.verifier_encrypted.encode()).decode()
        consumed = s.execute(delete(OAuthState).where(OAuthState.state_hash == record.state_hash, OAuthState.user_id == request.state.user.id, OAuthState.session_hash == request.state.session.token_hash, OAuthState.expires_at > int(time.time()))).rowcount
        s.commit()
        if consumed != 1:
            raise HTTPException(400, 'The Gmail connection request has already been used.')
        if error or not code:
            return RedirectResponse(security.APP_ORIGIN + '/?gmail=cancelled', status_code=303)
        try:
            tokens, expiry = validate_tokens(google('POST', TOKEN_URL, data={'client_id': client_id, 'client_secret': client_secret, 'code': code, 'code_verifier': verifier, 'grant_type': 'authorization_code', 'redirect_uri': security.APP_ORIGIN + '/api/connectors/gmail/callback'}))
            profile = google('GET', API_URL + '/profile', headers={'Authorization': 'Bearer ' + tokens['access_token']})
            email = profile.get('emailAddress')
            if not isinstance(email, str) or len(email) > 254 or '@' not in email:
                raise ValueError('Invalid Gmail profile')
            s.expire_all()
            account=s.scalar(select(User).where(User.id==request.state.user.id).with_for_update())
            if not account or not account.active or account.gmail_epoch!=epoch:
                s.rollback()
                try:google('POST',REVOKE_URL,data={'token':tokens.get('refresh_token') or tokens['access_token']})
                except Exception:pass
                return RedirectResponse(security.APP_ORIGIN+'/?gmail=cancelled',status_code=303)
            existing = s.get(GmailConnection, request.state.user.id)
            if existing:
                s.delete(existing);s.flush()
            s.add(GmailConnection(owner=request.state.user.id, generation=uid(), email=email, tokens_encrypted=cipher.encrypt(json.dumps(tokens).encode()).decode(), expires_at=expiry, locked_until=0))
            s.commit()
        except Exception:
            s.rollback()
            return RedirectResponse(security.APP_ORIGIN + '/?gmail=error', status_code=303)
    return RedirectResponse(security.APP_ORIGIN + '/?gmail=connected', status_code=303)


def plain_body(payload, depth=0):
    """Ignore HTML and attachments; cap decoded message text before parsing."""
    if depth > 5 or not isinstance(payload, dict) or payload.get('filename'):
        return ''
    if payload.get('mimeType') == 'text/plain':
        encoded = payload.get('body', {}).get('data', '')
        if not isinstance(encoded, str) or len(encoded) > 30000:
            return ''
        try:
            raw = base64.b64decode(encoded + '=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
            text = raw.decode('utf-8')
            return text if len(text) <= 20000 else ''
        except (ValueError, UnicodeError):
            return ''
    parts = payload.get('parts', [])
    if not isinstance(parts, list) or len(parts) > 30:
        return ''
    # Gmail MIME nesting is bounded independently from response size.
    text = '\n'.join(plain_body(p, depth + 1) for p in parts if isinstance(p, dict))
    return text if len(text) <= 20000 else ''


@router.post('/import')
def import_mail(payload: GmailImport, request: Request):
    return execute_import(payload, request)


def execute_import(payload, request, expected_generation=None):
    require_account(request)
    client_id, client_secret, cipher = config()
    now = int(time.time())
    with Session() as s:
        security.throttle(s, 'gmail-import:' + request.state.user.id, 5)
        connection = s.get(GmailConnection, request.state.user.id)
        if not connection:
            raise HTTPException(409, 'Connect Gmail before importing messages.')
        generation = connection.generation
        if expected_generation is not None and generation != expected_generation:
            raise HTTPException(409, 'Gmail connection changed. Start a new import.')
        acquired = s.execute(update(GmailConnection).where(GmailConnection.owner == request.state.user.id, GmailConnection.generation == generation, GmailConnection.locked_until <= now).values(locked_until=now + 900)).rowcount
        s.commit()
        if acquired != 1:
            raise HTTPException(409, 'An email import is already in progress. Please try again later.')
        try:
            tokens = json.loads(cipher.decrypt(connection.tokens_encrypted.encode()))
            if connection.expires_at <= now + 30:
                if not tokens.get('refresh_token'):
                    raise ValueError('Reconnect required')
                tokens, expiry = validate_tokens(google('POST', TOKEN_URL, data={'client_id': client_id, 'client_secret': client_secret, 'refresh_token': tokens['refresh_token'], 'grant_type': 'refresh_token'}), tokens)
                s.execute(update(GmailConnection).where(GmailConnection.owner == request.state.user.id, GmailConnection.generation == generation).values(tokens_encrypted=cipher.encrypt(json.dumps(tokens).encode()).decode(), expires_at=expiry));s.commit()
            headers = {'Authorization': 'Bearer ' + tokens['access_token']}
            start=int(datetime.combine(payload.after,datetime.min.time(),ZoneInfo('Asia/Kolkata')).timestamp())
            end=int(datetime.combine(payload.before,datetime.min.time(),ZoneInfo('Asia/Kolkata')).timestamp())
            query = f'after:{start-1} before:{end} {{bank payment transaction refund statement invoice cashback credit debit}}'
            params={'q':query,'maxResults':payload.limit}
            if payload.cursor:
                try:
                    page=json.loads(cipher.decrypt(payload.cursor.encode()))
                    if page.get('purpose')!='gmail-pagination' or page.get('owner')!=request.state.user.id or page.get('generation')!=generation or page.get('query')!=security.digest(query) or page.get('expires_at',0)<=int(time.time()):raise ValueError('Invalid cursor')
                    params['pageToken']=page['token']
                except Exception:raise HTTPException(400,'This email import page expired or belongs to another date range. Start a new import.') from None
            result = google('GET', API_URL + '/messages', headers=headers, params=params)
            ids = result.get('messages', [])
            if not isinstance(ids, list) or len(ids) > payload.limit:
                raise ValueError('Invalid message list')
            import re
            messages = [];skipped = 0
            mailbox = security.digest(connection.email.lower())
            for item in ids:
                message_id = item.get('id') if isinstance(item, dict) else None
                if not isinstance(message_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', message_id):
                    raise ValueError('Invalid Gmail message id')
                mail = google('GET', API_URL + '/messages/' + message_id, headers=headers, params={'format': 'full'})
                body = plain_body(mail.get('payload'))
                # Discard quoted reply tails and reduce retention to the direct message.
                body = '\n'.join(line for line in body.splitlines() if not line.lstrip().startswith('>'))
                body = re.split(r'(?im)^On .+ wrote:|^-----Original Message-----', body)[0].strip()
                if not body:
                    skipped += 1;continue
                received = None
                try:received = datetime.fromtimestamp(int(mail.get('internalDate', 0)) / 1000, timezone.utc) if mail.get('internalDate') else None
                except (ValueError, TypeError, OverflowError):pass
                messages.append(InputMessage(body=body, source='email', source_id='gmail:' + mailbox + ':' + message_id, received_at=received))
            # Never persist a fetched message after the connection was disconnected/replaced.
            s.expire_all()
            account=s.get(User,request.state.user.id)
            session=s.get(AuthSession,request.state.session.token_hash)
            if not account or not account.active or not session or session.expires_at<=int(time.time()) or session.last_seen_at+security.IDLE_SECONDS<=int(time.time()):raise HTTPException(401,'Please sign in again before importing email.')
            current = s.get(GmailConnection, request.state.user.id)
            if not current or current.generation != generation:
                raise HTTPException(409, 'Gmail was disconnected. The import was stopped.')
            next_token=result.get('nextPageToken')
            next_cursor=None
            if next_token:
                if not isinstance(next_token,str) or len(next_token)>2000:raise ValueError('Invalid page token')
                page={'purpose':'gmail-pagination','owner':request.state.user.id,'generation':generation,'query':security.digest(query),'token':next_token,'expires_at':int(time.time())+900}
                next_cursor=cipher.encrypt(json.dumps(page).encode()).decode()
            # Serialize retention with disconnect/data deletion until the batch commits.
            held=s.execute(update(GmailConnection).where(GmailConnection.owner==request.state.user.id,GmailConnection.generation==generation).values(last_success_at=db_now())).rowcount
            if held!=1:raise HTTPException(409,'Gmail connection changed. The import was stopped.')
            job = import_batch(s, messages, request.state.owner, 'rules', commit=False)
            s.execute(update(GmailConnection).where(GmailConnection.owner == request.state.user.id, GmailConnection.generation == generation).values(last_success_at=db_now()));s.commit()
            return {**job, 'fetched': len(ids), 'unsupported_content_skipped': skipped, 'more_available': bool(next_cursor), 'next_cursor': next_cursor, 'processing': 'local rules', 'after': str(payload.after), 'before': str(payload.before)}
        except HTTPException:
            raise
        except Exception:
            s.rollback()
            raise HTTPException(502, 'Gmail could not finish this import. Reconnect or try again; saved messages will not be added twice.') from None
        finally:
            s.execute(update(GmailConnection).where(GmailConnection.owner == request.state.user.id, GmailConnection.generation == generation).values(locked_until=0));s.commit()


@router.delete('/connection')
def disconnect(request: Request):
    require_account(request)
    try:_, _, cipher = config()
    except HTTPException:cipher = None
    with Session() as s:
        connection = s.get(GmailConnection, request.state.user.id)
        s.execute(update(User).where(User.id==request.state.user.id).values(gmail_epoch=User.gmail_epoch+1))
        s.execute(delete(OAuthState).where(OAuthState.user_id == request.state.user.id))
        if not connection:
            s.commit();return {'connected':False,'provider_revoked':False}
        encrypted = connection.tokens_encrypted
        s.delete(connection)
        s.execute(delete(OAuthState).where(OAuthState.user_id == request.state.user.id));s.commit()
    revoked = False
    if cipher:
        try:
            tokens = json.loads(cipher.decrypt(encrypted.encode()))
            google('POST', REVOKE_URL, data={'token': tokens.get('refresh_token') or tokens['access_token']})
            revoked = True
        except httpx.HTTPStatusError as exc:
            revoked = exc.response.status_code == 400
        except Exception:pass
    return {'connected': False, 'provider_revoked': revoked}
