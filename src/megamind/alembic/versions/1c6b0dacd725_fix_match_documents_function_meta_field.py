"""Fix match_documents function meta field

Revision ID: 1c6b0dacd725
Revises: 8d07e2aa2862
Create Date: 2025-06-13 15:56:17.045147

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c6b0dacd725'
down_revision: Union[str, None] = '8d07e2aa2862'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP FUNCTION IF EXISTS match_documents(vector, float, int, jsonb);")
    op.execute("DROP FUNCTION IF EXISTS match_documents;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            filter jsonb,
            query_embedding vector(1536),
            match_count int DEFAULT 5
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
                documents.metadata @> filter
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
            filter jsonb,
            query_embedding vector(1536),
            match_count int DEFAULT 5
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
