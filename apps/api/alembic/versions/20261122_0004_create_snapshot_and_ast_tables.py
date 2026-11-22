"""Create snapshot and AST tables for Module 3.2

Revision ID: 20261122_0004
Revises: 20261122_0003
Create Date: 2026-11-22 12:35:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20261122_0004'
down_revision: Union[str, None] = '20261122_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. snapshots
    op.create_table(
        'snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=False),
        sa.Column('branch', sa.String(length=255), nullable=False, server_default='main'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_lines', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'commit_sha', name='uq_snapshot_repo_commit')
    )
    op.create_index(op.f('ix_snapshots_repository_id'), 'snapshots', ['repository_id'], unique=False)
    op.create_index(op.f('ix_snapshots_commit_sha'), 'snapshots', ['commit_sha'], unique=False)
    op.create_index(op.f('ix_snapshots_status'), 'snapshots', ['status'], unique=False)

    # 2. repo_files
    op.create_table(
        'repo_files',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('snapshot_id', sa.UUID(), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('extension', sa.String(length=32), nullable=True),
        sa.Column('language', sa.String(length=64), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('line_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['snapshot_id'], ['snapshots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_id', 'path', name='uq_repo_file_snapshot_path')
    )
    op.create_index(op.f('ix_repo_files_snapshot_id'), 'repo_files', ['snapshot_id'], unique=False)
    op.create_index(op.f('ix_repo_files_path'), 'repo_files', ['path'], unique=False)
    op.create_index(op.f('ix_repo_files_filename'), 'repo_files', ['filename'], unique=False)
    op.create_index(op.f('ix_repo_files_language'), 'repo_files', ['language'], unique=False)

    # 3. symbols
    op.create_table(
        'symbols',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('qualified_name', sa.String(length=512), nullable=False),
        sa.Column('kind', sa.String(length=64), nullable=False),
        sa.Column('scope', sa.String(length=255), nullable=True),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('start_column', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('end_column', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('docstring', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['repo_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_symbols_file_id'), 'symbols', ['file_id'], unique=False)
    op.create_index(op.f('ix_symbols_name'), 'symbols', ['name'], unique=False)
    op.create_index(op.f('ix_symbols_qualified_name'), 'symbols', ['qualified_name'], unique=False)
    op.create_index(op.f('ix_symbols_kind'), 'symbols', ['kind'], unique=False)

    # 4. imports
    op.create_table(
        'imports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.Column('source_module', sa.String(length=512), nullable=False),
        sa.Column('imported_symbol', sa.String(length=255), nullable=True),
        sa.Column('alias', sa.String(length=255), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['repo_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_imports_file_id'), 'imports', ['file_id'], unique=False)
    op.create_index(op.f('ix_imports_source_module'), 'imports', ['source_module'], unique=False)

    # 5. code_chunks
    op.create_table(
        'code_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.Column('symbol_id', sa.UUID(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.String(length=64), nullable=False, server_default='CODE'),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['repo_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_code_chunks_file_id'), 'code_chunks', ['file_id'], unique=False)
    op.create_index(op.f('ix_code_chunks_symbol_id'), 'code_chunks', ['symbol_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_code_chunks_symbol_id'), table_name='code_chunks')
    op.drop_index(op.f('ix_code_chunks_file_id'), table_name='code_chunks')
    op.drop_table('code_chunks')

    op.drop_index(op.f('ix_imports_source_module'), table_name='imports')
    op.drop_index(op.f('ix_imports_file_id'), table_name='imports')
    op.drop_table('imports')

    op.drop_index(op.f('ix_symbols_kind'), table_name='symbols')
    op.drop_index(op.f('ix_symbols_qualified_name'), table_name='symbols')
    op.drop_index(op.f('ix_symbols_name'), table_name='symbols')
    op.drop_index(op.f('ix_symbols_file_id'), table_name='symbols')
    op.drop_table('symbols')

    op.drop_index(op.f('ix_repo_files_language'), table_name='repo_files')
    op.drop_index(op.f('ix_repo_files_filename'), table_name='repo_files')
    op.drop_index(op.f('ix_repo_files_path'), table_name='repo_files')
    op.drop_index(op.f('ix_repo_files_snapshot_id'), table_name='repo_files')
    op.drop_table('repo_files')

    op.drop_index(op.f('ix_snapshots_status'), table_name='snapshots')
    op.drop_index(op.f('ix_snapshots_commit_sha'), table_name='snapshots')
    op.drop_index(op.f('ix_snapshots_repository_id'), table_name='snapshots')
    op.drop_table('snapshots')
