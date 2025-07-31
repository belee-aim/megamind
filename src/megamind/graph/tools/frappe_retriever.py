import tempfile
from typing import Annotated

from loguru import logger
from pydantic import BaseModel, Field
from megamind.clients.frappe_client import FrappeClient
from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import InjectedState
from megamind.graph.states import AgentState
from megamind.utils.parser import Parser


class FrappeRetrieverSchema(BaseModel):
    """
    Retrieves team documents from Frappe Drive.
    """

    state: Annotated[AgentState, InjectedState]
    team_ids: list[str] = Field(
        description="List of team IDs to retrieve documents from Frappe Drive."
    )


@tool(args_schema=FrappeRetrieverSchema)
def frappe_retriever(state, team_ids):
    logger.debug("---FRAPPE RETRIEVER TOOL---")

    try:
        cookie = state.get("cookie")
        frappe_client = FrappeClient(cookie=cookie)

        parser = Parser()
        documents = []
        for team_id in team_ids:
            files = frappe_client.get_files(team=team_id)
            for file in files:
                file_path = file.get("path", "")
                file_extension = (
                    f".{file_path.split('.')[-1]}" if "." in file_path else ""
                )
                try:
                    raw_content = frappe_client.get_file_content(file.get("name"))
                    if raw_content:
                        file_path = file.get("path", "")
                        file_extension = (
                            f".{file_path.split('.')[-1]}" if "." in file_path else ""
                        )
                        temp_file_path = None
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=file_extension
                        ) as temp_file:
                            temp_file.write(raw_content)
                            temp_file_path = temp_file.name

                        loaded_documents = parser.parse_file(temp_file_path)
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

    return documents
