"use strict";

/* =========================================================
   GHANA NATIONAL FOOD & AGRIBUSINESS FAIR 2026
   FRONTEND REGISTRATION APPLICATION
========================================================= */


/* =========================================================
   AWS API CONFIGURATION
========================================================= */

const API_BASE_URL =
    "https://q6pdblcj7e.execute-api.us-east-1.amazonaws.com";

const EVENT_ID =
    "GNAF-2026";

const REGISTRATION_ENDPOINT =
    `${API_BASE_URL}/events/${EVENT_ID}/register`;


/* =========================================================
   START APPLICATION
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        const registrationForm =
            document.getElementById(
                "registrationForm"
            );

        const formMessage =
            document.getElementById(
                "formMessage"
            );


        if (!registrationForm) {

            console.error(
                "Registration form could not be found."
            );

            return;
        }


        registrationForm.addEventListener(
            "submit",
            handleRegistration
        );


        async function handleRegistration(event) {

            event.preventDefault();

            clearMessage(formMessage);


            const submitButton =
                registrationForm.querySelector(
                    "button[type='submit']"
                );


            const originalButtonText =
                submitButton.textContent;


            setButtonLoading(
                submitButton,
                true,
                "Processing Registration..."
            );


            /* =============================================
               GET FORM VALUES
            ============================================= */

            const fullName =
                getInputValue("fullName");


            const email =
                getInputValue("email")
                    .toLowerCase();


            const phone =
                getInputValue("phone");


            const organisation =
                getInputValue("organisation");


            const attendeeType =
                getInputValue("attendeeType");


            /* =============================================
               VALIDATE FORM
            ============================================= */

            const validationError =
                validateForm({
                    fullName,
                    email,
                    phone,
                    attendeeType
                });


            if (validationError) {

                showMessage(
                    formMessage,
                    validationError,
                    "error"
                );


                setButtonLoading(
                    submitButton,
                    false,
                    originalButtonText
                );


                return;
            }


            /* =============================================
               BUILD REQUEST
            ============================================= */

            const registrationData = {

                fullName:
                    fullName,

                email:
                    email,

                phone:
                    phone,

                organisation:
                    organisation,

                attendeeType:
                    attendeeType

            };


            /* =============================================
               SEND REQUEST TO AWS
            ============================================= */

            try {

                const response =
                    await fetch(
                        REGISTRATION_ENDPOINT,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                "Accept":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(
                                    registrationData
                                )
                        }
                    );


                const result =
                    await readJsonResponse(
                        response
                    );


                /* =========================================
                   SUCCESSFUL REGISTRATION
                ========================================= */

                if (response.status === 201) {

                    const registration =
                        result.registration || {};


                    const ticketNumber =
                        registration.ticketNumber || "";


                    const registrationId =
                        registration.registrationId || "";


                    let successMessage =
                        result.message ||
                        "Registration completed successfully.";


                    if (ticketNumber) {

                        successMessage +=
                            ` Your ticket number is ${ticketNumber}.`;
                    }


                    if (registrationId) {

                        successMessage +=
                            ` Registration ID: ${registrationId}.`;
                    }


                    showMessage(
                        formMessage,
                        successMessage,
                        "success"
                    );


                    registrationForm.reset();


                    formMessage.scrollIntoView({
                        behavior: "smooth",
                        block: "center"
                    });


                    return;
                }


                /* =========================================
                   DUPLICATE OR OTHER CONFLICT
                ========================================= */

                if (response.status === 409) {

                    let conflictMessage =
                        result.message ||
                        "Registration could not be completed.";


                    if (result.registrationId) {

                        conflictMessage +=
                            ` Registration ID: ${result.registrationId}.`;
                    }


                    showMessage(
                        formMessage,
                        conflictMessage,
                        "error"
                    );


                    return;
                }


                /* =========================================
                   BAD REQUEST
                ========================================= */

                if (response.status === 400) {

                    showMessage(
                        formMessage,
                        result.message ||
                        "Please check your registration information.",
                        "error"
                    );


                    return;
                }


                /* =========================================
                   EVENT NOT FOUND
                ========================================= */

                if (response.status === 404) {

                    showMessage(
                        formMessage,
                        result.message ||
                        "The selected event could not be found.",
                        "error"
                    );


                    return;
                }


                /* =========================================
                   OTHER SERVER/API ERROR
                ========================================= */

                throw new Error(
                    result.message ||
                    "Registration could not be completed."
                );

            }
            catch (error) {

                console.error(
                    "Registration request failed:",
                    error
                );


                showMessage(
                    formMessage,
                    error.message ||
                    "We could not complete your registration. Please try again.",
                    "error"
                );

            }
            finally {

                setButtonLoading(
                    submitButton,
                    false,
                    originalButtonText
                );

            }

        }

    }
);


/* =========================================================
   GET INPUT VALUE
========================================================= */

function getInputValue(id) {

    const element =
        document.getElementById(id);


    if (!element) {
        return "";
    }


    return element.value.trim();

}


/* =========================================================
   FORM VALIDATION
========================================================= */

function validateForm(data) {

    if (!data.fullName) {

        return "Please enter your full name.";
    }


    if (data.fullName.length < 2) {

        return "Please enter a valid full name.";
    }


    if (!data.email) {

        return "Please enter your email address.";
    }


    const emailPattern =
        /^[^@\s]+@[^@\s]+\.[^@\s]+$/;


    if (!emailPattern.test(data.email)) {

        return "Please enter a valid email address.";
    }


    if (!data.phone) {

        return "Please enter your phone number.";
    }


    const cleanedPhone =
        data.phone.replace(
            /[\s\-()+]/g,
            ""
        );


    if (
        cleanedPhone.length < 9 ||
        !/^\d+$/.test(cleanedPhone)
    ) {

        return "Please enter a valid phone number.";
    }


    if (!data.attendeeType) {

        return "Please select your attendee type.";
    }


    return "";

}


/* =========================================================
   READ API JSON RESPONSE
========================================================= */

async function readJsonResponse(response) {

    try {

        return await response.json();

    }
    catch (error) {

        console.error(
            "Could not read API response:",
            error
        );


        return {};
    }

}


/* =========================================================
   DISPLAY FORM MESSAGE
========================================================= */

function showMessage(
    element,
    message,
    type
) {

    if (!element) {
        return;
    }


    element.textContent =
        message;


    element.style.display =
        "block";


    element.style.marginTop =
        "16px";


    element.style.padding =
        "14px 16px";


    element.style.borderRadius =
        "10px";


    element.style.fontWeight =
        "600";


    element.style.lineHeight =
        "1.5";


    if (type === "success") {

        element.style.background =
            "#e8f6ed";

        element.style.color =
            "#187642";

        element.style.border =
            "1px solid #b9e4c8";

    }
    else {

        element.style.background =
            "#fff0ee";

        element.style.color =
            "#b83a34";

        element.style.border =
            "1px solid #f0c8c4";
    }

}


/* =========================================================
   CLEAR FORM MESSAGE
========================================================= */

function clearMessage(element) {

    if (!element) {
        return;
    }


    element.textContent = "";

    element.style.display =
        "none";


    element.style.background =
        "transparent";


    element.style.border =
        "none";

}


/* =========================================================
   SUBMIT BUTTON STATE
========================================================= */

function setButtonLoading(
    button,
    loading,
    label
) {

    if (!button) {
        return;
    }


    button.disabled =
        loading;


    button.textContent =
        label;


    button.style.opacity =
        loading
            ? "0.70"
            : "1";


    button.style.cursor =
        loading
            ? "not-allowed"
            : "pointer";

}
