import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------
# Make the repository root available to Python
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------
# Lambda environment variables
# ---------------------------------------------------------

# These test values are set before importing lambda_function.py
# because the Lambda application reads them during startup.

os.environ["EVENTS_TABLE"] = "GNAF-Events"
os.environ["REGISTRATIONS_TABLE"] = "GNAF-Registrations"
os.environ["REGISTRATIONS_INDEX"] = "eventId-registrationDate-index"
os.environ["TICKET_PREFIX"] = "GNAF"


# ---------------------------------------------------------
# Test fixture
# ---------------------------------------------------------

@pytest.fixture(scope="module")
def lambda_app():
    """
    Import lambda_function.py while mocking AWS resources.

    This prevents the unit tests from connecting to real
    DynamoDB tables or making AWS service calls.
    """

    mock_dynamodb_resource = MagicMock()
    mock_dynamodb_client = MagicMock()

    with patch(
        "boto3.resource",
        return_value=mock_dynamodb_resource,
    ), patch(
        "boto3.client",
        return_value=mock_dynamodb_client,
    ):

        # Remove a previous import if one exists.
        if "lambda_function" in sys.modules:
            del sys.modules["lambda_function"]

        module = importlib.import_module(
            "lambda_function"
        )

    return module


# ---------------------------------------------------------
# Health endpoint test
# ---------------------------------------------------------

def test_health_endpoint(lambda_app):
    event = {
        "requestContext": {
            "http": {
                "method": "GET"
            }
        },
        "rawPath": "/health",
    }

    context = MagicMock()
    context.aws_request_id = "test-request"

    response = lambda_app.lambda_handler(
        event,
        context,
    )

    body = json.loads(
        response["body"]
    )

    assert response["statusCode"] == 200
    assert body["status"] == "healthy"

    assert (
        body["service"]
        == "GNAF Event Registration API"
    )


# ---------------------------------------------------------
# Unknown route test
# ---------------------------------------------------------

def test_unknown_route_returns_404(lambda_app):
    event = {
        "requestContext": {
            "http": {
                "method": "GET"
            }
        },
        "rawPath": "/unknown",
    }

    context = MagicMock()
    context.aws_request_id = "test-request"

    response = lambda_app.lambda_handler(
        event,
        context,
    )

    body = json.loads(
        response["body"]
    )

    assert response["statusCode"] == 404

    assert (
        "No route exists"
        in body["message"]
    )


# ---------------------------------------------------------
# Registration validation test
# ---------------------------------------------------------

def test_registration_validation(lambda_app):
    data = {
        "fullName": "  Kojo Asare  ",
        "email": "  KOJO.ASARE@EXAMPLE.COM ",
        "phone": "0240000000",
    }

    full_name, email, phone = (
        lambda_app.validate_registration(
            data
        )
    )

    assert full_name == "Kojo Asare"
    assert email == "kojo.asare@example.com"
    assert phone == "0240000000"


# ---------------------------------------------------------
# Invalid email test
# ---------------------------------------------------------

def test_invalid_email_is_rejected(lambda_app):
    data = {
        "fullName": "Kojo Asare",
        "email": "wrong-email",
        "phone": "0240000000",
    }

    with pytest.raises(
        ValueError,
        match="valid email",
    ):
        lambda_app.validate_registration(
            data
        )


# ---------------------------------------------------------
# Missing registration information test
# ---------------------------------------------------------

def test_missing_registration_fields(lambda_app):
    data = {
        "fullName": "",
        "email": "",
        "phone": "",
    }

    with pytest.raises(
        ValueError,
        match="required",
    ):
        lambda_app.validate_registration(
            data
        )


# ---------------------------------------------------------
# Duplicate-registration ID test
# ---------------------------------------------------------

def test_registration_id_is_deterministic(
    lambda_app,
):
    first_id = (
        lambda_app.create_registration_id(
            "GNAF-2026",
            "participant@example.com",
        )
    )

    second_id = (
        lambda_app.create_registration_id(
            "GNAF-2026",
            "participant@example.com",
        )
    )

    assert first_id == second_id

    assert first_id.startswith(
        "GNAF-2026-"
    )


# ---------------------------------------------------------
# Ticket number test
# ---------------------------------------------------------

def test_ticket_number_prefix(lambda_app):
    ticket = (
        lambda_app.create_ticket_number()
    )

    assert ticket.startswith(
        "GNAF-"
    )

    assert len(ticket) > len(
        "GNAF-"
    )
