
const authForm = document.getElementById("auth-form");
const loginTab = document.getElementById("login-tab");
const registerTab = document.getElementById("register-tab");
const submitButton = document.getElementById("submit-button");
const authMessage = document.getElementById("auth-message");
const passwordInput = document.getElementById("password");

let authMode = "login";

function setAuthMode(mode) {
    authMode = mode;

    const isLogin = mode === "login";

    loginTab.classList.toggle("active", isLogin);
    registerTab.classList.toggle("active", !isLogin);

    submitButton.textContent = isLogin ? "Login" : "Create account";
    passwordInput.autocomplete = isLogin
        ? "current-password"
        : "new-password";

    authMessage.textContent = "";
}

loginTab.addEventListener("click", () => {
    setAuthMode("login");
});

registerTab.addEventListener("click", () => {
    setAuthMode("register");
});

authForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = passwordInput.value;

    authMessage.textContent = "";
    submitButton.disabled = true;

    try {
        if (authMode === "register") {
            await apiRequest("/auth/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ email, password }),
            });

            authMessage.textContent =
                "Account created. You can now log in.";

            setAuthMode("login");
            return;
        }

        const result = await apiRequest("/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
        });

        setAccessToken(result.access_token);

        authMessage.textContent = "Login successful.";

        window.location.href = "index.html";
    } catch (error) {
        authMessage.textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});
