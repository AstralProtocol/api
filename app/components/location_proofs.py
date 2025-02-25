"""OGC API - Features compliant location proofs router."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
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

    bbox: List[List[float]] = Field(default_factory=lambda: [[-180.0, -90.0, 180.0, 90.0]])
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
    id: UUID
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
    """Error response model following OGC API - Features specification."""

    type: str = "https://api.astral.global/errors/1"
    title: str
    status: int
    detail: str
    instance: Optional[str] = None


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
        html_content = (
            f"""
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
                <p><strong>License:</strong> """
            + f"""<a href="{collection.license}">{collection.license}</a></p>
                <p><strong>Attribution:</strong> {collection.attribution}</p>
            </div>
            <div class="links">
                <h2>Links</h2>
                <div class="link-list">"""
            + "".join(
                [
                    f'<div class="link"><a href="{link.href}">{link.title}</a> ({link.rel})</div>'
                    for link in collection.links
                ]
            )
            + """
                </div>
            </div>
        </body>
        </html>
        """
        )
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

    # Parse and validate spatial filters
    if bbox:
        try:
            bbox_parts = bbox.split(",")
            if len(bbox_parts) != 4:
                error = ErrorResponse(
                    title="Invalid parameter",
                    status=400,
                    detail=(
                        "Invalid bbox format. Expected: minLon,minLat,maxLon,maxLat"
                    ),
                    instance=(f"/collections/{collection_id}/items?bbox={bbox}"),
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error.model_dump(),
                )
            # Parse bbox coordinates but don't store in unused variable
            [float(part) for part in bbox_parts]
        except ValueError:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail="Invalid bbox values. Expected numeric values.",
                instance=(f"/collections/{collection_id}/items?bbox={bbox}"),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
            )

    # Parse and validate intersects/within GeoJSON
    geometry = None
    if intersects:
        try:
            # In a real implementation, we would parse and validate the GeoJSON here
            # For now, we'll just check if it's valid JSON
            geometry = {"type": "intersects", "value": intersects}
        except Exception:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail="Invalid GeoJSON for intersects parameter.",
                instance=(
                    f"/collections/{collection_id}/items?intersects={intersects}"
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
            )
    elif within:
        try:
            # In a real implementation, we would parse and validate the GeoJSON here
            geometry = {"type": "within", "value": within}
        except Exception:
            error = ErrorResponse(
                title="Invalid parameter",
                status=400,
                detail="Invalid GeoJSON for within parameter.",
                instance=(f"/collections/{collection_id}/items?within={within}"),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.model_dump(),
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
                error = ErrorResponse(
                    title="Invalid parameter",
                    status=400,
                    detail=("Invalid datetime format. Expected: date or start/end"),
                    instance=(
                        f"/collections/{collection_id}/items?datetime={datetime_filter}"
                    ),
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error.model_dump(),
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
        features=[],
        links=links,
        timeStamp=datetime.now(UTC).isoformat(),
        numberMatched=0,
        numberReturned=0,
    )

    if f == FormatEnum.html:
        # Return HTML representation
        html_content = (
            f"""
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
                <p><strong>Timestamp:</strong> {feature_collection.timeStamp}</p>"""
            + f"""
                <p><strong>Number matched:</strong> {feature_collection.numberMatched}</p>
                <p><strong>Number returned:</strong> {feature_collection.numberReturned}</p>
            </div>
            <div class="links">
                <h2>Links</h2>
                <div class="link-list">"""
            + "".join(
                [
                    f'<div class="link"><a href="{link.href}">{link.title}</a> ({link.rel})</div>'
                    for link in feature_collection.links
                ]
            )
            + """
                </div>
            </div>
            <div class="features">
                <h2>Features</h2>
                <p>No features found matching the query criteria.</p>
            </div>
        </body>
        </html>
        """
        )
        return Response(content=html_content, media_type="text/html")

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
