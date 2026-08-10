"use strict";

/* =========================================================
   GNAF 2026 FRONTEND APPLICATION
========================================================= */

const API_BASE_URL =
    "https://q6pdblcj7e.execute-api.us-east-1.amazonaws.com";

const EVENT_ID = "GNAF-2026";


/* =========================================================
   PAGE ELEMENTS
========================================================= */

const eventStatus =
    document.getElementById("event-status");

const availableSeats =
    document.getElementById("available-seats");

const registrationDeadline =
    document.getElementById("registration-deadline");

const registrationForm =
    document.getElementById("registration-form");

const fullNameInput =
    document.getElementById("fullName");

const emailInput =
    document.getElementById("email");

const phoneInput =
    document.getElementById("phone");

const formMessage =
    document.getElementById("form-message");

const registerButton =
    document.getElementById("register-button");

const ticketSection =
    document.getElementById("ticket-section");

const ticketName =
    document.getElementById("ticket-name");

const ticketNumber =
    document.getElementById("ticket-number");

const registrationId =
    document.getElementById("registration-id");

const printTicketButton =
    document.getElementById("print-ticket");


/* =========================================================
   START WEBSITE
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    initialiseWebsite
);


async function initialiseWebsite() {

    setRegisterButton(
        true,
        "Checking Availability..."
    );

    await loadEvent();

}


/* =========================================================
   LOAD LIVE EVENT DATA
========================================================= */

async function loadEvent() {

    try {

        const response = await fetch(
            `${API_BASE_URL}/events/${EVENT_ID}`
        );

        const data = await response.json();


        if (!response.ok) {
            throw new Error(
                data.message ||
                "Unable to load event information."
            );
        }


        displayEvent(data);

    }
    catch (error) {

        console.error(
            "Event loading error:",
            error
        );

        eventStatus.textContent =
            "Temporarily Unavailable";

        availableSeats.textContent = "—";

        setRegisterButton(
            true,
            "Registration Unavailable"
        );

    }

}


/* =========================================================
   DISPLAY EVENT DATA
========================================================= */

function displayEvent(event) {

    const status =
        String(
            event.status || "UNKNOWN"
        ).toUpperCase();


    const seats =
        Number(
            event.availableSeats ?? 0
        );


    eventStatus.textContent =
        formatStatus(status);


    availableSeats.textContent =
        Number.isFinite(seats)
            ? seats.toLocaleString()
            : "—";


    if (event.registrationDeadline) {

        registrationDeadline.textContent =
            formatDate(
                event.registrationDeadline
            );

    }


    const registrationOpen =
        status === "OPEN" &&
        seats > 0;


    if (registrationOpen) {

        setRegisterButton(
            false,
            "Complete Registration"
        );

    }
    else {

        setRegisterButton(
            true,
            seats <= 0
                ? "Event Fully Booked"
                : "Registration Closed"
        );

    }

}


/* =========================================================
   REGISTRATION FORM
========================================================= */

registrationForm.addEventListener(
    "submit",
    registerParticipant
);


async function registerParticipant(event) {

    event.preventDefault();

    clearMessage();


    const participant = {

        fullName:
            fullNameInput.value.trim(),

        email:
            emailInput.value
                .trim()
                .toLowerCase(),

        phone:
            phoneInput.value.trim()

    };


    const validationError =
        validateForm(participant);


    if (validationError) {

        showMessage(
            validationError,
            "error"
        );

        return;

    }


    setRegisterButton(
        true,
        "Processing Registration..."
    );


    try {

        const response = await fetch(
            `${API_BASE_URL}/events/${EVENT_ID}/register`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(participant)
            }
        );


        const data =
            await response.json();


        if (response.status === 201) {

            showSuccessfulRegistration(
                data
            );

            return;

        }


        if (response.status === 409) {

            showDuplicateMessage(
                data
            );

            return;

        }


        throw new Error(
            data.message ||
            "Registration could not be completed."
        );

    }
    catch (error) {

        console.error(
            "Registration error:",
            error
        );

        showMessage(
            error.message ||
            "Something went wrong. Please try again.",
            "error"
        );

    }
    finally {

        await loadEvent();

    }

}


/* =========================================================
   FORM VALIDATION
========================================================= */

function validateForm(data) {

    if (
        !data.fullName ||
        !data.email ||
        !data.phone
    ) {

        return (
            "Please enter your full name, " +
            "email address and phone number."
        );

    }


    if (data.fullName.length < 2) {

        return "Please enter a valid full name.";

    }


    const emailPattern =
        /^[^@\s]+@[^@\s]+\.[^@\s]+$/;


    if (
        !emailPattern.test(data.email)
    ) {

        return "Please enter a valid email address.";

    }


    if (data.phone.length < 9) {

        return "Please enter a valid phone number.";

    }


    return "";

}


/* =========================================================
   SUCCESSFUL REGISTRATION
========================================================= */

function showSuccessfulRegistration(data) {

    const registration =
        data.registration;


    if (!registration) {

        showMessage(
            "Registration succeeded, but ticket details could not be displayed.",
            "error"
        );

        return;

    }


    ticketName.textContent =
        registration.fullName || "Participant";


    ticketNumber.textContent =
        registration.ticketNumber || "—";


    registrationId.textContent =
        registration.registrationId || "—";


    ticketSection.classList.remove(
        "hidden"
    );


    showMessage(
        data.message ||
        "Registration completed successfully.",
        "success"
    );


    registrationForm.reset();


    ticketSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

}


/* =========================================================
   DUPLICATE REGISTRATION
========================================================= */

function showDuplicateMessage(data) {

    let message =
        data.message ||
        "This participant is already registered.";


    if (data.registrationId) {

        message +=
            ` Registration ID: ${data.registrationId}`;

    }


    showMessage(
        message,
        "error"
    );

}


/* =========================================================
   MESSAGES
========================================================= */

function showMessage(
    message,
    type
) {

    formMessage.textContent =
        message;

    formMessage.className =
        `form-message ${type}`;

}


function clearMessage() {

    formMessage.textContent = "";

    formMessage.className =
        "form-message";

}


/* =========================================================
   REGISTER BUTTON
========================================================= */

function setRegisterButton(
    disabled,
    text
) {

    registerButton.disabled =
        disabled;

    registerButton.textContent =
        text;

    registerButton.style.opacity =
        disabled ? "0.65" : "1";

    registerButton.style.cursor =
        disabled
            ? "not-allowed"
            : "pointer";

}


/* =========================================================
   FORMAT EVENT STATUS
========================================================= */

function formatStatus(status) {

    if (status === "OPEN") {
        return "Open";
    }

    if (status === "CLOSED") {
        return "Closed";
    }

    if (status === "FULL") {
        return "Fully Booked";
    }

    return status;

}


/* =========================================================
   FORMAT DATE
========================================================= */

function formatDate(dateValue) {

    const date =
        new Date(
            `${dateValue}T00:00:00`
        );


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return dateValue;

    }


    return new Intl.DateTimeFormat(
        "en-GB",
        {
            day: "numeric",
            month: "long",
            year: "numeric"
        }
    ).format(date);

}


/* =========================================================
   PRINT EVENT TICKET
========================================================= */

printTicketButton.addEventListener(
    "click",
    function () {

        window.print();

    }
);
