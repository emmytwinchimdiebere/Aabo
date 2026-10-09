from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from ...models import LocationExtractionRequest, LocationExtractionResponse
from ...services.location_extraction import LocationExtractionError
from ..dependencies import LocationExtractor

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("/extract", response_model=LocationExtractionResponse)
async def extract_location(
    request: LocationExtractionRequest,
    extractor: LocationExtractor,
) -> LocationExtractionResponse:
    try:
        result = await extractor.extract(request.transcript, request.language)
    except LocationExtractionError as error:
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if str(error) == "location_extraction_not_configured"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=str(error)) from error
    return LocationExtractionResponse(**asdict(result))
