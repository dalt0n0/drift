"""add organizations table and engagement.organization_id

Revision ID: 005
Revises: 004
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('website', sa.String(512), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_organizations_created_by', 'organizations', ['created_by'])

    # Add organization_id to engagements
    op.add_column('engagements', sa.Column('organization_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_engagements_organization_id',
        'engagements', 'organizations',
        ['organization_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_engagements_organization_id', 'engagements', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_engagements_organization_id', 'engagements')
    op.drop_constraint('fk_engagements_organization_id', 'engagements', type_='foreignkey')
    op.drop_column('engagements', 'organization_id')
    op.drop_index('ix_organizations_created_by', 'organizations')
    op.drop_table('organizations')
