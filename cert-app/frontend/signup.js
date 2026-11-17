// ---------- Sign-up page ----------
const form = $("#signup-form");
const message = $("#form-message");
const strength = $("#strength");

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const STRENGTH_LABELS = ["", "Weak password", "Fair password", "Good password", "Strong password"];
const STRENGTH_HINT = $(".strength-label", strength).textContent;

// 1 (weak) to 4 (strong). Only a guide for the user; the server checks the length.
function passwordScore(pw) {
  let score = 1;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw) && /\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return Math.min(score, 4);
}

$("#password").addEventListener("input", (e) => {
  const pw = e.target.value;
  const level = pw ? passwordScore(pw) : 0;
  strength.dataset.level = level;
  $(".strength-label", strength).textContent = level ? STRENGTH_LABELS[level] : STRENGTH_HINT;
});

function validate({ name, email, password, confirmPassword }) {
  const errors = {};
  if (name.length < 2) errors.name = "Enter your full name";
  if (!EMAIL_RE.test(email)) errors.email = "Enter a valid email address";
  if (password.length < 8) errors.password = "Use at least 8 characters";
  if (password !== confirmPassword) errors.confirm_password = "Passwords do not match";
  return errors;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFieldErrors(form);
  hideMessage(message);

  const values = {
    name: $("#name").value.trim(),
    email: $("#email").value.trim(),
    password: $("#password").value,
    confirmPassword: $("#password").value,
  };

  const errors = validate(values);
  if (Object.keys(errors).length) {
    showFieldErrors(form, errors);
    return;
  }

  const button = form.querySelector('button[type="submit"]');
  setLoading(button, true);
  const { ok, status, body } = await api("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ name: values.name, email: values.email, password: values.password }),
  });

  if (ok) {
    window.location.href = "/";
    return;
  }

  setLoading(button, false);
  if (status === 409) {
    showFieldErrors(form, { email: body.error.message });
    showMessage(message, "That email is already registered. Try signing in instead.", "error");
    return;
  }
  showFieldErrors(form, body?.error?.details);
  showMessage(message, body?.error?.message || "Could not create your account. Please try again.", "error");
});
