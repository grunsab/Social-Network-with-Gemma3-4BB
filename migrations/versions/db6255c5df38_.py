"""empty message

Revision ID: db6255c5df38
Revises: db0b9244e094
Create Date: 2025-05-05 22:48:25.325289

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db6255c5df38'
down_revision = 'db0b9244e094'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('post_category_score', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_post_category_score_post_id_post', 'post', ['post_id'], ['id'], ondelete='CASCADE')

    # Step 1: Add email column as nullable
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))

    # Step 2: Populate existing rows with unique placeholder emails
    # Use CAST(id AS TEXT) for compatibility, especially with PostgreSQL if used later.
    op.execute("UPDATE \"user\" SET email = 'user_' || CAST(id AS TEXT) || '@example.com' WHERE email IS NULL")

    # Step 3: Apply NOT NULL and UNIQUE constraints
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('email', nullable=False)
        batch_op.create_unique_constraint('uq_user_email', ['email'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Drop constraints and column in reverse order of application
        batch_op.drop_constraint('uq_user_email', type_='unique')
        batch_op.drop_column('email')

    with op.batch_alter_table('post_category_score', schema=None) as batch_op:
        batch_op.drop_constraint('fk_post_category_score_post_id_post', type_='foreignkey')
        batch_op.create_foreign_key(None, 'post', ['post_id'], ['id']) # Recreate original FK (assuming unnamed)

    # ### end Alembic commands ###
