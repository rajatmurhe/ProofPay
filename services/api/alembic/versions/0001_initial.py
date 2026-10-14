"""Initial owner-scoped financial domain."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('jobs',sa.Column('id',sa.String,primary_key=True),sa.Column('owner',sa.String,nullable=False),sa.Column('status',sa.String,nullable=False),sa.Column('counts',sa.JSON,nullable=False),sa.Column('created_at',sa.String,nullable=False))
    op.create_table('events',sa.Column('id',sa.String,primary_key=True),sa.Column('owner',sa.String,nullable=False),sa.Column('data',sa.JSON,nullable=False))
    op.create_table('messages',sa.Column('id',sa.String,primary_key=True),sa.Column('owner',sa.String,nullable=False),sa.Column('fingerprint',sa.String,nullable=False),sa.Column('source',sa.String,nullable=False),sa.Column('received_at',sa.String),sa.Column('job_id',sa.String,sa.ForeignKey('jobs.id'),nullable=False),sa.Column('evidence',sa.JSON,nullable=False),sa.Column('mode',sa.String,nullable=False),sa.UniqueConstraint('owner','fingerprint'))
    op.create_table('message_events',sa.Column('message_id',sa.String,sa.ForeignKey('messages.id'),primary_key=True),sa.Column('event_id',sa.String,sa.ForeignKey('events.id'),primary_key=True))
    op.create_table('relationships',sa.Column('id',sa.String,primary_key=True),sa.Column('owner',sa.String,nullable=False),sa.Column('left_id',sa.String,sa.ForeignKey('events.id'),nullable=False),sa.Column('right_id',sa.String,sa.ForeignKey('events.id'),nullable=False),sa.Column('kind',sa.String,nullable=False),sa.Column('status',sa.String,nullable=False),sa.Column('reason',sa.String,nullable=False))
    op.create_table('corrections',sa.Column('id',sa.String,primary_key=True),sa.Column('owner',sa.String,nullable=False),sa.Column('event_id',sa.String,nullable=False),sa.Column('data',sa.JSON,nullable=False),sa.Column('created_at',sa.String,nullable=False))
    for table in ['jobs','events','messages','relationships','corrections']:op.create_index('ix_'+table+'_owner',table,['owner'])
def downgrade():
    for table in ['corrections','relationships','message_events','messages','events','jobs']:op.drop_table(table)
