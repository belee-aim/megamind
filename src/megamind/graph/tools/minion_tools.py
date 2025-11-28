from langchain_core.tools import tool
from megamind.clients.minion_client import MinionClient
from megamind.utils.config import settings


@tool
async def search_role_permissions(query: str):
    """
    Searches for role permissions in the Minion service.
    """
    client = MinionClient(settings.minion_api_url)
    return await client.search_role_permissions(query)


@tool
async def search_document(query: str):
    """
    Searches for documents in the Minion service.
    """
    client = MinionClient(settings.minion_api_url)
    return await client.search_document(query)


@tool
async def search_wiki(query: str):
    """
    Searches for knowledge in Company's Wiki in the Minion service.
    """
    client = MinionClient(settings.minion_api_url)
    return await client.search_wiki(query)


@tool
async def search_processes(query: str, top_k: int = 5) -> str:
    """
    Search for business processes using natural language.

    Use this when users ask about business processes, workflows, or procedures.
    Returns matching processes ranked by relevance.

    Args:
        query: Natural language search query describing the process you're looking for
        top_k: Number of results to return (default: 5)

    Returns:
        Ranked list of business processes matching the query
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.search_processes(query, top_k)
    return str(result)


@tool
async def search_workflows(query: str, top_k: int = 5) -> str:
    """
    Search for workflows using natural language.

    Use this when users ask about approval workflows, state transitions, or workflow definitions.
    Returns matching workflows ranked by relevance.

    Args:
        query: Natural language search query describing the workflow
        top_k: Number of results to return (default: 5)

    Returns:
        Ranked list of workflows matching the query
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.search_workflows(query, top_k)
    return str(result)


@tool
async def get_process_definition(process_name: str) -> str:
    """
    Get complete definition of a business process including all steps, conditions, and triggers.

    Use this when you need detailed information about a specific business process.

    Args:
        process_name: Name of the business process

    Returns:
        Complete process definition with all details
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.get_process(process_name)
    return str(result)


@tool
async def get_workflow_definition(workflow_name: str) -> str:
    """
    Get complete definition of a workflow including states, transitions, and role requirements.

    Use this when you need to understand workflow approval chains or state machines.

    Args:
        workflow_name: Name of the workflow

    Returns:
        Complete workflow definition with states, transitions, and roles
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.get_workflow(workflow_name)
    return str(result)


@tool
async def query_workflow_next_steps(workflow_name: str, state_name: str) -> str:
    """
    Query what workflows or actions are triggered after a workflow state completes.

    Use this to determine what happens next in a business process.

    Args:
        workflow_name: Current workflow name
        state_name: Current workflow state

    Returns:
        List of next workflows/steps to execute
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.query_next_steps(workflow_name, state_name)
    return str(result)


@tool
async def query_workflow_available_actions(workflow_name: str, state_name: str) -> str:
    """
    Query available actions and transitions from a workflow state.

    Use this to understand what actions a user can take in a specific workflow state.

    Args:
        workflow_name: Current workflow name
        state_name: Current workflow state

    Returns:
        List of available transitions and authorized roles
    """
    client = MinionClient(settings.minion_api_url)
    result = await client.query_available_actions(workflow_name, state_name)
    return str(result)
