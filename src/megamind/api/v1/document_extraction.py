from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from megamind.clients.titan_client import TitanClient
from megamind.graph.nodes.document_extraction_agent import extract_company_information
from megamind.models.requests import (
    DocumentExtractionRequest,
    TitanCallbackRequest,
)
from megamind.models.responses import MainResponse
from megamind.utils.config import settings

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
        callback_url = f"/api/v1/document-extraction/callback"

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
    Extracts company information using LLM and returns structured data.
    """
    try:
        logger.info(f"Received callback with {len(request_data.documents)} documents")

        # Extract company information from documents
        extracted_data = await extract_company_information(request_data.documents)

        logger.info("Successfully extracted company information")

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
