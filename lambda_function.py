import base64
import hashlib
import html
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------
# Environment variables
# ---------------------------------------------------------

EVENTS_TABLE = os.environ["EVENTS_TABLE"]
REGISTRATIONS_TABLE = os.environ["REGISTRATIONS_TABLE"]
REGISTRATIONS_INDEX = os.environ["REGISTRATIONS_INDEX"]

TICKET_PREFIX = os.environ.get(
    "TICKET_PREFIX",
    "GNAF",
)

SES_SENDER_EMAIL = os.environ.get(
    "SES_SENDER_EMAIL",
    "",
).strip()


# ---------------------------------------------------------
# AWS resources
# ---------------------------------------------------------

dynamodb = boto3.resource(
    "dynamodb"
)

dynamodb_client = boto3.client(
    "dynamodb"
)

ses_client = boto3.client(
    "ses"
)

events_table = dynamodb.Table(
    EVENTS_TABLE
)

registrations_table = dynamodb.Table(
    REGISTRATIONS_TABLE
)

serializer = TypeSerializer()


# ---------------------------------------------------------
# API response configuration
# ---------------------------------------------------------

HEADERS = {
    "Content-Type":
        "application/json",

    "Access-Control-Allow-Origin":
        "*",

    "Access-Control-Allow-Headers":
        "Content-Type,Authorization",

    "Access-Control-Allow-Methods":
        "GET,POST,DELETE,OPTIONS",
}


class DecimalEncoder(
    json.JSONEncoder
):
    """Convert DynamoDB Decimal values into JSON-compatible numbers."""

    def default(
        self,
        value,
    ):

        if isinstance(
            value,
            Decimal,
        ):

            if value % 1 == 0:
                return int(
                    value
                )

            return float(
                value
            )

        return super().default(
            value
        )


def api_response(
    status_code,
    body,
):
    """Create a standard API Gateway response."""

    return {
        "statusCode":
            status_code,

        "headers":
            HEADERS,

        "body":
            json.dumps(
                body,
                cls=DecimalEncoder,
            ),
    }


# ---------------------------------------------------------
# Request helpers
# ---------------------------------------------------------

def get_method_and_path(
    event,
):
    """Extract HTTP method and request path from API Gateway."""

    request_context = (
        event.get(
            "requestContext",
            {},
        )
    )

    http_context = (
        request_context.get(
            "http",
            {},
        )
    )

    method = (
        http_context.get(
            "method"
        )
        or event.get(
            "httpMethod"
        )
        or "GET"
    ).upper()

    path = (
        event.get(
            "rawPath"
        )
        or event.get(
            "path"
        )
        or "/"
    )

    if len(path) > 1:

        path = (
            path.rstrip("/")
        )

    return (
        method,
        path,
    )


def get_json_body(
    event,
):
    """Read and validate the JSON request body."""

    body = (
        event.get(
            "body"
        )
    )

    if body is None:

        return {}

    if (
        event.get(
            "isBase64Encoded"
        )
        is True
    ):

        body = (
            base64
            .b64decode(
                body
            )
            .decode(
                "utf-8"
            )
        )

    if isinstance(
        body,
        dict,
    ):

        return body

    if not isinstance(
        body,
        str,
    ):

        raise ValueError(
            "The request body must contain valid JSON."
        )

    try:

        return json.loads(
            body
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "The request body contains invalid JSON."
        ) from error


# ---------------------------------------------------------
# Event operations
# ---------------------------------------------------------

def list_events():
    """Return all available events."""

    result = (
        events_table.scan()
    )

    events = (
        result.get(
            "Items",
            [],
        )
    )

    while result.get(
        "LastEvaluatedKey"
    ):

        result = (
            events_table.scan(
                ExclusiveStartKey=
                    result[
                        "LastEvaluatedKey"
                    ]
            )
        )

        events.extend(
            result.get(
                "Items",
                [],
            )
        )

    events.sort(
        key=lambda item:
            item.get(
                "startDate",
                "",
            )
    )

    return api_response(
        200,
        {
            "count":
                len(events),

            "events":
                events,
        },
    )


def get_event(
    event_id,
):
    """Return one event by event ID."""

    result = (
        events_table.get_item(
            Key={
                "eventId":
                    event_id
            }
        )
    )

    event = (
        result.get(
            "Item"
        )
    )

    if not event:

        return api_response(
            404,
            {
                "message":
                    "Event not found."
            },
        )

    return api_response(
        200,
        event,
    )


# ---------------------------------------------------------
# Registration validation
# ---------------------------------------------------------

def validate_registration(
    data,
):
    """Validate participant registration information."""

    required_fields = {
        "fullName":
            "Full name",

        "email":
            "Email address",

        "phone":
            "Phone number",
    }

    missing_fields = []

    for (
        field,
        label,
    ) in required_fields.items():

        value = (
            data.get(
                field
            )
        )

        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):

            missing_fields.append(
                label
            )

    if missing_fields:

        raise ValueError(
            "The following fields are required: "
            + ", ".join(
                missing_fields
            )
            + "."
        )

    full_name = (
        data[
            "fullName"
        ]
        .strip()
    )

    email = (
        data[
            "email"
        ]
        .strip()
        .lower()
    )

    phone = (
        data[
            "phone"
        ]
        .strip()
    )

    email_pattern = (
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    if not re.match(
        email_pattern,
        email,
    ):

        raise ValueError(
            "Enter a valid email address."
        )

    if len(
        full_name
    ) < 2:

        raise ValueError(
            "Enter a valid full name."
        )

    if len(
        phone
    ) < 9:

        raise ValueError(
            "Enter a valid phone number."
        )

    return (
        full_name,
        email,
        phone,
    )


# ---------------------------------------------------------
# Registration and ticket helpers
# ---------------------------------------------------------

def create_registration_id(
    event_id,
    email,
):
    """Create a deterministic ID to prevent duplicate registration."""

    email_hash = (
        hashlib
        .sha256(
            email.encode(
                "utf-8"
            )
        )
        .hexdigest()[:20]
    )

    return (
        f"{event_id}-"
        f"{email_hash}"
    )


def create_ticket_number():
    """Generate a unique ticket number."""

    random_part = (
        uuid
        .uuid4()
        .hex[:10]
        .upper()
    )

    return (
        f"{TICKET_PREFIX}-"
        f"{random_part}"
    )


def serialize_item(
    item,
):
    """Convert normal Python data into DynamoDB attribute format."""

    return {
        key:
            serializer.serialize(
                value
            )

        for (
            key,
            value,
        ) in item.items()
    }


# ---------------------------------------------------------
# Email confirmation
# ---------------------------------------------------------

def send_registration_confirmation(
    recipient_email,
    full_name,
    registration_item,
    event_item,
):
    """
    Send a registration confirmation email through Amazon SES.

    Registration remains successful even if the email
    cannot be delivered.
    """

    if not SES_SENDER_EMAIL:

        logger.warning(
            "SES_SENDER_EMAIL is not configured."
        )

        return False


    event_name = (
        event_item.get(
            "eventName",
            "Ghana National Food & Agribusiness Fair 2026",
        )
    )


    start_date = (
        event_item.get(
            "startDate",
            "20 November 2026",
        )
    )


    end_date = (
        event_item.get(
            "endDate",
            "22 November 2026",
        )
    )


    venue = (
        event_item.get(
            "venue",
            (
                "Accra International "
                "Conference Centre, "
                "Accra, Ghana"
            ),
        )
    )


    ticket_number = (
        registration_item[
            "ticketNumber"
        ]
    )


    registration_id = (
        registration_item[
            "registrationId"
        ]
    )


    subject = (
        "GNAF 2026 Registration Confirmation"
    )


    text_body = f"""
Dear {full_name},

Your registration for the {event_name} has been completed successfully.

Ticket Number: {ticket_number}
Registration ID: {registration_id}
Event Date: {start_date} to {end_date}
Venue: {venue}

Please keep your ticket number and registration ID for your records.

Thank you for registering for GNAF 2026.

GNAF 2026
Connecting Farmers, Markets and Opportunities
""".strip()


    safe_name = (
        html.escape(
            str(
                full_name
            )
        )
    )


    safe_event_name = (
        html.escape(
            str(
                event_name
            )
        )
    )


    safe_ticket_number = (
        html.escape(
            str(
                ticket_number
            )
        )
    )


    safe_registration_id = (
        html.escape(
            str(
                registration_id
            )
        )
    )


    safe_start_date = (
        html.escape(
            str(
                start_date
            )
        )
    )


    safe_end_date = (
        html.escape(
            str(
                end_date
            )
        )
    )


    safe_venue = (
        html.escape(
            str(
                venue
            )
        )
    )


    html_body = f"""
<!DOCTYPE html>

<html>

<body
    style="
        margin: 0;
        padding: 0;
        background: #f6f1e7;
        font-family: Arial, sans-serif;
        color: #1f2d24;
    "
>

<div
    style="
        max-width: 620px;
        margin: 30px auto;
        background: #ffffff;
        border: 1px solid #dddddd;
        border-radius: 12px;
        overflow: hidden;
    "
>


    <div
        style="
            background: #153d29;
            color: #ffffff;
            padding: 28px;
            text-align: center;
        "
    >

        <h1
            style="
                margin: 0;
                font-size: 30px;
            "
        >
            GNAF 2026
        </h1>

        <p
            style="
                margin: 8px 0 0;
            "
        >
            Ghana National Food &amp;
            Agribusiness Fair
        </p>

    </div>


    <div
        style="
            padding: 30px;
        "
    >

        <h2
            style="
                color: #153d29;
                margin-top: 0;
            "
        >
            Registration Successful
        </h2>


        <p>
            Dear {safe_name},
        </p>


        <p>
            Your registration for the
            <strong>
                {safe_event_name}
            </strong>
            has been completed successfully.
        </p>


        <div
            style="
                background: #fff8e8;
                border-left: 5px solid #e0a52b;
                padding: 18px;
                margin: 24px 0;
            "
        >

            <p
                style="
                    margin-top: 0;
                "
            >

                <strong>
                    Ticket Number:
                </strong>

                <br>

                {safe_ticket_number}

            </p>


            <p>

                <strong>
                    Registration ID:
                </strong>

                <br>

                {safe_registration_id}

            </p>


            <p>

                <strong>
                    Event Date:
                </strong>

                <br>

                {safe_start_date}
                to
                {safe_end_date}

            </p>


            <p
                style="
                    margin-bottom: 0;
                "
            >

                <strong>
                    Venue:
                </strong>

                <br>

                {safe_venue}

            </p>

        </div>


        <p>
            Please keep your ticket number
            and registration ID for your
            records.
        </p>


        <p>
            We look forward to welcoming
            you to GNAF 2026.
        </p>

    </div>


    <div
        style="
            background: #102d20;
            color: #ffffff;
            padding: 18px;
            text-align: center;
        "
    >

        Connecting Farmers,
        Markets and Opportunities

    </div>


</div>

</body>

</html>
""".strip()


    try:

        ses_client.send_email(

            Source=(
                f"GNAF 2026 "
                f"<{SES_SENDER_EMAIL}>"
            ),

            Destination={
                "ToAddresses": [
                    recipient_email
                ]
            },

            Message={

                "Subject": {

                    "Data":
                        subject,

                    "Charset":
                        "UTF-8",
                },

                "Body": {

                    "Text": {

                        "Data":
                            text_body,

                        "Charset":
                            "UTF-8",
                    },

                    "Html": {

                        "Data":
                            html_body,

                        "Charset":
                            "UTF-8",
                    },
                },
            },
        )


        logger.info(
            "Registration confirmation email sent successfully."
        )


        return True


    except ClientError:

        logger.exception(
            (
                "Registration succeeded, "
                "but confirmation email "
                "could not be sent."
            )
        )


        return False


# ---------------------------------------------------------
# Participant registration
# ---------------------------------------------------------

def register_participant(
    event_id,
    request_event,
):
    """
    Register a participant,
    issue a ticket,
    save the registration,
    and send confirmation email.
    """

    data = (
        get_json_body(
            request_event
        )
    )


    (
        full_name,
        email,
        phone,
    ) = (
        validate_registration(
            data
        )
    )


    organisation = (
        data.get(
            "organisation",
            "",
        )
        if isinstance(
            data.get(
                "organisation",
                "",
            ),
            str,
        )
        else ""
    ).strip()


    attendee_type = (
        data.get(
            "attendeeType",
            "",
        )
        if isinstance(
            data.get(
                "attendeeType",
                "",
            ),
            str,
        )
        else ""
    ).strip()


    event_result = (
        events_table.get_item(
            Key={
                "eventId":
                    event_id
            }
        )
    )


    event_item = (
        event_result.get(
            "Item"
        )
    )


    if not event_item:

        return api_response(
            404,
            {
                "message":
                    (
                        "The selected event "
                        "does not exist."
                    )
            },
        )


    if (
        event_item.get(
            "status"
        )
        != "OPEN"
    ):

        return api_response(
            409,
            {
                "message":
                    (
                        "Registration for "
                        "this event is not open."
                    )
            },
        )


    available_seats = int(
        event_item.get(
            "availableSeats",
            0,
        )
    )


    if available_seats < 1:

        return api_response(
            409,
            {
                "message":
                    (
                        "No seats are available "
                        "for this event."
                    )
            },
        )


    registration_deadline = (
        event_item.get(
            "registrationDeadline"
        )
    )


    current_date = (
        datetime
        .now(
            timezone.utc
        )
        .date()
        .isoformat()
    )


    if (
        registration_deadline
        and current_date
        > registration_deadline
    ):

        return api_response(
            409,
            {
                "message":
                    (
                        "The registration "
                        "deadline has passed."
                    )
            },
        )


    registration_id = (
        create_registration_id(
            event_id,
            email,
        )
    )


    ticket_number = (
        create_ticket_number()
    )


    registration_date = (
        datetime
        .now(
            timezone.utc
        )
        .isoformat()
    )


    registration_item = {

        "registrationId":
            registration_id,

        "eventId":
            event_id,

        "eventName":
            event_item.get(
                "eventName",
                "GNAF Event",
            ),

        "fullName":
            full_name,

        "email":
            email,

        "phone":
            phone,

        "registrationDate":
            registration_date,

        "ticketNumber":
            ticket_number,

        "ticketStatus":
            "VALID",

        "checkInStatus":
            "NOT_CHECKED_IN",
    }


    if organisation:

        registration_item[
            "organisation"
        ] = (
            organisation
        )


    if attendee_type:

        registration_item[
            "attendeeType"
        ] = (
            attendee_type
        )


    try:

        dynamodb_client.transact_write_items(

            TransactItems=[

                {

                    "Update": {

                        "TableName":
                            EVENTS_TABLE,

                        "Key": {

                            "eventId": {
                                "S":
                                    event_id
                            }
                        },

                        "UpdateExpression": (
                            "SET availableSeats = "
                            "availableSeats - :one"
                        ),

                        "ConditionExpression": (
                            "attribute_exists(eventId) "
                            "AND #eventStatus = :open "
                            "AND availableSeats >= :one"
                        ),

                        "ExpressionAttributeNames": {

                            "#eventStatus":
                                "status"
                        },

                        "ExpressionAttributeValues": {

                            ":one": {

                                "N":
                                    "1"
                            },

                            ":open": {

                                "S":
                                    "OPEN"
                            },
                        },
                    }
                },


                {

                    "Put": {

                        "TableName":
                            REGISTRATIONS_TABLE,

                        "Item":
                            serialize_item(
                                registration_item
                            ),

                        "ConditionExpression": (
                            "attribute_not_exists("
                            "registrationId)"
                        ),
                    }
                },
            ]
        )


    except (
        dynamodb_client
        .exceptions
        .TransactionCanceledException
    ):


        existing_registration = (
            registrations_table
            .get_item(
                Key={
                    "registrationId":
                        registration_id
                }
            )
            .get(
                "Item"
            )
        )


        if existing_registration:

            return api_response(
                409,
                {
                    "message": (
                        "This email address "
                        "is already registered "
                        "for this event."
                    ),

                    "registrationId":
                        registration_id,
                },
            )


        latest_event = (
            events_table
            .get_item(
                Key={
                    "eventId":
                        event_id
                }
            )
            .get(
                "Item"
            )
        )


        if not latest_event:

            return api_response(
                404,
                {
                    "message": (
                        "The selected event "
                        "no longer exists."
                    )
                },
            )


        if (
            latest_event.get(
                "status"
            )
            != "OPEN"
        ):

            return api_response(
                409,
                {
                    "message": (
                        "Registration for "
                        "this event is no "
                        "longer open."
                    )
                },
            )


        if int(
            latest_event.get(
                "availableSeats",
                0,
            )
        ) < 1:

            return api_response(
                409,
                {
                    "message": (
                        "The event became "
                        "fully booked before "
                        "registration was "
                        "completed."
                    )
                },
            )


        logger.exception(
            (
                "Registration transaction "
                "was cancelled."
            )
        )


        return api_response(
            409,
            {
                "message": (
                    "Registration could "
                    "not be completed. "
                    "Please try again."
                )
            },
        )


    email_sent = (
        send_registration_confirmation(

            recipient_email=
                email,

            full_name=
                full_name,

            registration_item=
                registration_item,

            event_item=
                event_item,
        )
    )


    if email_sent:

        response_message = (
            "Registration completed successfully. "
            "A confirmation email has been sent."
        )


    else:

        response_message = (
            "Registration completed successfully. "
            "Your ticket has been created, but the "
            "confirmation email could not be sent."
        )


    return api_response(
        201,
        {

            "message":
                response_message,

            "emailSent":
                email_sent,

            "registration":
                registration_item,
        },
    )


# ---------------------------------------------------------
# API routing
# ---------------------------------------------------------

def route_request(
    method,
    path,
    event,
):
    """Route incoming API Gateway requests."""

    parts = [

        part

        for part
        in path.split("/")

        if part
    ]


    if method == "OPTIONS":

        return api_response(
            204,
            {},
        )


    if (
        method == "GET"
        and path in [
            "/",
            "/health",
        ]
    ):

        return api_response(
            200,
            {

                "service":
                    (
                        "GNAF Event "
                        "Registration API"
                    ),

                "status":
                    "healthy",
            },
        )


    if (
        method == "GET"
        and parts
        == [
            "events"
        ]
    ):

        return list_events()


    if (
        method == "GET"
        and len(
            parts
        ) == 2
        and parts[
            0
        ] == "events"
    ):

        return get_event(
            parts[
                1
            ]
        )


    if (
        method == "POST"
        and len(
            parts
        ) == 3
        and parts[
            0
        ] == "events"
        and parts[
            2
        ] == "register"
    ):

        return register_participant(
            parts[
                1
            ],
            event,
        )


    return api_response(
        404,
        {
            "message": (
                f"No route exists for "
                f"{method} {path}."
            )
        },
    )


# ---------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------

def lambda_handler(
    event,
    context,
):
    """AWS Lambda function entry point."""

    request_id = (
        getattr(
            context,
            "aws_request_id",
            "local-test",
        )
    )


    try:

        (
            method,
            path,
        ) = (
            get_method_and_path(
                event
            )
        )


        # Avoid logging personal registration data.

        logger.info(
            (
                "Request %s received: "
                "%s %s"
            ),
            request_id,
            method,
            path,
        )


        return route_request(
            method,
            path,
            event,
        )


    except ValueError as error:

        logger.warning(
            (
                "Invalid request "
                "%s: %s"
            ),
            request_id,
            str(
                error
            ),
        )


        return api_response(
            400,
            {

                "message":
                    str(
                        error
                    )
            },
        )


    except ClientError:

        logger.exception(
            (
                "AWS service error "
                "for request %s"
            ),
            request_id,
        )


        return api_response(
            500,
            {

                "message":
                    (
                        "An AWS service "
                        "error occurred."
                    ),

                "requestId":
                    request_id,
            },
        )


    except Exception:

        logger.exception(
            (
                "Unexpected error "
                "for request %s"
            ),
            request_id,
        )


        return api_response(
            500,
            {

                "message": (
                    "An unexpected server "
                    "error occurred."
                ),

                "requestId":
                    request_id,
            },
        )
