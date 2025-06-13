"""Fix match_documents function signature

Revision ID: efaf07cb80ac
Revises: ea1b10bb8434
Create Date: 2025-06-13 12:47:00.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efaf07cb80ac'
down_revision: Union[str, None] = 'ea1b10bb8434'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP FUNCTION IF EXISTS match_documents;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            query_embedding vector(1536),
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
                documents.meta,
                1 - (documents.embedding <=> query_embedding) as similarity
            FROM
                documents
            WHERE
                documents.meta @> filter
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
    op.execute("DROP FUNCTION IF EXISTS match_documents;")
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
