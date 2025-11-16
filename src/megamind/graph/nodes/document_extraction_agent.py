from loguru import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig

from megamind.configuration import Configuration
from megamind.graph.schemas import CompanyInformation, RawCompanyInformation
from megamind.graph.states import DocumentExtractionState
from megamind.utils.config import settings
from megamind import prompts


async def extract_facts_node(
    state: DocumentExtractionState, config: RunnableConfig
) -> dict:
    """
    Node 1: Extracts only explicitly stated facts from documents.

    This node analyzes the input documents and extracts ONLY information
    that is explicitly present, without any inference or guessing.

    Args:
        state: DocumentExtractionState containing documents list
        config: RunnableConfig for the node

    Returns:
        dict: Updated state with raw_extraction field populated

    Raises:
        Exception: If extraction fails
    """
    documents = state["documents"]
    logger.info(f"Node 1: Extracting facts from {len(documents)} documents")

    try:
        # Initialize LLM with Gemini
        configuration = Configuration()
        llm = ChatGoogleGenerativeAI(
            model=configuration.query_generator_model,
            google_api_key=settings.google_api_key,
        )

        # Combine documents into a single text
        combined_documents = "\n\n---DOCUMENT SEPARATOR---\n\n".join(
            [f"Document {i+1}:\n{doc}" for i, doc in enumerate(documents)]
        )

        # Format the prompt for fact extraction
        prompt = prompts.fact_extraction_agent_instructions.format(
            documents=combined_documents
        )

        # Use structured output to extract facts
        structured_llm = llm.with_structured_output(RawCompanyInformation)
        result: RawCompanyInformation = await structured_llm.ainvoke(prompt)

        logger.info("Successfully extracted raw facts from documents")
        logger.debug(f"Raw extraction data: {result.model_dump()}")

        return {"raw_extraction": result}

    except Exception as e:
        logger.error(f"Error extracting facts from documents: {e}")
        raise


async def infer_values_node(
    state: DocumentExtractionState, config: RunnableConfig
) -> dict:
    """
    Node 2: Infers missing values based on extracted facts.

    This node takes the raw extraction from Node 1 and enriches it by:
    - Inferring employee reporting structure (reports_to)
    - Generating company_roles from employee data
    - Inferring gender from names where possible
    - Adding other contextual information

    Args:
        state: DocumentExtractionState containing raw_extraction
        config: RunnableConfig for the node

    Returns:
        dict: Updated state with final_extraction field populated

    Raises:
        Exception: If inference fails
    """
    raw_extraction = state["raw_extraction"]
    logger.info("Node 2: Inferring missing values from raw extraction")

    try:
        # Initialize LLM with Gemini
        configuration = Configuration()
        llm = ChatGoogleGenerativeAI(
            model=configuration.query_generator_model,
            google_api_key=settings.google_api_key,
        )

        # Format the prompt for value inference
        # Convert raw extraction to JSON string for the prompt
        raw_data_json = raw_extraction.model_dump_json(indent=2)
        prompt = prompts.value_inference_agent_instructions.format(
            raw_extraction=raw_data_json
        )

        # Use structured output to infer values
        structured_llm = llm.with_structured_output(CompanyInformation)
        result: CompanyInformation = await structured_llm.ainvoke(prompt)

        logger.info("Successfully inferred missing values and enriched company information")
        logger.debug(f"Final extraction data: {result.model_dump()}")

        return {"final_extraction": result}

    except Exception as e:
        logger.error(f"Error inferring values: {e}")
        raise


# Legacy function for backward compatibility (if needed)
async def extract_company_information(documents: list[str]) -> CompanyInformation:
    """
    Legacy function: Extracts structured company information from a list of document texts.

    This function is kept for backward compatibility but internally uses the new two-node workflow.

    Args:
        documents: List of document contents as strings

    Returns:
        CompanyInformation: Structured company data extracted from documents

    Raises:
        Exception: If extraction fails
    """
    logger.warning(
        "Using legacy extract_company_information function. Consider using the graph workflow instead."
    )

    # Create initial state
    state: DocumentExtractionState = {
        "documents": documents,
        "raw_extraction": None,
        "final_extraction": None,
    }

    # Run node 1: Extract facts
    updated_state = await extract_facts_node(state, RunnableConfig())
    state.update(updated_state)

    # Run node 2: Infer values
    updated_state = await infer_values_node(state, RunnableConfig())
    state.update(updated_state)

    return state["final_extraction"]
