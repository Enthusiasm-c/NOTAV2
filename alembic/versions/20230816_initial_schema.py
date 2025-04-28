"""Update models structure

Revision ID: 20250428_update_models
Revises: 
Create Date: 2025-04-28 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250428_update_models'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаем новую таблицу product_name_lookup
    op.create_table('product_name_lookup',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('alias', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_name_lookup_product_id'), 'product_name_lookup', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_name_lookup_alias'), 'product_name_lookup', ['alias'], unique=False)
    
    # Добавляем обновленные индексы в существующие таблицы
    op.create_index(op.f('ix_invoice_items_invoice_id'), 'invoice_items', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_invoice_items_product_id'), 'invoice_items', ['product_id'], unique=False)


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index(op.f('ix_invoice_items_product_id'), table_name='invoice_items')
    op.drop_index(op.f('ix_invoice_items_invoice_id'), table_name='invoice_items')
    op.drop_index(op.f('ix_product_name_lookup_alias'), table_name='product_name_lookup')
    op.drop_index(op.f('ix_product_name_lookup_product_id'), table_name='product_name_lookup')
    
    # Удаляем таблицу
    op.drop_table('product_name_lookup')
