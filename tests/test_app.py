import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api_auth import app, get_current_user, User, ReportGenerator
from datetime import datetime, timedelta, timezone
import jwt

client = TestClient(app)

# Mock user for authentication
mock_user = User(username="testuser", hashed_password="hashed_password")

def get_test_user():
    return mock_user

app.dependency_overrides[get_current_user] = get_test_user

@pytest.fixture
def mock_db():
    with patch('api_auth.get_db') as mock:
        yield mock

@pytest.fixture
def mock_report_generator():
    with patch('api_auth.ReportGenerator') as mock:
        instance = mock.return_value
        instance.load_result.return_value = True
        instance.final_result = {"test": "result"}
        instance.reprocess_content.return_value = {
            "original_content": "original",
            "modified_content": "modified",
            "part": "test_part"
        }
        instance.username = "testuser"
        yield mock

def test_register_user(mock_db):
    mock_db_session = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_db_session
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.post("/register", json={"username": "newuser", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_for_access_token(mock_db):
    mock_db_session = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_db_session
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    with patch('api_auth.verify_password', return_value=True):
        response = client.post("/token", data={"username": "testuser", "password": "password123"})
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"

def test_generate_report(mock_report_generator):
    mock_instance = mock_report_generator.return_value
    mock_instance.generate_report.return_value = ({"result": "mocked result"}, 10.5)

    response = client.post("/generate_report", json={
        "theme": "Test Theme",
        "titles": {"Title1": ["Subtitle1"]},
        "links": ["http://example.com"],
        "openai_config": {"openai_key": "test_key"}
    })

    assert response.status_code == 200
    assert "result" in response.json()
    assert "total_time" in response.json()

def test_check_result(mock_report_generator):
    mock_instance = mock_report_generator.return_value
    mock_instance.load_result.return_value = True

    response = client.get("/check_result")

    assert response.status_code == 200
    assert response.json() == {"result": True}

def test_get_report(mock_report_generator):
    mock_instance = mock_report_generator.return_value
    mock_instance.load_result.return_value = True
    mock_instance.final_result = {"test": "result"}

    response = client.get("/get_report")

    assert response.status_code == 200
    assert response.json() == {"result": {"test": "result"}}

def test_reprocess_content(mock_report_generator):
    mock_instance = mock_report_generator.return_value
    mock_instance.reprocess_content.return_value = {
        "original_content": "original",
        "modified_content": "modified",
        "part": "test_part"
    }

    response = client.post("/reprocess_content", json={
        "command": "Test command",
        "openai_config": {"openai_key": "test_key"}
    })

    assert response.status_code == 200
    assert "result" in response.json()
    assert "original_content" in response.json()["result"]
    assert "modified_content" in response.json()["result"]
    assert "part" in response.json()["result"]

def test_delete_report(mock_report_generator):
    mock_instance = mock_report_generator.return_value
    mock_instance.username = "testuser"

    response = client.delete("/delete_report")

    assert response.status_code == 200
    assert response.json() == {"result": "Report deleted"}

# Additional tests can be added here to cover more scenarios and edge cases