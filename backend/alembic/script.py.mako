"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

WordPress equivalent: This migration file is like a wp_upgrade() step,
but versioned and reversible. Each file represents a single schema change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Apply this migration — move the schema forward."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Reverse this migration — roll back to the previous state."""
    ${downgrades if downgrades else "pass"}
