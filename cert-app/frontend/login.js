// ---------- Login page ----------
const form = $("#login-form");
const message = $("#form-message");
const params = new URLSearchParams(window.location.search);
const next = params.get("next");

if (params.has("signed_out")) {
  showMessage(message, "You've been signed out.", "info");
} else if (next) {
  showMessage(message, "Please sign in to continue.", "info");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFieldErrors(form);
  hideMessage(message);

  const email = form.email.value.trim();
  const password = form.password.value;

  const errors = {};
  if (!email) errors.email = "Enter your email address";
  if (!password) errors.password = "Enter your password";
  if (Object.keys(errors).length) {
    showFieldErrors(form, errors);
    return;
  }

  const button = form.querySelector('button[type="submit"]');
  setLoading(button, true);
  const { ok, body } = await api("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  if (ok) {
    // Send the user back to the page they were on before they had to log in.
    window.location.href = next || "/";
    return;
  }

  setLoading(button, false);
  showFieldErrors(form, body?.error?.details);
  showMessage(message, body?.error?.message || "Could not sign you in. Please try again.", "error");
  form.password.select();
});
