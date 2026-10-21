const showUploadButton = document.getElementById("show-upload-button");
const cancelUploadButton = document.getElementById("cancel-upload-button");
const uploadPanel = document.getElementById("upload-panel");
const uploadForm = document.getElementById("upload-form");
const uploadMessage = document.getElementById("upload-message");

const userEmail = document.getElementById("user-email");
const logoutButton = document.getElementById("logout-button");
const documentList = document.getElementById("document-list");
const libraryMessage = document.getElementById("library-message");
const searchInput = document.getElementById("search-input");
const subjectFilter = document.getElementById("subject-filter");
const sortSelect = document.getElementById("sort-select");
const previousPage = document.getElementById("previous-page");
const nextPage = document.getElementById("next-page");
const pageLabel = document.getElementById("page-label");

const PAGE_SIZE = 20;

let currentPage = 0;
let totalLoaded = 0;
let searchTimer;

function showError(error) {
    libraryMessage.textContent = error.message || "Something went wrong.";
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}


function createDocumentCard(document) {
    const card = documentList.ownerDocument.createElement("article");
    card.className = "document-card";

    const title = documentList.ownerDocument.createElement("h3");
    title.textContent = document.title;

    const details = documentList.ownerDocument.createElement("p");
    details.textContent =
        `${formatFileSize(document.file_size)} · ` +
        new Date(document.created_at).toLocaleDateString();

    const subject = documentList.ownerDocument.createElement("p");
    subject.className = "document-subject";
    subject.textContent = document.subject_id
        ? `Subject ID: ${document.subject_id}`
        : "No subject";

    const actions = documentList.ownerDocument.createElement("div");
    actions.className = "document-actions";

    const renameButton = documentList.ownerDocument.createElement("button");
    renameButton.type = "button";
    renameButton.textContent = "Rename";

    renameButton.addEventListener("click", async () => {
        const newTitle = window.prompt("Enter the new document title:", document.title);

        if (newTitle === null) return;

        const trimmedTitle = newTitle.trim();

        if (!trimmedTitle || trimmedTitle.length > 255) {
            window.alert("Title must contain 1–255 characters.");
            return;
        }

        renameButton.disabled = true;

        try {
            await apiRequest(`/documents/${document.id}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ title: trimmedTitle }),
            });

            await loadDocuments();
        } catch (error) {
            window.alert(error.message);
        } finally {
            renameButton.disabled = false;
        }
    });

    const deleteButton = documentList.ownerDocument.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.className = "delete-button";

    deleteButton.addEventListener("click", async () => {
        const confirmed = window.confirm(
            `Delete "${document.title}"? This action cannot be undone.`
        );

        if (!confirmed) return;

        deleteButton.disabled = true;

        try {
            await apiRequest(`/documents/${document.id}`, {
                method: "DELETE",
            });

            await loadDocuments();
        } catch (error) {
            window.alert(error.message);
            deleteButton.disabled = false;
        }
    });

    actions.append(renameButton, deleteButton);
    card.append(title, details, subject, actions);

    return card;
}


async function loadCurrentUser() {
    try {
        const user = await apiRequest("/auth/me");
        userEmail.textContent = user.email;
    } catch {
        clearAccessToken();
        window.location.href = "login.html";
        throw new Error("Please log in again.");
    }
}

async function loadSubjects() {
    const subjects = await apiRequest("/subjects/");

    for (const subject of subjects) {
        const filterOption = document.createElement("option");
        filterOption.value = subject.id;
        filterOption.textContent = subject.name;
        subjectFilter.appendChild(filterOption);

        const uploadOption = document.createElement("option");
        uploadOption.value = subject.id;
        uploadOption.textContent = subject.name;

        document.getElementById("document-subject").appendChild(uploadOption);
    }
}

async function loadDocuments() {
    libraryMessage.textContent = "Loading documents...";
    documentList.replaceChildren();

    const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(currentPage * PAGE_SIZE),
    });

    const search = searchInput.value.trim();
    if (search) params.set("search", search);

    if (subjectFilter.value) {
        params.set("subject_id", subjectFilter.value);
    }

    const [sortBy, order] = sortSelect.value.split(":");
    params.set("sort_by", sortBy);
    params.set("order", order);

    try {
        const documents = await apiRequest(
            `/documents/?${params.toString()}`
        );

        totalLoaded = documents.length;

        if (documents.length === 0) {
            libraryMessage.textContent = "No documents found.";
        } else {
            libraryMessage.textContent = "";
            for (const document of documents) {
                documentList.appendChild(createDocumentCard(document));
            }
        }

        pageLabel.textContent = `Page ${currentPage + 1}`;
        previousPage.disabled = currentPage === 0;
        nextPage.disabled = documents.length < PAGE_SIZE;
    } catch (error) {
        showError(error);
    }
}

logoutButton.addEventListener("click", () => {
    clearAccessToken();
    window.location.href = "login.html";
});

searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);

    searchTimer = setTimeout(() => {
        currentPage = 0;
        loadDocuments();
    }, 300);
});

subjectFilter.addEventListener("change", () => {
    currentPage = 0;
    loadDocuments();
});

sortSelect.addEventListener("change", () => {
    currentPage = 0;
    loadDocuments();
});

previousPage.addEventListener("click", () => {
    if (currentPage > 0) {
        currentPage--;
        loadDocuments();
    }
});

nextPage.addEventListener("click", () => {
    if (totalLoaded === PAGE_SIZE) {
        currentPage++;
        loadDocuments();
    }
});

async function initializeDashboard() {
    try {
        await loadCurrentUser();
        await loadSubjects();
        await loadDocuments();
    } catch (error) {
        if (sessionStorage.getItem("studyvault_token")) {
            showError(error);
        }
    }
}

initializeDashboard();

showUploadButton.addEventListener("click", () => {
    uploadPanel.hidden = false;
    uploadMessage.textContent = "";
});

cancelUploadButton.addEventListener("click", () => {
    uploadPanel.hidden = true;
    uploadForm.reset();
    uploadMessage.textContent = "";
});

uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const title = document.getElementById("document-title").value.trim();
    const file = document.getElementById("document-file").files[0];
    const subjectId = document.getElementById("document-subject").value;

    if (!title || !file) {
        uploadMessage.textContent = "Enter a title and choose a PDF.";
        return;
    }

    if (
        file.type !== "application/pdf" &&
        !file.name.toLowerCase().endsWith(".pdf")
    ) {
        uploadMessage.textContent = "Please select a PDF file.";
        return;
    }

    const formData = new FormData();
    formData.append("title", title);
    formData.append("file", file);

    if (subjectId) {
        formData.append("subject_id", subjectId);
    }

    const uploadButton = uploadForm.querySelector(
        'button[type="submit"]'
    );

    uploadButton.disabled = true;
    uploadMessage.textContent = "Uploading PDF...";

    try {
        await apiRequest("/documents/", {
            method: "POST",
            body: formData,
        });

        uploadMessage.textContent = "Document uploaded successfully.";
        uploadForm.reset();
        currentPage = 0;
        await loadDocuments();
    } catch (error) {
        uploadMessage.textContent = error.message;
    } finally {
        uploadButton.disabled = false;
    }
});
