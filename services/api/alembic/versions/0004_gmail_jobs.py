"""Durable Gmail tasks and last successful import timestamp."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
 op.add_column('gmail_connections',sa.Column('last_success_at',sa.String(),nullable=True))
 op.create_table('gmail_import_tasks',sa.Column('id',sa.String(),primary_key=True),sa.Column('user_id',sa.String(),sa.ForeignKey('users.id'),nullable=False),sa.Column('session_hash',sa.String(),nullable=False),sa.Column('generation',sa.String(),nullable=False),sa.Column('active_key',sa.String(),nullable=True,unique=True),sa.Column('parameters',sa.JSON(),nullable=False),sa.Column('status',sa.String(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('available_at',sa.BigInteger(),nullable=False),sa.Column('lease_until',sa.BigInteger(),nullable=False),sa.Column('result',sa.JSON(),nullable=True),sa.Column('error',sa.String(),nullable=True),sa.Column('created_at',sa.String(),nullable=False),sa.Column('finished_at',sa.String(),nullable=True))
 op.create_index('ix_gmail_import_tasks_user_id','gmail_import_tasks',['user_id'])

def downgrade():
 op.drop_table('gmail_import_tasks');op.drop_column('gmail_connections','last_success_at')
