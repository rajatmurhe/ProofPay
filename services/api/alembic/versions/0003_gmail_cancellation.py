"""Invalidate pending/in-flight Gmail consent when the user disconnects."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('gmail_epoch',sa.Integer,nullable=False,server_default='0'))
    op.add_column('oauth_states',sa.Column('connection_epoch',sa.Integer,nullable=False,server_default='0'))

def downgrade():
    op.drop_column('oauth_states','connection_epoch')
    op.drop_column('users','gmail_epoch')
