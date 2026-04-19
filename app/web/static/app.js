const state = {
  apiBase: document.body.dataset.apiBase,
  capabilities: null,
  runtime: null,
  transientMessages: [],
};

const elements = {
  abilityStrip: document.getElementById("abilityStrip"),
  activityList: document.getElementById("activityList"),
  chatForm: document.getElementById("chatForm"),
  cliStatusBadge: document.getElementById("cliStatusBadge"),
  commandMenu: document.getElementById("commandMenu"),
  composerInput: document.getElementById("composerInput"),
  keyStatusBadge: document.getElementById("keyStatusBadge"),
  messageList: document.getElementById("messageList"),
  runtimeFacts: document.getElementById("runtimeFacts"),
  runtimeModeBadge: document.getElementById("runtimeModeBadge"),
  runtimeSummary: document.getElementById("runtimeSummary"),
  selectedAbility: document.getElementById("selectedAbility"),
  sendButton: document.getElementById("sendButton"),
  uploadInput: document.getElementById("uploadInput"),
  uploadList: document.getElementById("uploadList"),
};

function escapeHtml(value = "") {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function api(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function getAbilities() {
  return state.capabilities?.abilities || [];
}

function getDefaultAbility() {
  return getAbilities().find((item) => item.slash === "/agent") || {
    slash: "/agent",
    label: "General Agent",
    workflow: "general",
    skills: [],
    description: "Use the full agent.",
  };
}

function findAbilityBySlash(slash) {
  return getAbilities().find((item) => item.slash === slash) || null;
}

function parseComposer(text) {
  const trimmed = text.trimStart();
  const match = trimmed.match(/^\/([a-z-]+)/);
  const defaultAbility = getDefaultAbility();
  if (!match) {
    return {
      ability: defaultAbility,
      message: text.trim(),
      query: null,
    };
  }

  const slash = `/${match[1]}`;
  const ability = findAbilityBySlash(slash) || defaultAbility;
  const body = trimmed.slice(match[0].length).trim();
  return {
    ability,
    message: body,
    query: slash,
  };
}

function getCommandMatches() {
  const trimmed = elements.composerInput.value.trimStart();
  if (!trimmed.startsWith("/")) {
    return [];
  }
  const query = trimmed.split(/\s+/, 1)[0].toLowerCase();
  return getAbilities().filter((item) => item.slash.startsWith(query));
}

function setComposerAbility(ability) {
  const parsed = parseComposer(elements.composerInput.value);
  const nextMessage = parsed.message ? ` ${parsed.message}` : " ";
  elements.composerInput.value = `${ability.slash}${nextMessage}`;
  elements.composerInput.focus();
  renderComposerState();
}

function showTransientMessage(message) {
  state.transientMessages = [
    ...state.transientMessages,
    {
      role: "system",
      content: message,
      created_at: new Date().toISOString(),
      workflow: null,
      metadata: {},
    },
  ].slice(-3);
  renderMessages();
}

function renderAbilityStrip() {
  elements.abilityStrip.innerHTML = "";
  for (const ability of getAbilities()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ability-chip";
    button.innerHTML = `
      <span>${escapeHtml(ability.slash)}</span>
      <strong>${escapeHtml(ability.label)}</strong>
    `;
    button.addEventListener("click", () => setComposerAbility(ability));
    elements.abilityStrip.appendChild(button);
  }
}

function renderCommandMenu() {
  const matches = getCommandMatches();
  if (!matches.length) {
    elements.commandMenu.classList.add("hidden");
    elements.commandMenu.innerHTML = "";
    return;
  }

  elements.commandMenu.classList.remove("hidden");
  elements.commandMenu.innerHTML = "";
  for (const ability of matches) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "command-option";
    button.innerHTML = `
      <div>
        <div class="command-title">${escapeHtml(ability.slash)} <strong>${escapeHtml(ability.label)}</strong></div>
        <div class="command-description">${escapeHtml(ability.description)}</div>
      </div>
    `;
    button.addEventListener("click", () => setComposerAbility(ability));
    elements.commandMenu.appendChild(button);
  }
}

function renderComposerState() {
  const parsed = parseComposer(elements.composerInput.value);
  elements.selectedAbility.innerHTML = `
    <span class="selected-slash">${escapeHtml(parsed.ability.slash)}</span>
    <span>${escapeHtml(parsed.ability.description)}</span>
  `;
  renderCommandMenu();
}

function renderMessages() {
  const baseMessages = state.runtime?.messages || [];
  const messages = [...baseMessages, ...state.transientMessages];
  elements.messageList.innerHTML = "";

  if (!messages.length) {
    elements.messageList.innerHTML = `
      <div class="empty-state">
        <strong>No messages yet.</strong>
        <p>Start with <code>/discover</code> to frame the problem, or <code>/plan</code> if you already know what needs to ship.</p>
      </div>
    `;
    return;
  }

  for (const item of messages) {
    const wrapper = document.createElement("article");
    wrapper.className = `message-card role-${item.role}`;
    wrapper.innerHTML = `
      <div class="message-meta">
        <span>${escapeHtml(item.role)}</span>
        <span>${new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      <div class="message-body">${escapeHtml(item.content)}</div>
      <div class="message-tags">
        ${item.workflow ? `<span class="message-tag">${escapeHtml(item.workflow)}</span>` : ""}
        ${(item.metadata?.skills || []).map((skill) => `<span class="message-tag">${escapeHtml(skill)}</span>`).join("")}
      </div>
    `;
    elements.messageList.appendChild(wrapper);
  }

  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderUploads() {
  const uploads = state.runtime?.uploads || [];
  elements.uploadList.innerHTML = "";
  if (!uploads.length) {
    elements.uploadList.innerHTML = "<p class='muted-copy'>No files attached yet.</p>";
    return;
  }

  for (const item of uploads) {
    const wrapper = document.createElement("div");
    wrapper.className = "upload-item";
    wrapper.innerHTML = `
      <strong>${escapeHtml(item.name)}</strong>
      <span>${escapeHtml(item.path)}</span>
    `;
    elements.uploadList.appendChild(wrapper);
  }
}

function renderActivity() {
  const activity = [...(state.runtime?.activity || [])].reverse();
  elements.activityList.innerHTML = "";
  if (!activity.length) {
    elements.activityList.innerHTML = "<p class='muted-copy'>No runtime events yet.</p>";
    return;
  }

  for (const item of activity) {
    const wrapper = document.createElement("div");
    wrapper.className = `activity-item level-${item.level}`;
    wrapper.innerHTML = `
      <div class="message-meta">
        <strong>${escapeHtml(item.title)}</strong>
        <span>${new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      ${item.detail ? `<p>${escapeHtml(item.detail)}</p>` : ""}
      <span class="activity-event">${escapeHtml(item.event)}</span>
    `;
    elements.activityList.appendChild(wrapper);
  }
}

function renderRuntimeFacts() {
  const runtime = state.runtime?.session;
  const capabilityRuntime = state.capabilities?.runtime;
  if (!runtime || !capabilityRuntime) {
    elements.runtimeFacts.innerHTML = "<p class='muted-copy'>Runtime unavailable.</p>";
    return;
  }

  elements.runtimeSummary.textContent =
    `Runtime ${runtime.id} is active. Uploaded files and conversation state last only for the current backend process.`;

  elements.runtimeFacts.innerHTML = `
    <div class="fact-row"><span>Session ID</span><strong>${escapeHtml(runtime.id)}</strong></div>
    <div class="fact-row"><span>Started</span><strong>${new Date(runtime.created_at).toLocaleString()}</strong></div>
    <div class="fact-row"><span>Updated</span><strong>${new Date(runtime.updated_at).toLocaleString()}</strong></div>
    <div class="fact-row"><span>Claude CLI</span><strong>${escapeHtml(capabilityRuntime.claude_cli_path)}</strong></div>
  `;

  elements.cliStatusBadge.textContent = capabilityRuntime.claude_cli_available
    ? "Claude CLI ready"
    : "Claude CLI missing";
  elements.cliStatusBadge.className = `status-badge ${
    capabilityRuntime.claude_cli_available ? "good-badge" : "warn-badge"
  }`;

  elements.keyStatusBadge.textContent = capabilityRuntime.anthropic_api_key_configured
    ? "API key detected"
    : "API key not set";
  elements.keyStatusBadge.className = `status-badge ${
    capabilityRuntime.anthropic_api_key_configured ? "good-badge" : "warn-badge"
  }`;
}

function renderAll() {
  renderAbilityStrip();
  renderComposerState();
  renderMessages();
  renderUploads();
  renderActivity();
  renderRuntimeFacts();
}

async function refreshRuntime() {
  const [capabilities, runtime] = await Promise.all([
    api("/api/runtime/capabilities"),
    api("/api/runtime/state"),
  ]);
  state.capabilities = capabilities;
  state.runtime = runtime;
  renderAll();
}

async function sendChat(event) {
  event.preventDefault();
  const parsed = parseComposer(elements.composerInput.value);
  if (!parsed.message) {
    showTransientMessage("Add a prompt after the slash ability before sending.");
    return;
  }

  elements.sendButton.disabled = true;
  elements.sendButton.textContent = "Running...";
  state.transientMessages = [];
  renderMessages();

  try {
    await api("/api/runtime/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: parsed.message,
        workflow: parsed.ability.workflow,
        skills: parsed.ability.skills,
      }),
    });
    await refreshRuntime();
    elements.composerInput.value = `${parsed.ability.slash} `;
    renderAll();
  } catch (error) {
    showTransientMessage(error.message);
    await refreshRuntime().catch(() => null);
  } finally {
    elements.sendButton.disabled = false;
    elements.sendButton.textContent = "Run agent";
  }
}

async function uploadFile() {
  const file = elements.uploadInput.files?.[0];
  if (!file) {
    return;
  }

  const form = new FormData();
  form.append("file", file);
  try {
    state.runtime = await api("/api/runtime/upload", {
      method: "POST",
      body: form,
    });
    renderAll();
  } catch (error) {
    showTransientMessage(error.message);
  } finally {
    elements.uploadInput.value = "";
  }
}

elements.chatForm.addEventListener("submit", sendChat);
elements.composerInput.addEventListener("input", renderComposerState);
elements.uploadInput.addEventListener("change", uploadFile);

document.addEventListener("click", (event) => {
  if (!elements.chatForm.contains(event.target)) {
    elements.commandMenu.classList.add("hidden");
  }
});

refreshRuntime().catch((error) => {
  elements.runtimeSummary.textContent = error.message;
});
