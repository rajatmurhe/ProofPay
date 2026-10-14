"""Account sessions. Credentials never appear in logs or API responses."""
import hashlib
import os
import secrets
import time
from urllib.parse import urlparse
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request
from sqlalchemy import select, delete
from .db import User, AuthSession, RateLimit, DATABASE_URL

ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
AUTH_MODE = os.getenv('AUTH_MODE', 'authenticated')
APP_ORIGIN = os.getenv('LOCAL_WEB_ORIGIN', 'http://127.0.0.1:3017').rstrip('/')
REGISTRATION_ENABLED = os.getenv('ENABLE_REGISTRATION', 'false').lower() == 'true'
SESSION_SECONDS = 7 * 24 * 3600
IDLE_SECONDS = 30 * 60
COOKIE = '__Host-proofpay_session' if ENVIRONMENT == 'production' else 'proofpay_session'
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))

if ENVIRONMENT not in {'development', 'production'} or AUTH_MODE not in {'authenticated', 'demo'}:
    raise RuntimeError('Invalid ENVIRONMENT or AUTH_MODE')
origin = urlparse(APP_ORIGIN)
if origin.path or origin.query or origin.fragment or origin.username or not origin.hostname:
    raise RuntimeError('LOCAL_WEB_ORIGIN must be an origin without a path')
if ENVIRONMENT == 'production' and (AUTH_MODE != 'authenticated' or REGISTRATION_ENABLED or origin.scheme != 'https'):
    raise RuntimeError('Production requires authenticated mode, HTTPS, and registration disabled')
if ENVIRONMENT == 'production' and (not DATABASE_URL.startswith('postgresql') or not os.getenv('ALLOWED_HOSTS') or '*' in os.getenv('ALLOWED_HOSTS','').split(',') or 'testserver' in os.getenv('ALLOWED_HOSTS','').split(',')):
    raise RuntimeError('Production requires PostgreSQL and explicit allowed hosts')
if ENVIRONMENT == 'development' and AUTH_MODE=='demo' and any(h.strip() not in {'localhost','127.0.0.1','testserver'} for h in os.getenv('ALLOWED_HOSTS','127.0.0.1,localhost').split(',')):
    raise RuntimeError('Demo mode must use loopback hosts')
if ENVIRONMENT == 'development' and origin.hostname not in {'localhost', '127.0.0.1'}:
    raise RuntimeError('Development must use a loopback web origin')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(encoded, password):
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def throttle(s, key, limit, window=900):
    """Database-backed bounded counters, shared across API workers."""
    now = int(time.time())
    bucket = now // window
    hashed = digest(key + ':' + str(bucket))
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    insert = sqlite_insert if s.bind.dialect.name == 'sqlite' else pg_insert
    statement = insert(RateLimit).values(key=hashed, attempts=1, expires_at=(bucket + 1) * window)
    statement = statement.on_conflict_do_update(index_elements=['key'], set_={'attempts': RateLimit.attempts + 1}).returning(RateLimit.attempts)
    attempts = s.execute(statement).scalar_one()
    s.execute(delete(RateLimit).where(RateLimit.expires_at < now))
    s.commit()
    if attempts > limit:
        raise HTTPException(429, 'Too many attempts. Please try again later.', headers={'Retry-After': str((bucket + 1) * window - now)})


def authenticate(request, s):
    if AUTH_MODE == 'demo':
        request.state.owner = os.getenv('LOCAL_OWNER', 'local-demo')
        request.state.user = None
        request.state.session = None
        return
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 100:
        raise HTTPException(401, 'Sign in to continue.')
    session = s.get(AuthSession, digest(token))
    now = int(time.time())
    if not session or session.expires_at <= now or session.last_seen_at + IDLE_SECONDS <= now:
        raise HTTPException(401, 'Your session has expired. Please sign in again.')
    user = s.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, 'Sign in to continue.')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        supplied = request.headers.get('x-csrf-token', '')
        if not supplied or not secrets.compare_digest(supplied, session.csrf_token):
            raise HTTPException(403, 'Please refresh the page and try again.')
    if session.last_seen_at + 60 < now:
        session.last_seen_at = now
        s.commit()
    request.state.owner = user.workspace_id
    request.state.user = user
    request.state.session = session


def new_session(s, user, response, previous_token=''):
    now = int(time.time())
    if previous_token:
        s.execute(delete(AuthSession).where(AuthSession.token_hash == digest(previous_token)))
    s.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    session = AuthSession(token_hash=digest(token), user_id=user.id, csrf_token=secrets.token_urlsafe(32), expires_at=now + SESSION_SECONDS, last_seen_at=now)
    s.add(session)
    s.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=ENVIRONMENT == 'production', samesite='lax', path='/')
    return {'authenticated': True, 'user': {'id': user.id, 'email': user.email}, 'csrf_token': session.csrf_token, 'auth_mode': AUTH_MODE, 'registration_enabled': REGISTRATION_ENABLED}
