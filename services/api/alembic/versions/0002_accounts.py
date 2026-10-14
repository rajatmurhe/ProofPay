"""Accounts, revocable sessions and encrypted Gmail connection storage."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.String,primary_key=True),sa.Column('workspace_id',sa.String,nullable=False,unique=True),sa.Column('email',sa.String,nullable=False),sa.Column('password_hash',sa.String,nullable=False),sa.Column('active',sa.Boolean,nullable=False),sa.Column('created_at',sa.String,nullable=False))
    op.create_index('ix_users_email','users',['email'],unique=True)
    op.create_table('auth_sessions',sa.Column('token_hash',sa.String,primary_key=True),sa.Column('user_id',sa.String,sa.ForeignKey('users.id'),nullable=False),sa.Column('csrf_token',sa.String,nullable=False),sa.Column('expires_at',sa.BigInteger,nullable=False),sa.Column('last_seen_at',sa.BigInteger,nullable=False))
    op.create_index('ix_auth_sessions_user_id','auth_sessions',['user_id'])
    op.create_table('rate_limits',sa.Column('key',sa.String,primary_key=True),sa.Column('attempts',sa.Integer,nullable=False),sa.Column('expires_at',sa.BigInteger,nullable=False))
    op.create_index('ix_rate_limits_expires_at','rate_limits',['expires_at'])
    op.create_table('oauth_states',sa.Column('state_hash',sa.String,primary_key=True),sa.Column('user_id',sa.String,sa.ForeignKey('users.id'),nullable=False),sa.Column('session_hash',sa.String,nullable=False),sa.Column('verifier_encrypted',sa.String,nullable=False),sa.Column('expires_at',sa.BigInteger,nullable=False))
    op.create_index('ix_oauth_states_user_id','oauth_states',['user_id'])
    op.create_index('ix_oauth_states_expires_at','oauth_states',['expires_at'])
    op.create_table('gmail_connections',sa.Column('owner',sa.String,sa.ForeignKey('users.id'),primary_key=True),sa.Column('generation',sa.String,nullable=False),sa.Column('email',sa.String,nullable=False),sa.Column('tokens_encrypted',sa.String,nullable=False),sa.Column('expires_at',sa.BigInteger,nullable=False),sa.Column('locked_until',sa.BigInteger,nullable=False),sa.Column('created_at',sa.String,nullable=False))

def downgrade():
    for table in ['gmail_connections','oauth_states','rate_limits','auth_sessions','users']:op.drop_table(table)
