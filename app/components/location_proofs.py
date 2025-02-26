"""OGC API - Features compliant location proofs router."""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

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


class Link(BaseModel):
    """Link model following OGC API - Features specification."""

    href: str
    rel: str
    type: str
    title: str
    hreflang: Optional[str] = None
    length: Optional[int] = None


class SpatialExtent(BaseModel):
    """Spatial extent model following OGC API - Features specification."""

    bbox: List[List[float]] = Field(
        default_factory=lambda: [[-180.0, -90.0, 180.0, 90.0]]
    )
    crs: str = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


class TemporalExtent(BaseModel):
    """Temporal extent model following OGC API - Features specification."""

    interval: List[List[Optional[str]]] = Field(
        default_factory=lambda: [["2024-01-01T00:00:00Z", None]]
    )
    trs: str = "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"


class Extent(BaseModel):
    """Extent model following OGC API - Features specification."""

    spatial: SpatialExtent = Field(default_factory=SpatialExtent)
    temporal: TemporalExtent = Field(default_factory=TemporalExtent)


class Feature(BaseModel):
    """GeoJSON Feature model."""

    model_config = ConfigDict(extra="allow")

    type: Literal["Feature"]
    geometry: Dict[str, Any]
    properties: Dict[str, Any]
    id: Any  # Changed from UUID to Any to accept both UUID and int
    links: List[Link]


class FeatureCollection(BaseModel):
    """GeoJSON FeatureCollection model."""

    type: Literal["FeatureCollection"]
    features: List[Feature]
    links: List[Link]
    timeStamp: str
    numberMatched: int
    numberReturned: int


class Collection(BaseModel):
    """Collection model following OGC API - Features specification."""

    id: str
    title: str
    description: str
    links: List[Link]
    extent: Extent = Field(default_factory=Extent)
    itemType: str = "feature"
    crs: List[str] = Field(
        default_factory=lambda: ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
    )
    storageCRS: Optional[str] = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    keywords: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    attribution: Optional[str] = None


class Collections(BaseModel):
    """Collections model following OGC API - Features specification."""

    collections: List[Collection]
    links: List[Link]


class ErrorResponse(BaseModel):
    """Error response model following RFC 7807 Problem Details for HTTP APIs."""

    type: str = Field(
        default="https://api.astral.global/errors/validation-error",
        description="A URI reference that identifies the problem type",
    )
    title: str = Field(
        ..., description="A short, human-readable summary of the problem"
    )
    status: int = Field(..., description="The HTTP status code")
    detail: str = Field(..., description="A human-readable explanation of the problem")
    instance: str = Field(
        ...,
        description="A URI reference that identifies the specific occurrence of the problem",
    )

    # Additional fields for more detailed error information
    validation_errors: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of validation errors for request parameters"
    )
    error_code: Optional[str] = Field(
        None, description="Application-specific error code"
    )
    help_url: Optional[str] = Field(
        None, description="URL to documentation about this error"
    )


# Validation models for query parameters
class BBoxModel(BaseModel):
    """Validation model for bbox parameter."""

    bbox: str

    @field_validator("bbox")
    def validate_bbox(cls, v: str) -> str:
        """Validate bbox format: minLon,minLat,maxLon,maxLat."""
        try:
            parts = v.split(",")
            if len(parts) != 4:
                raise ValueError(
                    "Invalid bbox format: Expected format: minLon,minLat,maxLon,maxLat"
                )

            min_lon, min_lat, max_lon, max_lat = parts

            try:
                min_lon_float = float(min_lon)
                min_lat_float = float(min_lat)
                max_lon_float = float(max_lon)
                max_lat_float = float(max_lat)
            except ValueError:
                raise ValueError("Invalid bbox values: All values must be numeric")

            # Validate longitude and latitude ranges
            if not (-180 <= min_lon_float <= 180) or not (-180 <= max_lon_float <= 180):
                raise ValueError("Longitude values must be between -180 and 180")
            if not (-90 <= min_lat_float <= 90) or not (-90 <= max_lat_float <= 90):
                raise ValueError("Latitude values must be between -90 and 90")
            if min_lon_float > max_lon_float:
                raise ValueError("minLon must be less than or equal to maxLon")
            if min_lat_float > max_lat_float:
                raise ValueError("minLat must be less than or equal to maxLat")

            return v
        except ValueError as e:
            raise ValueError(f"{str(e)}")


class DateTimeModel(BaseModel):
    """Validation model for datetime parameter."""

    datetime: str

    @field_validator("datetime")
    def validate_datetime(cls, v: str) -> str:
        """Validate datetime format according to RFC 3339."""
        if "/" in v:
            # Interval format: start/end, start/.., or ../end
            parts = v.split("/")
            if len(parts) != 2:
                raise ValueError(
                    "Invalid datetime format: Expected format: start/end, start/.., or ../end"
                )

            start, end = parts

            # Validate start date if not open-ended
            if start != "..":
                try:
                    # Ensure the format includes time component and timezone
                    if not (
                        ("T" in start)
                        and (start.endswith("Z") or "+" in start or "-" in start[10:])
                    ):
                        raise ValueError(
                            "Invalid datetime format: Date must include time and timezone (e.g., 2023-01-01T00:00:00Z)"
                        )
                    datetime.fromisoformat(start.replace("Z", "+00:00"))
                except ValueError as e:
                    raise ValueError(f"Invalid datetime format: {str(e)}")

            # Validate end date if not open-ended
            if end != "..":
                try:
                    # Ensure the format includes time component and timezone
                    if not (
                        ("T" in end)
                        and (end.endswith("Z") or "+" in end or "-" in end[10:])
                    ):
                        raise ValueError(
                            "Invalid datetime format: Date must include time and timezone (e.g., 2023-01-01T00:00:00Z)"
                        )
                    datetime.fromisoformat(end.replace("Z", "+00:00"))
                except ValueError as e:
                    raise ValueError(f"Invalid datetime format: {str(e)}")
        else:
            # Single date format
            try:
                # Ensure the format includes time component and timezone
                if not (("T" in v) and (v.endswith("Z") or "+" in v or "-" in v[10:])):
                    raise ValueError(
                        "Invalid datetime format: Date must include time and timezone (e.g., 2023-01-01T00:00:00Z)"
                    )
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError(f"Invalid datetime format: {str(e)}")

        return v


class GeoJSONModel(BaseModel):
    """Validation model for GeoJSON parameters."""

    geojson: str

    @field_validator("geojson")
    def validate_geojson(cls, v: str) -> str:
        """Validate GeoJSON format."""
        try:
            data = json.loads(v)

            # Basic GeoJSON validation
            if "type" not in data:
                raise ValueError("Missing 'type' property")

            if data["type"] not in [
                "Point",
                "LineString",
                "Polygon",
                "MultiPoint",
                "MultiLineString",
                "MultiPolygon",
                "GeometryCollection",
            ]:
                raise ValueError(f"Invalid geometry type: {data['type']}")

            if "coordinates" not in data and data["type"] != "GeometryCollection":
                raise ValueError("Missing 'coordinates' property")

            if data["type"] == "GeometryCollection" and "geometries" not in data:
                raise ValueError("GeometryCollection missing 'geometries' property")

            return v
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")
        except Exception as e:
            raise ValueError(f"Invalid GeoJSON: {str(e)}")


# Helper function for validating query parameters
def validate_query_params(
    collection_id: str,
    bbox: Optional[str] = None,
    intersects: Optional[str] = None,
    within: Optional[str] = None,
    datetime_filter: Optional[str] = None,
) -> None:
    """Validate query parameters using Pydantic models.

    Args:
        collection_id: The collection ID
        bbox: Bounding box parameter
        intersects: GeoJSON for intersection test
        within: GeoJSON for within test
        datetime_filter: Datetime filter

    Raises:
        HTTPException: If validation fails
    """
    # Validate bbox parameter
    if bbox:
        try:
            BBoxModel(bbox=bbox)
        except ValueError as e:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail=f"Invalid bbox parameter: {str(e)}",
                instance=f"/collections/{collection_id}/items?bbox={bbox}",
                validation_errors=[{"field": "bbox", "error": str(e)}],
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
            )

    # Validate intersects parameter
    if intersects:
        try:
            GeoJSONModel(geojson=intersects)
        except ValueError as e:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail=f"Invalid intersects parameter: {str(e)}",
                instance=f"/collections/{collection_id}/items?intersects={intersects}",
                validation_errors=[{"field": "intersects", "error": str(e)}],
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
            )

    # Validate within parameter
    if within:
        try:
            GeoJSONModel(geojson=within)
        except ValueError as e:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail=f"Invalid within parameter: {str(e)}",
                instance=f"/collections/{collection_id}/items?within={within}",
                validation_errors=[{"field": "within", "error": str(e)}],
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
            )

    # Validate datetime parameter
    if datetime_filter:
        try:
            DateTimeModel(datetime=datetime_filter)
        except ValueError as e:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail=f"Invalid datetime parameter: {str(e)}",
                instance=f"/collections/{collection_id}/items?datetime={datetime_filter}",
                validation_errors=[{"field": "datetime", "error": str(e)}],
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
            )


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
            Link(
                href="/",
                rel="self",
                type="application/json",
                title="this document",
            ).model_dump(),
            Link(
                href="/api",
                rel="service-desc",
                type="application/vnd.oai.openapi+json;version=3.0",
                title="the API definition",
            ).model_dump(),
            Link(
                href="/conformance",
                rel="conformance",
                type="application/json",
                title="OGC API conformance classes implemented by this server",
            ).model_dump(),
            Link(
                href="/collections",
                rel="data",
                type="application/json",
                title="Information about the feature collections",
            ).model_dump(),
            Link(
                href="https://docs.astral.global",
                rel="doc",
                type="text/html",
                title="Documentation for the Astral API",
            ).model_dump(),
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
                keywords=["location", "proof", "attestation", "EAS", "blockchain"],
                license="https://creativecommons.org/licenses/by/4.0/",
                attribution="Astral Network",
                links=[
                    Link(
                        href="/collections/location_proofs",
                        rel="self",
                        type="application/json",
                        title="Location Proofs Collection",
                    ),
                    Link(
                        href="/collections/location_proofs/items",
                        rel="items",
                        type="application/geo+json",
                        title="Location Proofs Items",
                    ),
                    Link(
                        href="/collections/location_proofs?f=html",
                        rel="alternate",
                        type="text/html",
                        title="HTML version of this collection",
                    ),
                    Link(
                        href="https://docs.astral.global/collections/location_proofs",
                        rel="describedby",
                        type="text/html",
                        title="Documentation for the Location Proofs collection",
                    ),
                ],
                extent=Extent(
                    spatial=SpatialExtent(bbox=[[-180, -90, 180, 90]]),
                    temporal=TemporalExtent(interval=[["2024-01-01T00:00:00Z", None]]),
                ),
            )
        ],
        links=[
            Link(
                href="/collections",
                rel="self",
                type="application/json",
                title="Collections",
            ),
            Link(
                href="/collections?f=html",
                rel="alternate",
                type="text/html",
                title="HTML version of the collections",
            ),
            Link(
                href="/",
                rel="parent",
                type="application/json",
                title="Landing page",
            ),
        ],
    )


@router.get("/collections/{collection_id}", response_model=Collection)
async def get_collection(
    collection_id: str,
    f: FormatEnum = Query(FormatEnum.json, description="Output format"),
) -> Union[Collection, Response]:
    """Information about a specific collection.

    Args:
        collection_id: The ID of the collection
        f: Output format (json, html, geojson)

    Returns:
        Union[Collection, Response]: Detailed information about the collection

    Raises:
        HTTPException: If the collection is not found
    """
    if collection_id != "location_proofs":
        error = ErrorResponse(
            title="Collection not found",
            status=404,
            detail=f"Collection '{collection_id}' does not exist",
            instance=f"/collections/{collection_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.model_dump(),
        )

    collection = Collection(
        id="location_proofs",
        title="Location Proofs",
        description="Collection of location proofs (attestations) from EAS",
        keywords=["location", "proof", "attestation", "EAS", "blockchain"],
        license="https://creativecommons.org/licenses/by/4.0/",
        attribution="Astral Network",
        links=[
            Link(
                href=f"/collections/{collection_id}",
                rel="self",
                type="application/json",
                title="Location Proofs Collection",
            ),
            Link(
                href=f"/collections/{collection_id}/items",
                rel="items",
                type="application/geo+json",
                title="Location Proofs Items",
            ),
            Link(
                href=f"/collections/{collection_id}?f=html",
                rel="alternate",
                type="text/html",
                title="HTML version of this collection",
            ),
            Link(
                href="/collections",
                rel="collection",
                type="application/json",
                title="Collections",
            ),
            Link(
                href="/",
                rel="root",
                type="application/json",
                title="Landing page",
            ),
            Link(
                href="https://docs.astral.global/collections/location_proofs",
                rel="describedby",
                type="text/html",
                title="Documentation for the Location Proofs collection",
            ),
        ],
        extent=Extent(
            spatial=SpatialExtent(bbox=[[-180, -90, 180, 90]]),
            temporal=TemporalExtent(interval=[["2024-01-01T00:00:00Z", None]]),
        ),
    )

    if f == FormatEnum.html:
        # Return HTML representation
        link_list = "".join(
            [
                f'<div class="link"><a href="{link.href}">{link.title}</a> '
                f"({link.rel})</div>"
                for link in collection.links
            ]
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{collection.title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .metadata {{ margin-bottom: 20px; }}
                .links {{ margin-top: 20px; }}
                .link {{ margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <h1>{collection.title}</h1>
            <div class="metadata">
                <p><strong>ID:</strong> {collection.id}</p>
                <p><strong>Description:</strong> {collection.description}</p>
                <p><strong>License:</strong> <a href="{collection.license}">{collection.license}</a></p>
                <p><strong>Attribution:</strong> {collection.attribution}</p>
            </div>
            <div class="links">
                <h2>Links</h2>
                <div class="link-list">
                {link_list}
                </div>
            </div>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")

    return collection


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
    # Database session
    session: AsyncSession = Depends(get_session),
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
        session: SQLAlchemy async session

    Returns:
        Union[FeatureCollection, Response]: GeoJSON FeatureCollection or formatted
            response

    Raises:
        HTTPException: If the collection is not found or parameters are invalid
    """
    if collection_id != "location_proofs":
        error = ErrorResponse(
            title="Collection not found",
            status=404,
            detail=f"Collection '{collection_id}' does not exist",
            instance=f"/collections/{collection_id}/items",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.model_dump(),
        )

    # Validate query parameters
    validate_query_params(
        collection_id=collection_id,
        bbox=bbox,
        intersects=intersects,
        within=within,
        datetime_filter=datetime_filter,
    )

    # Additional validation for property filters
    if property_name and not property_op:
        error = ErrorResponse(
            title="Invalid parameter",
            status=400,
            detail="Property operator (property_op) is required when property_name is provided",
            instance=f"/collections/{collection_id}/items?property_name={property_name}",
            validation_errors=[
                {"field": "property_op", "error": "Missing required parameter"}
            ],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.model_dump(),
        )

    if property_op and not property_name:
        error = ErrorResponse(
            title="Invalid parameter",
            status=400,
            detail="Property name (property_name) is required when property_op is provided",
            instance=f"/collections/{collection_id}/items?property_op={property_op.value}",
            validation_errors=[
                {"field": "property_name", "error": "Missing required parameter"}
            ],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.model_dump(),
        )

    # Validate buffer parameter
    if buffer is not None and buffer < 0:
        error = ErrorResponse(
            title="Invalid parameter",
            status=400,
            detail="Buffer distance must be non-negative",
            instance=f"/collections/{collection_id}/items?buffer={buffer}",
            validation_errors=[{"field": "buffer", "error": "Must be non-negative"}],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.model_dump(),
        )

    # Parse and validate spatial filters
    geometry = None
    if intersects:
        geometry = {"type": "intersects", "value": intersects}
    elif within:
        geometry = {"type": "within", "value": within}

    # Apply buffer if specified
    if buffer is not None and buffer > 0 and geometry:
        geometry["buffer"] = str(buffer)

    # Parse temporal filter
    if datetime_filter:
        # Temporal filter is handled directly in the SQL query
        # No need to parse it here as we're using the raw datetime_filter in the SQL query
        pass

    # Parse property filter
    property_filter = None
    if property_name and property_op:
        property_filter = {
            "name": property_name,
            "operator": property_op.value,
            "value": property_value,
        }

    # Parse sorting
    sort_options = None
    if sortby:
        descending = sortby.startswith("-")
        field = sortby[1:] if descending else sortby
        sort_options = {"field": field, "descending": descending}

    # Implement actual feature retrieval from database with filters
    try:
        # Build the SQL query
        query = """
        SELECT
            lp.id,
            lp.uid,
            lp.schema,
            lp.event_timestamp,
            lp.revoked,
            lp.revocable,
            lp.srs,
            lp.location_type,
            ST_AsGeoJSON(lp.location) as location_geojson,
            lp.recipe_type,
            lp.recipe_payload,
            lp.media_type,
            lp.media_data,
            lp.status,
            lp.chain_id,
            lp.attester_id,
            lp.recipient_id,
            lp.memo,
            lp.created_at,
            lp.updated_at,
            a1.address as attester_address,
            a2.address as recipient_address,
            c.name as chain_name
        FROM
            location_proof lp
        LEFT JOIN
            address a1 ON lp.attester_id = a1.id
        LEFT JOIN
            address a2 ON lp.recipient_id = a2.id
        LEFT JOIN
            chain c ON lp.chain_id = c.chain_id
        """

        # Add WHERE clauses based on filters
        where_clauses = []
        params: Dict[str, Any] = {}

        # Handle bbox parameter (convert to float)
        if bbox:
            bbox_parts = bbox.split(",")
            if len(bbox_parts) == 4:
                min_lon = float(bbox_parts[0])
                min_lat = float(bbox_parts[1])
                max_lon = float(bbox_parts[2])
                max_lat = float(bbox_parts[3])

                # Add bbox filter to WHERE clause
                where_clauses.append(
                    f"ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326) && location_proof.location"
                )

        # Handle datetime filter
        if datetime_filter:
            if "=" in datetime_filter:
                # Exact match
                dt_parts = datetime_filter.split("=")
                if len(dt_parts) == 2:
                    timestamp = float(dt_parts[1]) if dt_parts[1] else None
                    if timestamp:
                        where_clauses.append(
                            f"location_proof.event_timestamp = {timestamp}"
                        )
            elif ".." in datetime_filter:
                # Range
                dt_parts = datetime_filter.split("..")
                if len(dt_parts) == 2:
                    start_time = float(dt_parts[0]) if dt_parts[0] else None
                    end_time = float(dt_parts[1]) if dt_parts[1] else None

                    if start_time:
                        where_clauses.append(
                            f"location_proof.event_timestamp >= {start_time}"
                        )
                    if end_time:
                        where_clauses.append(
                            f"location_proof.event_timestamp <= {end_time}"
                        )

        # Add property filters if needed
        if property_filter:
            if property_filter["name"] == "chain_id":
                where_clauses.append("lp.chain_id = :chain_id_filter")
                params["chain_id_filter"] = property_filter["value"]
            elif property_filter["name"] == "attester":
                where_clauses.append("a1.address = :attester")
                params["attester"] = property_filter["value"]
            elif property_filter["name"] == "recipient":
                where_clauses.append("a2.address = :recipient")
                params["recipient"] = property_filter["value"]

        # Combine WHERE clauses if any
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Add ORDER BY clause
        if sort_options:
            sort_field = sort_options["field"]
            sort_direction = "DESC" if sort_options["descending"] else "ASC"

            # Map sort field to actual column
            sort_column = "lp.created_at"  # Default sort
            if sort_field == "timestamp":
                sort_column = "lp.event_timestamp"
            elif sort_field == "chain":
                sort_column = "lp.chain_id"

            query += f" ORDER BY {sort_column} {sort_direction}"
        else:
            # Default sort by created_at descending
            query += " ORDER BY lp.created_at DESC"

        # Add LIMIT and OFFSET
        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = int(limit)
        params["offset"] = int(offset)

        # Execute the query
        result = await session.execute(text(query), params)
        rows = result.fetchall()

        # Get total count for numberMatched
        count_query = "SELECT COUNT(*) FROM location_proof"
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)

        count_result = await session.execute(text(count_query), params)
        total_count = count_result.scalar()

        # Convert rows to GeoJSON features
        features = []
        for row in rows:
            # Convert row to dict
            row_dict = {}
            for key, value in row._mapping.items():
                row_dict[key] = value

            # Parse location GeoJSON
            location_geojson = json.loads(row_dict["location_geojson"])

            # Create properties
            properties = {
                "uid": row_dict["uid"],
                "schema": row_dict["schema"],
                "eventTimestamp": row_dict["event_timestamp"],
                "revoked": row_dict["revoked"],
                "revocable": row_dict["revocable"],
                "srs": row_dict["srs"],
                "locationType": row_dict["location_type"],
                "status": row_dict["status"],
                "chainId": row_dict["chain_id"],
                "chainName": row_dict["chain_name"],
                "attester": row_dict["attester_address"],
                "recipient": row_dict["recipient_address"],
                "memo": row_dict["memo"],
                "createdAt": (
                    row_dict["created_at"].isoformat()
                    if row_dict["created_at"]
                    else None
                ),
                "updatedAt": (
                    row_dict["updated_at"].isoformat()
                    if row_dict["updated_at"]
                    else None
                ),
            }

            # Create feature links
            feature_links = [
                Link(
                    href=f"/collections/{collection_id}/items/{row_dict['id']}",
                    rel="self",
                    type="application/geo+json",
                    title="This feature",
                ),
                Link(
                    href=f"/collections/{collection_id}",
                    rel="collection",
                    type="application/json",
                    title="The collection description",
                ),
            ]

            # Create feature
            feature = Feature(
                type="Feature",
                geometry=location_geojson,
                properties=properties,
                id=row_dict["id"],
                links=feature_links,
            )

            features.append(feature)

    except Exception as e:
        # Log the error
        print(f"Error retrieving features: {str(e)}")
        # Return empty feature collection on error
        features = []
        total_count = 0

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

    # Create links for different formats
    format_links = []
    for format_type in FormatEnum:
        if format_type != f:
            format_params = query_params.copy()
            format_found = False
            for i, param in enumerate(format_params):
                if param.startswith("f="):
                    format_params[i] = f"f={format_type.value}"
                    format_found = True
                    break

            if not format_found:
                format_params.append(f"f={format_type.value}")

            format_query_string = "&".join(format_params)
            format_url = f"{base_url}?{format_query_string}"

            media_type = "application/geo+json"
            if format_type == FormatEnum.html:
                media_type = "text/html"
            elif format_type == FormatEnum.json:
                media_type = "application/json"

            format_links.append(
                Link(
                    href=format_url,
                    rel="alternate",
                    type=media_type,
                    title=f"{format_type.value.upper()} version",
                )
            )

    links = [
        Link(
            href=self_url,
            rel="self",
            type="application/geo+json",
            title="This collection",
        ),
        Link(
            href=next_url,
            rel="next",
            type="application/geo+json",
            title="Next page",
        ),
        Link(
            href=f"/collections/{collection_id}",
            rel="collection",
            type="application/json",
            title="The collection description",
        ),
        Link(
            href="/",
            rel="root",
            type="application/json",
            title="Landing page",
        ),
    ]

    # Add format links
    links.extend(format_links)

    feature_collection = FeatureCollection(
        type="FeatureCollection",
        features=features,
        links=links,
        timeStamp=datetime.now(timezone.utc).isoformat(),
        numberMatched=total_count or 0,
        numberReturned=len(features),
    )

    if f == FormatEnum.html:
        # Return HTML representation
        link_list = "".join(
            [
                f'<div class="link"><a href="{link.href}">{link.title}</a> '
                f"({link.rel})</div>"
                for link in feature_collection.links
            ]
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Features - {collection_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .metadata {{ margin-bottom: 20px; }}
                .links {{ margin-top: 20px; }}
                .link {{ margin-bottom: 10px; }}
                .features {{ margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>Features - {collection_id}</h1>
            <div class="metadata">
                <p><strong>Timestamp:</strong> {feature_collection.timeStamp}</p>
                <p><strong>Number matched:</strong> {feature_collection.numberMatched}</p>
                <p><strong>Number returned:</strong> {feature_collection.numberReturned}</p>
            </div>
            <div class="links">
                <h2>Links</h2>
                <div class="link-list">
                {link_list}
                </div>
            </div>
            <div class="features">
                <h2>Features</h2>
                <p>No features found matching the query criteria.</p>
            </div>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")

    return feature_collection


@router.get("/collections/{collection_id}/items/{feature_id}", response_model=Feature)
async def get_feature(
    collection_id: str,
    feature_id: Any,  # Changed from UUID to Any
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
        error = ErrorResponse(
            title="Collection not found",
            status=404,
            detail=f"Collection '{collection_id}' does not exist",
            instance=(f"/collections/{collection_id}/items/{feature_id}"),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.model_dump(),
        )

    # TODO: Implement actual feature retrieval from database
    # For now, return a 404 since we don't have any features
    error = ErrorResponse(
        title="Feature not found",
        status=404,
        detail=(
            f"Feature '{feature_id}' does not exist in collection '{collection_id}'"
        ),
        instance=(f"/collections/{collection_id}/items/{feature_id}"),
    )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=error.model_dump(),
    )
