/**
 * Chat application – client-side logic.
 *
 * Manages WebSocket communication, agent selection sidebar,
 * and the chat message stream.
 */

// ── DOM references ──────────────────────────────────────────
const chatContainer = document.getElementById("chat-container");
const userInput     = document.getElementById("user-input");
const sendBtn       = document.getElementById("send-btn");
const typingEl      = document.getElementById("typing");
const statusDot     = document.getElementById("status-dot");
const statusText    = document.getElementById("status-text");
const agentListEl   = document.getElementById("agent-list");
const sidebar       = document.getElementById("sidebar");
const overlay       = document.getElementById("sidebar-overlay");
const fileInput     = document.getElementById("file-input");
const filePreviewBar = document.getElementById("file-preview-bar");
const uploadBtn      = document.getElementById("upload-btn");
const sessionIdEl    = document.getElementById("session-id");
const newSessionBtn  = document.getElementById("new-session-btn");
const artifactsTabBtn = document.getElementById("artifacts-tab-btn");
const memoryTabBtn    = document.getElementById("memory-tab-btn");
const panelAgents     = document.getElementById("panel-agents");
const panelArtifacts  = document.getElementById("panel-artifacts");
const panelMemory     = document.getElementById("panel-memory");
const panelRag        = document.getElementById("panel-rag");
const ragTabBtn       = document.getElementById("rag-tab-btn");
const artifactListEl  = document.getElementById("artifact-list");
const memoryListEl    = document.getElementById("memory-list");
const ragFileListEl   = document.getElementById("rag-file-list");
const ragGcsInput     = document.getElementById("rag-gcs-input");

// ── State ───────────────────────────────────────────────────
let ws = null;
let currentAgentBubble = null;
let selectedAgentId = null;
let agents = [];
let pendingFiles = [];  // { name, size, base64, mime }
let isFirstConnect = true;
let reconnectAttempts = 0;
let pendingAgentSwitch = false;  // true when the user explicitly requested a switch
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000;  // ms

// ── Sidebar toggle (mobile) ─────────────────────────────────

function toggleSidebar() {
  sidebar.classList.toggle("open");
  overlay.classList.toggle("visible");
}

// ── Agent list ──────────────────────────────────────────────

async function loadAgents() {
  try {
    const resp = await fetch("/api/v1/agents");
    const data = await resp.json();
    agents = data.agents || [];
    const defaultId = data.default || (agents.length ? agents[0].id : null);
    renderAgentList();
    if (defaultId) highlightAgent(defaultId);
  } catch (e) {
    console.error("Failed to load agents:", e);
  }
}

function renderAgentList() {
  agentListEl.innerHTML = "";
  for (const agent of agents) {
    const li = document.createElement("li");
    li.dataset.agentId = agent.id;
    li.innerHTML =
      '<span class="agent-icon">' + agent.icon + "</span>" +
      '<div class="agent-info">' +
        '<div class="agent-label">' + escapeHtml(agent.label) + " Agent</div>" +
        '<div class="agent-desc">'  + escapeHtml(agent.description) + "</div>" +
      "</div>";
    li.onclick = () => selectAgent(agent.id);
    agentListEl.appendChild(li);
  }
}

function highlightAgent(agentId) {
  selectedAgentId = agentId;
  for (const li of agentListEl.children) {
    li.classList.toggle("active", li.dataset.agentId === agentId);
  }
  // Show file upload only for the summarizer agent
  uploadBtn.style.display = (agentId === "summarizer_agent") ? "" : "none";

  // Show / hide Artifacts tab based on agent capabilities
  var agentMeta = agents.find(function (a) { return a.id === agentId; });
  if (agentMeta && agentMeta.has_artifacts) {
    artifactsTabBtn.style.display = "";
  } else {
    artifactsTabBtn.style.display = "none";
  }

  // Show / hide Memory tab based on agent capabilities
  if (agentMeta && agentMeta.has_memory) {
    memoryTabBtn.style.display = "";
  } else {
    memoryTabBtn.style.display = "none";
  }

  // Show / hide RAG Documents tab based on agent capabilities
  if (agentMeta && agentMeta.has_rag) {
    ragTabBtn.style.display = "";
  } else {
    ragTabBtn.style.display = "none";
  }

  // Update current-agent badges in Artifacts / Memory / RAG panels
  var badgeHtml = agentMeta
    ? '<span class="badge-icon">' + agentMeta.icon + '</span>' +
      '<span class="badge-label">' + escapeHtml(agentMeta.label) + ' Agent</span>'
    : '';
  document.getElementById('artifact-agent-badge').innerHTML = badgeHtml;
  document.getElementById('memory-agent-badge').innerHTML   = badgeHtml;
  document.getElementById('rag-agent-badge').innerHTML      = badgeHtml;

  // If current panel's tab is now hidden, fall back to agents
  var activeTab = document.querySelector(".sidebar-nav-btn.active");
  if (activeTab && activeTab.style.display === "none") {
    switchSidebarTab("agents");
  }
}

// ── Sidebar tab switching ───────────────────────────────────

function switchSidebarTab(tab) {
  var btns = document.querySelectorAll(".sidebar-nav-btn");
  btns.forEach(function (b) { b.classList.toggle("active", b.dataset.tab === tab); });

  panelAgents.style.display    = (tab === "agents")    ? "" : "none";
  panelArtifacts.style.display = (tab === "artifacts") ? "" : "none";
  panelMemory.style.display    = (tab === "memory")    ? "" : "none";
  panelRag.style.display       = (tab === "rag")       ? "" : "none";

  if (tab === "artifacts") loadArtifacts();
  if (tab === "memory")    loadMemories();
  if (tab === "rag")       loadRagFiles();
}

// ── Artifact listing ────────────────────────────────────────

async function loadArtifacts() {
  if (!selectedAgentId) return;
  try {
    var resp = await fetch("/api/v1/artifacts?agent_id=" + encodeURIComponent(selectedAgentId));
    var data = await resp.json();
    renderArtifactList(data.artifacts || []);
  } catch (e) {
    console.error("Failed to load artifacts:", e);
    renderArtifactList([]);
  }
}

function renderArtifactList(artifacts) {
  artifactListEl.innerHTML = "";
  if (artifacts.length === 0) {
    artifactListEl.innerHTML = '<p class="artifact-empty">No artifacts yet.</p>';
    return;
  }
  artifacts.forEach(function (name) {
    var item = document.createElement("a");
    item.className = "artifact-item";
    item.href = "/api/v1/artifacts/download?agent_id=" + encodeURIComponent(selectedAgentId) + "&filename=" + encodeURIComponent(name);
    item.download = name;
    item.innerHTML =
      '<span class="artifact-icon">' + artifactIcon(name) + '</span>' +
      '<span class="artifact-name" title="' + escapeHtml(name) + '">' + escapeHtml(name) + '</span>' +
      '<span class="artifact-download">⬇</span>';
    artifactListEl.appendChild(item);
  });
}

function artifactIcon(filename) {
  if (filename.endsWith(".pdf")) return "\uD83D\uDCC4";
  if (filename.endsWith(".md"))  return "\uD83D\uDCDD";
  if (filename.endsWith(".txt")) return "\uD83D\uDCC3";
  return "\uD83D\uDCCE";
}

// ── Memory listing ──────────────────────────────────────────────────

async function loadMemories() {
  if (!selectedAgentId) return;
  try {
    var resp = await fetch("/api/v1/memories?agent_id=" + encodeURIComponent(selectedAgentId));
    var data = await resp.json();
    renderMemoryList(data.memories || []);
  } catch (e) {
    console.error("Failed to load memories:", e);
    renderMemoryList([]);
  }
}

function renderMemoryList(memories) {
  memoryListEl.innerHTML = "";
  if (memories.length === 0) {
    memoryListEl.innerHTML = '<p class="memory-empty">No memory facts yet.</p>';
    return;
  }
  memories.forEach(function (m) {
    var item = document.createElement("div");
    item.className = "memory-item";
    var timeHtml = m.timestamp ? '<div class="memory-time">' + escapeHtml(formatTimestamp(m.timestamp)) + '</div>' : '';
    item.innerHTML =
      '<span class="memory-icon">\uD83D\uDCA1</span>' +
      '<div class="memory-content">' +
        '<div class="memory-fact">' + escapeHtml(m.text) + '</div>' +
        timeHtml +
      '</div>';
    memoryListEl.appendChild(item);
  });
}

function formatTimestamp(iso) {
  try {
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return iso;
  }
}

// ── RAG file management ──────────────────────────────────────────────

async function loadRagFiles() {
  try {
    var resp = await fetch("/api/v1/rag/files");
    var data = await resp.json();
    renderRagFileList(data.files || []);
  } catch (e) {
    console.error("Failed to load RAG files:", e);
    renderRagFileList([]);
  }
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  var k = 1024;
  var sizes = ["B", "KB", "MB", "GB"];
  var i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function renderRagFileList(files) {
  ragFileListEl.innerHTML = "";
  if (files.length === 0) {
    ragFileListEl.innerHTML = '<p class="rag-empty">No documents yet.</p>';
    return;
  }
  files.forEach(function (f) {
    var item = document.createElement("div");
    item.className = "rag-file-item";
    var sizeHtml = f.size_bytes ? '<div class="rag-file-size">' + formatBytes(f.size_bytes) + '</div>' : '';
    item.innerHTML =
      '<span class="rag-file-icon">\uD83D\uDCC4</span>' +
      '<div class="rag-file-info">' +
        '<div class="rag-file-name" title="' + escapeHtml(f.display_name || f.name) + '">' + escapeHtml(f.display_name || f.name) + '</div>' +
        sizeHtml +
      '</div>' +
      '<button class="rag-file-delete" title="Remove from corpus" onclick="deleteRagFile(\'' + escapeHtml(f.name) + '\')">&#10005;</button>';
    ragFileListEl.appendChild(item);
  });
}

async function importRagFile() {
  var uri = ragGcsInput.value.trim();
  if (!uri) return;
  try {
    var resp = await fetch("/api/v1/rag/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gcs_uris: [uri] }),
    });
    var data = await resp.json();
    if (data.status === "ok") {
      ragGcsInput.value = "";
      loadRagFiles();
    } else {
      alert("Import failed: " + (data.message || "Unknown error"));
    }
  } catch (e) {
    console.error("Failed to import RAG file:", e);
    alert("Import failed: " + e.message);
  }
}

async function deleteRagFile(fileName) {
  if (!confirm("Remove this document from the RAG corpus?")) return;
  try {
    var resp = await fetch("/api/v1/rag/files?file_name=" + encodeURIComponent(fileName), { method: "DELETE" });
    var data = await resp.json();
    if (data.status === "ok") {
      loadRagFiles();
    } else {
      alert("Delete failed: " + (data.message || "Unknown error"));
    }
  } catch (e) {
    console.error("Failed to delete RAG file:", e);
  }
}

function selectAgent(agentId) {
  if (agentId === selectedAgentId) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  pendingAgentSwitch = true;
  ws.send(JSON.stringify({ action: "select_agent", agent_id: agentId }));
  // Server confirms via agent_ready before we highlight

  sidebar.classList.remove("open");
  overlay.classList.remove("visible");
}

// ── WebSocket connection ────────────────────────────────────

function connect() {
  // Guard: don't open a new socket if one is already connecting or open
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(proto + "//" + location.host + "/api/v1/ws/chat");

  ws.onopen = function () {
    reconnectAttempts = 0;
    statusDot.classList.add("connected");
    statusText.textContent = "Connected";
    sendBtn.disabled = false;
  };

  ws.onclose = function () {
    statusDot.classList.remove("connected");
    sendBtn.disabled = true;

    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      statusText.textContent = "Disconnected \u2013 please reload the page";
      return;
    }

    var delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts), 30000);
    reconnectAttempts++;
    statusText.textContent = "Disconnected \u2013 reconnecting in " + Math.round(delay / 1000) + "s\u2026";
    setTimeout(connect, delay);
  };

  ws.onerror = function () {
    ws.close();
  };

  ws.onmessage = function (event) {
    var data = JSON.parse(event.data);
    handleServerMessage(data);
  };
}

// ── Handle messages from server ─────────────────────────────

function handleServerMessage(data) {
  // Agent switched confirmation
  if (data.type === "agent_ready") {
    highlightAgent(data.agent_id);
    if (data.session_id) {
      sessionIdEl.textContent = "Session: " + data.session_id.slice(0, 8);
      sessionIdEl.title = data.session_id;
    }

    // On first connect, silently prompt the greeting agent for a hello
    if (isFirstConnect) {
      isFirstConnect = false;
      typingEl.classList.add("visible");
      sendBtn.disabled = true;
      userInput.disabled = true;
      ws.send(JSON.stringify({ action: "message", message: "Hello!" }));
      return;
    }

    // User-initiated agent switch: show notification and prompt intro
    if (pendingAgentSwitch) {
      pendingAgentSwitch = false;
      var agentMeta = agents.find(function (a) { return a.id === data.agent_id; });
      var name = agentMeta ? agentMeta.label : data.agent_id;
      appendMessage("system", "System", "\uD83E\uDD16 Switched to " + name + " Agent");

      typingEl.classList.add("visible");
      sendBtn.disabled = true;
      userInput.disabled = true;
      ws.send(JSON.stringify({ action: "message", message: "Hello! Please introduce yourself briefly." }));
      return;
    }

    // Silent reconnect: don't show "Switched to" or re-greet
    return;
  }

  if (data.type === "done") {
    typingEl.classList.remove("visible");
    currentAgentBubble = null;
    sendBtn.disabled = false;
    userInput.disabled = false;
    userInput.focus();
    // Refresh artifact list if currently viewing the artifacts panel
    if (panelArtifacts.style.display !== "none") {
      loadArtifacts();
    }
    // Refresh memory list if currently viewing the memory panel
    if (panelMemory.style.display !== "none") {
      loadMemories();
    }
    return;
  }

  if (data.type === "error") {
    appendMessage("error", "System", data.content);
    typingEl.classList.remove("visible");
    currentAgentBubble = null;
    sendBtn.disabled = false;
    userInput.disabled = false;
    return;
  }

  // partial or final – stream into the agent bubble
  typingEl.classList.remove("visible");

  if (!currentAgentBubble) {
    currentAgentBubble = appendMessage("agent", friendlyAgentName(data.author), data.content, data.author);
  } else {
    var contentNode = currentAgentBubble.querySelector(".content");
    contentNode.innerHTML = renderMarkdown(data.content);
  }

  chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ── Send user message ───────────────────────────────────────

function sendMessage() {
  var text = userInput.value.trim();
  var hasFiles = pendingFiles.length > 0;
  if ((!text && !hasFiles) || !ws || ws.readyState !== WebSocket.OPEN) return;

  // Build display text
  var displayText = text;
  if (hasFiles) {
    var names = pendingFiles.map(function (f) { return "\uD83D\uDCCE " + f.name; }).join("\n");
    displayText = hasFiles && text ? names + "\n\n" + text : names;
  }
  appendMessage("user", "You", displayText);

  // Build payload
  var payload = { action: "message", message: text || "" };
  if (hasFiles) {
    payload.files = pendingFiles.map(function (f) {
      return { name: f.name, mime: f.mime, data: f.base64 };
    });
  }
  ws.send(JSON.stringify(payload));

  userInput.value = "";
  clearPendingFiles();
  sendBtn.disabled = true;
  userInput.disabled = true;
  typingEl.classList.add("visible");
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ── DOM helpers ─────────────────────────────────────────────

function appendMessage(role, author, text, agentId) {
  var el = document.createElement("div");
  el.className = "message " + role;

  // Agent messages get markdown rendering; others stay escaped
  var bodyHtml = (role === "agent")
    ? renderMarkdown(text)
    : escapeHtml(text);

  // Look up icon for agent and user messages
  var iconHtml = "";
  if (role === "agent") {
    var lookupId = agentId || selectedAgentId;
    var agentMeta = agents.find(function (a) { return a.id === lookupId; });
    var icon = agentMeta ? agentMeta.icon : "\uD83E\uDD16";
    iconHtml = '<span class="message-icon">' + icon + '</span>';
  } else if (role === "user") {
    iconHtml = '<span class="message-icon">😊</span>';
  }

  el.innerHTML =
    iconHtml +
    '<div class="message-body">' +
      '<div class="author">' + escapeHtml(author) + "</div>" +
      '<div class="content">' + bodyHtml + "</div>" +
    '</div>';
  chatContainer.appendChild(el);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  return el;
}

/**
 * Render markdown text to safe HTML via marked.js.
 * Falls back to escaped plain text if marked is unavailable.
 */
function renderMarkdown(text) {
  if (typeof marked !== "undefined" && marked.parse) {
    return marked.parse(text, { breaks: true });
  }
  return escapeHtml(text);
}

function escapeHtml(str) {
  var d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

/**
 * Map a raw agent author id (e.g. "summarizer_agent") to its
 * friendly label from the loaded agents list. Falls back to "Agent".
 */
function friendlyAgentName(author) {
  if (!author) return "Agent";
  var meta = agents.find(function (a) { return a.id === author; });
  return meta ? meta.label + " Agent" : author.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
}

// ── Keyboard shortcut ───────────────────────────────────────

userInput.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
// ── File upload handling ───────────────────────────────────────

fileInput.addEventListener("change", function () {
  var files = Array.from(fileInput.files);
  fileInput.value = "";  // reset so same file can be re-selected
  files.forEach(function (file) {
    var reader = new FileReader();
    reader.onload = function () {
      var base64 = reader.result.split(",")[1]; // strip data:...;base64,
      pendingFiles.push({
        name: file.name,
        size: file.size,
        mime: file.type || "application/octet-stream",
        base64: base64
      });
      renderFilePreview();
    };
    reader.readAsDataURL(file);
  });
});

function renderFilePreview() {
  filePreviewBar.innerHTML = "";
  if (pendingFiles.length === 0) {
    filePreviewBar.classList.remove("has-files");
    return;
  }
  filePreviewBar.classList.add("has-files");
  pendingFiles.forEach(function (f, idx) {
    var chip = document.createElement("div");
    chip.className = "file-chip";
    chip.innerHTML =
      '<span class="file-name">' + escapeHtml(f.name) + "</span>" +
      '<span class="file-size">' + formatFileSize(f.size) + "</span>" +
      '<button class="file-remove" title="Remove">&times;</button>';
    chip.querySelector(".file-remove").onclick = function () {
      pendingFiles.splice(idx, 1);
      renderFilePreview();
    };
    filePreviewBar.appendChild(chip);
  });
}

function clearPendingFiles() {
  pendingFiles = [];
  renderFilePreview();
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}
// ── New session ─────────────────────────────────────────────

var confirmModal  = document.getElementById("confirm-modal");
var modalConfirm  = document.getElementById("modal-confirm");
var modalCancel   = document.getElementById("modal-cancel");

function requestNewSession() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  confirmModal.classList.add("visible");
}

modalCancel.addEventListener("click", function () {
  confirmModal.classList.remove("visible");
});

modalConfirm.addEventListener("click", function () {
  confirmModal.classList.remove("visible");
  ws.send(JSON.stringify({ action: "new_session" }));
  chatContainer.innerHTML = "";
  appendMessage("system", "System", "\uD83D\uDD04 Starting a new session\u2026");
});

confirmModal.addEventListener("click", function (e) {
  if (e.target === confirmModal) confirmModal.classList.remove("visible");
});

// ── Sidebar resize ──────────────────────────────────────────

(function initSidebarResize() {
  var handle = document.getElementById("sidebar-resize-handle");
  if (!handle) return;

  var dragging = false;

  handle.addEventListener("mousedown", function (e) {
    e.preventDefault();
    dragging = true;
    handle.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  });

  document.addEventListener("mousemove", function (e) {
    if (!dragging) return;
    var newWidth = e.clientX;
    if (newWidth < 180) newWidth = 180;
    if (newWidth > 500) newWidth = 500;
    sidebar.style.width = newWidth + "px";
  });

  document.addEventListener("mouseup", function () {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("dragging");
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  });
})();

// ── Boot ────────────────────────────────────────────────────

loadAgents();
connect();
