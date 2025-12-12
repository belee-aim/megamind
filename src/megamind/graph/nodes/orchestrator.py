from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage
from loguru import logger
from pydantic import BaseModel, Field
from typing import Optional, Literal

from megamind.configuration import Configuration
from megamind.graph.states import AgentState

ORCHESTRATOR_PROMPT = """# Aimee - AI Assistant for {company}

You are Aimee, an intelligent orchestrator helping {user_name} ({user_email}) with their tasks.

## User Context
- **Name**: {user_name}
- **Email**: {user_email}
- **Roles**: {user_roles}
- **Company**: {company}
- **Current Time**: {current_datetime}

## Your Role
Analyze the user's request and decide how to handle it:
1. **Respond directly** when you have all the information needed to answer
2. **Route to a specialist** when you need more information or need to perform an action

**Important**: The company has already configured their business processes in the knowledge graph. 
Route to the **knowledge** specialist to retrieve company-specific workflows and processes.

## Specialist Routing Guide

| Specialist | Route When User Wants To... | Examples |
|------------|----------------------------|----------|
| **knowledge** | Understand processes, schemas, workflows, company structure | "How does our sales order work?", "What fields does Invoice have?", "Who approves purchase orders?" |
| **report** | Get reports, analytics, financial data | "Show revenue this month", "Stock balance report", "Accounts receivable aging" |
| **operations** | Create, update, delete documents, perform workflow actions | "Create a sales order", "Submit this invoice", "Update customer address" |

## Multi-Step Operations Pattern

For operations (create, update, delete), follow this pattern:
1. **First**: Route to `knowledge` to understand the business process and required fields
2. **Then**: Route to `operations` to execute the action with the knowledge gathered

Example: User says "Create a sales order"
- Step 1: Route to `knowledge` → get Sales Order workflow and required fields
- Step 2: Route to `operations` → create the document using that knowledge

## 5W3H1R Protocol for Operations

When user requests CREATE, UPDATE, DELETE, or workflow actions, gather this data:
| Element | What to Check |
|---------|---------------|
| **Who** | Customer, supplier, employee involved |
| **What** | Document type, items, details |
| **When** | Date, deadline, schedule |
| **Where** | Warehouse, location, department |
| **Why** | Purpose, reason (optional) |
| **How** | Process to follow (from knowledge) |
| **How much** | Quantity, amount, price |
| **How long** | Duration, timeline (if applicable) |
| **Result** | Expected outcome |

**If critical data is missing, ask the user before proceeding.**

## Decision Rules

1. **respond** → Answer directly when:
   - Simple greeting or thanks
   - You have gathered all needed information and can provide a complete answer
   - Need to ask user for missing information
   - Specialists have provided sufficient information to synthesize a response

2. **route** → Delegate to a specialist when:
   - Need to fetch knowledge/process information → route to `knowledge`
   - Need to generate a report → route to `report`
   - Need to perform an operation (after having the required knowledge) → route to `operations`
   - Previous specialist result indicates more work is needed by another specialist

## Evaluating Specialist Results

When you have specialist results, evaluate:
- **Knowledge results**: Do you now have enough context to answer the user, or do you need to perform an operation?
- **Report results**: Is the report complete, or does the user need additional reports?
- **Operations results**: Was the operation successful? Do you need to confirm with the user?

If specialists have provided comprehensive information, synthesize it into a clear response. 
Do NOT route to the same specialist repeatedly for the same information.

{context}

Analyze the current state and decide: respond or route."""


class OrchestratorDecision(BaseModel):
    """Orchestrator decision: respond directly or route to specialist."""

    action: Literal["respond", "route"] = Field(
        description="respond=answer directly or ask for info, route=delegate to specialist"
    )
    target_specialist: Optional[Literal["knowledge", "report", "operations"]] = Field(
        default=None,
        description="Required if action=route. Which specialist to delegate to.",
    )
    reasoning: str = Field(description="Brief explanation of decision", max_length=200)


# Prompt for Phase 2: Streaming response generation
RESPONSE_PROMPT = """# Aimee - AI Assistant for {company}

You are Aimee, responding to {user_name} ({user_email}).

## Your Task
Generate a helpful, clear response to the user based on the available information.

## Guidelines
- Be conversational and professional
- Synthesize any specialist results into a coherent answer
- If asking for clarification, be specific about what you need
- Format responses appropriately (use markdown for lists, tables when helpful)

{context}

Respond naturally to the user's message."""


async def orchestrator_node(state: AgentState, config: RunnableConfig):
    """
    Orchestrator Phase 1: Decision Node.

    Decides to respond directly or route to a specialist.
    If responding, routes to orchestrator_response_node for streaming.
    """
    logger.debug("---ORCHESTRATOR (Phase 1: Decision)---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()
    messages = state.get("messages", [])
    specialist_results = state.get("specialist_results", [])

    # Extract user context from RunnableConfig
    cfg = config.get("configurable", {}) if config else {}
    company = cfg.get("company", "N/A")
    user_name = cfg.get("user_name", "User")
    user_email = cfg.get("user_email", "N/A")
    user_roles = cfg.get("user_roles", [])
    current_datetime = cfg.get("current_datetime", "N/A")
    roles_str = ", ".join(user_roles) if user_roles else "N/A"

    # ========================================
    # Build context including any specialist results
    # ========================================
    context_parts = []

    user_context = state.get("user_context")
    if user_context:
        context_parts.append(f"## User Knowledge\n{user_context}")

    # Include specialist results in context with specialist identification
    if specialist_results:
        results_text = "\n\n".join(
            [
                f"**{r.get('specialist', 'unknown').title()} Specialist Result:**\n{r.get('result', '')}"
                if isinstance(r, dict)
                else f"**Specialist Result:**\n{r}"
                for r in specialist_results
            ]
        )
        context_parts.append(f"## Previous Specialist Results\n{results_text}")

    execution_context = (
        "\n".join(context_parts)
        if context_parts
        else "## Execution Context\nNew conversation"
    )

    # ========================================
    # Phase 1: Make decision (respond or route)
    # ========================================
    try:
        system_message = SystemMessage(
            content=ORCHESTRATOR_PROMPT.format(
                company=company,
                user_name=user_name,
                user_email=user_email,
                user_roles=roles_str,
                current_datetime=current_datetime,
                context=execution_context,
            )
        )

        router = llm.with_structured_output(OrchestratorDecision)
        decision: OrchestratorDecision = await router.ainvoke(
            [system_message] + messages
        )

        logger.debug(f"Decision: {decision.action} | reason: {decision.reasoning}")

        if decision.action == "respond":
            # Route to Phase 2 for streaming response
            return {
                "next_action": "respond_streaming",
                "target_specialist": None,
            }

        else:  # route
            # Keep specialist_results when routing - they accumulate
            return {
                "next_action": "route",
                "target_specialist": decision.target_specialist,
            }

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        return {
            "next_action": "respond_streaming",
            "target_specialist": None,
        }


async def orchestrator_response_node(state: AgentState, config: RunnableConfig):
    """
    Orchestrator Phase 2: Streaming Response Node.

    Generates the final response using regular LLM call (not structured output)
    which enables true token-by-token streaming.
    """
    logger.debug("---ORCHESTRATOR (Phase 2: Streaming Response)---")

    configurable = Configuration.from_runnable_config(config)
    llm = configurable.get_chat_model()
    messages = state.get("messages", [])
    specialist_results = state.get("specialist_results", [])

    # Extract user context from RunnableConfig
    cfg = config.get("configurable", {}) if config else {}
    company = cfg.get("company", "N/A")
    user_name = cfg.get("user_name", "User")
    user_email = cfg.get("user_email", "N/A")

    # Build context for response
    context_parts = []

    user_context = state.get("user_context")
    if user_context:
        context_parts.append(f"## User Knowledge\n{user_context}")

    if specialist_results:
        results_text = "\n\n".join(
            [
                f"**{r.get('specialist', 'unknown').title()} Specialist Result:**\n{r.get('result', '')}"
                if isinstance(r, dict)
                else f"**Specialist Result:**\n{r}"
                for r in specialist_results
            ]
        )
        context_parts.append(f"## Available Information\n{results_text}")

    execution_context = "\n".join(context_parts) if context_parts else ""

    system_message = SystemMessage(
        content=RESPONSE_PROMPT.format(
            company=company,
            user_name=user_name,
            user_email=user_email,
            context=execution_context,
        )
    )

    # Regular LLM call - enables streaming
    response = await llm.ainvoke([system_message] + messages)

    return {
        "messages": [response],
        "next_action": "respond",
        "target_specialist": None,
        "specialist_results": None,  # Clear results after responding
    }
