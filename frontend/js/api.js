
const API_BASE_URL = "http://127.0.0.1:8000";

function setAccessToken(token) {
    sessionStorage.setItem("studyvault_token", token);
}

function clearAccessToken() {
    sessionStorage.removeItem("studyvault_token");
}

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});

    const accessToken = sessionStorage.getItem("studyvault_token");

if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
}

    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
    });

    if (response.status === 204) {
        return null;
    }

    const contentType = response.headers.get("content-type") || "";

    const data = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

    if (!response.ok) {
        const message =
            typeof data === "object" && data !== null
                ? data.detail || "Request failed"
                : data || "Request failed";

        throw new Error(
            typeof message === "string"
                ? message
                : JSON.stringify(message)
        );
    }

    return data;
}
