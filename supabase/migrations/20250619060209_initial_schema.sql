CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL,
    embedding VECTOR(768)
);

CREATE OR REPLACE FUNCTION match_documents(
    filter JSONB,
    query_embedding VECTOR(768),
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id,
        documents.content,
        documents.metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
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
