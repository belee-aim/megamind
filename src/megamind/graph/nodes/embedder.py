from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from megamind.clients.supa_client import get_supabase_client
from megamind.configuration import Configuration
from ..states import AgentState

def embedder_node(state: AgentState, config: RunnableConfig):
    """
    Processes documents, embeds them, and stores them in a vector store.
    """
    configurable = Configuration.from_runnable_config(config)
    documents = state["documents"]
    
    # Clean documents
    for doc in documents:
        doc.page_content = doc.page_content.replace("\x00", "")

    # Chunk documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunked_documents = text_splitter.split_documents(documents)
    
    print(f"---CHUNCKED {len(documents)} into {len(chunked_documents)} documents---")

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
    
    return {"vector_store": vector_store}
