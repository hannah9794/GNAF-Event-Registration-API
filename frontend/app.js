const API_BASE_URL = "https://q6pdblcj7e.execute-api.us-east-1.amazonaws.com";
const EVENT_ID = "GNAF-2026";
const REGISTRATION_ENDPOINT = `${API_BASE_URL}/register`;

document.addEventListener("DOMContentLoaded", () => {
  const registrationForm = document.getElementById("registrationForm");
  const formMessage = document.getElementById("formMessage");

  if (!registrationForm) {
    return;
  }

  registrationForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    clearMessage(formMessage);

    const submitButton = registrationForm.querySelector("button[type='submit']");
    const originalButtonText = submitButton.textContent;

    submitButton.disabled = true;
    submitButton.textContent = "Submitting...";

    const fullName = document.getElementById("fullName").value.trim();
    const email = document.getElementById("email").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const organisation = document.getElementById("organisation").value.trim();
    const attendeeType = document.getElementById("attendeeType").value.trim();

    if (!fullName || !email || !phone || !attendeeType) {
      showMessage(formMessage, "Please fill in all required fields.", "error");
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
      return;
    }

    const payload = {
      eventId: EVENT_ID,
      fullName: fullName,
      email: email,
      phone: phone,
      organisation: organisation,
      attendeeType: attendeeType
    };

    try {
      const response = await fetch(REGISTRATION_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          result.message ||
          result.error ||
          "Registration failed. Please try again."
        );
      }

      const ticketNumber =
        result.ticketNumber ||
        result.ticket_number ||
        result.registrationId ||
        result.registration_id ||
        "";

      let successMessage = "Registration successful!";
      if (ticketNumber) {
        successMessage += ` Your ticket number is ${ticketNumber}.`;
      }

      showMessage(formMessage, successMessage, "success");
      registrationForm.reset();
    } catch (error) {
      showMessage(
        formMessage,
        error.message || "Something went wrong. Please try again.",
        "error"
      );
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  });
});

function showMessage(element, message, type) {
  element.textContent = message;
  element.style.marginTop = "12px";
  element.style.fontWeight = "600";

  if (type === "success") {
    element.style.color = "#187642";
  } else {
    element.style.color = "#b83a34";
  }
}

function clearMessage(element) {
  element.textContent = "";
  element.style.marginTop = "";
  element.style.fontWeight = "";
  element.style.color = "";
}
