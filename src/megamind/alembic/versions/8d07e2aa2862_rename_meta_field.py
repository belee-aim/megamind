"""Rename meta field

Revision ID: 8d07e2aa2862
Revises: 1b34ccca48d6
Create Date: 2025-06-13 15:50:21.234168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8d07e2aa2862'
down_revision: Union[str, None] = '1b34ccca48d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('documents', 'meta', new_column_name='metadata', existing_type=postgresql.JSONB(astext_type=sa.Text()), existing_nullable=False)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            query_embedding vector(1536),
            match_threshold float,
            match_count int,
            filter jsonb
        )
        RETURNS TABLE (
            id integer,
            content text,
            metadata jsonb,
            similarity float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                documents.id,
                documents.content,
                documents.metadata,
                1 - (documents.embedding <=> query_embedding) as similarity
            FROM
                documents
            WHERE
                1 - (documents.embedding <=> query_embedding) > match_threshold
                AND documents.metadata @> filter
            ORDER BY
                documents.embedding <=> query_embedding
            LIMIT
                match_count;
        END;
        $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('documents', 'metadata', new_column_name='meta', existing_type=postgresql.JSONB(astext_type=sa.Text()), existing_nullable=False)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            query_embedding vector(1536),
            match_threshold float,
            match_count int,
            filter jsonb
        )
        RETURNS TABLE (
            id integer,
            content text,
            meta jsonb,
            similarity float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                documents.id,
                documents.content,
                documents.meta,
                1 - (documents.embedding <=> query_embedding) as similarity
            FROM
                documents
            WHERE
                1 - (documents.embedding <=> query_embedding) > match_threshold
                AND documents.meta @> filter
            ORDER BY
                documents.embedding <=> query_embedding
            LIMIT
                match_count;
        END;
        $$;
        """
    )
