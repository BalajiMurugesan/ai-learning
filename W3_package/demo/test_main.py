import pytest  # Imports the pytest testing framework
from unittest.mock import AsyncMock, MagicMock, patch  # Imports mocking utilities from unittest
from fastapi.testclient import TestClient  # Imports TestClient from FastAPI for testing endpoints
from main import app  # Imports the FastAPI application instance from main

# Initialize FastAPI TestClient
client = TestClient(app)  # Instantiates the test client with the FastAPI app


# ==========================================
# 1. Test Health Check Endpoint
# ==========================================
def test_health_check():  # Defines the health check test function
    response = client.get("/health")  # Sends a GET request to the /health endpoint
    assert response.status_code == 200  # Asserts that the response status code is 200
    assert response.json() == {"status": "ok"}  # Asserts that the response JSON matches the expected status


# ==========================================
# 2. Test GET Standard Generation (Mocked OpenAI)
# ==========================================
@patch("main.client.chat.completions.create", new_callable=AsyncMock)  # Patches the OpenAI completions create method with an AsyncMock
def test_generate_get_standard(mock_openai_create):  # Defines the standard GET generation test function
    # Mock OpenAI response object structure
    mock_response = MagicMock()  # Creates a mock response object
    mock_response.choices = [MagicMock()]  # Initializes the choices list with a mock choice object
    mock_response.choices[0].message.content = "This is a mock response."  # Sets the mock message content
    mock_response.usage.prompt_tokens = 10  # Sets the mock prompt token count
    mock_response.usage.completion_tokens = 5  # Sets the mock completion token count
    mock_response.usage.total_tokens = 15  # Sets the mock total token count
    mock_openai_create.return_value = mock_response  # Configures the mock return value

    response = client.get("/generate/get?query=What%20is%20FastAPI")  # Sends a GET request with query parameters to the FastAPI endpoint
    
    assert response.status_code == 200  # Asserts a successful status code
    data = response.json()  # Parses the JSON response body
    assert data["model"] == "gpt-4o-mini"  # Asserts the model name matches the expected value
    assert data["response"] == "This is a mock response."  # Asserts the response text matches the mock
    assert data["usage"]["prompt_tokens"] == 10  # Verifies the prompt tokens value
    assert data["usage"]["completion_tokens"] == 5  # Verifies the completion tokens value
    assert data["usage"]["total_tokens"] == 15  # Verifies the total tokens value
    assert "cost_usd" in data["usage"]  # Verifies that cost_usd exists in the usage dictionary


# ==========================================
# 3. Test POST Standard Generation (Mocked OpenAI)
# ==========================================
@patch("main.client.chat.completions.create", new_callable=AsyncMock)  # Patches the OpenAI completions create method for the POST test
def test_generate_post_standard(mock_openai_create):  # Defines the standard POST generation test function
    mock_response = MagicMock()  # Creates a mock response object
    mock_response.choices = [MagicMock()]  # Initializes the choices list with a mock choice object
    mock_response.choices[0].message.content = "Mock post response."  # Sets the mock post response content
    mock_response.usage.prompt_tokens = 12  # Sets the prompt tokens for the POST mock
    mock_response.usage.completion_tokens = 8  # Sets the completion tokens for the POST mock
    mock_response.usage.total_tokens = 20  # Sets the total tokens for the POST mock
    mock_openai_create.return_value = mock_response  # Configures the mock return value for the POST test

    payload = {"query": "Explain testing in FastAPI."}  # Defines the JSON payload for the POST request
    response = client.post("/generate/post", json=payload)  # Sends a POST request with the JSON payload
    
    assert response.status_code == 200  # Asserts the POST response status code is 200
    data = response.json()  # Parses the JSON response body
    assert data["response"] == "Mock post response."  # Asserts the response content matches the mock
    assert data["usage"]["total_tokens"] == 20  # Verifies the total token usage value


# ==========================================
# 4. Test Strict Pydantic Parameter Validation
# ==========================================
def test_validation_error_extra_field():  # Defines test function for extra field validation error
    # Passing an incorrect/extra parameter like 'q' instead of 'query'
    # should be rejected because extra="forbid" is set on the Question model.
    response = client.get("/generate/get?q=InvalidField")  # Sends a GET request with an invalid query parameter
    
    assert response.status_code == 422  # Unprocessable Entity
    error_data = response.json()  # Parses the error response JSON
    assert "detail" in error_data  # Asserts that error details are present in the response


def test_validation_error_missing_field():  # Defines test function for missing required field validation error
    # Omitting the required 'query' parameter entirely should fail
    response = client.get("/generate/get")  # Sends a GET request without the required query parameter
    assert response.status_code == 422  # Asserts that the response status code indicates an unprocessable entity