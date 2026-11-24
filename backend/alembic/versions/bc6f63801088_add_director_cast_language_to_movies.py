"""add_director_cast_language_to_movies

Revision ID: bc6f63801088
Revises: c5693771c7dd
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc6f63801088'
down_revision: Union[str, None] = 'c5693771c7dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('movies', sa.Column('original_language', sa.String(length=10), nullable=True))
    op.add_column('movies', sa.Column('director', sa.String(length=255), nullable=True))
    op.add_column('movies', sa.Column('cast', sa.JSON(), nullable=True))
    op.create_index(op.f('ix_movies_director'), 'movies', ['director'], unique=False)
    op.create_index(op.f('ix_movies_original_language'), 'movies', ['original_language'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_movies_original_language'), table_name='movies')
    op.drop_index(op.f('ix_movies_director'), table_name='movies')
    op.drop_column('movies', 'cast')
    op.drop_column('movies', 'director')
    op.drop_column('movies', 'original_language')