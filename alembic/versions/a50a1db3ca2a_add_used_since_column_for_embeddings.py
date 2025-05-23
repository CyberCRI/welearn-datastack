"""add_used_since_column_for_embeddings

Revision ID: a50a1db3ca2a
Revises: 4fcbfb7f3145
Create Date: 2025-05-23 16:59:53.290752

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a50a1db3ca2a"
down_revision: Union[str, None] = "4fcbfb7f3145"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "corpus_embedding_model",
        sa.Column(
            "used_since", postgresql.TIMESTAMP(), server_default="NOW()", nullable=False
        ),
        schema="corpus_related",
    )


def downgrade() -> None:
    op.drop_column("corpus_embedding_model", "used_since", schema="corpus_related")
