import tempfile
from typing import Annotated

from loguru import logger
from pydantic import BaseModel, Field
from megamind.clients.frappe_client import FrappeClient
from langchain_core.tools import tool, ToolException, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_docling.loader import DoclingLoader
from langgraph.types import Command

SUPPORTED_MIMETYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/markdown",
    "text/asciidoc",
    "text/html",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
]

class FrappeRetrieverSchema(BaseModel):
    """
    Retrieves team documents from Frappe Drive.
    """
    tool_call_id: Annotated[str, InjectedToolCallId]
    team_ids: list[str] = Field(description="List of team IDs to retrieve documents from Frappe Drive.")

@tool(args_schema=FrappeRetrieverSchema)
def frappe_retriever(tool_call_id, team_ids):
    logger.debug("---FRAPPE RETRIEVER TOOL---")
    
    try:
        frappe_client = FrappeClient()
        
        documents = []
        for team_id in team_ids:
            files = frappe_client.get_files(team=team_id)
            for file in files:
                if file.get("mime_type") in SUPPORTED_MIMETYPES:
                    file_path = file.get("path", "")
                    file_extension = f".{file_path.split('.')[-1]}" if "." in file_path else ""
                    try:
                        raw_content = frappe_client.get_file_content(file.get("name"))
                        if raw_content:
                            file_path = file.get("path", "")
                            file_extension = f".{file_path.split('.')[-1]}" if "." in file_path else ""
                            temp_file_path = None
                            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                                temp_file.write(raw_content)
                                temp_file_path = temp_file.name
                            
                            loader = DoclingLoader(temp_file_path)
                            loaded_documents = loader.load()
                            for doc in loaded_documents:
                                doc.metadata["source"] = "frappe/drive"
                                doc.metadata["file_name"] = file.get("name")
                                doc.metadata["team_id"] = team_id
                            documents.extend(loaded_documents)
                    except Exception as e:
                        logger.error(f"Error processing file {file.get('name')}: {e}")
                        continue
    except Exception as e:
        raise ToolException(f"Failed to retrieve documents from Frappe Drive: {e}")

    return Command(update={"documents": documents, "messages": [ToolMessage("Retrieved documents from Frappe Drive.", tool_call_id=tool_call_id)]})
