async function initializeSquare() {
  const { Square } = window;
  const config = window.squareConfig || {};
  if (!Square || !config.applicationId || !config.locationId) {
    console.warn("Square configuration missing; checkout disabled.");
    return null;
  }

  try {
    const payments = Square.payments(config.applicationId, config.locationId, {
      environment: config.environment || "sandbox",
    });
    const card = await payments.card();
    await card.attach("#card-container");
    return { payments, card };
  } catch (error) {
    console.error("Failed to initialize Square payments", error);
    showStatus("Unable to load payment form. Please try again later.", "danger");
    return null;
  }
}

function showStatus(message, level) {
  const statusEl = document.getElementById("payment-status");
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = `alert alert-${level}`;
  statusEl.classList.remove("d-none");
}

function clearStatus() {
  const statusEl = document.getElementById("payment-status");
  if (!statusEl) return;
  statusEl.textContent = "";
  statusEl.className = "alert d-none";
}

document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("checkout-form");
  const payButton = document.getElementById("card-button");

  if (!form || !payButton) {
    return;
  }

  const square = await initializeSquare();
  if (!square) {
    payButton.disabled = true;
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearStatus();
    payButton.disabled = true;
    payButton.textContent = "Processing...";

    try {
      const formData = new FormData(form);
      const paymentToken = await square.card.tokenize();
      if (paymentToken.status !== "OK") {
        throw new Error(paymentToken.message || "We couldn't process your card. Please try again.");
      }

      const body = {
        sourceId: paymentToken.token,
        verificationToken: paymentToken.verificationToken,
        familyName: formData.get("family_name"),
        familyEmail: formData.get("family_email"),
        familyPhone: formData.get("family_phone"),
        exposeContact: formData.get("expose_contact") === "y" || formData.get("expose_contact") === "on",
      };

      const csrfToken = formData.get("csrf_token");

      const response = await fetch("/api/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(body),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || "Payment failed. Please try again.");
      }

      showStatus("Payment successful! Check your email for a receipt.", "success");
      if (result.redirect_url) {
        window.setTimeout(() => {
          window.location.href = result.redirect_url;
        }, 800);
      }
    } catch (error) {
      console.error(error);
      showStatus(error.message || "Something went wrong during checkout.", "danger");
      payButton.disabled = false;
      payButton.textContent = payButton.dataset.label || "Pay";
      return;
    }

    payButton.textContent = "Success!";
  });

  payButton.dataset.label = payButton.textContent;
});

