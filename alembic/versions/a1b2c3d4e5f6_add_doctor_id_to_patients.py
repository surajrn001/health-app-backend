"""Add doctor_id foreign key to patients

Revision ID: a1b2c3d4e5f6
Revises: 09e4ce24e6e2
Create Date: 2026-09-28 09:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '09e4ce24e6e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('doctor_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_patients_doctor_id'), ['doctor_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_patients_doctor_id_doctors',
            'doctors',
            ['doctor_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_patients_doctor_id_doctors', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_patients_doctor_id'))
        batch_op.drop_column('doctor_id')
