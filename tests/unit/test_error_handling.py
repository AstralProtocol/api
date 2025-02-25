"""Unit tests for error handling and validation in OGC API Features."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_error_response_format() -> None:
    """Test the error response format follows RFC 7807 Problem Details."""
    # Test with invalid bbox parameter
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "invalid"}
    )
    assert response.status_code == 400
    data = response.json()

    # Verify error response structure
    assert "detail" in data
    error = data["detail"]
    assert "type" in error
    assert "title" in error
    assert "status" in error
    assert error["status"] == 400
    assert "detail" in error
    assert "instance" in error
    assert "validation_errors" in error
    assert isinstance(error["validation_errors"], list)
    assert len(error["validation_errors"]) > 0
    assert "field" in error["validation_errors"][0]
    assert "error" in error["validation_errors"][0]


def test_bbox_validation() -> None:
    """Test validation of bbox parameter."""
    # Test with valid bbox
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-90,180,90"}
    )
    assert response.status_code == 200

    # Test with invalid format (missing value)
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-90,180"}
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid bbox parameter" in error["detail"]

    # Test with invalid values (non-numeric)
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-90,180,invalid"}
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid bbox parameter" in error["detail"]

    # Test with invalid range (longitude out of bounds)
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-190,-90,180,90"}
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid bbox parameter" in error["detail"]
    assert "Longitude values must be between -180 and 180" in error["detail"]

    # Test with invalid range (latitude out of bounds)
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-100,180,90"}
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid bbox parameter" in error["detail"]
    assert "Latitude values must be between -90 and 90" in error["detail"]

    # Test with invalid range (min > max)
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "180,-90,-180,90"}
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid bbox parameter" in error["detail"]
    assert "minLon must be less than or equal to maxLon" in error["detail"]


def test_datetime_validation() -> None:
    """Test validation of datetime parameter."""
    # Test with valid single date
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z"},
    )
    assert response.status_code == 200

    # Test with valid date interval
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z"},
    )
    assert response.status_code == 200

    # Test with valid open-ended interval (start date only)
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z/.."},
    )
    assert response.status_code == 200

    # Test with valid open-ended interval (end date only)
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "../2023-12-31T23:59:59Z"},
    )
    assert response.status_code == 200

    # Test with invalid format (too many parts)
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z/extra"},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid datetime parameter" in error["detail"]

    # Test with invalid date format
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01"},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid datetime parameter" in error["detail"]


def test_geojson_validation() -> None:
    """Test validation of GeoJSON parameters."""
    # Test with valid Point GeoJSON
    valid_point = '{"type":"Point","coordinates":[0,0]}'
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": valid_point},
    )
    assert response.status_code == 200

    # Test with valid Polygon GeoJSON
    valid_polygon = '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}'
    response = client.get(
        "/collections/location_proofs/items",
        params={"within": valid_polygon},
    )
    assert response.status_code == 200

    # Test with invalid JSON
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": "{invalid json}"},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid intersects parameter" in error["detail"]
    assert "Invalid JSON format" in error["detail"]

    # Test with missing type property
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": '{"coordinates":[0,0]}'},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid intersects parameter" in error["detail"]
    assert "Missing 'type' property" in error["detail"]

    # Test with invalid geometry type
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": '{"type":"InvalidType","coordinates":[0,0]}'},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid intersects parameter" in error["detail"]
    assert "Invalid geometry type" in error["detail"]

    # Test with missing coordinates
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": '{"type":"Point"}'},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid intersects parameter" in error["detail"]
    assert "Missing 'coordinates' property" in error["detail"]


def test_property_filter_validation() -> None:
    """Test validation of property filter parameters."""
    # Test with all property filter parameters
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "property_name": "status",
            "property_op": "eq",
            "property_value": "verified",
        },
    )
    assert response.status_code == 200

    # Test with missing property_op
    response = client.get(
        "/collections/location_proofs/items",
        params={"property_name": "status"},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Property operator (property_op) is required" in error["detail"]

    # Test with missing property_name
    response = client.get(
        "/collections/location_proofs/items",
        params={"property_op": "eq"},
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Property name (property_name) is required" in error["detail"]


def test_buffer_validation() -> None:
    """Test validation of buffer parameter."""
    # Test with valid buffer
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "intersects": '{"type":"Point","coordinates":[0,0]}',
            "buffer": 1000,
        },
    )
    assert response.status_code == 200

    # Test with negative buffer
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "intersects": '{"type":"Point","coordinates":[0,0]}',
            "buffer": -1000,
        },
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Buffer distance must be non-negative" in error["detail"]


def test_combined_validation() -> None:
    """Test validation with multiple parameters."""
    # Test with multiple valid parameters
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "bbox": "-180,-90,180,90",
            "datetime": "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z",
            "property_name": "accuracy",
            "property_op": "gt",
            "property_value": "10",
            "sortby": "-timestamp",
        },
    )
    assert response.status_code == 200

    # Test with one invalid parameter among valid ones
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "bbox": "invalid",
            "datetime": "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z",
            "property_name": "accuracy",
            "property_op": "gt",
            "property_value": "10",
        },
    )
    assert response.status_code == 400
    error = response.json()["detail"]
    assert "Invalid bbox parameter" in error["detail"]
