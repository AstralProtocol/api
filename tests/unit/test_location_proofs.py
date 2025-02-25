"""Unit tests for OGC API Features endpoints."""

from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_landing_page() -> None:
    """Test the landing page endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "Astral API"
    description = "A decentralized geospatial data API with EAS integration"
    assert data["description"] == description

    # Verify required links are present
    links = {link["rel"]: link for link in data["links"]}
    assert "self" in links
    assert "service-desc" in links
    assert "conformance" in links
    assert "data" in links


def test_api_definition() -> None:
    """Test the OpenAPI definition endpoint."""
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()

    # Basic OpenAPI schema validation
    assert "openapi" in data
    assert "paths" in data
    assert "components" in data
    assert "/collections" in data["paths"]


def test_conformance() -> None:
    """Test the conformance declaration endpoint."""
    response = client.get("/conformance")
    assert response.status_code == 200
    data = response.json()

    assert "conformsTo" in data
    conformance_classes = data["conformsTo"]

    # Verify required conformance classes
    assert (
        "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"
        in conformance_classes
    )
    assert (
        "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30"
        in conformance_classes
    )
    assert (
        "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson"
        in conformance_classes
    )


def test_list_collections() -> None:
    """Test the collections listing endpoint."""
    response = client.get("/collections")
    assert response.status_code == 200
    data = response.json()

    assert "collections" in data
    assert len(data["collections"]) > 0

    collection = data["collections"][0]
    assert collection["id"] == "location_proofs"
    assert "title" in collection
    assert "description" in collection
    assert "links" in collection
    assert "extent" in collection

    # Verify collection links
    links = {link["rel"]: link for link in collection["links"]}
    assert "self" in links
    assert "items" in links


def test_get_collection() -> None:
    """Test getting a specific collection."""
    # Test valid collection
    response = client.get("/collections/location_proofs")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "location_proofs"
    assert "title" in data
    assert "description" in data
    assert "extent" in data
    assert "links" in data

    # Test invalid collection
    response = client.get("/collections/nonexistent")
    assert response.status_code == 404


def test_get_features() -> None:
    """Test getting features from a collection."""
    # Test basic request
    response = client.get("/collections/location_proofs/items")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert "links" in data
    assert "timeStamp" in data
    assert "numberMatched" in data
    assert "numberReturned" in data

    # Test with query parameters
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "bbox": "-180,-90,180,90",
            "datetime": "2024-01-01T00:00:00Z",
            "limit": 5,
            "offset": 0,
        },
    )
    assert response.status_code == 200

    # Test invalid collection
    response = client.get("/collections/nonexistent/items")
    assert response.status_code == 404

    # Test format parameter
    response = client.get("/collections/location_proofs/items", params={"f": "html"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_get_feature() -> None:
    """Test getting a single feature."""
    test_uuid = UUID("12345678-1234-5678-1234-567812345678")

    # Test with valid collection but non-existent feature
    response = client.get(f"/collections/location_proofs/items/{test_uuid}")
    assert response.status_code == 404

    # Test with invalid collection
    response = client.get(f"/collections/nonexistent/items/{test_uuid}")
    assert response.status_code == 404

    # Test with invalid UUID
    response = client.get("/collections/location_proofs/items/not-a-uuid")
    assert response.status_code == 422  # FastAPI validation error
