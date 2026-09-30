const registerForm = document.getElementById("registerForm");
const registerSubmit = document.getElementById("registerSubmit");
const authError = document.getElementById("authError");

function showError(message) {
    authError.innerText = message;
    authError.classList.add("visible");
}

function hideError() {
    authError.classList.remove("visible");
}

registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    if (username.length < 3) {
        showError("Username must be at least 3 characters.");
        return;
    }

    if (password.length < 6) {
        showError("Password must be at least 6 characters.");
        return;
    }

    registerSubmit.disabled = true;
    registerSubmit.innerText = "Creating account...";

    try {

        const response = await fetch("/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Could not create account.");
        }

        window.location.href = "/";

    } catch (error) {
        showError(error.message);
        registerSubmit.disabled = false;
        registerSubmit.innerText = "Create account";
    }
});

// If the person is already logged in, skip straight to the app.
(async () => {
    try {
        const response = await fetch("/auth/me");
        if (response.ok) {
            window.location.href = "/";
        }
    } catch (error) {
        // Not logged in — stay on this page.
    }
})();
