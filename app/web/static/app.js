function normalizeApiBase(rawBase) {
  try {
    const url = new URL(rawBase, window.location.origin);
    const localAliases = new Set(["127.0.0.1", "localhost"]);
    if (localAliases.has(url.hostname) && localAliases.has(window.location.hostname) && url.hostname !== window.location.hostname) {
      url.hostname = window.location.hostname;
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return rawBase;
  }
}

const state = {
  apiBase: normalizeApiBase(document.body.dataset.apiBase),
  capabilities: null,
  runtime: null,
  testCases: [],
  transientMessages: [],
  pendingUserMessage: null,
  streamingText: "",
  streamingStatuses: [],
  statusHistory: [],
  streamDetail: "",
  streamActive: false,
  selectedAbilitySlash: "/agent",
  stagedAttachments: [],
  currentAbortController: null,
};

const elements = {
  addLinkButton: document.getElementById("addLinkButton"),
  alertStack: document.getElementById("alertStack"),
  attachmentTray: document.getElementById("attachmentTray"),
  chatForm: document.getElementById("chatForm"),
  commandMenu: document.getElementById("commandMenu"),
  composerInput: document.getElementById("composerInput"),
  composerMode: document.getElementById("composerMode"),
  messageList: document.getElementById("messageList"),
  modeList: document.getElementById("modeList"),
  modeSection: document.getElementById("modeSection"),
  newChatButton: document.getElementById("newChatButton"),
  sendButton: document.getElementById("sendButton"),
  sessionList: document.getElementById("sessionList"),
  subagentList: document.getElementById("subagentList"),
  subagentSection: document.getElementById("subagentSection"),
  testCaseList: document.getElementById("testCaseList"),
  testCaseSection: document.getElementById("testCaseSection"),
  uploadInput: document.getElementById("uploadInput"),
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function redirectToLogin() {
  window.location.href = "/login";
}

async function parseErrorPayload(response) {
  const payload = await response.json().catch(() => null);
  if (payload && typeof payload.detail === "string" && payload.detail) {
    return payload.detail;
  }
  return `Request failed: ${response.status}`;
}

async function api(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, {
    credentials: "include",
    ...options,
  });
  if (response.status === 401) {
    redirectToLogin();
    throw new Error("Authentication required.");
  }
  if (!response.ok) {
    throw new Error(await parseErrorPayload(response));
  }
  return response.json();
}

function renderInlineMarkdown(text = "") {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function renderMarkdown(markdown = "") {
  const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let paragraph = [];
  let listItems = [];
  let listType = null;
  let inCodeFence = false;
  let codeLines = [];
  let codeLanguage = "";

  function flushParagraph() {
    if (!paragraph.length) {
      return;
    }
    html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!listItems.length || !listType) {
      return;
    }
    html.push(
      `<${listType}>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${listType}>`,
    );
    listItems = [];
    listType = null;
  }

  function flushCodeFence() {
    if (!inCodeFence) {
      return;
    }
    const languageClass = codeLanguage ? ` class="language-${escapeHtml(codeLanguage)}"` : "";
    html.push(`<pre><code${languageClass}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    inCodeFence = false;
    codeLines = [];
    codeLanguage = "";
  }

  for (const line of lines) {
    const fenceMatch = line.match(/^```(\w+)?\s*$/);
    if (fenceMatch) {
      if (inCodeFence) {
        flushCodeFence();
      } else {
        flushParagraph();
        flushList();
        inCodeFence = true;
        codeLanguage = fenceMatch[1] || "";
      }
      continue;
    }

    if (inCodeFence) {
      codeLines.push(line);
      continue;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = Math.min(headingMatch[1].length, 4);
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const bulletMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (bulletMatch) {
      flushParagraph();
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(bulletMatch[1]);
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(orderedMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushCodeFence();
  return html.join("");
}

function getUiConfig() {
  return state.capabilities?.ui || {
    show_mode_picker: false,
    show_subagents: false,
    modes: [],
    subagents: [],
  };
}

function getAlerts() {
  return state.capabilities?.alerts || [];
}

function getAbilities() {
  const abilities = state.capabilities?.abilities || [];
  if (abilities.length) {
    return abilities;
  }
  return [
    {
      slash: "/agent",
      label: "Transformation Agent",
      workflow: "general",
      skills: [],
      description: "Run the primary transformation agent.",
      primary: true,
    },
  ];
}

function getDefaultAbility() {
  return getAbilities().find((item) => item.slash === "/agent") || getAbilities()[0];
}

function getSelectedAbility() {
  return getAbilities().find((item) => item.slash === state.selectedAbilitySlash) || getDefaultAbility();
}

function parseComposer(text) {
  const trimmed = text.trimStart();
  const match = trimmed.match(/^\/([a-z-]+)/);
  const selectedAbility = getSelectedAbility();
  if (!match) {
    return { ability: selectedAbility, message: text.trim() };
  }
  const slash = `/${match[1]}`;
  const ability = getAbilities().find((item) => item.slash === slash) || selectedAbility;
  const body = trimmed.slice(match[0].length).trim();
  return { ability, message: body };
}

function getCommandMatches() {
  if (!getUiConfig().show_mode_picker) {
    return [];
  }
  const trimmed = elements.composerInput.value.trimStart();
  if (!trimmed.startsWith("/")) {
    return [];
  }
  const query = trimmed.split(/\s+/, 1)[0].toLowerCase();
  return getAbilities().filter((item) => item.slash.startsWith(query));
}

function setSelectedAbility(ability) {
  state.selectedAbilitySlash = ability.slash;
  renderComposerState();
  renderModes();
}

function showTransientMessage(message) {
  state.transientMessages = [
    ...state.transientMessages,
    {
      role: "system",
      content: message,
      created_at: new Date().toISOString(),
      workflow: null,
      metadata: { message_kind: "notice" },
    },
  ].slice(-3);
  renderMessages();
}

function formatTime(value) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function describeDeliverable(name) {
  const lower = name.toLowerCase();
  if (lower.endsWith(".py")) return "Implementation";
  if (lower.includes("mapping")) return "Mapping rules";
  if (lower.includes("validation")) return "Validation";
  if (lower.includes("summary") || lower.includes("understanding")) return "Summary";
  if (lower.endsWith(".json") || lower.endsWith(".csv")) return "Sample output";
  return "Deliverable";
}

function buildOutgoingMessage(message, attachments) {
  const links = attachments.filter((item) => item.kind === "link");
  let finalMessage = message.trim();
  if (!finalMessage && attachments.length) {
    finalMessage = "Please review the attached evidence and explain what is supported, inferred, or still missing.";
  }
  if (!links.length) {
    return finalMessage;
  }
  const urlBlock = `Reference URLs:\n${links.map((item) => `- ${item.url}`).join("\n")}`;
  return finalMessage ? `${finalMessage}\n\n${urlBlock}` : urlBlock;
}

function attachmentLabel(item) {
  if (item.kind === "link") {
    return "Link";
  }
  return item.source === "sample" ? "Sample file" : "Attachment";
}

function attachmentPreview(item) {
  if (item.kind === "link") {
    return item.url;
  }
  return item.name;
}

function renderAlerts() {
  const alerts = getAlerts();
  elements.alertStack.innerHTML = alerts
    .map(
      (alert) => `
        <div class="inline-alert ${escapeHtml(alert.level || "warning")}">
          ${escapeHtml(alert.title)}
        </div>
      `,
    )
    .join("");
}

function renderSessions() {
  const updatedAt = state.runtime?.session?.updated_at;
  elements.sessionList.innerHTML = `
    <button type="button" class="session-item active">
      <strong>Current chat</strong>
      <span>${updatedAt ? `Updated ${escapeHtml(formatTime(updatedAt))}` : "Fresh runtime session"}</span>
    </button>
  `;
}

function renderTestCases() {
  if (!state.testCases.length) {
    elements.testCaseSection.classList.add("hidden");
    elements.testCaseList.innerHTML = "";
    return;
  }
  elements.testCaseSection.classList.remove("hidden");
  elements.testCaseList.innerHTML = state.testCases
    .map(
      (item) => `
        <button type="button" class="sidebar-chip" data-test-case="${escapeHtml(item.id)}">
          ${escapeHtml(item.label)}
        </button>
      `,
    )
    .join("");
}

function renderModes() {
  const ui = getUiConfig();
  const abilities = getAbilities();
  if (!ui.show_mode_picker || abilities.length <= 1) {
    elements.modeSection.classList.add("hidden");
    elements.modeList.innerHTML = "";
    return;
  }
  elements.modeSection.classList.remove("hidden");
  elements.modeList.innerHTML = abilities
    .map(
      (ability) => `
        <button
          type="button"
          class="sidebar-chip ${ability.slash === getSelectedAbility().slash ? "selected" : ""}"
          data-mode="${escapeHtml(ability.slash)}"
        >
          ${escapeHtml(ability.label)}
        </button>
      `,
    )
    .join("");
}

function renderSubagents() {
  const ui = getUiConfig();
  const subagents = ui.show_subagents ? ui.subagents || [] : [];
  if (!subagents.length) {
    elements.subagentSection.classList.add("hidden");
    elements.subagentList.innerHTML = "";
    return;
  }
  elements.subagentSection.classList.remove("hidden");
  elements.subagentList.innerHTML = subagents
    .map(
      (item) => `
        <div class="sidebar-detail">
          <strong>${escapeHtml(item.label)}</strong>
          <span>${escapeHtml(item.description || "")}</span>
        </div>
      `,
    )
    .join("");
}

function renderCommandMenu() {
  const matches = getCommandMatches();
  if (!matches.length) {
    elements.commandMenu.classList.add("hidden");
    elements.commandMenu.innerHTML = "";
    return;
  }
  elements.commandMenu.classList.remove("hidden");
  elements.commandMenu.innerHTML = matches
    .map(
      (ability) => `
        <button type="button" class="command-option" data-mode="${escapeHtml(ability.slash)}">
          <strong>${escapeHtml(ability.label)}</strong>
          <span>${escapeHtml(ability.description)}</span>
        </button>
      `,
    )
    .join("");
}

function renderAttachmentTray() {
  if (!state.stagedAttachments.length) {
    elements.attachmentTray.classList.add("hidden");
    elements.attachmentTray.innerHTML = "";
    return;
  }
  elements.attachmentTray.classList.remove("hidden");
  elements.attachmentTray.innerHTML = state.stagedAttachments
    .map(
      (item) => `
        <div class="attachment-chip">
          <div class="attachment-chip-copy">
            <span>${escapeHtml(attachmentLabel(item))}</span>
            <strong>${escapeHtml(attachmentPreview(item))}</strong>
          </div>
          <button type="button" class="chip-remove" data-remove-attachment="${escapeHtml(item.id)}">×</button>
        </div>
      `,
    )
    .join("");
}

function renderComposerState() {
  const ability = getSelectedAbility();
  elements.composerMode.innerHTML = `
    <span class="mode-pill">${escapeHtml(ability.label)}</span>
    ${getUiConfig().show_mode_picker ? `<span class="mode-copy">${escapeHtml(ability.description)}</span>` : ""}
  `;
  elements.composerInput.style.height = "auto";
  elements.composerInput.style.height = `${Math.min(elements.composerInput.scrollHeight, 220)}px`;
  renderAttachmentTray();
  renderCommandMenu();
}

function messageBadge(item) {
  if (item.metadata?.message_kind === "upload") return "File";
  if (item.metadata?.message_kind === "output") return "Deliverable";
  if (item.metadata?.message_kind === "notice") return "Update";
  return item.role === "assistant" ? "Transformation Agent" : item.role === "user" ? "You" : "System";
}

function renderMessageAttachments(item) {
  if (item.metadata?.message_kind && ["upload", "output"].includes(item.metadata.message_kind)) {
    const href = item.metadata?.download_path ? `${state.apiBase}${item.metadata.download_path}` : "";
    const label = item.metadata.message_kind === "upload" ? "Evidence file" : describeDeliverable(item.metadata?.filename || "");
    return `
      <div class="file-card ${escapeHtml(item.metadata.message_kind)}">
        <div class="file-card-copy">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(item.metadata?.filename || item.content)}</strong>
        </div>
        ${href ? `<a class="file-link" href="${escapeHtml(href)}">Download</a>` : ""}
      </div>
    `;
  }

  const attachments = item.metadata?.attachments || [];
  if (!attachments.length) {
    return "";
  }
  return `
    <div class="inline-attachments">
      ${attachments
        .map(
          (attachment) => `
            <div class="mini-chip">
              <span>${escapeHtml(attachment.kind === "link" ? "Link" : "File")}</span>
              <strong>${escapeHtml(attachment.name || attachment.url || "")}</strong>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function buildMissingSummaryCard() {
  const documents = state.runtime?.documents || [];
  const hasAssistantReply = (state.runtime?.messages || []).some((item) => item.role === "assistant");
  if (state.streamActive || !hasAssistantReply) {
    return "";
  }
  const gapCount = documents.reduce((total, item) => total + (item.gap_sections || 0), 0);
  const assumptionCount = documents.reduce((total, item) => total + (item.assumption_sections || 0), 0);
  if (!gapCount && !assumptionCount) {
    return "";
  }
  return `
    <section class="summary-card">
      <div class="summary-copy">
        <strong>Transformation session summary</strong>
        <p>${escapeHtml(`${gapCount} unresolved gap${gapCount === 1 ? "" : "s"} and ${assumptionCount} assumption-heavy section${assumptionCount === 1 ? "" : "s"} are reflected in the current merged markdown summary.`)}</p>
      </div>
      <a class="file-link" href="${escapeHtml(`${state.apiBase}/api/runtime/missing-information-summary`)}">Download markdown</a>
    </section>
  `;
}

function renderProgressThread() {
  if (!state.streamActive) {
    return "";
  }
  const statusLines = state.statusHistory.length
    ? state.statusHistory
    : [state.streamDetail || "Reviewing inputs and preparing the response."];
  return `
    <section class="progress-thread">
      <div class="progress-headline">
        <span class="progress-spinner" aria-hidden="true"></span>
        <strong>Working</strong>
      </div>
      <ul class="progress-list">
        ${statusLines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function renderEmptyState() {
  const actions = [
    "Attach source files and describe the target you need.",
    "Preload a sample test case from the sidebar.",
    "Ask for mappings, implementation, validation, or final deliverables.",
  ];
  return `
    <section class="empty-state">
      <h3>What should the agent transform?</h3>
      <div class="empty-actions">
        ${actions.map((item) => `<div class="empty-action">${escapeHtml(item)}</div>`).join("")}
      </div>
    </section>
  `;
}

function renderMessages() {
  const baseMessages = state.runtime?.messages || [];
  const messages = [...baseMessages];
  if (state.pendingUserMessage) {
    messages.push(state.pendingUserMessage);
  }
  if (state.streamingText) {
    messages.push({
      role: "assistant",
      content: state.streamingText,
      created_at: new Date().toISOString(),
      metadata: { pending: true },
    });
  }
  messages.push(...state.transientMessages);

  if (!messages.length) {
    elements.messageList.innerHTML = renderEmptyState();
    return;
  }

  elements.messageList.innerHTML = `
    <div class="thread">
      ${buildMissingSummaryCard()}
      ${messages
        .map(
          (item) => `
            <article class="message ${escapeHtml(item.role)} ${item.metadata?.pending ? "is-pending" : ""}">
              <div class="message-meta">
                <span>${escapeHtml(messageBadge(item))}</span>
                <span>${escapeHtml(formatTime(item.created_at))}</span>
              </div>
              ${renderMessageAttachments(item)}
              <div class="message-body">${renderMarkdown(item.content)}</div>
            </article>
          `,
        )
        .join("")}
      ${renderProgressThread()}
    </div>
  `;
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderShell() {
  elements.sendButton.disabled = false;
  elements.sendButton.textContent = state.streamActive ? "Stop" : "Send";
}

function renderAll() {
  renderAlerts();
  renderSessions();
  renderTestCases();
  renderModes();
  renderSubagents();
  renderComposerState();
  renderMessages();
  renderShell();
}

function resetStreamState() {
  state.pendingUserMessage = null;
  state.streamingText = "";
  state.streamingStatuses = [];
  state.statusHistory = [];
  state.streamDetail = "";
  state.streamActive = false;
  state.currentAbortController = null;
}

async function refreshRuntime() {
  const [capabilities, runtime, testCaseResponse] = await Promise.all([
    api("/api/runtime/capabilities"),
    api("/api/runtime/state"),
    api("/api/runtime/test-cases").catch(() => ({ cases: [] })),
  ]);
  state.capabilities = capabilities;
  state.runtime = runtime;
  state.testCases = testCaseResponse.cases || [];
  state.selectedAbilitySlash = getSelectedAbility().slash;
  renderAll();
}

async function readNdjsonStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n");
    while (boundary !== -1) {
      const line = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 1);
      if (line) {
        handleStreamEvent(JSON.parse(line));
      }
      boundary = buffer.indexOf("\n");
    }
  }

  const finalLine = buffer.trim();
  if (finalLine) {
    handleStreamEvent(JSON.parse(finalLine));
  }
}

function handleStreamEvent(event) {
  if (event.type === "status") {
    state.streamingStatuses = event.statuses || [];
    state.streamDetail = event.detail || "Working through the request.";
    const nextLines = Array.isArray(event.detail_lines) && event.detail_lines.length
      ? event.detail_lines
      : [state.streamDetail];
    for (const line of nextLines) {
      if (!line || state.statusHistory.includes(line)) {
        continue;
      }
      state.statusHistory.push(line);
    }
    state.statusHistory = state.statusHistory.slice(-8);
    renderAll();
    return;
  }
  if (event.type === "delta") {
    state.streamingText += event.text || "";
    renderMessages();
    renderComposerState();
    renderShell();
    return;
  }
  if (event.type === "final") {
    state.runtime = event.runtime_state || state.runtime;
    resetStreamState();
    renderAll();
    return;
  }
  if (event.type === "error") {
    throw new Error(event.detail || "Streaming failed.");
  }
}

async function uploadStagedFiles(attachments) {
  const files = attachments.filter((item) => item.kind === "file");
  for (const attachment of files) {
    const form = new FormData();
    form.append("file", attachment.file, attachment.name);
    state.runtime = await api("/api/runtime/upload", {
      method: "POST",
      body: form,
      signal: state.currentAbortController?.signal,
    });
  }
}

async function sendChat(event) {
  event.preventDefault();
  if (state.streamActive) {
    stopActiveRun();
    return;
  }
  const parsed = parseComposer(elements.composerInput.value);
  const queuedAttachments = [...state.stagedAttachments];
  const message = buildOutgoingMessage(parsed.message, queuedAttachments);
  if (!message) {
    showTransientMessage("Describe the transformation task before sending.");
    return;
  }

  const pendingAttachments = queuedAttachments.map((item) => ({
    kind: item.kind,
    name: item.name,
    url: item.url || null,
  }));

  state.transientMessages = [];
  state.pendingUserMessage = {
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
    workflow: parsed.ability.workflow,
    metadata: { pending: true, attachments: pendingAttachments },
  };
  state.streamingText = "";
  state.streamingStatuses = [];
  state.streamDetail = "Reading uploaded evidence and preparing the run.";
  state.streamActive = true;
  state.stagedAttachments = [];
  elements.composerInput.value = "";
  state.currentAbortController = new AbortController();
  renderAll();

  try {
    await uploadStagedFiles(queuedAttachments);

    const response = await fetch(`${state.apiBase}/api/runtime/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      signal: state.currentAbortController.signal,
      body: JSON.stringify({
        message,
        workflow: parsed.ability.workflow,
        skills: parsed.ability.skills,
      }),
    });

    if (response.status === 401) {
      redirectToLogin();
      return;
    }
    if (!response.ok) {
      throw new Error(await parseErrorPayload(response));
    }

    await readNdjsonStream(response);
    await refreshRuntime();
  } catch (error) {
    resetStreamState();
    if (error.name === "AbortError") {
      showTransientMessage("Run stopped.");
    } else {
      showTransientMessage(error.message);
    }
    await refreshRuntime().catch(() => null);
  } finally {
    state.currentAbortController = null;
    renderAll();
  }
}

function stageFiles(files, source = "local") {
  const next = files.map((file) => ({
    id: crypto.randomUUID(),
    kind: "file",
    name: file.name,
    source,
    file,
  }));
  state.stagedAttachments = [...state.stagedAttachments, ...next];
  renderAll();
}

async function handleManualUploads() {
  const files = Array.from(elements.uploadInput.files || []);
  if (!files.length) return;
  stageFiles(files, "local");
  elements.uploadInput.value = "";
}

function decodeBase64ToFile(contentBase64, name, mimeType) {
  const binary = atob(contentBase64);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new File([bytes], name, { type: mimeType || "application/octet-stream" });
}

async function preloadTestCase(caseId) {
  const payload = await api(`/api/runtime/test-cases/${encodeURIComponent(caseId)}`);
  elements.composerInput.value = payload.request_text || "";
  const files = (payload.files || []).map((item) =>
    decodeBase64ToFile(item.content_base64, item.name, item.mime_type),
  );
  state.stagedAttachments = [];
  stageFiles(files, "sample");
  elements.composerInput.focus();
  renderComposerState();
}

async function resetChat() {
  if (!window.confirm("Start a fresh chat? Current uploads and conversation state will be cleared.")) {
    return;
  }
  state.stagedAttachments = [];
  resetStreamState();
  state.transientMessages = [];
  elements.composerInput.value = "";
  state.runtime = await api("/api/runtime/reset", { method: "POST" });
  await refreshRuntime();
}

function addLinkAttachment() {
  const input = window.prompt("Paste a URL to keep with this message:");
  if (!input) return;
  let url;
  try {
    url = new URL(input.trim());
  } catch {
    showTransientMessage("Enter a valid URL starting with http:// or https://");
    return;
  }
  if (!["http:", "https:"].includes(url.protocol)) {
    showTransientMessage("Only http:// or https:// links are supported.");
    return;
  }
  state.stagedAttachments = [
    ...state.stagedAttachments,
    {
      id: crypto.randomUUID(),
      kind: "link",
      name: url.hostname,
      url: url.toString(),
    },
  ];
  renderAll();
}

function stopActiveRun() {
  if (state.currentAbortController) {
    state.currentAbortController.abort();
  }
}

elements.chatForm.addEventListener("submit", sendChat);
elements.composerInput.addEventListener("input", renderComposerState);
elements.uploadInput.addEventListener("change", handleManualUploads);
elements.newChatButton.addEventListener("click", resetChat);
elements.addLinkButton.addEventListener("click", addLinkAttachment);

document.addEventListener("click", (event) => {
  const removeTrigger = event.target.closest("[data-remove-attachment]");
  if (removeTrigger) {
    state.stagedAttachments = state.stagedAttachments.filter((item) => item.id !== removeTrigger.dataset.removeAttachment);
    renderAll();
    return;
  }

  const modeTrigger = event.target.closest("[data-mode]");
  if (modeTrigger) {
    const ability = getAbilities().find((item) => item.slash === modeTrigger.dataset.mode);
    if (ability) {
      setSelectedAbility(ability);
      elements.commandMenu.classList.add("hidden");
    }
    return;
  }

  const testTrigger = event.target.closest("[data-test-case]");
  if (testTrigger) {
    preloadTestCase(testTrigger.dataset.testCase).catch((error) => showTransientMessage(error.message));
    return;
  }

  if (!elements.chatForm.contains(event.target)) {
    elements.commandMenu.classList.add("hidden");
  }
});

refreshRuntime().catch((error) => {
  showTransientMessage(error.message);
});
