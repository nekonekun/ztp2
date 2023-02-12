"""init

Revision ID: 3315ffb4cc8b
Revises: 
Create Date: 2023-02-11 01:32:50.772897

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3315ffb4cc8b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('portcount', sa.Integer(), nullable=True),
        sa.Column('configuration_prefix', sa.String(), nullable=True),
        sa.Column('default_initial_config', sa.String(), nullable=True),
        sa.Column('default_full_config', sa.String(), nullable=True),
        sa.Column('firmware', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'),
                  nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status',
                  sa.Enum('WAITING', 'IN_PROGRESS', 'DONE', name='ztp_status'),
                  nullable=True),
        sa.Column('celery_id', sa.String(), nullable=True),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=True),
        sa.Column('serial_number', sa.String(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('mac_address', postgresql.MACADDR(), nullable=False),
        sa.Column('ip_address', postgresql.INET(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('parent_switch', postgresql.INET(), nullable=True),
        sa.Column('parent_port', sa.String(), nullable=True),
        sa.Column('autochange_vlans', sa.Boolean(), nullable=False),
        sa.Column('original_port_settings',
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('port_movements',
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('modified_port_settings',
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('vlan_settings',
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('modified_vlan_settings',
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('entries')
    op.drop_table('models')
