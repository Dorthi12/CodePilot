"""Create repositories, repository_permissions, and repository_imports tables

Revision ID: 20261122_0002
Revises: 20261121_0001
Create Date: 2026-11-22 00:55:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20261122_0002'
down_revision: Union[str, None] = '20261121_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create repositories table
    op.create_table(
        'repositories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('owner_user_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='github'),
        sa.Column('provider_repo_id', sa.String(length=64), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('canonical_url', sa.String(length=1024), nullable=False),
        sa.Column('visibility', sa.String(length=32), nullable=False, server_default='PUBLIC'),
        sa.Column('default_branch', sa.String(length=255), nullable=False, server_default='main'),
        sa.Column('tracked_branch', sa.String(length=255), nullable=False, server_default='main'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=128), nullable=True),
        sa.Column('stargazers_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('forks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('open_issues_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('size_kb', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('analysis_status', sa.String(length=32), nullable=False, server_default='NOT_ANALYZED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_user_id', 'provider', 'provider_repo_id', name='uq_user_provider_repo')
    )
    op.create_index(op.f('ix_repositories_owner_user_id'), 'repositories', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_repositories_provider_repo_id'), 'repositories', ['provider_repo_id'], unique=False)
    op.create_index(op.f('ix_repositories_owner'), 'repositories', ['owner'], unique=False)
    op.create_index(op.f('ix_repositories_name'), 'repositories', ['name'], unique=False)

    # 2. Create repository_permissions table
    op.create_table(
        'repository_permissions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='OWNER'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'user_id', name='uq_repo_user_permission')
    )
    op.create_index(op.f('ix_repository_permissions_repository_id'), 'repository_permissions', ['repository_id'], unique=False)
    op.create_index(op.f('ix_repository_permissions_user_id'), 'repository_permissions', ['user_id'], unique=False)

    # 3. Create repository_imports table
    op.create_table(
        'repository_imports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='github'),
        sa.Column('provider_repo_id', sa.String(length=64), nullable=True),
        sa.Column('repo_name', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='SUCCEEDED'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_repository_imports_user_id'), 'repository_imports', ['user_id'], unique=False)
    op.create_index(op.f('ix_repository_imports_repository_id'), 'repository_imports', ['repository_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_repository_imports_repository_id'), table_name='repository_imports')
    op.drop_index(op.f('ix_repository_imports_user_id'), table_name='repository_imports')
    op.drop_table('repository_imports')
    op.drop_index(op.f('ix_repository_permissions_user_id'), table_name='repository_permissions')
    op.drop_index(op.f('ix_repository_permissions_repository_id'), table_name='repository_permissions')
    op.drop_table('repository_permissions')
    op.drop_index(op.f('ix_repositories_name'), table_name='repositories')
    op.drop_index(op.f('ix_repositories_owner'), table_name='repositories')
    op.drop_index(op.f('ix_repositories_provider_repo_id'), table_name='repositories')
    op.drop_index(op.f('ix_repositories_owner_user_id'), table_name='repositories')
    op.drop_table('repositories')
