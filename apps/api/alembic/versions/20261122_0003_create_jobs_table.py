"""Create jobs table for repository cloning and ingestion

Revision ID: 20261122_0003
Revises: 20261122_0002
Create Date: 2026-11-22 10:45:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20261122_0003'
down_revision: Union[str, None] = '20261122_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('job_type', sa.String(length=32), nullable=False, server_default='CLONE'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='QUEUED'),
        sa.Column('stage', sa.String(length=32), nullable=False, server_default='VALIDATING'),
        sa.Column('retrieval_method', sa.String(length=32), nullable=False, server_default='GIT_CLONE'),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('progress_message', sa.Text(), nullable=True),
        sa.Column('branch', sa.String(length=255), nullable=False, server_default='main'),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('bytes_downloaded', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=True),
        sa.Column('files_discovered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('files_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('files_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('files_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retryable', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('workspace_path', sa.String(length=1024), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_jobs_repository_id'), 'jobs', ['repository_id'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)
    op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_created_at'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_repository_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_user_id'), table_name='jobs')
    op.drop_table('jobs')
