"""Unit tests for advanced query capabilities in OGC API Features."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_spatial_filters() -> None:
    """Test spatial filter parameters."""
    # Test bbox parameter
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-90,180,90"}
    )
    assert response.status_code == 200

    # Test invalid bbox format
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-90,180"}
    )
    assert response.status_code == 400
    assert "Invalid bbox format" in response.json()["detail"]

    # Test invalid bbox values
    response = client.get(
        "/collections/location_proofs/items", params={"bbox": "-180,-90,180,invalid"}
    )
    assert response.status_code == 400
    assert "Invalid bbox values" in response.json()["detail"]

    # Test intersects parameter
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": '{"type":"Point","coordinates":[0,0]}'},
    )
    assert response.status_code == 200

    # Test within parameter
    polygon = '{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}'
    response = client.get(
        "/collections/location_proofs/items", params={"within": polygon}
    )
    assert response.status_code == 200

    # Test buffer parameter
    response = client.get(
        "/collections/location_proofs/items",
        params={"intersects": '{"type":"Point","coordinates":[0,0]}', "buffer": 1000},
    )
    assert response.status_code == 200


def test_temporal_filters() -> None:
    """Test temporal filter parameters."""
    # Test single date
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z"},
    )
    assert response.status_code == 200

    # Test date interval
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z"},
    )
    assert response.status_code == 200

    # Test open-ended interval (start date only)
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z/.."},
    )
    assert response.status_code == 200

    # Test open-ended interval (end date only)
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "../2023-12-31T23:59:59Z"},
    )
    assert response.status_code == 200

    # Test with temporal operator
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z", "temporal_op": "after"},
    )
    assert response.status_code == 200

    # Test invalid datetime format
    response = client.get(
        "/collections/location_proofs/items",
        params={"datetime": "2023-01-01T00:00:00Z/2023-12-31T23:59:59Z/extra"},
    )
    assert response.status_code == 400
    assert "Invalid datetime format" in response.json()["detail"]


def test_property_filters() -> None:
    """Test property filter parameters."""
    # Test property equals
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "property_name": "status",
            "property_op": "eq",
            "property_value": "verified",
        },
    )
    assert response.status_code == 200

    # Test property greater than
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "property_name": "accuracy",
            "property_op": "gt",
            "property_value": "10",
        },
    )
    assert response.status_code == 200

    # Test property LIKE
    response = client.get(
        "/collections/location_proofs/items",
        params={
            "property_name": "provider",
            "property_op": "like",
            "property_value": "GPS%",
        },
    )
    assert response.status_code == 200


def test_sorting() -> None:
    """Test sorting parameters."""
    # Test ascending sort
    response = client.get(
        "/collections/location_proofs/items", params={"sortby": "timestamp"}
    )
    assert response.status_code == 200

    # Test descending sort
    response = client.get(
        "/collections/location_proofs/items", params={"sortby": "-timestamp"}
    )
    assert response.status_code == 200


def test_combined_filters() -> None:
    """Test combining multiple filter types."""
    # Test spatial + temporal + property filters
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

    # Verify self link contains all parameters
    data = response.json()
    self_link = next(link for link in data["links"] if link["rel"] == "self")
    href = self_link["href"]

    assert "bbox=-180,-90,180,90" in href
    assert "datetime=2023-01-01T00:00:00Z/2023-12-31T23:59:59Z" in href
    assert "property_name=accuracy" in href
    assert "property_op=gt" in href
    assert "property_value=10" in href
    assert "sortby=-timestamp" in href

    # Verify next link contains all parameters with updated offset
    next_link = next(link for link in data["links"] if link["rel"] == "next")
    next_href = next_link["href"]

    assert "bbox=-180,-90,180,90" in next_href
    assert "datetime=2023-01-01T00:00:00Z/2023-12-31T23:59:59Z" in next_href
    assert "property_name=accuracy" in next_href
    assert "property_op=gt" in next_href
    assert "property_value=10" in next_href
    assert "sortby=-timestamp" in next_href
    assert "offset=10" in next_href  # Default limit is 10
