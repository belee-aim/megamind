from ..states import AgentState
from langchain_core.documents import Document
from ...clients.frappe_client import FrappeClient

def frappe_retriever_node(state: AgentState):
    """
    Retrieves documents from Frappe Drive.
    """
    print("---RETRIEVING DOCUMENTS FROM FRAPPE DRIVE---")
    user_id = state["user_id"]
    
    frappe_client = FrappeClient()
    files = frappe_client.get_files()
    
    documents = []
    for file in files:
        content = frappe_client.get_file_content(file.get("file_url"))
        if content:
            documents.append(
                Document(
                    page_content=content,
                    metadata={"source": "frappe", "file_name": file.get("file_name")}
                )
            )

    print(f"Retrieved {len(documents)} documents for user {user_id} from Frappe Drive.")
    
    return {"documents": documents}
