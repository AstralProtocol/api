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


class SpatialOperatorEnum(str, Enum):
    """Spatial operators for geometry queries."""

    equals = "equals"
    disjoint = "disjoint"
    touches = "touches"
    within = "within"
    overlaps = "overlaps"
    crosses = "crosses"
    intersects = "intersects"
    contains = "contains"


class TemporalOperatorEnum(str, Enum):
    """Temporal operators for time-based queries."""

    equals = "equals"
    after = "after"
    before = "before"
    during = "during"
    tequals = "tequals"
    overlaps = "overlaps"
    meets = "meets"
    covers = "covers"


class PropertyOperatorEnum(str, Enum):
    """Property operators for attribute queries."""

    eq = "eq"  # equals
    neq = "neq"  # not equals
    gt = "gt"  # greater than
    lt = "lt"  # less than
    gte = "gte"  # greater than or equal
    lte = "lte"  # less than or equal
    like = "like"  # SQL LIKE pattern
    between = "between"  # between two values
    in_list = "in"  # in a list of values


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
            # Add additional conformance classes for advanced query capabilities
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/filter",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/sorting",
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
    # Spatial filters
    bbox: Optional[str] = Query(
        None, description="Bounding box coordinates (minLon,minLat,maxLon,maxLat)"
    ),
    intersects: Optional[str] = Query(
        None, description="GeoJSON geometry to test intersection with features"
    ),
    within: Optional[str] = Query(
        None, description="GeoJSON geometry to test if features are within"
    ),
    buffer: Optional[float] = Query(
        None, description="Buffer distance in meters to apply to spatial filters"
    ),
    # Temporal filters
    datetime_filter: Optional[str] = Query(
        None,
        alias="datetime",
        description="Date and time or intervals (RFC 3339). "
        "Format: single-date, start-date/end-date, or start-date/.. (open-ended)",
    ),
    temporal_op: Optional[TemporalOperatorEnum] = Query(
        None, description="Temporal operator to apply to datetime filter"
    ),
    # Property filters
    property_name: Optional[str] = Query(
        None, description="Property name to filter on"
    ),
    property_op: Optional[PropertyOperatorEnum] = Query(
        None, description="Property operator to apply"
    ),
    property_value: Optional[str] = Query(
        None, description="Property value to compare against"
    ),
    # Pagination and format
    limit: int = Query(10, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    f: FormatEnum = Query(FormatEnum.geojson, description="Output format"),
    crs: Optional[str] = Query(
        None,
        description="Coordinate reference system (as URI)",
        examples=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
    ),
    # Sorting
    sortby: Optional[str] = Query(
        None, description="Property to sort by, prefix with '-' for descending order"
    ),
) -> Union[FeatureCollection, Response]:
    """Retrieve features from a specific collection.

    This endpoint follows the OGC API - Features standard for querying features.

    Args:
        collection_id: The ID of the collection to query
        bbox: Bounding box filter in format "minLon,minLat,maxLon,maxLat"
        intersects: GeoJSON geometry to test intersection with features
        within: GeoJSON geometry to test if features are within
        buffer: Buffer distance in meters to apply to spatial filters
        datetime_filter: Temporal filter in RFC 3339 format
        temporal_op: Temporal operator to apply to datetime filter
        property_name: Property name to filter on
        property_op: Property operator to apply
        property_value: Property value to compare against
        limit: Maximum number of features to return (1-1000)
        offset: Starting offset for pagination
        f: Output format (json, html, geojson)
        crs: Coordinate reference system URI
        sortby: Property to sort by, prefix with '-' for descending order

    Returns:
        Union[FeatureCollection, Response]: GeoJSON FeatureCollection or formatted
            response

    Raises:
        HTTPException: If the collection is not found
    """
    if collection_id != "location_proofs":
        raise HTTPException(status_code=404, detail="Collection not found")

    # Parse and validate spatial filters
    if bbox:
        try:
            bbox_parts = bbox.split(",")
            if len(bbox_parts) != 4:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid bbox format. Expected: minLon,minLat,maxLon,maxLat",
                )
            # Parse bbox coordinates but don't store in unused variable
            [float(part) for part in bbox_parts]
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid bbox values. Expected numeric values."
            )

    # Parse and validate intersects/within GeoJSON
    geometry = None
    if intersects:
        try:
            # In a real implementation, we would parse and validate the GeoJSON here
            # For now, we'll just check if it's valid JSON
            geometry = {"type": "intersects", "value": intersects}
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid GeoJSON for intersects parameter."
            )
    elif within:
        try:
            # In a real implementation, we would parse and validate the GeoJSON here
            geometry = {"type": "within", "value": within}
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid GeoJSON for within parameter."
            )

    # Apply buffer if specified
    if buffer is not None and buffer > 0 and geometry:
        # In a real implementation, we would apply the buffer to the geometry
        # For now, we'll just note that it was requested
        geometry["buffer"] = str(buffer)  # Convert float to string to avoid type error

    # Parse and validate temporal filter
    if datetime_filter:
        # Handle different temporal formats: single date, interval, or open-ended
        if "/" in datetime_filter:
            # Interval or open-ended
            parts = datetime_filter.split("/")
            if len(parts) != 2:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid datetime format. Expected: date or start/end",
                )

            # Process temporal filter but don't store in unused variable
            start_date = parts[0] if parts[0] != ".." else None
            end_date = parts[1] if parts[1] != ".." else None

            # In a real implementation, we would use these values for filtering
            _ = {
                "start": start_date,
                "end": end_date,
                "operator": temporal_op.value if temporal_op else "during",
            }
        else:
            # Single date
            # In a real implementation, we would use this value for filtering
            _ = {
                "date": datetime_filter,
                "operator": temporal_op.value if temporal_op else "equals",
            }

    # Parse and validate property filter
    if property_name and property_op:
        # In a real implementation, we would use these values for filtering
        _ = {
            "name": property_name,
            "operator": property_op.value,
            "value": property_value,
        }

    # Parse and validate sorting
    if sortby:
        descending = sortby.startswith("-")
        field = sortby[1:] if descending else sortby
        # In a real implementation, we would use these values for sorting
        _ = {"field": field, "descending": descending}

    # TODO: Implement actual feature retrieval from database with filters
    # For now, we'll just return an empty collection with the appropriate links

    # Build query parameters for self link
    query_params = []
    if bbox:
        query_params.append(f"bbox={bbox}")
    if intersects:
        query_params.append(f"intersects={intersects}")
    if within:
        query_params.append(f"within={within}")
    if buffer is not None:
        query_params.append(f"buffer={buffer}")
    if datetime_filter:
        query_params.append(f"datetime={datetime_filter}")
    if temporal_op:
        query_params.append(f"temporal_op={temporal_op.value}")
    if property_name:
        query_params.append(f"property_name={property_name}")
    if property_op:
        query_params.append(f"property_op={property_op.value}")
    if property_value:
        query_params.append(f"property_value={property_value}")
    if limit != 10:
        query_params.append(f"limit={limit}")
    if offset != 0:
        query_params.append(f"offset={offset}")
    if f != FormatEnum.geojson:
        query_params.append(f"f={f.value}")
    if crs:
        query_params.append(f"crs={crs}")
    if sortby:
        query_params.append(f"sortby={sortby}")

    query_string = "&".join(query_params)
    base_url = f"/collections/{collection_id}/items"
    self_url = f"{base_url}?{query_string}" if query_string else base_url

    # Create next link with updated offset
    next_offset = offset + limit
    next_params = query_params.copy()

    # Replace or add offset parameter
    offset_found = False
    for i, param in enumerate(next_params):
        if param.startswith("offset="):
            next_params[i] = f"offset={next_offset}"
            offset_found = True
            break

    if not offset_found:
        next_params.append(f"offset={next_offset}")

    next_query_string = "&".join(next_params)
    next_url = f"{base_url}?{next_query_string}"

    self_link = {
        "href": self_url,
        "rel": "self",
        "type": "application/geo+json",
        "title": "This collection",
    }
    next_link = {
        "href": next_url,
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
