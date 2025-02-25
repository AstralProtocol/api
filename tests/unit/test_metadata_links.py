"""Unit tests for metadata and links structure in OGC API Features."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_collection_metadata() -> None:
    """Test the enhanced metadata for collections."""
    response = client.get("/collections/location_proofs")
    assert response.status_code == 200
    data = response.json()

    # Test enhanced metadata fields
    assert "keywords" in data
    assert isinstance(data["keywords"], list)
    assert len(data["keywords"]) > 0
    assert "license" in data
    assert data["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "attribution" in data
    assert data["attribution"] == "Astral Network"

    # Test extent structure
    assert "extent" in data
    assert "spatial" in data["extent"]
    assert "temporal" in data["extent"]
    assert "bbox" in data["extent"]["spatial"]
    assert "interval" in data["extent"]["temporal"]

    # Test CRS information
    assert "crs" in data
    assert isinstance(data["crs"], list)
    assert "http://www.opengis.net/def/crs/OGC/1.3/CRS84" in data["crs"]
    assert "storageCRS" in data


def test_collection_links() -> None:
    """Test the enhanced link relations for collections."""
    response = client.get("/collections/location_proofs")
    assert response.status_code == 200
    data = response.json()

    # Test links structure
    assert "links" in data
    links = {link["rel"]: link for link in data["links"]}

    # Verify required link relations
    assert "self" in links
    assert "items" in links
    assert "alternate" in links
    assert "collection" in links
    assert "root" in links
    assert "describedby" in links

    # Verify link properties
    for link in data["links"]:
        assert "href" in link
        assert "rel" in link
        assert "type" in link
        assert "title" in link


def test_features_links() -> None:
    """Test the enhanced link relations for features."""
    response = client.get("/collections/location_proofs/items")
    assert response.status_code == 200
    data = response.json()

    # Test links structure
    assert "links" in data
    links = {link["rel"]: link for link in data["links"]}

    # Verify required link relations
    assert "self" in links
    assert "next" in links
    assert "collection" in links
    assert "root" in links

    # Check for alternate format links
    alternate_links = [link for link in data["links"] if link["rel"] == "alternate"]
    assert len(alternate_links) > 0

    # Verify different media types are available
    media_types = [link["type"] for link in alternate_links]
    assert "text/html" in media_types


def test_html_response_format() -> None:
    """Test HTML response format for collections and features."""
    # Test collection HTML format
    response = client.get("/collections/location_proofs?f=html")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<html>" in response.text
    assert "<title>" in response.text
    assert "Location Proofs" in response.text

    # Test features HTML format
    response = client.get("/collections/location_proofs/items?f=html")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<html>" in response.text
    assert "<title>" in response.text
    assert "Features" in response.text


def test_error_responses() -> None:
    """Test proper error responses and status codes."""
    # Test 404 for non-existent collection
    response = client.get("/collections/nonexistent")
    assert response.status_code == 404
    data = response.json()

    # Verify error response structure (nested inside 'detail')
    assert "detail" in data
    error = data["detail"]
    assert "title" in error
    assert "status" in error
    assert error["status"] == 404
    assert "detail" in error
    assert "instance" in error
    assert "type" in error

    # Test 404 for non-existent feature
    response = client.get(
        "/collections/location_proofs/items/12345678-1234-5678-1234-567812345678"
    )
    assert response.status_code == 404
    data = response.json()

    # Verify error response structure (nested inside 'detail')
    assert "detail" in data
    error = data["detail"]
    assert "title" in error
    assert "status" in error
    assert error["status"] == 404
    assert "detail" in error
    assert "instance" in error
    assert "type" in error

    # Test 400 for invalid query parameter
    response = client.get("/collections/location_proofs/items?bbox=invalid")
    assert response.status_code == 400
    data = response.json()

    # Verify error response structure (nested inside 'detail')
    assert "detail" in data
    error = data["detail"]
    assert "title" in error
    assert "status" in error
    assert error["status"] == 400
    assert "detail" in error
    assert "instance" in error
    assert "type" in error
