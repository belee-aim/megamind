"""Increase embedding dimension

Revision ID: 9c749913d234
Revises: 1c6b0dacd725
Create Date: 2025-06-13 17:51:12.253332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '9c749913d234'
down_revision: Union[str, None] = '1c6b0dacd725'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('documents', 'embedding', type_=Vector(768), existing_type=Vector(1536), existing_nullable=True)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            query_embedding vector(768),
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
    op.alter_column('documents', 'embedding', type_=Vector(1536), existing_type=Vector(768), existing_nullable=True)
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
