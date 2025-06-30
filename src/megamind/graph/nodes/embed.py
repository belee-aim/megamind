from langchain_core.documents import Document
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from megamind.clients.supa_client import get_supabase_client
from megamind.configuration import Configuration
from megamind.utils import get_human_message
from ..states import AgentState


def embed_node(state: AgentState, config: RunnableConfig):
    """
    Processes documents, embeds them, and stores them in a vector store.
    """
    logger.debug("---EMBEDDER NODE---")
    configurable = Configuration.from_runnable_config(config)

    documents = state.get("documents", [])

    if not documents:
        logger.warning("No documents found in the state.")
        return {"documents": []}

    # Clean documents
    for doc in documents:
        doc.page_content = doc.page_content.replace("\x00", "")

    # Chunk documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunked_documents = text_splitter.split_documents(documents)

    logger.info(
        f"---CHUNCKED {len(documents)} into {len(chunked_documents)} documents---"
    )

    # Embed and store documents
    embeddings = GoogleGenerativeAIEmbeddings(model=configurable.embedding_model)
    supabase_client = get_supabase_client()

    vector_store = SupabaseVectorStore.from_documents(
        documents=chunked_documents,
        embedding=embeddings,
        client=supabase_client,
        table_name="documents",
        query_name="match_documents",
    )

    retrieved_documents = []
    human_message = get_human_message(state)

    if not human_message:
        raise ValueError("No human message found in the state.")

    for team_id in state.get("team_ids", []):
        documents = vector_store.similarity_search(
            query=str(human_message.content), filter={"team_id": team_id}
        )
        retrieved_documents.extend(documents)

    return {"documents": retrieved_documents}
