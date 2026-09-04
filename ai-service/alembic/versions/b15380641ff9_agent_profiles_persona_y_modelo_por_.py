"""agent_profiles: persona y modelo por agente

Revision ID: b15380641ff9
Revises: 3d59e9c3abb5
Create Date: 2026-09-04 09:11:33.912626

Autogenerate propuso ADEMAS borrar `checkpoints`, `checkpoint_writes`,
`checkpoint_blobs` y `checkpoint_migrations`: son del `AsyncPostgresSaver` de
LangGraph, que las crea solo en el arranque del servicio y no las declara en
`Base.metadata`. Correr eso habria borrado cada hilo pausado esperando revision
humana. Los `drop_table` se sacaron a mano y `alembic/env.py` ahora las excluye
de la comparacion para que no vuelvan a aparecer.

|| Autogenerate ALSO proposed dropping LangGraph's checkpointer tables, which it
creates itself at startup and does not declare on `Base.metadata`. Running that
would have deleted every thread paused for human review. The drops were removed
by hand and `alembic/env.py` now excludes those tables from the comparison.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b15380641ff9'
down_revision: Union[str, Sequence[str], None] = '3d59e9c3abb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'agent_profiles',
        sa.Column('agent_key', sa.String(length=64), nullable=False),
        sa.Column('persona', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=64), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('agent_key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('agent_profiles')
