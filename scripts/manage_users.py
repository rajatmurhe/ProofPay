"""Local operator CLI. Prompts for passwords; never accepts them in arguments."""
import argparse
import getpass
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from sqlalchemy import select, delete
from app.db import Session, User, AuthSession, OAuthState, Event, Message, Job, Audit, Relationship
from app.security import HASHER
from app.schema import Credentials
from pydantic import ValidationError

def validate(email,password):
    try:return Credentials(email=email,password=password)
    except ValidationError:raise SystemExit('Use a valid email and a password of 12 to 128 characters.') from None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','reset-password','disable','adopt-demo'])
    parser.add_argument('--email',required=True)
    args=parser.parse_args()
    email=args.email.lower()
    with Session() as s:
        user=s.scalar(select(User).where(User.email==email))
        if args.action=='create':
            if user:raise SystemExit('Account already exists.')
            password=getpass.getpass('Password (at least 12 characters): ')
            if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
            credentials=validate(email,password)
            user=User(email=credentials.email,password_hash=HASHER.hash(credentials.password));s.add(user)
        elif not user:raise SystemExit('Account not found.')
        elif args.action=='reset-password':
            password=getpass.getpass('New password (at least 12 characters): ')
            if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match.')
            credentials=validate(email,password);user.password_hash=HASHER.hash(credentials.password)
        elif args.action=='disable':user.active=False
        elif args.action=='adopt-demo':
            legacy=os.getenv('LOCAL_OWNER','local-demo')
            if s.scalar(select(User).where(User.workspace_id==legacy)):raise SystemExit('Demo workspace already belongs to an account.')
            for model in [Event,Message,Job,Audit,Relationship]:
                if s.scalar(select(model).where(model.owner==user.workspace_id)):raise SystemExit('Target account already has financial records; refusing to replace its workspace.')
            user.workspace_id=legacy
            s.add(Audit(owner=legacy,event_id='account:'+user.id,data={'origin':'administrator workspace assignment','reason':'Explicit local CLI adoption of demo workspace'}))
        if args.action!='create':
            s.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
            s.execute(delete(OAuthState).where(OAuthState.user_id==user.id))
        s.commit()
        print('Account action completed. Existing sessions were revoked where applicable.')
if __name__=='__main__':main()
