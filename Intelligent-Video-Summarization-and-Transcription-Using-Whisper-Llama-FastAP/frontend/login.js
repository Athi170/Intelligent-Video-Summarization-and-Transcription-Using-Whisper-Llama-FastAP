const loginForm = document.getElementById("loginForm");
const loginSubmit = document.getElementById("loginSubmit");
const authError = document.getElementById("authError");

function showError(message) {
    authError.innerText = message;
    authError.classList.add("visible");
}

function hideError() {
    authError.classList.remove("visible");
}

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    loginSubmit.disabled = true;
    loginSubmit.innerText = "Logging in...";

    try {

        const response = await fetch("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Invalid username or password.");
        }

        window.location.href = "/";

    } catch (error) {
        showError(error.message);
        loginSubmit.disabled = false;
        loginSubmit.innerText = "Log in";
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
