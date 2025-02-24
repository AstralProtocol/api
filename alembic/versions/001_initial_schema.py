"""Initial schema.

Revision ID: 001
Create Date: 2025-02-24 12:00:00.000000

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables."""
    # Create users table
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default="user"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
    )

    # Create chain table
    op.create_table(
        "chain",
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("chain", sa.String(), nullable=False),
        sa.Column("rpc", postgresql.JSONB(), nullable=False),
        sa.Column("faucets", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("native_currency", postgresql.JSONB(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("info_url", sa.String(), nullable=True),
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("network_id", sa.Integer(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("explorers", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("chain_id", name=op.f("pk_chain")),
    )

    # Create address table
    op.create_table(
        "address",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("digital_signature", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_address_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_address")),
        sa.UniqueConstraint("address", name=op.f("uq_address_address")),
    )

    # Create location_proof table
    op.create_table(
        "location_proof",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("schema", sa.String(), nullable=False),
        sa.Column("event_timestamp", sa.BigInteger(), nullable=False),
        sa.Column("expiration_time", sa.BigInteger(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("revocation_time", sa.BigInteger(), nullable=True),
        sa.Column("ref_uid", sa.String(), nullable=True),
        sa.Column("revocable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("srs", sa.String(), nullable=False),
        sa.Column("location_type", sa.String(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(srid=4326),
            nullable=False,
        ),
        sa.Column("recipe_type", sa.String(), nullable=False),
        sa.Column("recipe_payload", postgresql.JSONB(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("media_data", sa.String(), nullable=False),
        sa.Column("memo", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("transaction_hash", sa.String(), nullable=True),
        sa.Column("cid", sa.String(), nullable=True),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("attester_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["attester_id"],
            ["address.id"],
            name=op.f("fk_location_proof_attester_id_address"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chain_id"],
            ["chain.chain_id"],
            name=op.f("fk_location_proof_chain_id_chain"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["address.id"],
            name=op.f("fk_location_proof_recipient_id_address"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location_proof")),
        sa.UniqueConstraint("uid", name=op.f("uq_location_proof_uid")),
    )

    # Create indexes
    op.create_index(op.f("ix_address_address"), "address", ["address"], unique=True)
    op.create_index(op.f("ix_address_user_id"), "address", ["user_id"], unique=False)
    op.create_index(op.f("ix_chain_chain_id"), "chain", ["chain_id"], unique=False)
    op.create_index(
        op.f("ix_location_proof_attester_id"),
        "location_proof",
        ["attester_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_proof_chain_id"),
        "location_proof",
        ["chain_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_proof_recipient_id"),
        "location_proof",
        ["recipient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_proof_uid"), "location_proof", ["uid"], unique=True
    )
    op.create_index(op.f("ix_user_id"), "user", ["id"], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index(op.f("ix_user_id"), table_name="user")
    op.drop_index(op.f("ix_location_proof_uid"), table_name="location_proof")
    op.drop_index(op.f("ix_location_proof_recipient_id"), table_name="location_proof")
    op.drop_index(op.f("ix_location_proof_chain_id"), table_name="location_proof")
    op.drop_index(op.f("ix_location_proof_attester_id"), table_name="location_proof")
    op.drop_index(op.f("ix_chain_chain_id"), table_name="chain")
    op.drop_index(op.f("ix_address_user_id"), table_name="address")
    op.drop_index(op.f("ix_address_address"), table_name="address")
    op.drop_table("location_proof")
    op.drop_table("address")
    op.drop_table("chain")
    op.drop_table("user")
