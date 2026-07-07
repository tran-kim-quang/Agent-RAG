const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatLog = document.getElementById("chat-log");
const chatStatus = document.getElementById("chat-status");
const chatSteps = document.getElementById("chat-steps");
const chatRunId = document.getElementById("chat-run-id");

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");
const uploadResult = document.getElementById("upload-result");
const graphStatus = document.getElementById("graph-status");
const graphDocuments = document.getElementById("graph-documents");
const graphSummary = document.getElementById("graph-summary");
const graphCanvas = document.getElementById("graph-canvas");
let uploadPollTimer = null;
let graphPollTimer = null;
let chatPollTimer = null;
let selectedGraphSource = null;
let activeChatRunId = null;
const completedChatRuns = new Set();

function setStatus(element, state, label) {
  element.className = `status-pill ${state}`;
  element.textContent = label;
}

function normalizeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function appendMessage(role, content) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.innerHTML = `<p>${escapeHtml(normalizeText(content)).replace(/\n/g, "<br/>")}</p>`;
  chatLog.appendChild(node);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function readApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return { detail: text };
}

function stopUploadPolling() {
  if (uploadPollTimer) {
    clearInterval(uploadPollTimer);
    uploadPollTimer = null;
  }
}

function stopGraphPolling() {
  if (graphPollTimer) {
    clearInterval(graphPollTimer);
    graphPollTimer = null;
  }
}

function stopChatPolling() {
  if (chatPollTimer) {
    clearInterval(chatPollTimer);
    chatPollTimer = null;
  }
}

function escapeHtml(value) {
  return normalizeText(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatPhaseLabel(phase) {
  return String(phase || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderChatSteps(events, status) {
  if (!events?.length) {
    chatSteps.innerHTML = `
      <div class="step-item idle">
        <strong>Idle</strong>
        <span>Agent monitoring will appear here after you send a question.</span>
      </div>
    `;
    return;
  }

  chatSteps.innerHTML = events
    .map((event, index) => {
      const state =
        status === "failed" && index === events.length - 1
          ? "error"
          : index === events.length - 1 && status !== "completed"
            ? "loading"
            : "success";

      return `
        <div class="step-item ${state}">
          <strong>${escapeHtml(formatPhaseLabel(event.phase))}</strong>
          <span>${escapeHtml(event.message || "")}</span>
        </div>
      `;
    })
    .join("");
}

async function pollChatStatus(runId) {
  const response = await fetch(`/api/chat/${runId}`);
  const payload = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || "Could not load chat status.");
  }

  chatRunId.textContent = `Run ${runId.slice(0, 8)}`;
  renderChatSteps(payload.events || [], payload.status);
  setStatus(
    chatStatus,
    payload.status === "failed" ? "error" : payload.status === "completed" ? "success" : "loading",
    payload.status === "processing" ? "Thinking" : payload.status,
  );

  if (payload.status === "completed") {
    if (!completedChatRuns.has(runId)) {
      appendMessage("assistant", payload.answer || "");
      completedChatRuns.add(runId);
    }
    stopChatPolling();
    return;
  }

  if (payload.status === "failed") {
    if (!completedChatRuns.has(runId)) {
      appendMessage("assistant", `Error: ${payload.error || payload.message || "Chat request failed."}`);
      completedChatRuns.add(runId);
    }
    stopChatPolling();
  }
}

function renderGraphDocuments(documents) {
  if (!documents.length) {
    graphDocuments.innerHTML = "<div class='document-card'>No indexed documents yet.</div>";
    return;
  }

  graphDocuments.innerHTML = documents
    .map((document) => {
      const active = document.source === selectedGraphSource ? "active" : "";
      return `
        <button class="document-card ${active}" data-source="${encodeURIComponent(document.source)}" type="button">
          <strong>${escapeHtml(document.name || document.original_file_name || document.source)}</strong>
          <span>Indexed: ${document.indexed_chunks ?? 0}/${document.chunk_count ?? "?"} chunks</span>
          <span>Source type: ${escapeHtml(document.source_type || "unknown")}</span>
        </button>
      `;
    })
    .join("");

  graphDocuments.querySelectorAll("[data-source]").forEach((element) => {
    element.addEventListener("click", () => {
      selectedGraphSource = decodeURIComponent(element.dataset.source);
      refreshGraphView().catch((error) => {
        graphSummary.textContent = `Error: ${error.message}`;
        setStatus(graphStatus, "error", "Error");
      });
    });
  });
}

function renderGraph(documentGraph) {
  const { document, nodes } = documentGraph;
  if (!document) {
    graphSummary.textContent = "Selected document is not in Neo4j yet.";
    graphCanvas.innerHTML = "";
    return;
  }

  graphSummary.textContent = JSON.stringify(document, null, 2);
  graphCanvas.innerHTML = nodes.length
    ? nodes
        .map(
          (node) => `
            <article class="chunk-node">
              <div class="chunk-label">Chunk ${node.chunk_index ?? "?"}</div>
              <div class="chunk-preview">${escapeHtml(node.preview || "")}</div>
            </article>
          `,
        )
        .join("")
    : "<div class='chunk-node'><div class='chunk-label'>No chunks yet</div><div class='chunk-preview'>Neo4j has not received chunk nodes for this document yet.</div></div>";
}

async function refreshGraphView() {
  setStatus(graphStatus, "loading", "Refreshing");
  const overviewResponse = await fetch("/api/graph/documents");
  const overviewPayload = await readApiResponse(overviewResponse);

  if (!overviewResponse.ok) {
    throw new Error(overviewPayload.detail || "Could not load graph overview.");
  }

  const documents = overviewPayload.documents || [];
  if (!selectedGraphSource && documents.length) {
    selectedGraphSource = documents[0].source;
  }
  renderGraphDocuments(documents);

  if (!selectedGraphSource) {
    graphSummary.textContent = "No document selected.";
    graphCanvas.innerHTML = "";
    setStatus(graphStatus, "idle", "Idle");
    return;
  }

  const graphResponse = await fetch(`/api/graph/document?source=${encodeURIComponent(selectedGraphSource)}`);
  const graphPayload = await readApiResponse(graphResponse);

  if (!graphResponse.ok) {
    throw new Error(graphPayload.detail || "Could not load document graph.");
  }

  renderGraph(graphPayload);
  setStatus(graphStatus, "success", "Visible");
}

async function pollUploadStatus(jobId) {
  const response = await fetch(`/api/documents/upload/${jobId}`);
  const payload = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(payload.detail || "Could not load upload status.");
  }

  uploadResult.textContent = JSON.stringify(payload, null, 2);
  if (payload.processed_path) {
    selectedGraphSource = payload.processed_path;
    await refreshGraphView();
  }

  if (payload.status === "completed") {
    setStatus(uploadStatus, "success", "Indexed");
    await refreshGraphView();
    stopUploadPolling();
    stopGraphPolling();
    return;
  }

  if (payload.status === "failed") {
    setStatus(uploadStatus, "error", "Failed");
    stopUploadPolling();
    stopGraphPolling();
    return;
  }

  setStatus(uploadStatus, "loading", payload.phase || "Processing");
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  stopChatPolling();
  activeChatRunId = null;
  appendMessage("user", message);
  chatInput.value = "";
  setStatus(chatStatus, "loading", "Waiting");
  chatRunId.textContent = "Starting run...";
  renderChatSteps([], "idle");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const payload = await readApiResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Chat request failed.");
    }

    chatRunId.textContent = `Run ${payload.run_id.slice(0, 8)}`;
    activeChatRunId = payload.run_id;
    renderChatSteps(payload.events || [], payload.status);
    setStatus(chatStatus, "loading", "Thinking");
    chatPollTimer = setInterval(() => {
      pollChatStatus(payload.run_id).catch((error) => {
        appendMessage("assistant", `Error: ${error.message}`);
        setStatus(chatStatus, "error", "Error");
        stopChatPolling();
      });
    }, 1200);
    await pollChatStatus(payload.run_id);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
    setStatus(chatStatus, "error", "Error");
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files?.[0];
  if (!file) return;

  stopUploadPolling();
  stopGraphPolling();
  setStatus(uploadStatus, "loading", "Uploading");
  uploadResult.textContent = "Uploading document and starting background ingest job...";

  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/documents/upload", {
      method: "POST",
      body: formData,
    });

    const payload = await readApiResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || "Upload failed.");
    }

    uploadResult.textContent = JSON.stringify(payload, null, 2);
    if (payload.status === "accepted" && payload.job_id) {
      setStatus(uploadStatus, "loading", "Queued");
      graphPollTimer = setInterval(() => {
        refreshGraphView().catch(() => {});
      }, 4000);
      uploadPollTimer = setInterval(() => {
        pollUploadStatus(payload.job_id).catch((error) => {
          uploadResult.textContent = `Error: ${error.message}`;
          setStatus(uploadStatus, "error", "Error");
          stopUploadPolling();
        });
      }, 2000);
      await pollUploadStatus(payload.job_id);
    } else {
      setStatus(uploadStatus, "success", payload.status === "accepted" ? "Queued" : "Indexed");
    }
  } catch (error) {
    uploadResult.textContent = `Error: ${error.message}`;
    setStatus(uploadStatus, "error", "Error");
    stopUploadPolling();
  }
});

refreshGraphView().catch((error) => {
  graphSummary.textContent = `Error: ${error.message}`;
  setStatus(graphStatus, "error", "Error");
});
