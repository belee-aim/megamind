from loguru import logger
from langchain_google_genai import ChatGoogleGenerativeAI

from megamind.configuration import Configuration
from megamind.graph.schemas import CompanyInformation
from megamind.utils.config import settings
from megamind import prompts


async def extract_company_information(documents: list[str]) -> CompanyInformation:
    """
    Extracts structured company information from a list of document texts.

    Args:
        documents: List of document contents as strings

    Returns:
        CompanyInformation: Structured company data extracted from documents

    Raises:
        Exception: If extraction fails
    """
    logger.info(f"Extracting company information from {len(documents)} documents")

    try:
        # Initialize LLM with Gemini (hardcoded)
        config = Configuration()
        llm = ChatGoogleGenerativeAI(
            model=config.query_generator_model, google_api_key=settings.google_api_key
        )

        # Combine documents into a single text
        combined_documents = "\n\n---DOCUMENT SEPARATOR---\n\n".join(
            [f"Document {i+1}:\n{doc}" for i, doc in enumerate(documents)]
        )

        # Format the prompt
        prompt = prompts.document_extraction_agent_instructions.format(
            documents=combined_documents
        )

        # Use structured output to extract information
        structured_llm = llm.with_structured_output(CompanyInformation)
        result: CompanyInformation = await structured_llm.ainvoke(prompt)

        logger.info("Successfully extracted company information")
        logger.debug(f"Extracted data: {result.model_dump()}")

        return result

    except Exception as e:
        logger.error(f"Error extracting company information: {e}")
        raise
