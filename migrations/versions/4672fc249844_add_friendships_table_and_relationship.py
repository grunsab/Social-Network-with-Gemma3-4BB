"""Add friendships table and relationship

Revision ID: 4672fc249844
Revises: e7955ad878ba
Create Date: 2025-05-03 23:35:46.491861

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4672fc249844'
down_revision = 'e7955ad878ba'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('friendships',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('friend_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['friend_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'friend_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('friendships')
    # ### end Alembic commands ###
