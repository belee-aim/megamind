from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from megamind.clients.supa_client import get_supabase_client
from ..states import AgentState


def check_cache_node(state: AgentState):
    """
    Checks if the user's documents are already cached.
    """
    print("---CHECKING CACHE---")
    user_id = state["user_id"]
    question = state["question"]

    client = get_supabase_client()
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    vector_store = SupabaseVectorStore(
        client=client,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents",
    )

    documents = vector_store.similarity_search(
        query=question, filter={"user_id": user_id}
    )

    if not documents:
        print(f"No cache found for user {user_id}.")
        return {"documents": []}

    print(f"Found {len(documents)} documents in cache for user {user_id}.")
    return {"documents": documents}

def should_retrieve_from_frappe(state: AgentState) -> str:
    """
    Determines whether to retrieve documents from Frappe or proceed with generation.
    """
    print("---ASSESSING DOCUMENT STATUS---")
    if not state.get("documents"):
        print("---DOCUMENTS NOT FOUND, RETRIEVING FROM FRAPPE---")
        return "retrieve_from_frappe"
    else:
        print("---DOCUMENTS FOUND, SKIPPING FRAPPE---")
        return "process_and_embed"
