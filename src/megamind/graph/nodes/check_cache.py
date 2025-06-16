from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from megamind.clients.supa_client import get_supabase_client
from megamind.configuration import Configuration
from ..states import AgentState
from ...clients.frappe_client import FrappeClient


def check_cache_node(state: AgentState, config: RunnableConfig):
    """
    Checks if the user's documents are already cached.
    """
    print("---CHECKING CACHE---")
    configurable = Configuration.from_runnable_config(config)
    question = state["question"]

    frappe_client = FrappeClient()
    teams = frappe_client.get_teams()
    team_ids = [team.get("name") for team in teams.values()]
    state["team_ids"] = team_ids

    client = get_supabase_client()
    embeddings = GoogleGenerativeAIEmbeddings(model=configurable.embedding_model)

    vector_store = SupabaseVectorStore(
        client=client,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents",
    )

    all_documents = []
    for team_id in team_ids:
        documents = vector_store.similarity_search(
            query=question, filter={"team_id": team_id}
        )
        all_documents.extend(documents)

    if not all_documents:
        print(f"No cache found for teams {team_ids}.")
        return {"documents": [], "team_ids": team_ids}

    print(f"Found {len(all_documents)} documents in cache for teams {team_ids}.")
    return {"documents": all_documents, "team_ids": team_ids}

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
        return "generate"
