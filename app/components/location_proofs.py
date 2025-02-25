"""OGC API - Features compliant location proofs router."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["Location Proofs"])


class FormatEnum(str, Enum):
    """Output format options for API responses."""

    json = "json"
    html = "html"
    geojson = "geojson"


class Feature(BaseModel):
    """GeoJSON Feature model."""

    model_config = ConfigDict(extra="allow")

    type: Literal["Feature"]
    geometry: Dict[str, Any]
    properties: Dict[str, Any]
    id: UUID
    links: List[Dict[str, str]]


class FeatureCollection(BaseModel):
    """GeoJSON FeatureCollection model."""

    type: Literal["FeatureCollection"]
    features: List[Feature]
    links: List[Dict[str, str]]
    timeStamp: str
    numberMatched: int
    numberReturned: int


class Collection(BaseModel):
    """Collection model following OGC API - Features specification."""

    id: str
    title: str
    description: str
    links: List[Dict[str, str]]
    extent: Dict[str, Any] = Field(
        default_factory=lambda: {
            "spatial": {
                "bbox": [[-180, -90, 180, 90]],
                "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            },
            "temporal": {"interval": [["2024-01-01T00:00:00Z", None]]},
        }
    )
    itemType: str = "feature"
    crs: List[str] = Field(
        default_factory=lambda: ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
    )


class Collections(BaseModel):
    """Collections model following OGC API - Features specification."""

    collections: List[Collection]
    links: List[Dict[str, str]]


@router.get("/", response_model=Dict[str, Any])
async def landing_page() -> Dict[str, Any]:
    """Landing page following OGC API - Features specification.

    Returns:
        Dict[str, Any]: Landing page content with links
    """
    return {
        "title": "Astral API",
        "description": "A decentralized geospatial data API with EAS integration",
        "links": [
            {
                "href": "/",
                "rel": "self",
                "type": "application/json",
                "title": "this document",
            },
            {
                "href": "/api",
                "rel": "service-desc",
                "type": "application/vnd.oai.openapi+json;version=3.0",
                "title": "the API definition",
            },
            {
                "href": "/conformance",
                "rel": "conformance",
                "type": "application/json",
                "title": "OGC API conformance classes implemented by this server",
            },
            {
                "href": "/collections",
                "rel": "data",
                "type": "application/json",
                "title": "Information about the feature collections",
            },
        ],
    }


@router.get("/conformance", response_model=Dict[str, List[str]])
async def conformance() -> Dict[str, List[str]]:
    """Information about standards that this API conforms to.

    Returns:
        Dict[str, List[str]]: List of conformance classes
    """
    return {
        "conformsTo": [
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
        ]
    }


@router.get("/collections", response_model=Collections)
async def list_collections() -> Collections:
    """List available collections following OGC API - Features specification.

    Returns:
        Collections: A list of available collections and related links
    """
    return Collections(
        collections=[
            Collection(
                id="location_proofs",
                title="Location Proofs",
                description="Collection of location proofs (attestations) from EAS",
                links=[
                    {
                        "href": "/collections/location_proofs",
                        "rel": "self",
                        "type": "application/json",
                        "title": "Location Proofs Collection",
                    },
                    {
                        "href": "/collections/location_proofs/items",
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": "Location Proofs Items",
                    },
                ],
            )
        ],
        links=[
            {
                "href": "/collections",
                "rel": "self",
                "type": "application/json",
                "title": "Collections",
            }
        ],
    )


@router.get("/collections/{collection_id}", response_model=Collection)
async def get_collection(collection_id: str) -> Collection:
    """Information about a specific collection.

    Args:
        collection_id: The ID of the collection

    Returns:
        Collection: Detailed information about the collection

    Raises:
        HTTPException: If the collection is not found
    """
    if collection_id != "location_proofs":
        raise HTTPException(status_code=404, detail="Collection not found")

    return Collection(
        id="location_proofs",
        title="Location Proofs",
        description="Collection of location proofs (attestations) from EAS",
        links=[
            {
                "href": "/collections/location_proofs",
                "rel": "self",
                "type": "application/json",
                "title": "Location Proofs Collection",
            },
            {
                "href": "/collections/location_proofs/items",
                "rel": "items",
                "type": "application/geo+json",
                "title": "Location Proofs Items",
            },
        ],
    )


@router.get("/api", response_model=Dict[str, Any])
async def api_definition() -> Dict[str, Any]:
    """Retrieve the OpenAPI definition following OGC API - Features specification.

    Returns:
        Dict[str, Any]: OpenAPI schema
    """
    openapi = get_openapi(
        title="Astral API",
        version="1.0.0",
        description="A decentralized geospatial data API with EAS integration",
        routes=router.routes,
    )
    return cast(Dict[str, Any], openapi)


@router.get("/collections/{collection_id}/items", response_model=FeatureCollection)
async def get_features(
    collection_id: str,
    bbox: Optional[str] = Query(
        None, description="Bounding box coordinates (minLon,minLat,maxLon,maxLat)"
    ),
    datetime_filter: Optional[str] = Query(
        None,
        alias="datetime",
        description="Date and time or intervals (RFC 3339)",
    ),
    limit: int = Query(10, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    f: FormatEnum = Query(FormatEnum.geojson, description="Output format"),
    crs: Optional[str] = Query(
        None,
        description="Coordinate reference system (as URI)",
        examples=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
    ),
) -> Union[FeatureCollection, Response]:
    """Retrieve features from a specific collection.

    This endpoint follows the OGC API - Features standard for querying features.

    Args:
        collection_id: The ID of the collection to query
        bbox: Bounding box filter in format "minLon,minLat,maxLon,maxLat"
        datetime_filter: Temporal filter in RFC 3339 format
        limit: Maximum number of features to return (1-1000)
        offset: Starting offset for pagination
        f: Output format (json, html, geojson)
        crs: Coordinate reference system URI

    Returns:
        Union[FeatureCollection, Response]: GeoJSON FeatureCollection or formatted
            response

    Raises:
        HTTPException: If the collection is not found
    """
    if collection_id != "location_proofs":
        raise HTTPException(status_code=404, detail="Collection not found")

    # TODO: Implement actual feature retrieval from database with filters
    next_offset = offset + limit
    base_url = f"/collections/{collection_id}/items"

    self_link = {
        "href": base_url,
        "rel": "self",
        "type": "application/geo+json",
        "title": "This collection",
    }
    next_link = {
        "href": f"{base_url}?offset={next_offset}",
        "rel": "next",
        "type": "application/geo+json",
        "title": "Next page",
    }

    feature_collection = FeatureCollection(
        type="FeatureCollection",
        features=[],
        links=[self_link, next_link],
        timeStamp=datetime.now(UTC).isoformat(),
        numberMatched=0,
        numberReturned=0,
    )

    if f == FormatEnum.html:
        return Response(
            content="<html><body>HTML view not implemented yet</body></html>",
            media_type="text/html",
        )

    return feature_collection


@router.get("/collections/{collection_id}/items/{feature_id}", response_model=Feature)
async def get_feature(
    collection_id: str,
    feature_id: UUID,
    f: FormatEnum = Query(FormatEnum.geojson, description="Output format"),
    crs: Optional[str] = Query(
        None,
        description="Coordinate reference system (as URI)",
        examples=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
    ),
) -> Union[Feature, Response]:
    """Retrieve a single feature from a collection.

    Args:
        collection_id: The ID of the collection
        feature_id: The ID of the feature
        f: Output format (json, html, geojson)
        crs: Coordinate reference system URI

    Returns:
        Union[Feature, Response]: A GeoJSON Feature or formatted response

    Raises:
        HTTPException: If the collection or feature is not found
    """
    if collection_id != "location_proofs":
        raise HTTPException(status_code=404, detail="Collection not found")

    # TODO: Implement actual feature retrieval from database
    # For now, return a 404 since we don't have any features
    raise HTTPException(status_code=404, detail="Feature not found")
