/**
 * Local AI Stack — front HTML5
 * API: mesmo FastAPI do Streamlit (CORS * no backend).
 */
(function () {
  function fmtDetail(d) {
    if (d == null) return "";
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => (x.msg || x) + "").join("; ");
    return String(d);
  }

  const DEFAULT_MODEL = "gemma4:e2b";
  const DEFAULT_SYSTEM = `Você é um assistente especializado em Ciência de Dados e análise financeira. Responda de forma clara e técnica.`;

  /** Porta do FastAPI (uvicorn); sobrescreva com localStorage las_api_base se precisar. */
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
    sidebar: document.getElementById("sidebar"),
    overlay: document.getElementById("overlay"),
    btnMenu: document.getElementById("btn-menu"),
    statusBadge: document.getElementById("status-badge"),
    modelSelect: document.getElementById("model-select"),
    temperature: document.getElementById("temperature"),
    topP: document.getElementById("top-p"),
    topK: document.getElementById("top-k"),
    maxTokens: document.getElementById("max-tokens"),
    think: document.getElementById("think"),
    systemPrompt: document.getElementById("system-prompt"),
    metricMsgs: document.getElementById("metric-msgs"),
    metricTokens: document.getElementById("metric-tokens"),
    metricTime: document.getElementById("metric-time"),
    metricTps: document.getElementById("metric-tps"),
    metricTtft: document.getElementById("metric-ttft"),
    btnClear: document.getElementById("btn-clear"),
    sessionPreview: document.getElementById("session-preview"),
    sidLabel: document.getElementById("sid-label"),
    alertError: document.getElementById("alert-error"),
    loadingRow: document.getElementById("loading-row"),
    messages: document.getElementById("messages"),
    welcome: document.getElementById("welcome"),
    welcomeModel: document.getElementById("welcome-model"),
    fileInput: document.getElementById("file-input"),
    btnClip: document.getElementById("btn-clip"),
    fileHint: document.getElementById("file-hint"),
    btnClearFile: document.getElementById("btn-clear-file"),
    messageInput: document.getElementById("message-input"),
    btnSend: document.getElementById("btn-send"),
    btnStop: document.getElementById("btn-stop"),
    historyDrawer: document.getElementById("history-drawer"),
    historyList: document.getElementById("history-list"),
  };

  /** @type {{ role: string, content: string }[]} */
  let messages = [];
  let sessionId = null;
  let totalTokens = 0;
  /** @type {File | null} */
  let pendingFile = null;
  let apiOnline = false;
  /** Evita dois envios em sequência (Enter + clique ou duplo Enter). */
  let sendBusy = false;
  let isFirstLoad = true;
  let abortController = null;

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

  function scrollMessagesToBottom() {
    el.messages.scrollTop = el.messages.scrollHeight;
  }

  /** Markdown → HTML com sanitização (CDN: marked + DOMPurify). */
  function markdownToSafeHtml(md) {
    if (md == null || md === "") return "";
    if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
      const src = String(md);
      const raw =
        typeof marked.parse === "function"
          ? marked.parse(src, { breaks: true, gfm: true })
          : marked(src);
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

  function setBubbleContent(bubble, text) {
    bubble.classList.add("bubble-md");
    bubble.innerHTML = markdownToSafeHtml(text);
    applyLinkPolicy(bubble);
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
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      setBubbleContent(bubble, m.content);
      if (m.role === "user") {
        row.appendChild(bubble);
        row.appendChild(av);
      } else {
        row.appendChild(av);
        const col = document.createElement("div");
        col.className = "assistant-col";
        col.appendChild(bubble);

        if (m.metrics) {
          const footer = document.createElement("div");
          footer.className = "msg-footer";

          const { duration, tps, tokens_used, ttft } = m.metrics;

          footer.innerHTML = `
            <div class="metric-pill" title="Velocidade de geração">
              <span class="icon">⚡</span> ${tps} tok/s
            </div>
            <div class="metric-pill" title="Total de tokens">
              <span class="icon">📝</span> ${tokens_used} tokens
            </div>
            <div class="metric-pill" title="Tempo total">
              <span class="icon">⏱️</span> ${duration}s
            </div>
            ${ttft ? `<div class="metric-pill" title="Tempo de raciocínio"><span class="icon">🧠</span> ${ttft}s</div>` : ''}
          `;
          col.appendChild(footer);
        }
        row.appendChild(col);
      }
      el.messages.appendChild(row);
    }
    scrollMessagesToBottom();
  }

  /**
   * Chat sem anexo: POST /chat/stream (SSE) — repassa tokens de raciocínio (thinking) e resposta.
   */
  async function streamChat(body, signal) {
    const r = await fetch(API_BASE + "/chat", { //chat/stream
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
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

    let thinkPanel = null;
    let thinkText = null;
    if (body.think) {
      thinkPanel = document.createElement("div");
      thinkPanel.className = "think-panel";
      thinkPanel.style.display = "none";
      const thinkLabel = document.createElement("div");
      thinkLabel.className = "think-label";
      thinkLabel.textContent = "Raciocínio";
      thinkText = document.createElement("div");
      thinkText.className = "think-body";
      thinkPanel.appendChild(thinkLabel);
      thinkPanel.appendChild(thinkText);
      col.appendChild(thinkPanel);
      thinkPanel.addEventListener("click", () => {
        if (thinkPanel.classList.contains("think-collapsed")) {
          thinkPanel.classList.remove("think-collapsed");
        }
      });
    }

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = "";
    col.appendChild(bubble);
    row.appendChild(av);
    row.appendChild(col);
    el.messages.appendChild(row);
    scrollMessagesToBottom();

    let fullThink = "";
    let fullReply = "";
    let sawContent = false;
    let lastRunMetrics = null;
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    const showThinkIfNeeded = () => {
      if (!thinkPanel || !thinkText) return;
      thinkPanel.style.display = "block";
    };

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
          sessionId = data.session_id;
        } else if (data.type === "think" && data.token) {
          if (!thinkPanel) {
            thinkPanel = document.createElement("div");
            thinkPanel.className = "think-panel";
            const thinkLabel = document.createElement("div");
            thinkLabel.className = "think-label";
            thinkLabel.textContent = "Raciocínio";
            thinkText = document.createElement("div");
            thinkText.className = "think-body";
            thinkPanel.appendChild(thinkLabel);
            thinkPanel.appendChild(thinkText);
            thinkPanel.addEventListener("click", () => {
              if (thinkPanel.classList.contains("think-collapsed")) {
                thinkPanel.classList.remove("think-collapsed");
              }
            });
            col.insertBefore(thinkPanel, bubble);
          }
          fullThink += data.token;
          thinkText.textContent = fullThink;
          showThinkIfNeeded();
          scrollMessagesToBottom();
        } else if (data.type === "token" && data.token) {
          if (!sawContent && thinkPanel) {
            sawContent = true;
            thinkPanel.classList.add("think-collapsed");
          }
          fullReply += data.token;
          bubble.textContent = fullReply;
          scrollMessagesToBottom();
        } else if (data.type === "done") {
          if (data.session_id) sessionId = data.session_id;
          if (typeof data.tokens_used === "number") totalTokens += data.tokens_used;
          lastRunMetrics = data;
          updateMetrics(data);
        } else if (data.type === "error") {
          throw new Error(data.detail || "Erro no stream");
        }
      }
    }

    row.classList.remove("msg-streaming");
    return { reply: fullReply, metrics: lastRunMetrics };
  }

  /**
   * Lê um ReadableStream de SSE e retorna o texto acumulado.
   * Atualiza sessionId, totalTokens e metrics como efeito colateral.
   */
  async function parseSSEStream(readableStream) {
    if (!readableStream) throw new Error("Stream indisponível.");

    let fullReply = "";
    let lastRunMetrics = null;
    const reader = readableStream.getReader();
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
          sessionId = data.session_id;
        } else if (data.type === "token" && data.token) {
          fullReply += data.token;
        } else if (data.type === "done") {
          if (data.session_id) sessionId = data.session_id;
          if (typeof data.tokens_used === "number") totalTokens += data.tokens_used;
          lastRunMetrics = data;
          updateMetrics(data);
        } else if (data.type === "error") {
          throw new Error(data.detail || "Erro no stream");
        }
      }
    }
    return { reply: fullReply, metrics: lastRunMetrics };
  }

  /**
   * Chat com anexo: POST /chat/upload (SSE).
   * Usa parseSSEStream para leitura + renderiza tokens em tempo real.
   */
  async function streamUpload(formData, signal) {
    const r = await fetch(API_BASE + "/chat/upload", {
      method: "POST",
      body: formData,
      signal,
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(fmtDetail(err.detail) || r.statusText || String(r.status));
    }

    // Cria UI de streaming (mesma estrutura do streamChat)
    const row = document.createElement("div");
    row.className = "msg-assistant msg-streaming";
    const av = document.createElement("div");
    av.className = "avatar avatar-ai";
    av.textContent = "AI";
    const col = document.createElement("div");
    col.className = "assistant-col";

    let thinkPanel = null;
    let thinkText = null;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = "";
    col.appendChild(bubble);
    row.appendChild(av);
    row.appendChild(col);
    el.messages.appendChild(row);
    scrollMessagesToBottom();

    let fullReply = "";
    let sawContent = false;
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
          sessionId = data.session_id;
        } else if (data.type === "think" && data.token) {
          if (!thinkPanel) {
            thinkPanel = document.createElement("div");
            thinkPanel.className = "think-panel";
            const thinkLabel = document.createElement("div");
            thinkLabel.className = "think-label";
            thinkLabel.textContent = "Raciocínio";
            thinkText = document.createElement("div");
            thinkText.className = "think-body";
            thinkPanel.appendChild(thinkLabel);
            thinkPanel.appendChild(thinkText);
            thinkPanel.addEventListener("click", () => {
              if (thinkPanel.classList.contains("think-collapsed")) {
                thinkPanel.classList.remove("think-collapsed");
              }
            });
            col.insertBefore(thinkPanel, bubble);
            thinkPanel.style.display = "block";
          }
          thinkText.textContent += data.token;
          scrollMessagesToBottom();
        } else if (data.type === "token" && data.token) {
          if (!sawContent && thinkPanel) {
            sawContent = true;
            thinkPanel.classList.add("think-collapsed");
          }
          fullReply += data.token;
          bubble.textContent = fullReply;
          scrollMessagesToBottom();
        } else if (data.type === "done") {
          if (data.session_id) sessionId = data.session_id;
          if (typeof data.tokens_used === "number") totalTokens += data.tokens_used;
          lastRunMetrics = data;
          updateMetrics(data);
        } else if (data.type === "error") {
          throw new Error(data.detail || "Erro no stream");
        }
      }
    }

    row.classList.remove("msg-streaming");
    return { reply: fullReply, metrics: lastRunMetrics };
  }

  function updateMetrics(lastMetrics = null) {
    el.metricMsgs.textContent = String(messages.length);
    el.metricTokens.textContent = totalTokens.toLocaleString("pt-BR");

    if (lastMetrics) {
      if (lastMetrics.duration !== undefined) el.metricTime.textContent = lastMetrics.duration + "s";
      if (lastMetrics.tps !== undefined) el.metricTps.textContent = lastMetrics.tps;
      if (lastMetrics.ttft !== undefined) el.metricTtft.textContent = lastMetrics.ttft + "s";
    }

    if (sessionId) {
      el.sidLabel.style.display = "block";
      el.sessionPreview.style.display = "block";
      el.sessionPreview.textContent = sessionId.slice(0, 22) + "…";
    } else {
      el.sidLabel.style.display = "none";
      el.sessionPreview.style.display = "none";
    }
  }

  function setLoading(on) {
    el.loadingRow.classList.toggle("active", on);
    el.btnSend.classList.toggle("generating", on); // Transforma visualmente em botão Stop

    // Habilita o botão para o usuário poder clicar no Stop se estiver gerando
    if (on) {
      el.btnSend.disabled = false;
    } else {
      el.btnSend.disabled = !apiOnline;
    }

    el.messageInput.disabled = on || !apiOnline;
    el.btnClip.disabled = on || !apiOnline;
  }

  async function fetchSessions() {
    try {
      const r = await fetch(API_BASE + "/sessions");
      const d = await r.json();
      renderHistoryList(d.sessions || []);
    } catch (e) {
      console.error("Erro ao carregar histórico:", e);
    }
  }

  function renderHistoryList(history) {
    if (!history.length) {
      el.historyList.innerHTML = '<p class="empty-history">Nenhum chat salvo.</p>';
      return;
    }
    el.historyList.innerHTML = "";
    history.forEach(s => {
      const item = document.createElement("div");
      item.className = "history-item";
      const date = new Date(s.created_at).toLocaleDateString("pt-BR", { day: '2-digit', month: '2-digit' });
      item.innerHTML = `
        <div class="title">${s.title}</div>
        <div class="meta">
          <span>${s.user}</span>
          <span>${date}</span>
        </div>
      `;
      item.onclick = () => loadSession(s.id);
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
      renderMessages();
      updateMetrics();
      // Fecha a gaveta no mobile se necessário
      if (window.innerWidth < 860) el.sidebar.classList.remove("open");
    } catch (e) {
      showError("Falha ao carregar conversa: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  function setPendingFile(file) {
    pendingFile = file;
    if (file) {
      el.fileHint.style.display = "block";
      el.fileHint.textContent = "✓ " + (file.name.length > 18 ? file.name.slice(0, 15) + "…" : file.name);
      el.btnClearFile.style.display = "block";
    } else {
      el.fileHint.style.display = "none";
      el.btnClearFile.style.display = "none";
    }
  }

  async function fetchHealth() {
    try {
      const r = await fetch(API_BASE + "/health", { method: "GET" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const h = await r.json();
      apiOnline = h.api === "online";
      const llmOk = h.llm === "online";
      el.statusBadge.className =
        "status-badge " + (llmOk ? "status-online" : "status-offline");
      el.statusBadge.textContent = llmOk ? "● LLM online" : "● LLM offline";

      if (!apiOnline) {
        showError("Backend offline. Suba o FastAPI (ex.: uvicorn na porta configurada).");
      } else {
        clearError();
      }

      const models = Array.isArray(h.models) ? h.models : [];
      const current = el.modelSelect.value;
      el.modelSelect.innerHTML = "";

      if (models.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "⚠️ Sem modelos locais";
        opt.disabled = true;
        opt.selected = true;
        el.modelSelect.appendChild(opt);
        el.welcomeModel.textContent = "Nenhum modelo carregado";
        showError("Nenhum modelo encontrado no Ollama. Use o script de download.");
      } else {
        for (const name of models) {
          const opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          if (isFirstLoad && name === DEFAULT_MODEL) {
            opt.selected = true;
            el.welcomeModel.textContent = name;
          }
          el.modelSelect.appendChild(opt);
        }
        if (!isFirstLoad && current && [...el.modelSelect.options].some((o) => o.value === current)) {
          el.modelSelect.value = current;
        }
      }

      isFirstLoad = false;
      fetchSessions();
    } catch (e) {
      apiOnline = false;
      el.statusBadge.className = "status-badge status-offline";
      el.statusBadge.textContent = "● Backend offline";
      showError("Não foi possível contatar " + API_BASE + " (CORS ou servidor parado).");
    }
    el.btnSend.disabled = !apiOnline || (Array.isArray(h?.models) && h.models.length === 0);
    el.messageInput.disabled = !apiOnline || (Array.isArray(h?.models) && h.models.length === 0);
    el.btnClip.disabled = !apiOnline || (Array.isArray(h?.models) && h.models.length === 0);
  }

  async function sendChat() {
    if (!apiOnline || sendBusy) return;
    const rawInput = el.messageInput.value;
    const text = rawInput.trim();
    const fileSnap = pendingFile;
    if (!text && !fileSnap) return;

    sendBusy = true;
    clearError();
    let userDisplay = text;
    if (fileSnap) {
      userDisplay = text ? text + "\n\n📎 `" + fileSnap.name + "`" : "📎 `" + fileSnap.name + "`";
    }
    messages.push({ role: "user", content: userDisplay });
    el.messageInput.value = "";
    resizeTextarea();
    renderMessages();
    updateMetrics();

    const body = {
      message: text,
      session_id: sessionId,
      model: el.modelSelect.value,
      system_prompt: el.systemPrompt.value.trim() || null,
      temperature: parseFloat(el.temperature.value),
      max_tokens: parseInt(el.maxTokens.value, 10),
      top_p: parseFloat(el.topP.value),
      top_k: parseInt(el.topK.value, 10),
      think: el.think.checked,
    };

    setLoading(true);
    abortController = new AbortController();

    try {
      let reply;
      let result;
      if (fileSnap) {
        // Upload com streaming: monta FormData e lê SSE do /chat/upload
        const fd = new FormData();
        fd.append("file", fileSnap, fileSnap.name);
        fd.append("message", text);
        fd.append("session_id", sessionId || "");
        fd.append("model", body.model);
        fd.append("system_prompt", el.systemPrompt.value.trim());
        fd.append("temperature", String(body.temperature));
        fd.append("max_tokens", String(body.max_tokens));
        fd.append("top_p", String(body.top_p));
        fd.append("top_k", String(body.top_k));
        fd.append("think", body.think ? "true" : "false");
        result = await streamUpload(fd, abortController.signal);
        setPendingFile(null);
        el.fileInput.value = "";
      } else {
        result = await streamChat(body, abortController.signal);
      }
      messages.push({
        role: "assistant",
        content: result.reply || "",
        metrics: result.metrics
      });
    } catch (e) {
      if (e.name === "AbortError") {
        console.log("Geração interrompida pelo usuário.");
      } else {
        messages.pop();
        el.messageInput.value = rawInput;
        resizeTextarea();
        renderMessages();
        updateMetrics();
        showError(String(e.message || e));
      }
    } finally {
      sendBusy = false;
      setLoading(false);
      abortController = null;
      renderMessages();
      updateMetrics();
      fetchSessions(); // Atualiza a gaveta com o novo chat/título
    }
  }

  function resizeTextarea() {
    el.messageInput.style.height = "auto";
    el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 160) + "px";
  }

  async function clearConversation() {
    // Apenas reseta o estado local para iniciar um chat novo. 
    // O histórico antigo permanece salvo no SQLite do pendrive.
    messages = [];
    sessionId = null;
    totalTokens = 0;
    setPendingFile(null);
    if (el.fileInput) el.fileInput.value = "";
    clearError();
    renderMessages();
    updateMetrics();
  }

  /* Init */
  el.welcomeModel.textContent = DEFAULT_MODEL;
  el.systemPrompt.value = DEFAULT_SYSTEM;
  updateRangeLabels();

  ["temperature", "top-p", "top-k", "max-tokens"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateRangeLabels);
  });

  el.btnClip.addEventListener("click", () => el.fileInput.click());
  el.btnStop.addEventListener("click", () => {
    if (abortController) {
      abortController.abort();
    }
  });
  el.fileInput.addEventListener("change", () => {
    const f = el.fileInput.files && el.fileInput.files[0];
    setPendingFile(f || null);
  });
  el.btnClearFile.addEventListener("click", () => {
    el.fileInput.value = "";
    setPendingFile(null);
  });

  el.btnSend.addEventListener("click", () => {
    // Se estiver gerando, o clique no botão funciona como Stop
    if (el.btnSend.classList.contains("generating")) {
      if (abortController) abortController.abort();
    } else {
      sendChat();
    }
  });
  el.messageInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendChat();
    }
  });
  el.messageInput.addEventListener("input", resizeTextarea);

  el.btnClear.addEventListener("click", clearConversation);

  el.btnMenu.addEventListener("click", () => {
    el.sidebar.classList.toggle("open");
    el.overlay.classList.toggle("show");
  });
  el.overlay.addEventListener("click", () => {
    el.sidebar.classList.remove("open");
    el.overlay.classList.remove("show");
  });

  fetchHealth();
  setInterval(fetchHealth, 15000);
})();
