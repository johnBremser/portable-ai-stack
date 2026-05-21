/**
 * Local AI Stack — UI moderna
 * Mantém as APIs/lógicas atuais com layout novo.
 */
(function () {
  function fmtDetail(d) {
    if (d == null) return "";
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => (x.msg || x) + "").join("; ");
    return String(d);
  }

  const DEFAULT_MODEL = "qwen3.5:4b";
  const DEFAULT_SYSTEM = "";
  const DEFAULT_API_PORT = "8500";

  function resolveApiBase() {
    const stored = window.localStorage.getItem("las_api_base");
    if (stored) return stored;
    const proto = window.location.protocol;
    const host = window.location.hostname;
    if ((proto === "http:" || proto === "https:") && host) {
      return `${proto}//${host}:${DEFAULT_API_PORT}`;
    }
    return "http://localhost:8500";
  }

  const API_BASE = resolveApiBase();

  const el = {
    chatSidebar: document.getElementById("chat-sidebar"),
    historyList: document.getElementById("history-list"),
    historySearch: document.getElementById("history-search"),
    btnNewChat: document.getElementById("btn-new-chat"),
    btnMenu: document.getElementById("btn-menu"),
    btnSettings: document.getElementById("btn-settings"),
    btnCloseSettings: document.getElementById("btn-close-settings"),
    btnFocus: document.getElementById("btn-focus"),
    overlay: document.getElementById("overlay"),
    settingsOverlay: document.getElementById("settings-overlay"),
    commandOverlay: document.getElementById("command-overlay"),
    sessionChip: document.getElementById("session-chip"),
    sessionOverlay: document.getElementById("session-overlay"),
    btnCloseSession: document.getElementById("btn-close-session"),
    sTemperature: document.getElementById("s-temperature"),
    sTopP: document.getElementById("s-top-p"),
    sTopK: document.getElementById("s-top-k"),
    sMaxTokens: document.getElementById("s-max-tokens"),
    sThink: document.getElementById("s-think"),
    sessionPrompt: document.getElementById("session-prompt"),

    tokenTracker: document.getElementById("token-tracker"),
    tokenChart: document.getElementById("token-chart"),
    tokenText: document.getElementById("token-text"),

    statusBadge: document.getElementById("status-badge"),
    modelSelect: document.getElementById("model-select"),
    temperature: document.getElementById("temperature"),
    topP: document.getElementById("top-p"),
    topK: document.getElementById("top-k"),
    maxTokens: document.getElementById("max-tokens"),
    think: document.getElementById("think"),
    systemPrompt: document.getElementById("system-prompt"),

    btnClear: document.getElementById("btn-clear"),

    alertError: document.getElementById("alert-error"),
    loadingRow: document.getElementById("loading-row"),
    attachmentNotice: document.getElementById("attachment-notice"),
    btnStop: document.getElementById("btn-stop"),
    messages: document.getElementById("messages"),
    welcome: document.getElementById("welcome"),
    welcomeModel: document.getElementById("welcome-model"),
    messageInput: document.getElementById("message-input"),
    btnSend: document.getElementById("btn-send"),
    fileInput: document.getElementById("file-input"),
    btnClip: document.getElementById("btn-clip"),
    fileHint: document.getElementById("file-hint"),
    btnClearFile: document.getElementById("btn-clear-file"),
  };

  let messages = [];
  let sessionId = null;
  let totalTokens = 0;
  let pendingFile = null;
  let apiOnline = false;
  let sendBusy = false;
  let isFirstLoad = true;
  let abortController = null;
  let allSessions = [];
  let pendingReuseAttachmentIds = new Set();

  function showError(msg) {
    el.alertError.textContent = msg;
    el.alertError.classList.add("show");
  }

  function clearError() {
    el.alertError.classList.remove("show");
    el.alertError.textContent = "";
  }

  function updateRangeLabels() {
    document.getElementById("temp-val").textContent = el.temperature.value;
    document.getElementById("topp-val").textContent = el.topP.value;
    document.getElementById("topk-val").textContent = el.topK.value;
    document.getElementById("mt-val").textContent = el.maxTokens.value;
  }

  function updateSessionRangeLabels() {
    document.getElementById("s-temp-val").textContent = el.sTemperature.value;
    document.getElementById("s-topp-val").textContent = el.sTopP.value;
    document.getElementById("s-topk-val").textContent = el.sTopK.value;
    document.getElementById("s-mt-val").textContent = el.sMaxTokens.value;
  }

  function markdownToSafeHtml(md) {
    if (md == null || md === "") return "";
    if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
      const src = String(md);
      const raw = typeof marked.parse === "function" ? marked.parse(src, { breaks: true, gfm: true }) : marked(src);
      return DOMPurify.sanitize(raw);
    }
    const d = document.createElement("div");
    d.textContent = String(md);
    return d.innerHTML.replace(/\n/g, "<br>");
  }

  function applyLinkPolicy(root) {
    root.querySelectorAll("a[href]").forEach((a) => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    });
  }

  async function loadGlobalSettings() {
    try {
      const resp = await fetch(`${API_BASE}/settings`);
      const data = await resp.json();
      if (data.global_system_prompt !== undefined) el.systemPrompt.value = data.global_system_prompt;
      if (data.temperature) el.temperature.value = data.temperature;
      if (data.top_p) el.topP.value = data.top_p;
      if (data.top_k) el.topK.value = data.top_k;
      if (data.max_tokens) el.maxTokens.value = data.max_tokens;
      if (data.think_enabled) el.think.checked = (data.think_enabled === "True" || data.think_enabled === true);
      updateRangeLabels();
    } catch (e) { console.error("Erro ao carregar settings:", e); }
  }

  async function saveGlobalSettings() {
    const body = {
      global_system_prompt: el.systemPrompt.value,
      temperature: parseFloat(el.temperature.value),
      top_p: parseFloat(el.topP.value),
      top_k: parseInt(el.topK.value),
      max_tokens: parseInt(el.maxTokens.value),
      think_enabled: el.think.checked
    };
    try {
      await fetch(`${API_BASE}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
    } catch (e) { console.error("Erro ao salvar settings:", e); }
  }

  function getEffectiveParams() {
    const globalPrompt = el.systemPrompt.value.trim();
    const sessionPrompt = el.sessionPrompt.value.trim();
    const finalPrompt = [globalPrompt, sessionPrompt].filter(Boolean).join("\n\n---\n\n");

    return {
      system_prompt: finalPrompt,
      temperature: parseFloat(el.sTemperature.value),
      top_p: parseFloat(el.sTopP.value),
      top_k: parseInt(el.sTopK.value),
      max_tokens: parseInt(el.sMaxTokens.value),
      think: el.sThink.checked
    };
  }

  async function saveSessionSettings() {
    if (!sessionId) return; // Só salva se a sessão já existe no backend

    const body = {
      system_prompt: el.sessionPrompt.value.trim() || null,
      temperature: parseFloat(el.sTemperature.value),
      top_p: parseFloat(el.sTopP.value),
      top_k: parseInt(el.sTopK.value),
      max_tokens: parseInt(el.sMaxTokens.value),
      think_enabled: el.sThink.checked
    };
    try {
      await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
    } catch (e) { console.error("Erro ao salvar session settings:", e); }
  }

  function enhanceCodeBlocks(root) {
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.querySelector(".copy-code-btn")) return;
      const code = pre.querySelector("code");
      if (!code) return;
      const btn = document.createElement("button");
      btn.className = "copy-code-btn";
      btn.type = "button";
      btn.title = "Copiar código";
      btn.textContent = "Copiar";
      btn.addEventListener("click", async () => {
        const raw = code.innerText || "";
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(raw);
          } else {
            const ta = document.createElement("textarea");
            ta.value = raw;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            ta.remove();
          }
          const old = btn.textContent;
          btn.textContent = "Copiado";
          setTimeout(() => (btn.textContent = old), 1200);
        } catch (e) {
          showError("Falha ao copiar bloco: " + e.message);
        }
      });
      pre.appendChild(btn);
    });
  }

  function setBubbleContent(bubble, text, { enhance = false } = {}) {
    bubble.classList.add("bubble-md");
    bubble.innerHTML = markdownToSafeHtml(text);
    applyLinkPolicy(bubble);
    if (enhance) enhanceCodeBlocks(bubble);
  }

  function makeCopyButton(getText) {
    const btn = document.createElement("button");
    btn.className = "btn-copy";
    btn.type = "button";
    btn.title = "Copiar resposta";
    btn.textContent = "⧉";
    btn.addEventListener("click", async () => {
      const text = getText() || "";
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement("textarea");
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
        }
        const old = btn.textContent;
        btn.textContent = "✓";
        setTimeout(() => {
          btn.textContent = old;
        }, 1200);
      } catch (e) {
        showError("Não foi possível copiar: " + e.message);
      }
    });
    return btn;
  }

  function refreshAttachmentNotice() {
    const hasAttachmentInMessages = messages.some(
      (m) => (m.attachments || []).some((att) => att && att.id)
    );
    const selected = pendingReuseAttachmentIds.size;
    if (!hasAttachmentInMessages && !selected) {
      el.attachmentNotice.style.display = "none";
      return;
    }
    let suffix = "";
    if (selected > 0) {
      suffix = ` | ${selected} anexo(s) marcado(s) para o próximo envio.`;
    }
    el.attachmentNotice.innerHTML =
      'Esta conversa possui anexos antigos. Eles não entram automaticamente no novo contexto. Clique no botão <strong>X</strong> no card do anexo para reutilizar no próximo envio.' + suffix;
    el.attachmentNotice.style.display = "block";
  }

  function scrollMessagesToBottom() {
    const container = el.messages;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
    setTimeout(() => {
      container.scrollTop = container.scrollHeight;
    }, 24);
  }

  function renderAttachmentPreview(att) {
    if (!att) return null;
    const wrap = document.createElement("div");
    wrap.className = "attachment-preview";

    const head = document.createElement("div");
    head.className = "attachment-head";
    head.textContent = "Anexo: " + (att.name || "arquivo");
    if (att.id) {
      const reuseBtn = document.createElement("button");
      reuseBtn.className = "btn-reuse-attachment";
      const isMarked = pendingReuseAttachmentIds.has(att.id);
      reuseBtn.textContent = isMarked ? "✓" : "X";
      reuseBtn.title = isMarked ? "Anexo marcado para o próximo envio" : "Marcar anexo para reuso no próximo envio";
      reuseBtn.addEventListener("click", () => {
        if (pendingReuseAttachmentIds.has(att.id)) {
          pendingReuseAttachmentIds.delete(att.id);
        } else {
          pendingReuseAttachmentIds.add(att.id);
        }
        refreshAttachmentNotice();
        renderMessages();
      });
      head.appendChild(reuseBtn);
    }
    wrap.appendChild(head);

    const previewUrl = att.previewUrl || (att.url ? API_BASE + att.url : null);

    if (att.kind === "image" && previewUrl) {
      const img = document.createElement("img");
      img.src = previewUrl;
      img.alt = att.name || "Imagem anexada";
      wrap.appendChild(img);
      return wrap;
    }

    if (att.kind === "pdf" && previewUrl) {
      const embed = document.createElement("embed");
      embed.src = previewUrl + "#page=1";
      embed.type = "application/pdf";
      wrap.appendChild(embed);
      return wrap;
    }

    const file = document.createElement("div");
    file.className = "attachment-file";
    file.textContent = "Arquivo anexado: " + (att.name || "sem nome");
    wrap.appendChild(file);
    return wrap;
  }

  function renderMessages() {
    el.welcome.style.display = messages.length ? "none" : "block";
    const existing = el.messages.querySelectorAll(".msg-user, .msg-assistant");
    existing.forEach((n) => n.remove());

    for (const m of messages) {
      const row = document.createElement("div");
      row.className = m.role === "user" ? "msg-user" : "msg-assistant";

      const av = document.createElement("div");
      av.className = "avatar " + (m.role === "user" ? "avatar-user" : "avatar-ai");
      av.textContent = m.role === "user" ? "você" : "AI";

      const col = document.createElement("div");
      col.className = m.role === "user" ? "user-col" : "assistant-col";

      if (m.role === "user") {
        const attachments = m.attachments || (m.attachment ? [m.attachment] : []);
        attachments.forEach((att) => {
          const prev = renderAttachmentPreview(att);
          if (prev) col.appendChild(prev);
        });
      }

      const bubbleWrap = document.createElement("div");
      bubbleWrap.className = "bubble-wrap";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      setBubbleContent(bubble, m.content || "", { enhance: true });
      bubbleWrap.appendChild(bubble);

      if (m.role === "assistant") {
        bubbleWrap.appendChild(makeCopyButton(() => m.content || ""));
      }

      col.appendChild(bubbleWrap);

      if (m.role === "assistant" && m.metrics) {
        const footer = document.createElement("div");
        footer.className = "msg-footer";
        const { duration, tps, tokens_used, ttft } = m.metrics;
        footer.innerHTML = `
          <div class="metric-pill">⚡ ${tps} tok/s</div>
          <div class="metric-pill">📝 ${tokens_used} tokens</div>
          <div class="metric-pill">⏱ ${duration}s</div>
          ${ttft ? `<div class="metric-pill">🧠 ${ttft}s</div>` : ""}
        `;
        col.appendChild(footer);
      }

      if (m.role === "user") {
        row.appendChild(col);
        row.appendChild(av);
      } else {
        row.appendChild(av);
        row.appendChild(col);
      }

      el.messages.appendChild(row);
    }

    scrollMessagesToBottom();
    refreshAttachmentNotice();
  }

  async function streamFromSse(fetchPromise, bodyThinkFlag) {
    const r = await fetchPromise;
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(fmtDetail(err.detail) || r.statusText || String(r.status));
    }
    if (!r.body) throw new Error("Stream indisponível.");

    const row = document.createElement("div");
    row.className = "msg-assistant msg-streaming";
    const av = document.createElement("div");
    av.className = "avatar avatar-ai";
    av.textContent = "AI";
    const col = document.createElement("div");
    col.className = "assistant-col";

    let fullReply = "";
    let fullThink = "";
    let sawContent = false;
    let lastRunMetrics = null;

    const bubbleWrap = document.createElement("div");
    bubbleWrap.className = "bubble-wrap";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = "";
    bubbleWrap.appendChild(bubble);
    bubbleWrap.appendChild(makeCopyButton(() => fullReply));
    col.appendChild(bubbleWrap);

    let thinkPanel = null;
    let thinkText = null;
    if (bodyThinkFlag) {
      thinkPanel = document.createElement("div");
      thinkPanel.className = "think-panel";
      thinkPanel.style.display = "none";
      const thinkLabel = document.createElement("div");
      thinkLabel.className = "think-label";
      thinkLabel.textContent = "Raciocínio";
      thinkText = document.createElement("div");
      thinkPanel.appendChild(thinkLabel);
      thinkPanel.appendChild(thinkText);
      thinkPanel.addEventListener("click", () => thinkPanel.classList.remove("think-collapsed"));
      col.insertBefore(thinkPanel, bubbleWrap);
    }

    row.appendChild(av);
    row.appendChild(col);
    el.messages.appendChild(row);
    scrollMessagesToBottom();

    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const blocks = buf.split("\n\n");
      buf = blocks.pop() || "";

      for (const block of blocks) {
        const line = block.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        let data;
        try {
          data = JSON.parse(line.slice(6).trim());
        } catch {
          continue;
        }

        if (data.type === "start" && data.session_id) {
          const wasNew = !sessionId;
          sessionId = data.session_id;
          if (wasNew) saveSessionSettings();
        } else if (data.type === "think" && data.token) {
          if (!thinkPanel) {
            thinkPanel = document.createElement("div");
            thinkPanel.className = "think-panel";
            const thinkLabel = document.createElement("div");
            thinkLabel.className = "think-label";
            thinkLabel.textContent = "Raciocínio";
            thinkText = document.createElement("div");
            thinkPanel.appendChild(thinkLabel);
            thinkPanel.appendChild(thinkText);
            col.insertBefore(thinkPanel, bubbleWrap);
          }
          fullThink += data.token;
          thinkText.textContent = fullThink;
          thinkPanel.style.display = "block";
          updateMetrics(data);
        } else if (data.type === "token" && data.token) {
          if (!sawContent && thinkPanel) {
            sawContent = true;
            thinkPanel.classList.add("think-collapsed");
          }
          fullReply += data.token;
          setBubbleContent(bubble, fullReply); // markdown re-render por chunk
          updateMetrics(data);
        } else if (data.type === "done") {
          if (data.session_id) sessionId = data.session_id;
          if (typeof data.total_tokens === "number") {
            totalTokens = data.total_tokens;
          } else if (typeof data.tokens_used === "number") {
            totalTokens = data.tokens_used; // Fallback se o backend for antigo (mas tokens_used já vinha como total_tokens antes)
          }
          lastRunMetrics = data;
          updateMetrics(data);
          renderMessages();
        } else if (data.type === "error") {
          throw new Error(data.detail || "Erro no stream");
        }
      }
      scrollMessagesToBottom();
    }

    row.classList.remove("msg-streaming");
    return { reply: fullReply, metrics: lastRunMetrics };
  }

  function updateMetrics(lastMetrics = null) {
    if (sessionId) {
      const short = sessionId.slice(0, 8) + "…" + sessionId.slice(-4);
      el.sessionChip.textContent = "Sessão: " + short;
      el.sessionChip.title = sessionId;
    } else {
      el.sessionChip.textContent = "Sessão: nova";
      el.sessionChip.title = "Sessão ainda não iniciada";
    }

    if (totalTokens > 0) {
      const maxCtx = parseInt(el.maxTokens.value, 10) || 32768;
      const pct = Math.min(100, Math.round((totalTokens / maxCtx) * 100));
      el.tokenTracker.style.display = "flex";
      el.tokenText.textContent = `${totalTokens}/${maxCtx}`;
      el.tokenChart.style.background = `conic-gradient(var(--accent) ${pct}%, var(--surface-2) ${pct}%)`;
    } else {
      el.tokenTracker.style.display = "none";
    }
  }

  function setLoading(on) {
    el.loadingRow.classList.toggle("active", on);
    el.btnSend.disabled = on || !apiOnline;
    el.messageInput.disabled = on || !apiOnline;
    el.btnClip.disabled = on || !apiOnline;
  }

  function setPendingFile(file) {
    pendingFile = file;
    if (file) {
      el.fileHint.style.display = "inline";
      el.fileHint.textContent = "Anexo pronto: " + file.name;
      el.btnClearFile.style.display = "inline";
    } else {
      el.fileHint.style.display = "none";
      el.btnClearFile.style.display = "none";
    }
  }

  function toAttachmentMeta(file) {
    if (!file) return null;
    const name = file.name || "anexo";
    const lower = name.toLowerCase();
    const mime = file.type || "";
    const isImage = mime.startsWith("image/");
    const isPdf = mime === "application/pdf" || lower.endsWith(".pdf");
    const previewUrl = (isImage || isPdf) ? URL.createObjectURL(file) : null;
    return {
      id: null,
      name,
      kind: isImage ? "image" : isPdf ? "pdf" : "file",
      previewUrl,
    };
  }

  function closeSidebarMobile() {
    el.chatSidebar.classList.remove("open");
    el.overlay.classList.remove("show");
  }

  function openSettings() {
    el.settingsOverlay.classList.add("show");
  }

  function closeSettings() {
    el.settingsOverlay.classList.remove("show");
    saveGlobalSettings();
  }

  function openSessionSettings() {
    el.sessionOverlay.classList.add("show");
    updateSessionRangeLabels();
  }

  function closeSessionSettings() {
    el.sessionOverlay.classList.remove("show");
    saveSessionSettings();
  }

  function openCommandPalette() {
    el.commandOverlay.classList.add("show");
  }

  function closeCommandPalette() {
    el.commandOverlay.classList.remove("show");
  }

  function toggleFocusMode() {
    document.body.classList.toggle("focus-mode");
    window.localStorage.setItem("las_focus_mode", document.body.classList.contains("focus-mode") ? "1" : "0");
  }

  function exportConversationMarkdown() {
    const lines = ["# Conversa Local AI Stack", ""];
    messages.forEach((m) => {
      lines.push(`## ${m.role === "user" ? "Você" : "Assistente"}`);
      lines.push(m.content || "");
      lines.push("");
    });
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `chat-${sessionId || "novo"}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 800);
  }

  async function fetchHealth() {
    try {
      const r = await fetch(API_BASE + "/health");
      if (!r.ok) throw new Error("HTTP " + r.status);
      const h = await r.json();
      apiOnline = h.api === "online";
      const ok = h.ollama === "online";
      el.statusBadge.className = "status-badge " + (ok ? "status-online" : "status-offline");
      el.statusBadge.textContent = ok ? "● Modelo online" : "● Modelo offline";

      const models = Array.isArray(h.models) && h.models.length ? h.models : [DEFAULT_MODEL];
      const current = el.modelSelect.value;
      el.modelSelect.innerHTML = "";
      models.forEach((name) => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        if (isFirstLoad && name === DEFAULT_MODEL) {
          opt.selected = true;
          el.welcomeModel.textContent = name;
        }
        el.modelSelect.appendChild(opt);
      });
      if (!isFirstLoad && current && [...el.modelSelect.options].some((o) => o.value === current)) {
        el.modelSelect.value = current;
      }
      isFirstLoad = false;
      clearError();
    } catch {
      apiOnline = false;
      el.statusBadge.className = "status-badge status-offline";
      el.statusBadge.textContent = "● Backend offline";
      showError("Não foi possível contatar " + API_BASE);
    }
    el.btnSend.disabled = !apiOnline;
    el.messageInput.disabled = !apiOnline;
    el.btnClip.disabled = !apiOnline;
  }

  async function sendChat() {
    if (!apiOnline || sendBusy) return;

    const rawInput = el.messageInput.value;
    const text = rawInput.trim();
    const fileSnap = pendingFile;
    if (!text && !fileSnap) return;

    sendBusy = true;
    clearError();

    const attachment = toAttachmentMeta(fileSnap);
    const reuseAttachmentIds = Array.from(pendingReuseAttachmentIds);
    messages.push({
      role: "user",
      content: text || "Anexo enviado para análise.",
      attachments: attachment ? [attachment] : [],
    });

    el.messageInput.value = "";
    resizeTextarea();
    renderMessages();
    updateMetrics();

    const params = getEffectiveParams();

    const body = {
      message: text,
      session_id: sessionId,
      model: el.modelSelect.value,
      system_prompt: params.system_prompt,
      temperature: params.temperature,
      max_tokens: params.max_tokens,
      top_p: params.top_p,
      top_k: params.top_k,
      think: params.think,
      reuse_attachment_ids: reuseAttachmentIds,
    };

    setLoading(true);
    abortController = new AbortController();

    try {
      let result;
      if (fileSnap) {
        const fd = new FormData();
        fd.append("file", fileSnap, fileSnap.name);
        fd.append("message", text);
        fd.append("session_id", sessionId || "");
        fd.append("model", body.model);
        fd.append("system_prompt", el.systemPrompt.value.trim());
        fd.append("temperature", String(params.temperature));
        fd.append("max_tokens", String(params.max_tokens));
        fd.append("top_p", String(params.top_p));
        fd.append("top_k", String(params.top_k));
        fd.append("think", params.think ? "true" : "false");
        fd.append("reuse_attachment_ids", JSON.stringify(reuseAttachmentIds));

        result = await streamFromSse(
          fetch(API_BASE + "/chat/upload", { method: "POST", body: fd, signal: abortController.signal }),
          body.think
        );
        setPendingFile(null);
        el.fileInput.value = "";
      } else {
        result = await streamFromSse(
          fetch(API_BASE + "/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal: abortController.signal,
          }),
          params.think
        );
      }

      messages.push({ role: "assistant", content: result.reply || "", metrics: result.metrics });
      pendingReuseAttachmentIds.clear();
    } catch (e) {
      if (e.name !== "AbortError") {
        messages.pop();
        el.messageInput.value = rawInput;
        resizeTextarea();
        showError(String(e.message || e));
      }
    } finally {
      sendBusy = false;
      setLoading(false);
      abortController = null;
      renderMessages();
      updateMetrics();
      fetchSessions();
    }
  }

  function resizeTextarea() {
    el.messageInput.style.height = "auto";
    el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 180) + "px";
  }

  async function clearConversation() {
    messages = [];
    sessionId = null;
    totalTokens = 0;
    pendingReuseAttachmentIds.clear();
    setPendingFile(null);
    el.fileInput.value = "";
    clearError();
    renderMessages();
    updateMetrics();
    fetchSessions();
  }

  async function fetchSessions() {
    try {
      const r = await fetch(API_BASE + "/sessions");
      const d = await r.json();
      allSessions = d.sessions || [];
      renderHistoryList();
    } catch (e) {
      console.error("Erro ao carregar histórico:", e);
    }
  }

  function renderHistoryList() {
    const q = (el.historySearch.value || "").trim().toLowerCase();
    const history = q
      ? allSessions.filter((s) => ((s.title || "") + " " + (s.user || "")).toLowerCase().includes(q))
      : allSessions;

    if (!history.length) {
      el.historyList.innerHTML = '<p class="empty-history">Nenhum chat salvo.</p>';
      return;
    }
    el.historyList.innerHTML = "";

    history.forEach((s) => {
      const item = document.createElement("div");
      item.className = "history-item" + (s.id === sessionId ? " active" : "");
      const date = new Date(s.created_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
      item.innerHTML = `
        <div class="history-item-row">
          <div class="history-item-info">
            <div class="title">${s.title || "Sem título"}</div>
            <div class="meta"><span>${s.user || ""}</span><span>${date}</span></div>
          </div>
          <button class="btn-delete-session" title="Apagar conversa">✕</button>
        </div>
      `;
      item.querySelector(".history-item-info").addEventListener("click", () => loadSession(s.id));
      item.querySelector(".btn-delete-session").addEventListener("click", (e) => {
        e.stopPropagation();
        deleteSession(s.id);
      });
      el.historyList.appendChild(item);
    });
  }

  async function loadSession(sid) {
    try {
      setLoading(true);
      const r = await fetch(API_BASE + "/session/" + sid);
      if (!r.ok) throw new Error("Erro ao carregar sessão");
      const d = await r.json();
      sessionId = d.session_id;
      messages = d.messages;
      totalTokens = 0;
      
      // Aplica configurações da sessão nos campos de override
      if (d.settings) {
        el.sessionPrompt.value = d.settings.system_prompt || "";
        el.sTemperature.value = d.settings.temperature ?? el.temperature.value;
        el.sTopP.value = d.settings.top_p ?? el.topP.value;
        el.sTopK.value = d.settings.top_k ?? el.topK.value;
        el.sMaxTokens.value = d.settings.max_tokens ?? el.maxTokens.value;
        el.sThink.checked = !!d.settings.think_enabled;
      } else {
        // Reset se não tiver
        el.sessionPrompt.value = "";
        el.sTemperature.value = el.temperature.value;
        el.sTopP.value = el.topP.value;
        el.sTopK.value = el.topK.value;
        el.sMaxTokens.value = el.maxTokens.value;
        el.sThink.checked = el.think.checked;
      }
      updateSessionRangeLabels();

      pendingReuseAttachmentIds.clear();
      renderMessages();
      updateMetrics();
      fetchSessions();
      closeSidebarMobile();
    } catch (e) {
      showError("Falha ao carregar conversa: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function deleteSession(sid) {
    try {
      await fetch(API_BASE + "/session/" + encodeURIComponent(sid), { method: "DELETE" });
      if (sid === sessionId) {
        messages = [];
        sessionId = null;
        totalTokens = 0;
        renderMessages();
        updateMetrics();
      }
      fetchSessions();
    } catch (e) {
      showError("Erro ao apagar conversa: " + e.message);
    }
  }

  function runQuickAction(action) {
    if (action === "new-chat") clearConversation();
    if (action === "toggle-focus") toggleFocusMode();
    if (action === "open-settings") openSettings();
    if (action === "export-markdown") exportConversationMarkdown();
    closeCommandPalette();
  }

  // Init
  el.welcomeModel.textContent = DEFAULT_MODEL;
  loadGlobalSettings();

  if (window.localStorage.getItem("las_focus_mode") === "1") {
    document.body.classList.add("focus-mode");
  }

  ["temperature", "top-p", "top-k", "max-tokens"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      updateRangeLabels();
      saveGlobalSettings();
    });
  });
  el.systemPrompt.addEventListener("change", saveGlobalSettings);
  el.think.addEventListener("change", saveGlobalSettings);

  ["s-temperature", "s-top-p", "s-top-k", "s-max-tokens"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      updateSessionRangeLabels();
      saveSessionSettings();
    });
  });
  el.sessionPrompt.addEventListener("change", saveSessionSettings);
  el.sThink.addEventListener("change", saveSessionSettings);

  el.sessionChip.addEventListener("click", openSessionSettings);
  el.btnCloseSession.addEventListener("click", closeSessionSettings);
  el.btnCloseSettings.addEventListener("click", closeSettings);

  el.btnClip.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", () => {
    const f = el.fileInput.files && el.fileInput.files[0];
    setPendingFile(f || null);
  });
  el.btnClearFile.addEventListener("click", () => {
    el.fileInput.value = "";
    setPendingFile(null);
  });
  el.btnStop.addEventListener("click", () => abortController && abortController.abort());

  el.btnSend.addEventListener("click", sendChat);
  el.messageInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendChat();
    }
  });
  el.messageInput.addEventListener("input", resizeTextarea);

  el.btnNewChat.addEventListener("click", clearConversation);
  el.btnClear.addEventListener("click", clearConversation);
  el.historySearch.addEventListener("input", renderHistoryList);

  el.btnSettings.addEventListener("click", openSettings);
  el.btnCloseSettings.addEventListener("click", closeSettings);
  el.settingsOverlay.addEventListener("click", (e) => {
    if (e.target === el.settingsOverlay) closeSettings();
  });

  el.sessionOverlay.addEventListener("click", (e) => {
    if (e.target === el.sessionOverlay) closeSessionSettings();
  });

  el.btnFocus.addEventListener("click", toggleFocusMode);
  el.btnMenu.addEventListener("click", () => {
    el.chatSidebar.classList.toggle("open");
    el.overlay.classList.toggle("show");
  });
  el.overlay.addEventListener("click", closeSidebarMobile);

  el.commandOverlay.addEventListener("click", (e) => {
    if (e.target === el.commandOverlay) closeCommandPalette();
  });
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => runQuickAction(btn.getAttribute("data-action")));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeSettings();
      closeCommandPalette();
      closeSidebarMobile();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      openCommandPalette();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === ",") {
      e.preventDefault();
      openSettings();
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "f") {
      e.preventDefault();
      toggleFocusMode();
    }
  });

  fetchHealth();
  fetchSessions();
  setInterval(fetchHealth, 15000);
  setInterval(fetchSessions, 30000);
})();
