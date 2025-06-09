from ..state import AgentState

def check_cache_node(state: AgentState):
    """
    Checks if the user's documents are already cached.
    For now, this is a placeholder.
    """
    print("---CHECKING CACHE---")
    user_id = state["user_id"]
    
    # Placeholder logic: Assume documents are not cached
    print(f"No cache found for user {user_id}.")
    return {"documents": []}

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
