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
    const doc = documentList.ownerDocument;
    const card = doc.createElement("article");
    card.className = "document-card";

    const title = doc.createElement("h3");
    title.textContent = document.title;

    const details = doc.createElement("p");
    details.textContent =
        `${formatFileSize(document.file_size)} · ` +
        new Date(document.created_at).toLocaleDateString();

    const subject = doc.createElement("p");
    subject.className = "document-subject";
    subject.textContent = document.subject_name || "No subject";

    const actions = doc.createElement("div");
    actions.className = "document-actions";

    // Edit title and subject
    const editButton = doc.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";

    editButton.addEventListener("click", async () => {
        try {
            const subjects = await apiRequest("/subjects/");

            const newTitle = window.prompt(
                "Document title:",
                document.title
            );

            if (newTitle === null) return;

            const trimmedTitle = newTitle.trim();

            if (!trimmedTitle || trimmedTitle.length > 255) {
                window.alert("Title must contain 1–255 characters.");
                return;
            }

            const currentSubject = document.subject_id == null
                ? ""
                : String(document.subject_id);

            const choices = [
                "0. No subject",
                ...subjects.map(
                    (item, index) => `${index + 1}. ${item.name}`
                ),
            ].join("\n");

            const subjectChoice = window.prompt(
                `Choose a subject by number:\n${choices}\n\nEnter 0 for no subject.`,
                currentSubject === ""
                    ? "0"
                    : String(
                        subjects.findIndex(
                            item => item.id === document.subject_id
                        ) + 1
                    )
            );

            if (subjectChoice === null) return;

            const choice = Number(subjectChoice);

            if (
                !Number.isInteger(choice) ||
                choice < 0 ||
                choice > subjects.length
            ) {
                window.alert("Please enter a valid subject number.");
                return;
            }

            const selectedSubjectId = choice === 0
                ? null
                : subjects[choice - 1].id;

            editButton.disabled = true;

            await apiRequest(`/documents/${document.id}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    title: trimmedTitle,
                    subject_id: selectedSubjectId,
                }),
            });

            await loadDocuments();
        } catch (error) {
            window.alert(error.message);
        } finally {
            editButton.disabled = false;
        }
    });

    // Delete document
    const deleteButton = doc.createElement("button");
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

    actions.append(editButton, deleteButton);
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

    const subjectList = document.getElementById("subject-list");
    const subjectsStatus = document.getElementById("subjects-status");
    const uploadSubject = document.getElementById("document-subject");

    // Reset dropdowns to prevent duplicate options.
    subjectFilter.replaceChildren(
        new Option("All subjects", "")
    );

    uploadSubject.replaceChildren(
        new Option("No subject", "")
    );

    // Render subject cards and populate both dropdowns.
    subjectList.replaceChildren();

    if (subjects.length === 0) {
        subjectsStatus.textContent =
            "No subjects yet. Create one to organize your documents.";
        return;
    }

    subjectsStatus.textContent = "";

    for (const subject of subjects) {
        subjectFilter.add(
            new Option(subject.name, String(subject.id))
        );

        uploadSubject.add(
            new Option(subject.name, String(subject.id))
        );


const card = document.createElement("div");
card.className = "subject-card";
const subjectButton = document.createElement("button");
subjectButton.type = "button";
subjectButton.className = "subject-name-button";
subjectButton.textContent = subject.name;
subjectButton.setAttribute(
    "aria-label",
    `Show documents in ${subject.name}`
);

subjectButton.addEventListener("click", () => {
    subjectFilter.value = String(subject.id);
    currentPage = 0;
    loadDocuments();
});

const deleteSubjectButton = document.createElement("button");
deleteSubjectButton.type = "button";
deleteSubjectButton.className = "delete-subject-button";
deleteSubjectButton.textContent = "Delete";
deleteSubjectButton.addEventListener("click", async () => {
    const confirmed = window.confirm(
        `Delete subject "${subject.name}"? Its documents will be kept without a subject.`
    );

    if (!confirmed) return;

    deleteSubjectButton.disabled = true;

    try {
        await apiRequest(`/subjects/${subject.id}`, {
            method: "DELETE",
        });

        if (subjectFilter.value === String(subject.id)) {
            subjectFilter.value = "";
        }

        currentPage = 0;
        await loadSubjects();
        await loadDocuments();
    } catch (error) {
        window.alert(error.message);
        deleteSubjectButton.disabled = false;
    }
});

card.append(subjectButton, deleteSubjectButton);
subjectList.appendChild(card);

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


const showSubjectFormButton = document.getElementById(
    "show-subject-form-button"
);
const subjectForm = document.getElementById("subject-form");
const cancelSubjectButton = document.getElementById(
    "cancel-subject-button"
);
const subjectNameInput = document.getElementById("subject-name");
const subjectMessage = document.getElementById("subject-message");

showSubjectFormButton.addEventListener("click", () => {
    subjectForm.hidden = false;
    subjectMessage.textContent = "";
    subjectNameInput.focus();
});

cancelSubjectButton.addEventListener("click", () => {
    subjectForm.reset();
    subjectForm.hidden = true;
    subjectMessage.textContent = "";
});

subjectForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = subjectNameInput.value.trim();

    if (!name) {
        subjectMessage.textContent = "Enter a subject name.";
        return;
    }

    const submitButton = subjectForm.querySelector(
        'button[type="submit"]'
    );

    submitButton.disabled = true;
    subjectMessage.textContent = "Creating subject...";

    try {
        await apiRequest(
            `/subjects/?name=${encodeURIComponent(name)}`,
            { method: "POST" }
        );

        subjectMessage.textContent = "Subject created successfully.";
        subjectForm.reset();

        await loadSubjects();
        subjectForm.hidden = true;
    } catch (error) {
        subjectMessage.textContent = error.message;
    } finally {
        submitButton.disabled = false;
    }
});
