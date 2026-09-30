const videoFile = document.getElementById("videoFile");
const summarizeButton = document.getElementById("summarizeButton");
const resetButton = document.getElementById("resetButton");
const dropArea = document.getElementById("dropArea");
const videoPreview = document.getElementById("videoPreview");
const videoInfo = document.getElementById("videoInfo");
const languageSelect = document.getElementById("languageSelect");
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

const transcript = document.getElementById("transcript");
const summary = document.getElementById("summary");
const videoId = document.getElementById("videoId");
const status = document.getElementById("status");

const loadHistoryButton = document.getElementById("loadHistoryButton");
const historyList = document.getElementById("historyList");
const deleteAllHistoryButton = document.getElementById("deleteAllHistoryButton");

const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");

const toastContainer = document.getElementById("toastContainer");

const userBar = document.getElementById("userBar");
const usernameLabel = document.getElementById("usernameLabel");
const logoutButton = document.getElementById("logoutButton");

// ---------- Auth guard ----------
// Every page load checks for a valid session before showing any video data.

async function guardAuth() {
    try {
        const response = await fetch("/auth/me");

        if (!response.ok) {
            window.location.href = "/login";
            return;
        }

        const data = await response.json();

        usernameLabel.innerText = data.username;
        userBar.style.display = "flex";

        loadHistory();

    } catch (error) {
        console.error(error);
        window.location.href = "/login";
    }
}

logoutButton.addEventListener("click", async () => {
    try {
        await fetch("/auth/logout", { method: "POST" });
    } catch (error) {
        console.error(error);
    } finally {
        window.location.href = "/login";
    }
});

guardAuth();

// Wrapper around fetch that bounces to the login page if the session
// has expired or was revoked server-side.
async function authFetch(url, options) {
    const response = await fetch(url, options);

    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Session expired");
    }

    return response;
}

// ---------- Toasts ----------

function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3500);
}

// ---------- Stepper ----------

const STEP_IDS = ["step-upload", "step-audio", "step-transcribe", "step-summarize"];

// Maps a backend status to how many steps are fully "done"
const STEP_ORDER = ["processing", "extracting_audio", "transcribing", "summarizing", "completed"];

function updateStepper(currentStatus) {
    const stepEls = STEP_IDS.map(id => document.getElementById(id));
    stepEls.forEach(el => el.classList.remove("active", "done", "failed"));

    if (currentStatus === "failed") {
        const idx = Math.max(0, STEP_ORDER.indexOf(currentStatus));
        stepEls[0].classList.add("failed");
        return;
    }

    const currentIndex = STEP_ORDER.indexOf(currentStatus);

    stepEls.forEach((el, i) => {
        if (currentStatus === "completed" || i < currentIndex) {
            el.classList.add("done");
        } else if (i === currentIndex) {
            el.classList.add("active");
        }
    });
}

function resetStepper() {
    STEP_IDS.forEach(id => {
        document.getElementById(id).classList.remove("active", "done", "failed");
    });
}

// Show video preview when a video is selected
videoFile.addEventListener("change", () => {

    if (videoFile.files.length > 0) {

        const file = videoFile.files[0];

        if (file.size > MAX_FILE_SIZE) {
            showToast("Video file is too large. Maximum size is 100 MB.", "error");
            return;
        }

        const videoURL = URL.createObjectURL(file);

        videoPreview.src = videoURL;
        videoPreview.style.display = "block";

        const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);

        videoInfo.innerText = `${file.name}  ·  ${fileSizeMB} MB`;

    } else {
        videoPreview.style.display = "none";
        videoInfo.innerText = "";
    }
});


summarizeButton.addEventListener("click", async () => {

    if (!videoFile.files.length) {
        showToast("Please select a video first.", "error");
        return;
    }

    progressBar.style.width = "0%";
    progressText.innerText = "0%";
    resetStepper();

    const file = videoFile.files[0];

    if (!file.type.startsWith("video/")) {
        showToast("Please select a video file.", "error");
        videoFile.value = "";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("language", languageSelect.value);

    summarizeButton.disabled = true;
    summarizeButton.innerText = "Uploading...";

    status.innerText = "Uploading video...";
    status.dataset.state = "processing";

    transcript.innerText = "Waiting for transcription...";
    summary.innerText = "Waiting for AI summary...";

    progressBar.style.width = "10%";
    progressText.innerText = "10%";

    try {

        const response = await authFetch("/summarize", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Something went wrong");
        }

        videoId.innerText = "Video ID: " + data.video_id;

        status.innerText = "Status: " + data.status;

        summarizeButton.innerText = "Processing...";

        const finalStatus = await pollStatus(data.video_id);

        if (finalStatus === "completed") {

            status.innerText = "Processing completed!";
            status.dataset.state = "completed";
            updateStepper("completed");

            const transcriptResponse = await authFetch(`/transcript/${data.video_id}`);
            const transcriptData = await transcriptResponse.json();
            transcript.innerText = transcriptData.transcript;
            transcript.classList.remove("placeholder");

            if (transcriptData.language) {
                showToast(`Language used: ${transcriptData.language}`, "success");
            }

            const summaryResponse = await authFetch(`/summary/${data.video_id}`);
            const summaryData = await summaryResponse.json();
            summary.innerText = summaryData.summary;
            summary.classList.remove("placeholder");

            summarizeButton.innerText = "Completed";

            loadHistory();

        } else {

            status.innerText = "Processing failed";
            status.dataset.state = "failed";
            updateStepper("failed");

            transcript.innerText = "Video processing failed.";
            summary.innerText = "Please try again.";

            summarizeButton.innerText = "Try again";
        }

    } catch (error) {

        status.innerText = "Error";
        status.dataset.state = "error";

        transcript.innerText = "An error occurred.";
        summary.innerText = error.message;

        summarizeButton.innerText = "Try again";

        console.error(error);

    } finally {
        summarizeButton.disabled = false;
    }
});


async function checkStatus(videoIdValue) {

    try {

        const response = await authFetch(`/status/${videoIdValue}`);
        const data = await response.json();
        const currentStatus = data.status;

        status.dataset.state = currentStatus;
        updateStepper(currentStatus);

        if (currentStatus === "processing") {

            status.innerText = "Video uploaded. Processing started...";
            progressBar.style.width = "20%";
            progressText.innerText = "20%";

        } else if (currentStatus === "extracting_audio") {

            status.innerText = "Extracting audio from video...";
            progressBar.style.width = "30%";
            progressText.innerText = "30%";

        } else if (currentStatus === "transcribing") {

            status.innerText = "Transcribing audio with Whisper...";
            progressBar.style.width = "50%";
            progressText.innerText = "50%";

        } else if (currentStatus === "summarizing") {

            status.innerText = "Generating AI summary with Ollama...";
            progressBar.style.width = "80%";
            progressText.innerText = "80%";

        } else if (currentStatus === "completed") {

            status.innerText = "Processing completed!";
            progressBar.style.width = "100%";
            progressText.innerText = "100%";

        } else if (currentStatus === "failed") {

            status.innerText = "Video processing failed.";
            progressBar.style.width = "0%";
            progressText.innerText = "Failed";

        } else {
            status.innerText = "Status: " + currentStatus;
        }

        return currentStatus;

    } catch (error) {

        console.error(error);
        status.innerText = "Error checking status";
        status.dataset.state = "error";
        return "failed";
    }
}


async function pollStatus(videoIdValue) {

    while (true) {

        const currentStatus = await checkStatus(videoIdValue);

        if (currentStatus === "completed") {
            return "completed";
        }

        if (currentStatus === "failed") {
            return "failed";
        }

        await new Promise(resolve => setTimeout(resolve, 2000));
    }
}

function copyText(elementId) {
    const text = document.getElementById(elementId).innerText;
    navigator.clipboard.writeText(text);
    showToast("Copied to clipboard", "success");
}

resetButton.addEventListener("click", () => {

    videoFile.value = "";

    videoPreview.style.display = "none";
    videoPreview.src = "";

    videoInfo.innerText = "";
    videoId.innerText = "";

    status.innerText = "";
    delete status.dataset.state;

    resetStepper();

    progressBar.style.width = "0%";
    progressText.innerText = "0%";

    transcript.innerText = "No transcript yet.";
    transcript.classList.add("placeholder");

    summary.innerText = "No summary yet.";
    summary.classList.add("placeholder");

    summarizeButton.innerText = "Summarize video";
    summarizeButton.disabled = false;
});

// Drag and Drop Events

dropArea.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropArea.classList.add("drag-over");
});

dropArea.addEventListener("dragleave", () => {
    dropArea.classList.remove("drag-over");
});

dropArea.addEventListener("drop", (event) => {
    event.preventDefault();
    dropArea.classList.remove("drag-over");

    const files = event.dataTransfer.files;

    if (files.length > 0) {
        videoFile.files = files;
        videoFile.dispatchEvent(new Event("change"));
    }
});

function downloadText(elementId, filename) {
    const text = document.getElementById(elementId).innerText;
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();

    URL.revokeObjectURL(url);
}

async function loadHistory() {

    try {

        const response = await authFetch("/history");
        const data = await response.json();

        if (data.history.length === 0) {
            historyList.innerHTML = '<p class="history-empty">No video history yet.</p>';
            return;
        }

        historyList.innerHTML = "";

        data.history.sort((a, b) => {
            return new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
        });

        data.history.forEach(item => {

            const historyItem = document.createElement("div");
            historyItem.className = "history-item";

            historyItem.innerHTML = `
                <div class="history-main">
                    <div class="history-id">${item.video_id}</div>
                    <div class="history-meta">
                        <span class="history-status" data-state="${item.status}">${item.status}</span>
                        <span>${item.timestamp || "Date not available"}</span>
                    </div>
                </div>
                <div class="history-actions">
                    <button class="icon-button" onclick="loadPreviousVideo('${item.video_id}')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                        Open
                    </button>
                    <button class="icon-button danger" onclick="deleteVideo('${item.video_id}')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>
                        Delete
                    </button>
                </div>
            `;

            historyList.appendChild(historyItem);
        });

    } catch (error) {
        console.error(error);
        historyList.innerHTML = '<p class="history-empty">Failed to load video history.</p>';
    }
}

loadHistoryButton.addEventListener("click", () => {
    loadHistory();
});

async function loadPreviousVideo(previousVideoId) {

    try {

        videoId.innerText = "Video ID: " + previousVideoId;
        status.innerText = "Loading previous video...";
        delete status.dataset.state;

        videoPreview.src = `/video/${previousVideoId}`;
        videoPreview.style.display = "block";
        videoPreview.load();

        const transcriptResponse = await authFetch(`/transcript/${previousVideoId}`);
        const transcriptData = await transcriptResponse.json();

        if (transcriptData.transcript) {
            transcript.innerText = transcriptData.transcript;
            transcript.classList.remove("placeholder");
        } else {
            transcript.innerText = "Transcript not found.";
        }

        const summaryResponse = await authFetch(`/summary/${previousVideoId}`);
        const summaryData = await summaryResponse.json();

        if (summaryData.summary) {
            summary.innerText = summaryData.summary;
            summary.classList.remove("placeholder");
        } else {
            summary.innerText = "Summary not found.";
        }

        status.innerText = "Previous video loaded.";
        status.dataset.state = "completed";

    } catch (error) {
        console.error(error);
        status.innerText = "Failed to load previous video.";
        status.dataset.state = "error";
    }
}

async function deleteVideo(videoIdValue) {

    const confirmDelete = confirm("Are you sure you want to delete this video history?");

    if (!confirmDelete) {
        return;
    }

    try {

        const response = await authFetch(`/history/${videoIdValue}`, {
            method: "DELETE"
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to delete video");
        }

        showToast("Video history deleted", "success");
        loadHistory();

    } catch (error) {
        console.error(error);
        showToast("Failed to delete video history", "error");
    }
}

deleteAllHistoryButton.addEventListener("click", async () => {

    const confirmDelete = confirm("Are you sure you want to delete ALL video history?");

    if (!confirmDelete) {
        return;
    }

    try {

        const response = await authFetch("/history", {
            method: "DELETE"
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to delete all history");
        }

        showToast(`Deleted ${data.deleted_count} video history record(s)`, "success");
        loadHistory();

    } catch (error) {
        console.error(error);
        showToast("Failed to delete all video history", "error");
    }
});
