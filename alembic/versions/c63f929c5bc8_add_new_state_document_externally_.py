"""Add new state: document_externally_classified

Revision ID: c63f929c5bc8
Revises: 4fcbfb7f3145
Create Date: 2025-03-28 16:05:59.572870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c63f929c5bc8'
down_revision: Union[str, None] = '4fcbfb7f3145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_related.step ADD VALUE 'document_externally_classified' AFTER 'document_with_keywords';")

def downgrade() -> None:
    # You cannot really delete a value into enum
    pass