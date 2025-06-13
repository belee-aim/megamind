from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from megamind.clients.supa_client import get_supabase_client
from ..states import AgentState

def embedder_node(state: AgentState):
    """
    Processes documents, embeds them, and stores them in a vector store.
    """
    print("---PROCESSING AND EMBEDDING DOCUMENTS---")
    documents = state["documents"]
    
    # Chunk documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunked_documents = text_splitter.split_documents(documents)
    
    print(f"---CHUNCKED {len(documents)} into {len(chunked_documents)} documents---")

    # Embed and store documents
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    supabase_client = get_supabase_client()
    
    vector_store = SupabaseVectorStore.from_documents(
        documents=chunked_documents,
        embedding=embeddings,
        client=supabase_client,
        table_name="documents",
        query_name="match_documents",
    )
    
    print("---DOCUMENTS EMBEDDED AND STORED---")
    return {"vector_store": vector_store}
