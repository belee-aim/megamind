from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from loguru import logger

from megamind.clients.supa_client import get_supabase_client
from megamind.configuration import Configuration
from megamind.graph.states import AgentState
from megamind.clients.frappe_client import FrappeClient
from megamind.utils import get_human_message


def check_cache_node(state: AgentState, config: RunnableConfig):
    """
    Checks if the user's documents are already cached.
    """
    logger.debug("---CHECK CACHE NODE---")
    configurable = Configuration.from_runnable_config(config)

    human_message = get_human_message(state)

    if not human_message:
        raise ValueError("No human message found in the state.")

    cookie = state.get("cookie")
    frappe_client = FrappeClient(cookie=cookie)
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
            query=str(human_message.content), filter={"team_id": team_id}
        )
        all_documents.extend(documents)

    if not all_documents:
        logger.warning(f"No cache found for teams {team_ids}.")
        return {"documents": [], "team_ids": team_ids}

    return {"documents": all_documents, "team_ids": team_ids}
