from typing import List
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document

def get_human_message(state):
    """
    Extracts the first human message from the state.
    """
    for message in state.get("messages", []):
        if isinstance(message, HumanMessage):
            return message

    return None

def clean_documents(documents: List[Document]):
    """
    Cleans the documents by removing null characters.
    """
    for doc in documents:
        if hasattr(doc, 'page_content'):
            doc.page_content = doc.page_content.replace("\x00", "")

    return documents