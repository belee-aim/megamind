import json
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind import prompts
from megamind.clients.frappe_client import FrappeClient
from megamind.configuration import Configuration
from megamind.graph.schemas import RoleGenerationResponse, RelatedRoleResponse
from megamind.graph.states import RoleGenerationState
from megamind.graph.tools.permission_tools import get_role_permissions


async def find_related_role_node(state: RoleGenerationState, config: RunnableConfig):
    """
    Finds a related role based on the user's description.
    """
    logger.debug("---FIND RELATED ROLE NODE---")

    configurable = Configuration.from_runnable_config(config)
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    structured_llm = llm.with_structured_output(RelatedRoleResponse)

    logger.debug("Cookie: " + str(state.get("cookie", None)))
    client = FrappeClient(
        cookie=state.get("cookie", None),
        access_token=state.get("access_token", None),
    )
    existing_roles = client.get_roles()
    system_prompt = prompts.find_related_role_instructions.format(
        role_name=state["role_name"],
        user_description=state["user_description"],
        existing_roles=existing_roles,
    )

    response = await structured_llm.ainvoke(system_prompt)
    return {"related_role": response.role_name, "existing_roles": existing_roles}


async def get_role_permissions_node(state: RoleGenerationState, config: RunnableConfig):
    """
    Gets the permissions for the related role.
    """
    logger.debug("---GET ROLE PERMISSIONS NODE---")
    related_role = state.get("related_role", None)
    permissions = await get_role_permissions.ainvoke(
        {
            "role": related_role,
            "cookie": state.get("cookie", None),
            "access_token": state.get("access_token", None),
        }
    )
    return {"related_role_permissions": permissions}


async def generate_role_node(state: RoleGenerationState, config: RunnableConfig):
    """
    Generates the role permissions based on the user's description.
    """
    logger.debug("---GENERATE ROLE NODE---")
    configurable = Configuration.from_runnable_config(config)
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)

    prompt = prompts.role_generation_agent_instructions.format(
        role_name=state.get("role_name"),
        user_description=state.get("user_description"),
        related_role=state.get("related_role"),
        related_role_permissions=state.get("related_role_permissions"),
    )

    structured_llm = llm.with_structured_output(RoleGenerationResponse)
    response: RoleGenerationResponse = await structured_llm.ainvoke(prompt)

    return {
        "generated_roles": response,
    }


async def describe_permissions_node(state: RoleGenerationState, config: RunnableConfig):
    """
    Describes the generated role permissions in a human-readable format.
    """
    logger.debug("---DESCRIBE PERMISSIONS NODE---")
    configurable = Configuration.from_runnable_config(config)
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)

    formatted_prompt = prompts.permission_description_agent_instructions.format(
        role_name=state.get("role_name", "User"),
        generated_roles=state.get("generated_roles", {}).model_dump(),
    )

    response = await llm.ainvoke(formatted_prompt)

    return {"permission_description": response.content}
