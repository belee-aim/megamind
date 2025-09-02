import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from megamind import prompts
from megamind.clients.manager import client_manager
from megamind.configuration import Configuration
from megamind.graph.schemas import RoleGenerationResponse
from megamind.graph.states import RoleGenerationState


async def generate_role_node(state: RoleGenerationState, config: RunnableConfig):
    """
    Generates the role permissions based on the user's description.
    """
    logger.debug("---GENERATE ROLE NODE---")
    configurable = Configuration.from_runnable_config(config)
    mcp_client = client_manager.get_client()
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)
    mcp_tools = await mcp_client.get_tools()

    messages = state.get("messages", [])
    feedback = state.get("feedback")

    if feedback:
        messages.append(HumanMessage(content=feedback))

    if not messages:
        system_prompt = prompts.role_generation_agent_instructions
        user_message = f"Role Name: {state['role_name']}\nUser Description: {state['user_description']}"
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

    llm_with_tools = llm.bind_tools(mcp_tools)
    structured_llm = llm_with_tools.with_structured_output(RoleGenerationResponse)
    response: RoleGenerationResponse = await structured_llm.ainvoke(messages)

    if not hasattr(response, "tool_calls") or not response.tool_calls:
        return {
            "generated_roles": response,
            "messages": [AIMessage(content="Generated roles successfully.")],
        }
    else:
        return {"messages": [response]}


async def reflect_node(state: RoleGenerationState, config: RunnableConfig):
    """
    Reflects on the generated role permissions and decides if they are sufficient.
    """
    logger.debug("---REFLECT NODE---")
    configurable = Configuration.from_runnable_config(config)
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)

    system_prompt = prompts.reflection_agent_instructions

    formatted_prompt = system_prompt.format(
        user_description=state.get("user_description", ""),
        generated_roles=state.get("generated_roles", {}).model_dump(),
    )

    response = await llm.ainvoke(formatted_prompt)

    return {"feedback": response.content}
