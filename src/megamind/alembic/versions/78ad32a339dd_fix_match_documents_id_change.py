"""Fix match_documents id change

Revision ID: 78ad32a339dd
Revises: 41f22c4d521a
Create Date: 2025-06-13 18:12:51.241849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78ad32a339dd'
down_revision: Union[str, None] = '41f22c4d521a'
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
            query_embedding vector(768),
            match_count int DEFAULT 5
        )
        RETURNS TABLE (
            id uuid,
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
