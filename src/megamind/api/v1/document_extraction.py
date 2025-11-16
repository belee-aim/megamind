from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger
from langgraph.graph.state import CompiledStateGraph

from megamind.clients.titan_client import TitanClient
from megamind.models.requests import (
    DocumentExtractionRequest,
    TitanCallbackRequest,
)
from megamind.models.responses import MainResponse

router = APIRouter()


@router.post("/document-extraction/submit")
async def submit_document_extraction(
    request: Request,
    request_data: DocumentExtractionRequest,
):
    """
    Endpoint to submit documents for extraction to Titan service.
    Returns a job_id that can be used to track the processing.
    """
    try:
        logger.info(
            f"Received document extraction request for {len(request_data.file_names)} files"
        )

        # Generate callback URL
        callback_url = "/api/v1/document-extraction/callback"

        # Initialize Titan client and submit documents
        titan_client = TitanClient()
        job_id = await titan_client.submit_documents(
            file_names=request_data.file_names,
            callback_url=callback_url,
        )

        logger.info(f"Document extraction job submitted successfully: {job_id}")

        return MainResponse(
            message="Documents submitted for processing",
            response={
                "job_id": job_id,
            },
        ).model_dump()

    except Exception as e:
        logger.error(f"Error in document extraction submit endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to submit documents for extraction: {str(e)}",
            ).model_dump(),
        )


@router.post("/document-extraction/callback")
async def document_extraction_callback(
    request: Request,
    request_data: TitanCallbackRequest,
):
    """
    Callback endpoint for Titan service to send processed documents.
    Extracts company information using the two-node LangGraph workflow:
    1. extract_facts_node: Extracts only explicitly stated information
    2. infer_values_node: Infers missing values based on hierarchy and context
    """
    try:
        logger.info(f"Received callback with {len(request_data.documents)} documents")

        # Get the document extraction graph from app state
        graph: CompiledStateGraph = request.app.state.document_extraction_graph

        # Prepare inputs for the graph
        inputs = {
            "documents": request_data.documents,
            "raw_extraction": None,
            "final_extraction": None,
        }

        logger.info("Starting document extraction workflow")
        # Invoke the graph to extract and enrich company information
        final_state = await graph.ainvoke(inputs)
        logger.info("Document extraction workflow completed successfully")

        # Get the final extraction from the state
        extracted_data = final_state.get("final_extraction")

        logger.info("Successfully extracted and enriched company information")

        # Return the extracted data to Titan
        return MainResponse(
            message="Company information extracted successfully",
            response=extracted_data.model_dump(),
        )

    except Exception as e:
        logger.error(f"Error in document extraction callback: {e}")
        return JSONResponse(
            status_code=500,
            content=MainResponse(
                message="Error",
                error=f"Failed to extract company information: {str(e)}",
            ).model_dump(),
        )
