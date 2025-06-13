"""Add default value to match_count in match_documents

Revision ID: 1b34ccca48d6
Revises: 76234f5a370d
Create Date: 2025-06-13 14:10:17.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b34ccca48d6'
down_revision: Union[str, None] = '76234f5a370d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP FUNCTION IF EXISTS match_documents;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            filter jsonb,
            match_count int,
            query_embedding vector(1536)
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
