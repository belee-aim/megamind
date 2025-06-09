from ..state import AgentState
from langchain_core.documents import Document

def frappe_retriever_node(state: AgentState):
    """
    Retrieves documents from Frappe Drive.
    For now, this is a placeholder.
    """
    print("---RETRIEVING DOCUMENTS FROM FRAPPE DRIVE---")
    user_id = state["user_id"]
    
    # Placeholder logic: Return dummy documents
    print(f"Retrieving documents for user {user_id} from Frappe Drive.")
    documents = [
        Document(page_content="This is a test document from Frappe Drive.", metadata={"source": "frappe"}),
        Document(page_content="This is another test document from Frappe Drive.", metadata={"source": "frappe"}),
    ]
    
    return {"documents": documents}
