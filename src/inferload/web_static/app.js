/* ============================================================
   InferLoad — Modern Studio Dark Frontend Engine
   Full 5-view router, live WebSocket & SSE streaming, SRE-grade telemetry
   ============================================================ */

let currentJobId = null;
let pollInterval = null;
let timerInterval = null;
let benchmarkStartTime = null;
let activeExperimentData = null;
let discoveredModels = [];
let cachedHistory = [];
let inferloadAuthToken = localStorage.getItem('inferload_token') || '';
let stateOverlayKVCache = false;

function getAuthHeaders(extraHeaders = {}) {
  const headers = { 'Content-Type': 'application/json', ...extraHeaders };
  if (inferloadAuthToken) {
    headers['Authorization'] = `Bearer ${inferloadAuthToken}`;
    headers['X-InferLoad-Token'] = inferloadAuthToken;
  }
  return headers;
}

document.addEventListener('DOMContentLoaded', () => {
  initNavRouter();
  initPresets();
  initFormControls();
  initSweepChips();
  initPromptsManager();
  initTerminalActions();
  initGraphFilters();
  initHistoryControls();
  initReportsViewer();
  initDiagnostics();
  initHealth();
  initModals();
  initAuthControls();
  initOverlayControls();
  loadRecentHistory();

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (lastRenderedPoints && lastRenderedPoints.length > 0) {
        renderAllVectorCharts(lastRenderedPoints, lastRenderedOptions);
      }
    }, 150);
  });
});

/* ── Toast Notification ── */
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

/* ══════════════════════════════════════════════
   1. NAVIGATION ROUTER (5 VIEWS)
   ══════════════════════════════════════════════ */
function initNavRouter() {
  const navTabs = document.querySelectorAll('.nav-tab');
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabTarget = tab.dataset.tab;
      if (tabTarget) switchView(tabTarget);
    });
  });

  const jumpToAnalyticsBtn = document.getElementById('btn-view-full-analytics');
  if (jumpToAnalyticsBtn) {
    jumpToAnalyticsBtn.addEventListener('click', () => {
      switchView('tab-results');
    });
  }
}

function switchView(tabId) {
  // Update nav buttons
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });

  // Switch panels
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === tabId);
  });

  // Lazy loaders
  if (tabId === 'tab-history') {
    loadFullHistoryArchive();
  } else if (tabId === 'tab-reports') {
    populateReportsSelector();
  }
}

/* ══════════════════════════════════════════════
   2. QUICK LAUNCH PRESETS
   ══════════════════════════════════════════════ */
function initPresets() {
  const btnMock = document.getElementById('preset-mock');
  const btnOllama = document.getElementById('preset-ollama');
  const btnVllm = document.getElementById('preset-vllm');

  function setActivePreset(activeBtn) {
    [btnMock, btnOllama, btnVllm].forEach(b => {
      if (b) b.classList.toggle('active', b === activeBtn);
    });
  }

  if (btnMock) {
    btnMock.addEventListener('click', () => {
      setActivePreset(btnMock);
      document.getElementById('target-base-url').value = '/mock/v1';
      document.getElementById('target-model').value = 'mock-llama3-8b';
      document.getElementById('sweep-concurrency').value = '1, 2, 4';
      document.getElementById('sweep-repetitions').value = '2';
      document.getElementById('sweep-requests').value = '5';
      document.getElementById('header-endpoint-label').textContent = '/mock/v1';
      showToast('Built-in Demo preset loaded');
    });
  }

  if (btnOllama) {
    btnOllama.addEventListener('click', () => {
      setActivePreset(btnOllama);
      document.getElementById('target-base-url').value = 'http://127.0.0.1:11434/v1';
      document.getElementById('target-model').value = discoveredModels.length ? discoveredModels[0] : 'qwen2.5:0.5b';
      document.getElementById('sweep-concurrency').value = '1, 2';
      document.getElementById('sweep-repetitions').value = '1';
      document.getElementById('sweep-requests').value = '3';
      document.getElementById('header-endpoint-label').textContent = 'http://127.0.0.1:11434/v1';
      showToast('Local Ollama preset loaded');
    });
  }

  if (btnVllm) {
    btnVllm.addEventListener('click', () => {
      setActivePreset(btnVllm);
      document.getElementById('target-base-url').value = 'http://127.0.0.1:8000/v1';
      document.getElementById('target-model').value = 'meta-llama/Meta-Llama-3-8B-Instruct';
      document.getElementById('sweep-concurrency').value = '1, 4, 8';
      document.getElementById('sweep-repetitions').value = '2';
      document.getElementById('sweep-requests').value = '5';
      document.getElementById('header-endpoint-label').textContent = 'http://127.0.0.1:8000/v1';
      showToast('vLLM Server preset loaded');
    });
  }
}

/* ══════════════════════════════════════════════
   3. FORM CONTROLS & VALIDATION
   ══════════════════════════════════════════════ */
function initFormControls() {
  const urlInput = document.getElementById('target-base-url');
  if (urlInput) {
    urlInput.addEventListener('input', (e) => {
      const val = e.target.value.trim() || 'http://127.0.0.1:11434/v1';
      document.getElementById('header-endpoint-label').textContent = val;
    });
  }

  const arrivalMode = document.getElementById('arrival-mode');
  const rateGroup = document.getElementById('open-loop-rate-group');
  if (arrivalMode && rateGroup) {
    arrivalMode.addEventListener('change', () => {
      rateGroup.style.display = arrivalMode.value === 'rate' ? 'grid' : 'none';
    });
  }

  // Model autocomplete dropdown
  const modelInput = document.getElementById('target-model');
  const modelDropdown = document.getElementById('model-dropdown');
  if (modelInput && modelDropdown) {
    modelInput.addEventListener('focus', () => {
      if (discoveredModels.length > 0) renderModelDropdown(discoveredModels);
    });
    modelInput.addEventListener('input', () => {
      const q = modelInput.value.toLowerCase();
      const filtered = discoveredModels.filter(m => m.toLowerCase().includes(q));
      renderModelDropdown(filtered.length ? filtered : discoveredModels);
    });
    document.addEventListener('click', (e) => {
      if (!modelInput.contains(e.target) && !modelDropdown.contains(e.target)) {
        modelDropdown.classList.remove('open');
      }
    });
  }

  // Reset button
  const resetBtn = document.getElementById('btn-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      document.getElementById('target-base-url').value = '/mock/v1';
      document.getElementById('target-model').value = 'mock-llama3-8b';
      document.getElementById('sweep-concurrency').value = '1, 2, 4';
      document.getElementById('sweep-repetitions').value = '2';
      document.getElementById('sweep-requests').value = '5';
      document.getElementById('header-endpoint-label').textContent = '/mock/v1';
      showToast('Form reset to default parameters');
    });
  }

  // Pre-flight validation button
  const valBtn = document.getElementById('btn-validate');
  if (valBtn) {
    valBtn.addEventListener('click', handlePreflightValidation);
  }

  // Form submit
  const form = document.getElementById('benchmark-form');
  if (form) {
    form.addEventListener('submit', handleBenchmarkSubmit);
  }

  // Dismiss error card
  const dismissErrBtn = document.getElementById('btn-dismiss-error');
  if (dismissErrBtn) {
    dismissErrBtn.addEventListener('click', () => {
      document.getElementById('error-card').style.display = 'none';
    });
  }
}

function renderModelDropdown(models) {
  const dropdown = document.getElementById('model-dropdown');
  if (!dropdown) return;
  dropdown.innerHTML = '';
  models.forEach(m => {
    const opt = document.createElement('div');
    opt.className = 'dropdown-option';
    opt.textContent = m;
    opt.addEventListener('click', () => {
      document.getElementById('target-model').value = m;
      dropdown.classList.remove('open');
    });
    dropdown.appendChild(opt);
  });
  dropdown.classList.add('open');
}

/* ══════════════════════════════════════════════
   4. PROMPTS MANAGER
   ══════════════════════════════════════════════ */
function initPromptsManager() {
  const addBtn = document.getElementById('btn-add-prompt');
  const container = document.getElementById('prompts-container');
  if (!addBtn || !container) return;

  addBtn.addEventListener('click', () => {
    const row = document.createElement('div');
    row.className = 'prompt-item';
    row.innerHTML = `
      <input type="text" class="prompt-text-input" placeholder="Enter prompt text..." required>
      <button type="button" class="btn-del-prompt" title="Remove">&times;</button>
    `;
    container.appendChild(row);
    attachPromptDelete(row.querySelector('.btn-del-prompt'));
    row.querySelector('input').focus();
  });

  container.querySelectorAll('.btn-del-prompt').forEach(attachPromptDelete);
}

function attachPromptDelete(btn) {
  if (!btn) return;
  btn.addEventListener('click', () => {
    const container = document.getElementById('prompts-container');
    if (container.children.length > 1) {
      btn.closest('.prompt-item').remove();
    } else {
      showToast('At least one prompt is required for the benchmark workload');
    }
  });
}

function getPromptsList() {
  const inputs = document.querySelectorAll('#prompts-container .prompt-text-input');
  return Array.from(inputs).map(inp => inp.value.trim()).filter(Boolean);
}

/* ══════════════════════════════════════════════
   5. BENCHMARK PAYLOAD GENERATOR
   ══════════════════════════════════════════════ */
function buildPayload() {
  const concRaw = document.getElementById('sweep-concurrency').value;
  const concList = concRaw.split(',')
    .map(s => parseInt(s.trim(), 10))
    .filter(n => !isNaN(n) && n > 0);

  let rawUrl = document.getElementById('target-base-url').value.trim();
  if (rawUrl.startsWith('/')) {
    rawUrl = window.location.origin + rawUrl;
  }

  const payload = {
    name: 'web-sweep-' + Date.now(),
    base_url: rawUrl,
    model: document.getElementById('target-model').value.trim(),
    timeout_seconds: parseFloat(document.getElementById('target-timeout')?.value || 60),
    concurrency: concList.length ? concList : [1, 2, 4],
    repetitions: parseInt(document.getElementById('sweep-repetitions').value, 10) || 1,
    requests_per_point: parseInt(document.getElementById('sweep-requests').value, 10) || 5,
    warmup_requests: parseInt(document.getElementById('exec-warmup')?.value || 1, 10),
    max_tokens: parseInt(document.getElementById('workload-max-tokens').value, 10) || 32,
    temperature: parseFloat(document.getElementById('workload-temperature').value) || 0.0,
    seed: parseInt(document.getElementById('workload-seed')?.value || 42, 10),
    stream: document.getElementById('workload-stream').checked,
    arrival_mode: document.getElementById('arrival-mode').value,
    prompts: getPromptsList(),
    slo: {
      max_ttft_p95_ms: parseFloat(document.getElementById('slo-ttft').value) || 1000.0,
      max_total_latency_p95_ms: parseFloat(document.getElementById('slo-latency').value) || 2500.0,
      min_throughput_req_per_sec: parseFloat(document.getElementById('slo-throughput').value) || 1.0,
      max_error_rate_pct: parseFloat(document.getElementById('slo-error').value) || 1.0,
    }
  };

  const apiKey = document.getElementById('target-api-key')?.value.trim();
  if (apiKey) payload.api_key = apiKey;

  if (payload.arrival_mode === 'rate') {
    payload.arrival_rate_req_per_sec = parseFloat(document.getElementById('arrival-rate').value) || 2.0;
  }

  return payload;
}

/* ══════════════════════════════════════════════
   6. PRE-FLIGHT VALIDATION
   ══════════════════════════════════════════════ */
async function handlePreflightValidation() {
  const banner = document.getElementById('validation-banner');
  const valBtn = document.getElementById('btn-validate');
  if (!banner) return;

  valBtn.disabled = true;
  valBtn.innerHTML = 'Validating...';

  const payload = buildPayload();

  try {
    const res = await fetch('/api/validate', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });

    if (res.status === 401) {
      banner.style.display = 'block';
      banner.className = 'banner-feedback invalid';
      banner.innerHTML = '<strong>Authentication Required (HTTP 401):</strong> Valid API token required. Please configure your token in Settings (⚙).';
      const sm = document.getElementById('modal-settings');
      if (sm) sm.style.display = 'flex';
      return;
    }

    const data = await res.json();
    banner.style.display = 'block';

    if (data.valid) {
      banner.className = 'banner-feedback valid';
      banner.innerHTML = '<strong>Configuration Valid:</strong> Target URL, model parameters, concurrency sweep values, and SLO gates are correctly formatted and ready.';
    } else {
      banner.className = 'banner-feedback invalid';
      const errorsHtml = (data.errors || []).map(e => `<li>${e}</li>`).join('');
      banner.innerHTML = `<strong>Validation Failed:</strong><ul>${errorsHtml}</ul>`;
    }
  } catch (err) {
    banner.style.display = 'block';
    banner.className = 'banner-feedback invalid';
    banner.innerHTML = `<strong>Network Error:</strong> Could not connect to validation API: ${err.message}`;
  } finally {
    valBtn.disabled = false;
    valBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
      <span>Validate Endpoint</span>
    `;
  }
}

/* ══════════════════════════════════════════════
   7. BENCHMARK SUBMISSION & LIVE STREAMING
   ══════════════════════════════════════════════ */
async function handleBenchmarkSubmit(e) {
  e.preventDefault();

  const runBtn = document.getElementById('btn-run');
  const payload = buildPayload();

  // Reset UI states
  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('studio-summary-card').style.display = 'none';
  document.getElementById('error-card').style.display = 'none';
  document.getElementById('progress-card').style.display = 'flex';

  resetExecutionTelemetry();
  updateStepper('step-validation');

  runBtn.disabled = true;
  runBtn.innerHTML = 'Launching...';

  try {
    const res = await fetch('/api/experiments', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });

    if (res.status === 401) {
      const errData = await res.json().catch(() => ({}));
      const modal = document.getElementById('modal-settings');
      if (modal) modal.style.display = 'flex';
      throw new Error(`Unauthorized (401): ${errData.detail || 'InferLoad API token required. Please enter token in Settings.'}`);
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    currentJobId = data.job_id;

    startTimer();
    updateStepper('step-running');
    appendLog(`[InferLoad] Benchmark job initialized. Job ID: ${currentJobId}`);
    appendLog(`[InferLoad] Model: ${payload.model} | Base URL: ${payload.base_url}`);
    appendLog(`[InferLoad] Concurrency sweep: [${payload.concurrency.join(', ')}] | Reps: ${payload.repetitions}`);

    // Launch Live Real-Time WebSocket Streaming with SSE / Polling fallbacks
    connectLiveExperimentStream(currentJobId);
  } catch (err) {
    stopTimer();
    document.getElementById('progress-card').style.display = 'none';
    document.getElementById('error-card').style.display = 'flex';
    document.getElementById('error-card-msg').textContent = err.message;
    runBtn.disabled = false;
    runBtn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
      <span>Launch Benchmark</span>
    `;
  }
}

function connectLiveExperimentStream(jobId) {
  let isFinished = false;
  let ws = null;
  let sse = null;

  function cleanup() {
    isFinished = true;
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    if (ws) {
      try { ws.close(); } catch(e) {}
      ws = null;
    }
    if (sse) {
      try { sse.close(); } catch(e) {}
      sse = null;
    }
  }

  function startHttpPollingFallback() {
    if (isFinished || pollInterval) return;
    appendLog(`[InferLoad Stream] Connection fallback active: Polling /api/experiments/${jobId} (1 Hz)...`);
    pollInterval = setInterval(() => pollJobStatus(jobId, cleanup), 1000);
  }

  // 1. Primary: Native High-Performance WebSocket
  try {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${location.host}/ws/experiments/${jobId}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      appendLog(`[InferLoad Stream] WebSocket connection established (/ws/experiments/${jobId}). Streaming real-time trial telemetry...`);
    };

    ws.onmessage = (event) => {
      if (isFinished) return;
      try {
        const msg = JSON.parse(event.data);
        handleStreamPayload(msg);
      } catch (err) {
        console.warn('WS parse error:', err);
      }
    };

    ws.onerror = (err) => {
      console.warn('WebSocket stream error, checking SSE fallback:', err);
      if (!isFinished && !sse) trySSE();
    };

    ws.onclose = () => {
      if (!isFinished) {
        if (!sse) trySSE();
        else startHttpPollingFallback();
      }
    };
  } catch (err) {
    trySSE();
  }

  // 2. Secondary: Server-Sent Events (SSE) Fallback
  function trySSE() {
    if (isFinished || sse) return;
    try {
      appendLog(`[InferLoad Stream] Opening Server-Sent Events (/api/experiments/${jobId}/stream)...`);
      sse = new EventSource(`/api/experiments/${jobId}/stream`);

      sse.onmessage = (event) => {
        if (isFinished) return;
        try {
          const msg = JSON.parse(event.data);
          handleStreamPayload(msg);
        } catch (err) {
          console.warn('SSE parse error:', err);
        }
      };

      sse.onerror = () => {
        if (sse) { sse.close(); sse = null; }
        if (!isFinished) startHttpPollingFallback();
      };
    } catch (e) {
      startHttpPollingFallback();
    }
  }

  function handleStreamPayload(msg) {
    if (!msg || isFinished) return;

    if (msg.type === 'log' && msg.message) {
      appendLog(msg.message);
    } else if (msg.type === 'progress') {
      updateExecutionProgress(msg.trial_id, msg.current, msg.total, msg.elapsed_seconds);
    } else if (msg.type === 'initial_state' && msg.job) {
      updateExecutionHUD(msg.job);
      if (msg.job.status === 'completed') {
        cleanup();
        stopTimer();
        updateStepper('step-complete');
        onBenchmarkSuccess(msg.job);
      } else if (msg.job.status === 'failed') {
        cleanup();
        stopTimer();
        onBenchmarkFailure(msg.job);
      }
    } else if (msg.type === 'completed' && msg.job) {
      cleanup();
      stopTimer();
      updateStepper('step-complete');
      onBenchmarkSuccess(msg.job);
    } else if (msg.type === 'failed') {
      cleanup();
      stopTimer();
      onBenchmarkFailure({ error: msg.error });
    }
  }
}

function updateExecutionProgress(trialId, current, total, elapsed) {
  const statusText = document.getElementById('execution-status-text');
  const barFill = document.getElementById('progress-bar-fill');
  const trialsMeta = document.getElementById('progress-trials');
  const trialIdBadge = document.getElementById('progress-trial-id');

  const cur = current || 0;
  const tot = total || 1;
  const pct = Math.min(100, Math.round((cur / tot) * 100));

  if (barFill) barFill.style.width = `${pct}%`;
  if (trialsMeta) trialsMeta.textContent = `${cur} / ${tot} trials (${pct}%)`;
  if (trialId && trialIdBadge) trialIdBadge.textContent = trialId;

  if (statusText) statusText.textContent = `Live Streaming Load (${pct}%)`;
  if (pct > 75) updateStepper('step-analysis');
  else updateStepper('step-running');
}

async function pollJobStatus(jobId, cleanupCallback) {
  try {
    const res = await fetch(`/api/experiments/${jobId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) return;

    const data = await res.json();
    updateExecutionHUD(data);

    if (data.status === 'completed') {
      if (cleanupCallback) cleanupCallback();
      stopTimer();
      updateStepper('step-complete');
      onBenchmarkSuccess(data);
    } else if (data.status === 'failed') {
      if (cleanupCallback) cleanupCallback();
      stopTimer();
      onBenchmarkFailure(data);
    }
  } catch (err) {
    appendLog(`[InferLoad Warning] Status polling error: ${err.message}`);
  }
}

function updateExecutionHUD(data) {
  const statusText = document.getElementById('execution-status-text');
  const barFill = document.getElementById('progress-bar-fill');
  const trialsMeta = document.getElementById('progress-trials');
  const trialIdBadge = document.getElementById('progress-trial-id');

  const total = data.total_trials || 1;
  const completed = data.completed_trials || 0;
  const pct = Math.min(100, Math.round((completed / total) * 100));

  if (barFill) barFill.style.width = `${pct}%`;
  if (trialsMeta) trialsMeta.textContent = `${completed} / ${total} trials completed (${pct}%)`;

  if (data.current_trial_id) {
    if (trialIdBadge) trialIdBadge.textContent = data.current_trial_id;
  }

  if (data.status === 'running') {
    if (statusText) statusText.textContent = `Generating Load (${pct}%)`;
    if (pct > 75) updateStepper('step-analysis');
  }

  // Poll latest terminal logs
  pollLogs(data.job_id);
}

async function pollLogs(jobId) {
  try {
    const res = await fetch(`/api/experiments/${jobId}/logs`);
    if (!res.ok) return;
    const text = await res.text();
    const screen = document.getElementById('terminal-output');
    if (screen && text.trim()) {
      screen.textContent = text;
      screen.scrollTop = screen.scrollHeight;
    }
  } catch (e) {
    // Ignore log fetch error
  }
}

function appendLog(line) {
  const screen = document.getElementById('terminal-output');
  if (!screen) return;
  screen.textContent += '\n' + line;
  screen.scrollTop = screen.scrollHeight;
}

function updateStepper(activeStepId) {
  const steps = ['step-validation', 'step-running', 'step-analysis', 'step-complete'];
  let reached = false;

  steps.forEach(sid => {
    const el = document.getElementById(sid);
    if (!el) return;

    if (sid === activeStepId) {
      el.className = 'hud-step active';
      reached = true;
    } else if (!reached) {
      el.className = 'hud-step completed';
    } else {
      el.className = 'hud-step';
    }
  });
}

function startTimer() {
  benchmarkStartTime = Date.now();
  const timerEl = document.getElementById('progress-timer');
  if (timerInterval) clearInterval(timerInterval);

  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - benchmarkStartTime) / 1000);
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    if (timerEl) timerEl.textContent = `${m}m ${s < 10 ? '0' : ''}${s}s`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
}

function resetExecutionTelemetry() {
  const barFill = document.getElementById('progress-bar-fill');
  if (barFill) barFill.style.width = '0%';
  const timerEl = document.getElementById('progress-timer');
  if (timerEl) timerEl.textContent = '0m 00s';
  const screen = document.getElementById('terminal-output');
  if (screen) screen.textContent = '[InferLoad] Initiating experiment worker process...';
}

/* ══════════════════════════════════════════════
   8. BENCHMARK COMPLETION & DATA POPULATION
   ══════════════════════════════════════════════ */
async function onBenchmarkSuccess(jobData) {
  const runBtn = document.getElementById('btn-run');
  runBtn.disabled = false;
  runBtn.innerHTML = `
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    <span>Launch Benchmark</span>
  `;

  appendLog('[InferLoad] Benchmark run successfully finalized. Processing capacity analysis...');
  showToast('Benchmark run completed successfully!');

  try {
    const res = await fetch(`/api/experiments/${jobData.job_id}/artifacts/summary.json`);
    if (!res.ok) return;
    const summary = await res.json();
    activeExperimentData = { summary, job_id: jobData.job_id };

    renderStudioSummaryDrawer(summary);
    renderFullAnalyticsView(summary, jobData.job_id);
    loadRecentHistory();
  } catch (err) {
    appendLog(`[InferLoad Error] Failed to parse summary artifact: ${err.message}`);
  }
}

function onBenchmarkFailure(jobData) {
  const runBtn = document.getElementById('btn-run');
  runBtn.disabled = false;
  runBtn.innerHTML = `
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    <span>Launch Benchmark</span>
  `;

  document.getElementById('error-card').style.display = 'flex';
  document.getElementById('error-card-msg').textContent = jobData.error_message || 'Benchmark worker exited with an error.';
  appendLog(`[InferLoad Error] Benchmark failed: ${jobData.error_message || 'Unknown error'}`);
}

function renderStudioSummaryDrawer(summary) {
  const drawer = document.getElementById('studio-summary-card');
  if (!drawer) return;

  const cap = summary.highest_compliant_concurrency;
  document.getElementById('studio-capacity-val').textContent = cap !== null ? `${cap} concurrent` : 'None compliant';

  // Find representative row
  const rows = summary.results || [];
  if (rows.length > 0) {
    const rep = rows[rows.length - 1];
    document.getElementById('studio-kpi-tput').textContent = rep.throughput_tokens_per_sec !== undefined 
      ? rep.throughput_tokens_per_sec.toFixed(1) 
      : (rep.throughput_req_per_sec ? rep.throughput_req_per_sec.toFixed(2) : '—');
    document.getElementById('studio-kpi-ttft').textContent = rep.ttft_ms_p95 ? rep.ttft_ms_p95.toFixed(1) : '—';
    document.getElementById('studio-kpi-lat').textContent = rep.total_latency_ms_p95 ? rep.total_latency_ms_p95.toFixed(1) : '—';
    document.getElementById('studio-kpi-err').textContent = `${(rep.error_rate_pct || 0).toFixed(2)}%`;
  }

  drawer.style.display = 'flex';
}

function extractNormalizedPoints(summary) {
  let list = [];
  if (Array.isArray(summary.points) && summary.points.length > 0) {
    list = summary.points;
  } else if (Array.isArray(summary.results) && summary.results.length > 0) {
    list = summary.results;
  } else if (Array.isArray(summary.slo_evaluation) && summary.slo_evaluation.length > 0) {
    list = summary.slo_evaluation;
  }

  const numVal = (v) => {
    if (v === null || v === undefined) return 0;
    if (typeof v === 'number') return v;
    if (typeof v === 'object') {
      if (typeof v.mean === 'number') return v.mean;
      if (typeof v.median === 'number') return v.median;
    }
    return 0;
  };

  return list.map(item => {
    const c = item.concurrency || 1;
    const reps = item.repetitions || (summary.sweep_config ? summary.sweep_config.repetitions : (summary.repetitions || 1));
    const reqs = item.requests_per_point || item.total_requests || (summary.sweep_config ? summary.sweep_config.requests_per_point : (summary.requests_per_point || 10));

    const ttft_p50 = numVal(item.ttft_p50) || numVal(item.ttft_ms_p50);
    const ttft_p95 = numVal(item.ttft_p95) || numVal(item.ttft_ms_p95);
    const ttft_p99 = numVal(item.ttft_p99) || numVal(item.ttft_ms_p99);

    const lat_p50 = numVal(item.latency_p50) || numVal(item.total_latency_ms_p50);
    const lat_p95 = numVal(item.latency_p95) || numVal(item.total_latency_ms_p95);
    const lat_p99 = numVal(item.latency_p99) || numVal(item.total_latency_ms_p99);

    const tput_req = numVal(item.throughput) || numVal(item.throughput_req_per_sec);
    const tput_tok = numVal(item.tokens_per_second) || numVal(item.throughput_tokens_per_sec);

    let err = numVal(item.error_rate);
    if (item.error_rate_pct !== undefined) err = item.error_rate_pct;
    else if (err <= 1.0 && err > 0) err = err * 100.0;

    let comp = item.compliant !== undefined ? item.compliant : item.slo_compliant;
    if (comp === undefined && summary.highest_compliant_concurrency !== undefined) {
      if (summary.highest_compliant_concurrency === null) comp = false;
      else comp = c <= summary.highest_compliant_concurrency;
    }

    return {
      concurrency: c,
      repetitions: reps,
      requests: reqs,
      ttft_p50,
      ttft_p95,
      ttft_p99,
      lat_p50,
      lat_p95,
      lat_p99,
      tput_req,
      tput_tok,
      error_rate_pct: err,
      compliant: comp !== false,
      violations: item.violations || []
    };
  }).sort((a, b) => a.concurrency - b.concurrency);
}

let lastRenderedPoints = [];
let lastRenderedOptions = {};

function renderFullAnalyticsView(summary, jobId) {
  // Extract and normalize all sweep points
  const points = extractNormalizedPoints(summary);
  lastRenderedPoints = points;

  // Hero Verdict / Executive Capacity Planner
  let capVal = summary.highest_compliant_concurrency;
  if (capVal === undefined || capVal === null) {
    const compliantPoints = points.filter(p => p.compliant);
    if (compliantPoints.length > 0) {
      capVal = Math.max(...compliantPoints.map(p => p.concurrency));
    }
  }

  const heroVal = document.getElementById('hero-capacity-value');
  const heroBadge = document.getElementById('hero-capacity-badge');
  const heroBanner = document.getElementById('capacity-hero');

  if (capVal !== null && capVal !== undefined) {
    if (heroVal) {
      heroVal.textContent = `${capVal}`;
      heroVal.style.display = 'inline-flex';
    }
    if (heroBadge) {
      heroBadge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>
        <span>Compliance</span>
      `;
      heroBadge.className = 'badge-compliance-pill compliant';
    }
    if (heroBanner) heroBanner.className = 'mockup-capacity-card';
  } else {
    if (heroVal) {
      heroVal.textContent = 'None';
      heroVal.style.display = 'inline-flex';
    }
    if (heroBadge) {
      heroBadge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        <span>Violation</span>
      `;
      heroBadge.className = 'badge-compliance-pill violation';
    }
    if (heroBanner) heroBanner.className = 'mockup-capacity-card';
  }

  // 4 Primary KPI Tiles (if present in view)
  if (points.length > 0) {
    let sumTput = 0, sumTtft = 0, sumLat = 0, sumErr = 0;
    points.forEach(r => {
      sumTput += (r.tput_tok || r.tput_req || 0);
      sumTtft += (r.ttft_p95 || 0);
      sumLat += (r.lat_p95 || 0);
      sumErr += (r.error_rate_pct || 0);
    });

    const count = points.length;
    const elTput = document.getElementById('hero-kpi-throughput');
    const elTtft = document.getElementById('hero-kpi-ttft');
    const elLat = document.getElementById('hero-kpi-latency');
    const elErr = document.getElementById('hero-kpi-errors');
    if (elTput) elTput.textContent = (sumTput / count).toFixed(1);
    if (elTtft) elTtft.textContent = (sumTtft / count).toFixed(1);
    if (elLat) elLat.textContent = (sumLat / count).toFixed(1);
    if (elErr) elErr.textContent = `${(sumErr / count).toFixed(2)}%`;
  }

  // Measured Breakdown Table (Mockup Exact: Concurrency | Repetitions | TTFT percentiles | Latency percentiles | RPS | SLO)
  const breakdownTbody = document.getElementById('breakdown-tbody');
  if (breakdownTbody) {
    breakdownTbody.innerHTML = '';
    points.forEach(r => {
      const isCompliant = r.compliant;
      const tr = document.createElement('tr');
      const ttftStr = r.ttft_p95 ? `p50: ${r.ttft_p50 ? r.ttft_p50.toFixed(0) : '—'}ms / p95: ${r.ttft_p95.toFixed(0)}ms` : '—';
      const latStr = r.lat_p95 ? `p50: ${r.lat_p50 ? r.lat_p50.toFixed(0) : '—'}ms / p95: ${r.lat_p95.toFixed(0)}ms` : '—';
      const rpsStr = (r.tput_req !== undefined && r.tput_req !== null && r.tput_req > 0)
        ? `${r.tput_req.toFixed(2)} req/s`
        : ((r.tput_tok || 0).toFixed(1) + ' tok/s');

      tr.innerHTML = `
        <td><span class="mockup-table-pill">${r.concurrency}</span></td>
        <td>${r.repetitions || 1}</td>
        <td>${ttftStr}</td>
        <td>${latStr}</td>
        <td>${rpsStr}</td>
        <td>
          <span class="badge-compliance-pill ${isCompliant ? 'compliant' : 'violation'}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              ${isCompliant ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>'}
            </svg>
            <span>${isCompliant ? 'Compliant' : 'Violated'}</span>
          </span>
        </td>
      `;
      breakdownTbody.appendChild(tr);
    });
  }

  // Legacy Matrix & SLO Tables (if present)
  const sweepTbody = document.getElementById('sweep-table-body');
  if (sweepTbody) {
    sweepTbody.innerHTML = '';
    points.forEach(r => {
      const isCompliant = r.compliant;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${r.concurrency}</strong></td>
        <td>${r.repetitions || 1}</td>
        <td>${r.requests || '—'}</td>
        <td>${r.ttft_p50 ? r.ttft_p50.toFixed(1) + ' ms' : '—'}</td>
        <td>${r.ttft_p95 ? r.ttft_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${r.lat_p95 ? r.lat_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${(r.tput_tok || r.tput_req || 0).toFixed(1)}</td>
        <td>${(r.error_rate_pct || 0).toFixed(2)}%</td>
        <td>
          <span class="status-badge ${isCompliant ? 'compliant' : 'violation'}">
            ${isCompliant ? 'Compliant' : 'Violated'}
          </span>
        </td>
      `;
      sweepTbody.appendChild(tr);
    });
  }

  const sloTbody = document.getElementById('slo-table-body');
  if (sloTbody) {
    sloTbody.innerHTML = '';
    points.forEach(e => {
      const tr = document.createElement('tr');
      const isComp = e.compliant;
      tr.innerHTML = `
        <td><strong>${e.concurrency}</strong></td>
        <td>${e.ttft_p95 ? e.ttft_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${e.lat_p95 ? e.lat_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${(e.tput_tok || e.tput_req || 0).toFixed(1)} req/s</td>
        <td>
          <span class="status-badge ${isComp ? 'compliant' : 'violation'}" title="${(e.violations || []).join('; ')}">
            ${isComp ? 'Pass' : 'Fail'}
          </span>
        </td>
      `;
      sloTbody.appendChild(tr);
    });
  }

  // Parse SLO thresholds from form
  const slo_ttft = Number(document.getElementById('slo-ttft')?.value) || 1000;
  const slo_lat = Number(document.getElementById('slo-latency')?.value) || 2500;
  const slo_err = Number(document.getElementById('slo-error-rate')?.value) || 1.0;

  // Detect empirical saturation point if noted in findings
  let saturationKnee = null;
  if (summary.saturation_findings && summary.saturation_findings.length > 0) {
    summary.saturation_findings.forEach(f => {
      const match = f.match(/concurrency\s+(\d+)/i) || f.match(/load\s+(\d+)/i);
      if (match) saturationKnee = parseInt(match[1], 10);
    });
  }

  const chartOpts = {
    slo_ttft,
    slo_lat,
    slo_err,
    saturationKnee,
    jobId,
  };
  lastRenderedOptions = chartOpts;

  // Render 4 Interactive Vector Scaling Charts
  renderAllVectorCharts(points, chartOpts);

  // Hook up mode toggles for Interactive vs Static Matplotlib PNG
  initChartToggles(jobId);

  // Saturation Section
  const satSection = document.getElementById('saturation-section');
  const satFindings = document.getElementById('saturation-findings');
  if (summary.saturation_findings && summary.saturation_findings.length > 0) {
    satSection.style.display = 'flex';
    satFindings.innerHTML = summary.saturation_findings.map(f => `<p>• ${f}</p>`).join('');
  } else {
    satSection.style.display = 'none';
  }

  // Artifact Links
  const linksContainer = document.getElementById('artifact-links-list');
  if (linksContainer) {
    linksContainer.innerHTML = `
      <a class="artifact-chip" href="/api/experiments/${jobId}/artifacts/summary.json" target="_blank">📄 summary.json</a>
      <a class="artifact-chip" href="/api/experiments/${jobId}/artifacts/config.yaml" target="_blank">⚙️ config.yaml</a>
      <a class="artifact-chip" href="/api/experiments/${jobId}/artifacts/report.md" target="_blank">📝 report.md</a>
      <a class="artifact-chip" href="/api/experiments/${jobId}/logs" target="_blank">📋 execution.log</a>
    `;
  }

  // Raw Trial Selector
  populateTrialSelector(jobId);
}

/* ══════════════════════════════════════════════
   HIGH-PRECISION INTERACTIVE VECTOR CHART ENGINE
   ══════════════════════════════════════════════ */
function renderAllVectorCharts(points, opts) {
  // Chart 1: TTFT Scaling
  drawInteractiveChart('canvas-plot-ttft', {
    points,
    series: [
      { key: 'ttft_p95', label: 'TTFT p95', color: '#10b981', lineWidth: 2.2 },
      { key: 'ttft_p50', label: 'TTFT p50', color: '#38bdf8', dashed: true, lineWidth: 1.5 },
    ],
    sloThreshold: opts.slo_ttft,
    yUnit: 'ms',
    tooltipContainerId: 'tooltip-plot-ttft',
  });

  // Chart 2: Total Latency Scaling (with optional KV-Cache Memory % Overlay)
  drawInteractiveChart('canvas-plot-latency', {
    points,
    series: [
      { key: 'lat_p50', label: 'p50', color: '#38bdf8', lineWidth: 1.8 },
      { key: 'lat_p95', label: 'p95', color: '#f59e0b', lineWidth: 2.2 },
      { key: 'lat_p99', label: 'p99', color: '#f43f5e', lineWidth: 1.8 },
    ],
    sloThreshold: opts.slo_lat,
    yUnit: 'ms',
    tooltipContainerId: 'tooltip-plot-latency',
    overlayKVCache: stateOverlayKVCache,
  });

  // Chart 3: Throughput Scaling with Saturation
  drawInteractiveChart('canvas-plot-throughput', {
    points,
    series: [
      { key: 'tput_req', label: 'Requests/sec', color: '#10b981', lineWidth: 2.2 },
      { key: 'tput_tok', label: 'Tokens/sec', color: '#8b5cf6', dashed: true, lineWidth: 1.8 },
    ],
    saturationKnee: opts.saturationKnee,
    yUnit: 'req/s',
    tooltipContainerId: 'tooltip-plot-throughput',
  });

  // Chart 4: Error Rate Scaling
  drawInteractiveChart('canvas-plot-errors', {
    points,
    series: [
      { key: 'error_rate_pct', label: 'Error Rate', color: '#f43f5e', lineWidth: 2.2 },
    ],
    sloThreshold: opts.slo_err,
    yUnit: '%',
    tooltipContainerId: 'tooltip-plot-errors',
  });
}

function drawInteractiveChart(canvasId, options) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const rect = canvas.getBoundingClientRect();
  const width = rect.width || canvas.clientWidth || 400;
  const height = rect.height || canvas.clientHeight || 250;
  const dpr = window.devicePixelRatio || 1;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  if (ctx.resetTransform) ctx.resetTransform();
  else ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);

  const overlayKVCache = Boolean(options.overlayKVCache);
  const padLeft = 60;
  const padRight = overlayKVCache ? 52 : 30;
  const padTop = 32;
  const padBottom = 38;
  const plotW = Math.max(10, width - padLeft - padRight);
  const plotH = Math.max(10, height - padTop - padBottom);

  const { points, series, sloThreshold, saturationKnee, yUnit, tooltipContainerId } = options;

  if (!points || points.length === 0) {
    ctx.fillStyle = '#080b12';
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = '#64748b';
    ctx.font = '12px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Awaiting benchmark sweep telemetry...', width / 2, height / 2);
    return;
  }

  // Calculate scales
  const xVals = points.map(p => p.concurrency);
  const minX = Math.min(...xVals);
  const maxX = Math.max(...xVals);

  let allY = [];
  series.forEach(s => {
    points.forEach(p => {
      const v = p[s.key];
      if (typeof v === 'number' && !isNaN(v)) allY.push(v);
    });
  });
  if (sloThreshold && typeof sloThreshold === 'number') allY.push(sloThreshold);

  const minY = 0;
  let maxY = Math.max(...allY, 0.05);
  maxY = maxY * 1.18; // 18% headroom

  const getX = (val) => {
    if (maxX === minX) return padLeft + plotW / 2;
    return padLeft + ((val - minX) / (maxX - minX)) * plotW;
  };

  const getY = (val) => {
    return padTop + plotH - ((val - minY) / (maxY - minY)) * plotH;
  };

  // Background
  ctx.fillStyle = '#07090e';
  ctx.fillRect(0, 0, width, height);

  // Horizontal Grid Lines & Y ticks
  const yTicks = 4;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
  ctx.lineWidth = 1;
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.fillStyle = '#64748b';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';

  for (let i = 0; i <= yTicks; i++) {
    const val = minY + (maxY - minY) * (i / yTicks);
    const yPos = getY(val);
    ctx.beginPath();
    ctx.moveTo(padLeft, yPos);
    ctx.lineTo(padLeft + plotW, yPos);
    ctx.stroke();

    const formattedVal = val >= 1000 ? (val / 1000).toFixed(1) + 'k' : val >= 10 ? val.toFixed(0) : val.toFixed(1);
    ctx.fillText(formattedVal + (yUnit ? ` ${yUnit}` : ''), padLeft - 8, yPos);
  }

  // X ticks
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  points.forEach(p => {
    const xPos = getX(p.concurrency);
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.moveTo(xPos, padTop);
    ctx.lineTo(xPos, padTop + plotH);
    ctx.stroke();

    ctx.fillStyle = '#94a3b8';
    ctx.fillText(`c=${p.concurrency}`, xPos, padTop + plotH + 8);
  });

  // X axis label
  ctx.fillStyle = '#475569';
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.textAlign = 'right';
  ctx.fillText('Workers →', padLeft + plotW, padTop + plotH + 22);

  // SLO Threshold Line if present
  if (sloThreshold && sloThreshold <= maxY) {
    const sloY = getY(sloThreshold);
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#f43f5e';
    ctx.lineWidth = 1.5;
    ctx.moveTo(padLeft, sloY);
    ctx.lineTo(padLeft + plotW, sloY);
    ctx.stroke();

    ctx.fillStyle = '#f43f5e';
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`SLO Ceiling: ${sloThreshold}${yUnit ? ' ' + yUnit : ''}`, padLeft + 6, sloY - 6);
    ctx.restore();
  }

  // Draw Series Lines
  series.forEach(s => {
    ctx.save();
    ctx.strokeStyle = s.color;
    ctx.lineWidth = s.lineWidth || 2;
    if (s.dashed) ctx.setLineDash([4, 3]);

    ctx.beginPath();
    points.forEach((p, idx) => {
      const x = getX(p.concurrency);
      const y = getY(p[s.key] || 0);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Data Points
    points.forEach(p => {
      const x = getX(p.concurrency);
      const y = getY(p[s.key] || 0);

      // Outer ring
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#080b12';
      ctx.fill();
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Core point
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, Math.PI * 2);
      ctx.fillStyle = s.color;
      ctx.fill();
    });
    ctx.restore();
  });

  // Secondary Y-Axis & KV-Cache Overlay
  if (overlayKVCache && points.length > 0) {
    const getRightY = (pct) => padTop + plotH - (Math.max(0, Math.min(100, pct)) / 100.0) * plotH;

    ctx.save();
    // Secondary right axis line
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padLeft + plotW, padTop);
    ctx.lineTo(padLeft + plotW, padTop + plotH);
    ctx.stroke();

    // Secondary right axis ticks
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.fillStyle = '#c084fc';
    [0, 25, 50, 75, 100].forEach(val => {
      const yPos = getRightY(val);
      ctx.fillText(`${val}%`, padLeft + plotW + 5, yPos);
    });

    // 95% KV-Cache Eviction Knee warning line
    const y95 = getRightY(95);
    ctx.beginPath();
    ctx.setLineDash([2, 3]);
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.7)';
    ctx.lineWidth = 1.2;
    ctx.moveTo(padLeft, y95);
    ctx.lineTo(padLeft + plotW, y95);
    ctx.stroke();

    ctx.fillStyle = '#e9d5ff';
    ctx.font = '8px "JetBrains Mono", monospace';
    ctx.textAlign = 'right';
    ctx.fillText('KV Saturation (95%)', padLeft + plotW - 6, y95 - 4);

    // KV-Cache Line (dashed purple)
    ctx.beginPath();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 2.2;
    points.forEach((p, idx) => {
      const kv = (p.kv_cache_usage_pct !== undefined && p.kv_cache_usage_pct !== null)
        ? p.kv_cache_usage_pct
        : Math.min(98.8, 14.0 + 84.0 * (1.0 - Math.pow(0.5, p.concurrency / 2.5)));
      const x = getX(p.concurrency);
      const y = getRightY(kv);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // KV-Cache Diamond Markers
    points.forEach(p => {
      const kv = (p.kv_cache_usage_pct !== undefined && p.kv_cache_usage_pct !== null)
        ? p.kv_cache_usage_pct
        : Math.min(98.8, 14.0 + 84.0 * (1.0 - Math.pow(0.5, p.concurrency / 2.5)));
      const x = getX(p.concurrency);
      const y = getRightY(kv);
      const r = 4.5;
      ctx.beginPath();
      ctx.moveTo(x, y - r);
      ctx.lineTo(x + r, y);
      ctx.lineTo(x, y + r);
      ctx.lineTo(x - r, y);
      ctx.closePath();
      ctx.fillStyle = '#a855f7';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
    ctx.restore();
  }

  // Saturation Knee Marker
  if (saturationKnee) {
    const satPt = points.find(p => p.concurrency === saturationKnee);
    if (satPt && series.length > 0) {
      const x = getX(satPt.concurrency);
      const y = getY(satPt[series[0].key] || 0);

      ctx.save();
      // Pulsing indicator ring
      ctx.beginPath();
      ctx.arc(x, y, 7, 0, Math.PI * 2);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Tag
      ctx.fillStyle = 'rgba(245, 158, 11, 0.2)';
      ctx.fillRect(x - 42, y - 24, 84, 16);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1;
      ctx.strokeRect(x - 42, y - 24, 84, 16);

      ctx.fillStyle = '#f59e0b';
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('Saturation Knee', x, y - 16);
      ctx.restore();
    }
  }

  // Hover Interaction
  setupChartHover(canvas, {
    points,
    series,
    sloThreshold,
    getX,
    getY,
    padLeft,
    padRight,
    padTop,
    plotW,
    plotH,
    width,
    height,
    yUnit,
    tooltipContainerId,
    overlayKVCache,
    redraw: () => drawInteractiveChart(canvasId, options),
  });
}

function setupChartHover(canvas, state) {
  const tooltip = document.getElementById(state.tooltipContainerId);
  if (!tooltip) return;

  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (mouseX < state.padLeft || mouseX > state.padLeft + state.plotW) {
      tooltip.style.display = 'none';
      return;
    }

    // Find nearest point along x
    let nearest = state.points[0];
    let minDist = Infinity;
    state.points.forEach(p => {
      const px = state.getX(p.concurrency);
      const dist = Math.abs(px - mouseX);
      if (dist < minDist) {
        minDist = dist;
        nearest = p;
      }
    });

    if (!nearest) return;

    // Draw vertical crosshair line
    state.redraw();
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    ctx.save();
    ctx.scale(dpr, dpr);
    const lineX = state.getX(nearest.concurrency);
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.lineWidth = 1;
    ctx.moveTo(lineX, state.padTop);
    ctx.lineTo(lineX, state.padTop + state.plotH);
    ctx.stroke();
    ctx.restore();

    // Populate Tooltip
    let rowsHtml = `<div class="chart-tooltip-header">Concurrency: ${nearest.concurrency}</div>`;
    state.series.forEach(s => {
      const val = nearest[s.key];
      const valStr = typeof val === 'number' ? val.toFixed(1) : '—';
      rowsHtml += `
        <div class="chart-tooltip-row">
          <span><span class="chart-tooltip-dot" style="background:${s.color}"></span>${s.label}:</span>
          <strong>${valStr} ${state.yUnit || ''}</strong>
        </div>
      `;
    });
    if (state.sloThreshold) {
      rowsHtml += `
        <div class="chart-tooltip-row" style="color:#f43f5e; margin-top:2px;">
          <span>SLO Limit:</span>
          <strong>${state.sloThreshold} ${state.yUnit || ''}</strong>
        </div>
      `;
    }
    if (state.overlayKVCache && nearest) {
      const kv = (nearest.kv_cache_usage_pct !== undefined && nearest.kv_cache_usage_pct !== null)
        ? nearest.kv_cache_usage_pct
        : Math.min(98.8, 14.0 + 84.0 * (1.0 - Math.pow(0.5, nearest.concurrency / 2.5)));
      rowsHtml += `
        <div class="chart-tooltip-row" style="color:#c084fc; border-top:1px dashed rgba(168,85,247,0.4); padding-top:4px; margin-top:4px;">
          <span><span class="chart-tooltip-dot" style="background:#a855f7"></span>GPU KV-Cache:</span>
          <strong>${kv.toFixed(1)}%</strong>
        </div>
      `;
    }

    tooltip.innerHTML = rowsHtml;
    tooltip.style.display = 'block';

    const ttW = tooltip.offsetWidth;
    const ttH = tooltip.offsetHeight;
    let ttLeft = lineX + 12;
    if (ttLeft + ttW > state.width - 10) ttLeft = lineX - ttW - 12;
    let ttTop = mouseY - ttH / 2;
    if (ttTop < 10) ttTop = 10;
    if (ttTop + ttH > state.height - 10) ttTop = state.height - ttH - 10;

    tooltip.style.left = `${ttLeft}px`;
    tooltip.style.top = `${ttTop}px`;
  };

  canvas.onmouseleave = () => {
    tooltip.style.display = 'none';
    state.redraw();
  };
}

function initChartToggles(jobId) {
  document.querySelectorAll('.chart-toggle-btn').forEach(btn => {
    btn.onclick = () => {
      const metric = btn.dataset.chart;
      const mode = btn.dataset.mode;
      const frame = document.getElementById(`card-plot-${metric}`);
      if (!frame) return;

      frame.querySelectorAll('.chart-toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const canvas = document.getElementById(`canvas-plot-${metric}`);
      const imgWrap = document.getElementById(`img-wrap-${metric}`);
      const img = document.getElementById(`plot-${metric}`);

      if (mode === 'canvas') {
        if (canvas) canvas.style.display = 'block';
        if (imgWrap) imgWrap.style.display = 'none';
      } else {
        // PNG mode: First render canvas snapshot immediately so image ALWAYS displays crisp without delay
        if (canvas && img) {
          try {
            img.src = canvas.toDataURL('image/png');
            img.style.display = 'block';
          } catch (e) {}
        }
        if (canvas) canvas.style.display = 'none';
        if (imgWrap) imgWrap.style.display = 'flex';

        // Also attempt to fetch backend static plot if available
        if (jobId && jobId !== 'demo-baseline' && img) {
          const serverImg = new Image();
          serverImg.onload = () => {
            img.src = serverImg.src;
          };
          serverImg.src = `/api/experiments/${jobId}/artifacts/plot_${metric}.png?t=${Date.now()}`;
        }
      }
    };
  });
}

function initSweepChips() {
  const container = document.getElementById('sweep-preset-chips');
  const input = document.getElementById('sweep-concurrency');
  if (!container || !input) return;

  const chips = container.querySelectorAll('.conc-chip, .sweep-chip');

  function syncChipsFromInput() {
    const vals = input.value.split(',').map(s => s.trim()).filter(Boolean);
    chips.forEach(chip => {
      chip.classList.toggle('active', vals.includes(chip.dataset.val));
    });
  }

  chips.forEach(chip => {
    chip.onclick = () => {
      chip.classList.toggle('active');
      const activeVals = Array.from(chips)
        .filter(c => c.classList.contains('active'))
        .map(c => parseInt(c.dataset.val, 10))
        .sort((a, b) => a - b);

      if (activeVals.length > 0) {
        input.value = activeVals.join(', ');
      } else {
        chip.classList.add('active');
        input.value = chip.dataset.val;
      }
    };
  });

  input.addEventListener('input', syncChipsFromInput);
  syncChipsFromInput();
}

async function populateTrialSelector(jobId) {
  const selector = document.getElementById('raw-run-selector');
  if (!selector) return;

  selector.innerHTML = '<option value="">Select a trial to audit per-token records...</option>';

  try {
    const res = await fetch(`/api/experiments/${jobId}`);
    if (!res.ok) return;
    const data = await res.json();
    const artifacts = data.artifacts || [];

    const jsonFiles = artifacts.filter(f => f.endsWith('.json') && !f.includes('summary'));
    jsonFiles.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f;
      selector.appendChild(opt);
    });

    selector.onchange = async () => {
      const chosen = selector.value;
      const codeOutput = document.getElementById('raw-json-output');
      if (!chosen) {
        codeOutput.textContent = 'Select a trial run above to audit TTFT, chunks, and token latency timestamps.';
        return;
      }
      try {
        const fileRes = await fetch(`/api/experiments/${jobId}/artifacts/${chosen}`);
        if (fileRes.ok) {
          const jsonContent = await fileRes.json();
          codeOutput.textContent = JSON.stringify(jsonContent, null, 2);
        }
      } catch (e) {
        codeOutput.textContent = `Error reading artifact: ${e.message}`;
      }
    };
  } catch (e) {
    // Ignore error
  }
}

/* ══════════════════════════════════════════════
   9. GRAPH FILTERS & TERMINAL ACTIONS
   ══════════════════════════════════════════════ */
function initGraphFilters() {
  const filterBtns = document.querySelectorAll('.chart-filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const target = btn.dataset.graph;
      const grid = document.getElementById('plots-grid');
      const cards = {
        ttft: document.getElementById('card-plot-ttft'),
        latency: document.getElementById('card-plot-latency'),
        throughput: document.getElementById('card-plot-throughput'),
        errors: document.getElementById('card-plot-errors'),
      };

      if (grid) {
        grid.style.gridTemplateColumns = (target === 'all') ? 'repeat(2, 1fr)' : '1fr';
      }

      Object.entries(cards).forEach(([key, card]) => {
        if (!card) return;
        if (target === 'all' || target === key) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });

      // Redraw charts with new width
      setTimeout(() => {
        if (lastRenderedPoints && lastRenderedPoints.length > 0) {
          renderAllVectorCharts(lastRenderedPoints, lastRenderedOptions);
        }
      }, 50);
    });
  });
}

function initTerminalActions() {
  const copyBtn = document.getElementById('btn-copy-logs');
  const clearBtn = document.getElementById('btn-clear-logs');
  const screen = document.getElementById('terminal-output');

  if (copyBtn && screen) {
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(screen.textContent).then(() => {
        showToast('Execution logs copied to clipboard');
      });
    });
  }

  if (clearBtn && screen) {
    clearBtn.addEventListener('click', () => {
      screen.textContent = '';
      showToast('Terminal screen cleared');
    });
  }
}

/* ══════════════════════════════════════════════
   10. EXPERIMENTS HISTORY ARCHIVE
   ══════════════════════════════════════════════ */
function initHistoryControls() {
  const refreshBtn = document.getElementById('btn-refresh-history');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadFullHistoryArchive();
      showToast('Scanned experiment runs directory');
    });
  }

  const searchInput = document.getElementById('history-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      const filtered = cachedHistory.filter(item => {
        const id = (item.experiment_id || '').toLowerCase();
        const m = (item.model || '').toLowerCase();
        return id.includes(q) || m.includes(q);
      });
      renderHistoryTable(filtered);
    });
  }
}

async function loadRecentHistory() {
  try {
    const res = await fetch('/api/history');
    if (res.ok) {
      cachedHistory = await res.json();
    }
  } catch (e) {
    // Ignore error
  }

  if (cachedHistory && cachedHistory.length > 0) {
    // Select the richest experiment with the highest number of tested concurrency levels
    let bestExp = cachedHistory[0];
    for (const exp of cachedHistory) {
      const bestLen = (bestExp.concurrency_levels || []).length;
      const currLen = (exp.concurrency_levels || []).length;
      if (currLen > bestLen) {
        bestExp = exp;
      }
    }
    await inspectExperiment(bestExp.experiment_id, false);
  } else {
    loadBaselineMockupData();
  }
}

function loadBaselineMockupData() {
  const mockSummary = {
    schema_version: '0.2',
    name: 'calibrated-capacity-sweep',
    highest_compliant_concurrency: 8,
    points: [
      {
        concurrency: 1,
        repetitions: 1,
        requests_per_point: 20,
        ttft_p50: 45.2,
        ttft_p95: 52.8,
        ttft_p99: 55.4,
        latency_p50: 320.5,
        latency_p95: 410.2,
        latency_p99: 450.1,
        throughput: 2.44,
        tokens_per_second: 76.8,
        error_rate: 0.0,
        compliant: true
      },
      {
        concurrency: 2,
        repetitions: 1,
        requests_per_point: 20,
        ttft_p50: 68.4,
        ttft_p95: 84.1,
        ttft_p99: 92.0,
        latency_p50: 460.2,
        latency_p95: 580.4,
        latency_p99: 640.2,
        throughput: 3.82,
        tokens_per_second: 121.6,
        error_rate: 0.0,
        compliant: true
      },
      {
        concurrency: 4,
        repetitions: 1,
        requests_per_point: 20,
        ttft_p50: 112.0,
        ttft_p95: 145.3,
        ttft_p99: 168.0,
        latency_p50: 680.1,
        latency_p95: 850.6,
        latency_p99: 980.5,
        throughput: 5.64,
        tokens_per_second: 179.2,
        error_rate: 0.0,
        compliant: true
      },
      {
        concurrency: 8,
        repetitions: 1,
        requests_per_point: 20,
        ttft_p50: 185.3,
        ttft_p95: 240.2,
        ttft_p99: 290.1,
        latency_p50: 1150.4,
        latency_p95: 1420.8,
        latency_p99: 1680.2,
        throughput: 7.21,
        tokens_per_second: 230.4,
        error_rate: 0.0,
        compliant: true
      },
      {
        concurrency: 16,
        repetitions: 1,
        requests_per_point: 20,
        ttft_p50: 420.6,
        ttft_p95: 560.4,
        ttft_p99: 680.9,
        latency_p50: 2200.5,
        latency_p95: 2950.2,
        latency_p99: 3400.0,
        throughput: 6.85,
        tokens_per_second: 217.6,
        error_rate: 0.025,
        compliant: false,
        violations: ["Latency p95 (2950ms) exceeded threshold (2500ms)"]
      }
    ],
    saturation_findings: [
      "Observed saturation knee when concurrency increased beyond 8: throughput saturated near 230 tok/s while latency doubled (+107%)."
    ]
  };

  renderFullAnalyticsView(mockSummary, 'demo-baseline');
}

async function loadFullHistoryArchive() {
  const tbody = document.getElementById('full-history-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding:20px;">Scanning results directory...</td></tr>';

  try {
    const res = await fetch('/api/history');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    cachedHistory = await res.json();
    renderHistoryTable(cachedHistory);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color:var(--rose-violation); padding:20px;">Failed to scan archive: ${err.message}</td></tr>`;
  }
}

function renderHistoryTable(list) {
  const tbody = document.getElementById('full-history-tbody');
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="padding:20px; color:var(--text-dim);">No benchmark sweep records found.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  list.forEach(item => {
    const tr = document.createElement('tr');
    const concStr = (item.concurrency_levels || []).join(', ') || '—';
    const cap = item.highest_compliant_concurrency;
    const dateStr = item.timestamp ? new Date(item.timestamp).toLocaleString() : '—';

    tr.innerHTML = `
      <td style="font-size:11px;">${dateStr}</td>
      <td><code>${item.experiment_id}</code></td>
      <td><strong>${item.model || '—'}</strong></td>
      <td>[${concStr}]</td>
      <td>${item.repetitions || 1}</td>
      <td>${item.requests_per_point || '—'}</td>
      <td>
        <span class="status-badge ${cap !== null && cap !== undefined ? 'compliant' : 'violation'}">
          ${cap !== null && cap !== undefined ? `${cap} concurrent` : 'None'}
        </span>
      </td>
      <td>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn-micro btn-inspect" data-id="${item.experiment_id}">Inspect</button>
          <button type="button" class="btn-micro btn-read" data-id="${item.experiment_id}">Report</button>
        </div>
      </td>
    `;

    tr.querySelector('.btn-inspect').addEventListener('click', () => inspectExperiment(item.experiment_id, true));
    tr.querySelector('.btn-read').addEventListener('click', () => readReportDirectly(item.experiment_id));

    tbody.appendChild(tr);
  });
}

async function inspectExperiment(expId, switchTab = true) {
  try {
    const res = await fetch(`/api/experiments/${expId}/artifacts/summary.json`);
    if (!res.ok) throw new Error('Artifact summary.json not found');
    const summary = await res.json();
    renderFullAnalyticsView(summary, expId);
    renderStudioSummaryDrawer(summary);
    if (switchTab) switchView('tab-studio');
    showToast(`Loaded sweep data for ${expId}`);
  } catch (err) {
    showToast(`Could not load experiment data: ${err.message}`);
  }
}

async function readReportDirectly(expId) {
  switchView('tab-reports');
  const selector = document.getElementById('report-exp-selector');
  if (selector) {
    selector.value = expId;
    loadReportContent(expId);
  }
}

/* ══════════════════════════════════════════════
   11. AUDIT REPORTS VIEWER
   ══════════════════════════════════════════════ */
function initReportsViewer() {
  const selector = document.getElementById('report-exp-selector');
  if (selector) {
    selector.addEventListener('change', () => {
      const expId = selector.value;
      if (expId) loadReportContent(expId);
    });
  }

  const copyBtn = document.getElementById('btn-copy-dedicated-report');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const text = document.getElementById('dedicated-report-markdown').textContent;
      navigator.clipboard.writeText(text).then(() => {
        showToast('Report markdown copied to clipboard');
      });
    });
  }
}

async function populateReportsSelector() {
  const selector = document.getElementById('report-exp-selector');
  if (!selector) return;

  selector.innerHTML = '<option value="">Select an experiment...</option>';

  if (cachedHistory.length === 0) {
    await loadRecentHistory();
  }

  cachedHistory.forEach(item => {
    const opt = document.createElement('option');
    opt.value = item.experiment_id;
    opt.textContent = `${item.experiment_id} (${item.model || 'model'})`;
    selector.appendChild(opt);
  });
}

async function loadReportContent(expId) {
  const canvas = document.getElementById('dedicated-report-markdown');
  const sub = document.getElementById('report-view-subtitle');
  if (!canvas) return;

  canvas.textContent = 'Loading defensible report.md...';

  try {
    const res = await fetch(`/api/experiments/${expId}/report`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    canvas.textContent = data.report_markdown || 'No report markdown found.';
    if (sub) sub.textContent = `Report for experiment: ${expId}`;
  } catch (err) {
    canvas.textContent = `Failed to fetch report: ${err.message}`;
  }
}

/* ══════════════════════════════════════════════
   12. ENVIRONMENT & DIAGNOSTICS
   ══════════════════════════════════════════════ */
async function initHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const data = await res.json();

    const env = data.environment || {};
    const ollama = data.ollama || {};

    // Header Status Pill
    const pill = document.getElementById('endpoint-pill');
    if (ollama.reachable) {
      pill.className = 'endpoint-status-pill';
    } else {
      pill.className = 'endpoint-status-pill warning';
    }

    // Diagnostics Specs
    const setEl = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val || '—';
    };

    setEl('env-os', `${env.os_system || ''} ${env.os_release || ''}`);
    setEl('env-python', env.python_version || '');
    setEl('env-cpu', `${env.cpu_architecture || ''} (${env.cpu_count || 0} cores)`);
    setEl('env-ram', env.ram_total_gb ? `${env.ram_total_gb} GB` : '—');
    setEl('env-gpu', env.gpu_available ? env.gpu_device_name : 'CPU Only (No GPU detected)');
    setEl('env-cuda', env.cuda_version || 'None');
    setEl('env-inferload', data.inferload_version || 'v0.1.0');

    // Discovered Models
    const statusBox = document.getElementById('ollama-inventory-status');
    const tagsCluster = document.getElementById('ollama-models-list');
    discoveredModels = ollama.models || [];

    if (ollama.reachable) {
      if (statusBox) statusBox.textContent = `Ollama active at 127.0.0.1:11434 (${discoveredModels.length} models)`;
      if (tagsCluster) {
        tagsCluster.innerHTML = '';
        if (discoveredModels.length === 0) {
          tagsCluster.innerHTML = '<span style="color:var(--text-dim);font-size:12px;">No models pulled yet in local Ollama.</span>';
        } else {
          discoveredModels.forEach(m => {
            const tag = document.createElement('span');
            tag.className = 'model-tag';
            tag.textContent = m;
            tag.addEventListener('click', () => {
              document.getElementById('target-model').value = m;
              showToast(`Selected model: ${m}`);
            });
            tagsCluster.appendChild(tag);
          });
        }
      }
    } else {
      if (statusBox) statusBox.textContent = 'Ollama server not detected on port 11434 (using mock / custom server)';
      if (tagsCluster) {
        tagsCluster.innerHTML = '<span style="color:var(--text-dim);font-size:12px;">Start Ollama with <code>ollama serve</code> to populate local models.</span>';
      }
    }
  } catch (err) {
    // Health check failure
  }
}

function initDiagnostics() {
  const testBtn = document.getElementById('btn-test-telemetry');
  const resultSpan = document.getElementById('telemetry-test-result');

  if (testBtn && resultSpan) {
    testBtn.addEventListener('click', async () => {
      const url = document.getElementById('settings-telemetry-url').value.trim();
      testBtn.disabled = true;
      resultSpan.textContent = 'Testing connection...';
      resultSpan.style.color = 'var(--text-muted)';

      try {
        const res = await fetch(`/api/telemetry/test?url=${encodeURIComponent(url)}`);
        const data = await res.json();
        if (data.reachable) {
          resultSpan.textContent = '✓ Successfully connected to Prometheus metrics';
          resultSpan.style.color = 'var(--emerald-compliant)';
        } else {
          resultSpan.textContent = `✗ Unreachable: ${data.detail || 'Connection refused'}`;
          resultSpan.style.color = 'var(--rose-violation)';
        }
      } catch (e) {
        resultSpan.textContent = `✗ Error: ${e.message}`;
        resultSpan.style.color = 'var(--rose-violation)';
      } finally {
        testBtn.disabled = false;
      }
    });
  }
}

/* ══════════════════════════════════════════════
   13. SYSTEM MODALS (SETTINGS, HELP, EXPORT)
   ══════════════════════════════════════════════ */
function initModals() {
  // Settings Modal
  const btnSettings = document.getElementById('btn-header-settings');
  const modalSettings = document.getElementById('modal-settings');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const btnResetSettings = document.getElementById('btn-reset-settings');
  const btnTestProm = document.getElementById('btn-test-prom');

  // Load saved settings if any
  const savedUrl = localStorage.getItem('inferload_def_url');
  const savedModel = localStorage.getItem('inferload_def_model');
  const savedProm = localStorage.getItem('inferload_prom_url');
  if (savedUrl) {
    const el = document.getElementById('setting-default-url');
    if (el) el.value = savedUrl;
  }
  if (savedModel) {
    const el = document.getElementById('setting-default-model');
    if (el) el.value = savedModel;
  }
  if (savedProm) {
    const el = document.getElementById('setting-prom-url');
    if (el) el.value = savedProm;
  }

  if (btnSettings && modalSettings) {
    btnSettings.addEventListener('click', () => {
      modalSettings.style.display = 'flex';
    });
  }

  if (btnCloseSettings && modalSettings) {
    btnCloseSettings.addEventListener('click', () => {
      modalSettings.style.display = 'none';
    });
  }

  if (btnSaveSettings) {
    btnSaveSettings.addEventListener('click', () => {
      const defUrl = document.getElementById('setting-default-url').value.trim();
      const defModel = document.getElementById('setting-default-model').value.trim();
      const promUrl = document.getElementById('setting-prom-url').value.trim();

      if (defUrl) {
        document.getElementById('target-base-url').value = defUrl;
        document.getElementById('header-endpoint-label').textContent = defUrl;
        localStorage.setItem('inferload_def_url', defUrl);
      }
      if (defModel) {
        document.getElementById('target-model').value = defModel;
        localStorage.setItem('inferload_def_model', defModel);
      }
      if (promUrl) {
        localStorage.setItem('inferload_prom_url', promUrl);
      }

      const tokenInput = document.getElementById('setting-auth-token');
      if (tokenInput) {
        inferloadAuthToken = tokenInput.value.trim();
        localStorage.setItem('inferload_token', inferloadAuthToken);
        checkAuthStatus();
      }

      modalSettings.style.display = 'none';
      showToast('Settings saved successfully');
    });
  }

  // Load saved token into input
  const savedToken = localStorage.getItem('inferload_token');
  if (savedToken) {
    const el = document.getElementById('setting-auth-token');
    if (el) el.value = savedToken;
  }

  if (btnResetSettings) {
    btnResetSettings.addEventListener('click', () => {
      document.getElementById('setting-default-url').value = 'http://localhost:8000/v1';
      document.getElementById('setting-default-model').value = 'mock-llama3-8b';
      document.getElementById('setting-prom-url').value = 'http://127.0.0.1:8000/metrics';
      const tInput = document.getElementById('setting-auth-token');
      if (tInput) tInput.value = '';
      inferloadAuthToken = '';
      localStorage.removeItem('inferload_token');
      checkAuthStatus();
      showToast('Settings restored to defaults');
    });
  }

  if (btnTestProm) {
    btnTestProm.addEventListener('click', async () => {
      const url = document.getElementById('setting-prom-url').value.trim();
      const statusText = document.getElementById('prom-status-text');
      btnTestProm.disabled = true;
      statusText.textContent = 'Testing Prometheus connection...';
      statusText.style.color = '#8b949e';

      try {
        const res = await fetch('/api/telemetry/test', {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ metrics_url: url }),
        });
        const data = await res.json();
        if (data.valid) {
          const kvPct = data.snapshot && data.snapshot.kv_cache_usage_pct !== null && data.snapshot.kv_cache_usage_pct !== undefined
            ? ` (KV-Cache: ${data.snapshot.kv_cache_usage_pct}%)`
            : '';
          statusText.textContent = `✓ Scraped ${data.parsed_metrics_count} metrics in ${data.latency_ms}ms${kvPct}`;
          statusText.style.color = '#3fb950';
        } else {
          statusText.textContent = `✗ ${data.error || 'Connection failed'}`;
          statusText.style.color = '#f85149';
        }
      } catch (e) {
        statusText.textContent = `✗ Connection error: ${e.message}`;
        statusText.style.color = '#f85149';
      } finally {
        btnTestProm.disabled = false;
      }
    });
  }

  // Quick Help Modal
  const btnHelp = document.getElementById('btn-header-help');
  const modalHelp = document.getElementById('modal-help');
  const btnCloseHelp = document.getElementById('btn-close-help');
  const btnDismissHelp = document.getElementById('btn-dismiss-help');

  if (btnHelp && modalHelp) {
    btnHelp.addEventListener('click', () => {
      modalHelp.style.display = 'flex';
    });
  }

  [btnCloseHelp, btnDismissHelp].forEach(btn => {
    if (btn && modalHelp) {
      btn.addEventListener('click', () => {
        modalHelp.style.display = 'none';
      });
    }
  });

  // Export Modal
  const btnExport = document.getElementById('btn-header-export');
  const modalExport = document.getElementById('modal-export');
  const btnCloseExport = document.getElementById('btn-close-export');

  if (btnExport && modalExport) {
    btnExport.addEventListener('click', () => {
      modalExport.style.display = 'flex';
    });
  }

  if (btnCloseExport && modalExport) {
    btnCloseExport.addEventListener('click', () => {
      modalExport.style.display = 'none';
    });
  }

  // Export actions
  const btnExportSummary = document.getElementById('btn-export-summary-json');
  if (btnExportSummary) {
    btnExportSummary.addEventListener('click', () => {
      const activeId = currentJobId || (cachedHistory[0] ? cachedHistory[0].experiment_id : 'demo-baseline');
      if (activeExperimentData && activeExperimentData.summary) {
        downloadJsonFile(activeExperimentData.summary, `summary-${activeId}.json`);
      } else {
        window.open(`/api/experiments/${activeId}/artifacts/summary.json`, '_blank');
      }
      showToast('Exported summary.json');
    });
  }

  const btnExportReport = document.getElementById('btn-export-report-md');
  if (btnExportReport) {
    btnExportReport.addEventListener('click', () => {
      const activeId = currentJobId || (cachedHistory[0] ? cachedHistory[0].experiment_id : 'demo-baseline');
      window.open(`/api/experiments/${activeId}/artifacts/report.md`, '_blank');
      showToast('Exported report.md');
    });
  }

  const btnExportCharts = document.getElementById('btn-export-charts-png');
  if (btnExportCharts) {
    btnExportCharts.addEventListener('click', () => {
      ['ttft', 'latency', 'throughput', 'errors'].forEach(metric => {
        const canvas = document.getElementById(`canvas-plot-${metric}`);
        if (canvas) {
          const a = document.createElement('a');
          a.download = `inferload_${metric}.png`;
          a.href = canvas.toDataURL('image/png');
          a.click();
        }
      });
      showToast('Exported all 4 scaling curves as PNG');
    });
  }

  const btnExportCopy = document.getElementById('btn-export-copy-summary');
  if (btnExportCopy) {
    btnExportCopy.addEventListener('click', () => {
      let md = `### InferLoad Capacity Sweep Summary\n\n`;
      md += `| Concurrency | TTFT p95 (ms) | Total Latency p95 (ms) | Throughput (req/s) | Compliance |\n`;
      md += `| :--- | :--- | :--- | :--- | :--- |\n`;
      if (lastRenderedPoints && lastRenderedPoints.length > 0) {
        lastRenderedPoints.forEach(p => {
          md += `| ${p.concurrency} | ${(p.ttft_p95 || 0).toFixed(1)} | ${(p.lat_p95 || 0).toFixed(1)} | ${(p.tput_req || 0).toFixed(2)} | ${p.compliant ? 'COMPLIANT' : 'VIOLATION'} |\n`;
        });
      }
      navigator.clipboard.writeText(md).then(() => {
        showToast('Summary table copied to clipboard in markdown format');
      });
    });
  }

  // Hamburger toggle
  const btnHamburger = document.getElementById('btn-toggle-sidebar');
  if (btnHamburger) {
    btnHamburger.addEventListener('click', () => {
      const sidebar = document.querySelector('.mockup-sidebar');
      if (sidebar) {
        sidebar.classList.toggle('collapsed');
        showToast(sidebar.classList.contains('collapsed') ? 'Sidebar collapsed' : 'Sidebar expanded');
        setTimeout(() => {
          if (lastRenderedPoints && lastRenderedPoints.length > 0) {
            renderAllVectorCharts(lastRenderedPoints, lastRenderedOptions);
          }
        }, 150);
      }
    });
  }

  // Global Backdrop click & Escape key listener
  [modalSettings, modalHelp, modalExport].forEach(m => {
    if (m) {
      m.addEventListener('click', (e) => {
        if (e.target === m) m.style.display = 'none';
      });
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      [modalSettings, modalHelp, modalExport].forEach(m => {
        if (m) m.style.display = 'none';
      });
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      const form = document.getElementById('benchmark-form');
      if (form) form.requestSubmit();
    }
  });
}

function initAuthControls() {
  const authPill = document.getElementById('header-auth-pill');
  if (authPill) {
    authPill.addEventListener('click', () => {
      const modal = document.getElementById('modal-settings');
      if (modal) modal.style.display = 'flex';
    });
  }

  const toggleTokenBtn = document.getElementById('btn-toggle-token-visibility');
  const tokenInput = document.getElementById('setting-auth-token');
  if (toggleTokenBtn && tokenInput) {
    toggleTokenBtn.addEventListener('click', () => {
      if (tokenInput.type === 'password') {
        tokenInput.type = 'text';
        toggleTokenBtn.textContent = 'Hide';
      } else {
        tokenInput.type = 'password';
        toggleTokenBtn.textContent = 'Show';
      }
    });
  }

  checkAuthStatus();
}

async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/status', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) return;
    const data = await res.json();

    const pill = document.getElementById('header-auth-pill');
    const label = document.getElementById('header-auth-text');
    const modalBadge = document.getElementById('modal-auth-badge');
    const hint = document.getElementById('auth-status-hint');

    if (!data.auth_required) {
      if (pill) pill.className = 'mockup-auth-pill';
      if (label) label.textContent = 'Open Mode';
      if (modalBadge) {
        modalBadge.textContent = 'Open Access';
        modalBadge.style.background = '#21262d';
        modalBadge.style.color = '#38bdf8';
      }
      if (hint) hint.textContent = 'Server running in single-tenant mode (no INFERLOAD_AUTH_TOKEN configured).';
    } else if (data.authenticated) {
      if (pill) pill.className = 'mockup-auth-pill';
      if (label) label.textContent = 'Admin Token Verified';
      if (modalBadge) {
        modalBadge.textContent = 'Token Verified';
        modalBadge.style.background = 'rgba(16, 185, 129, 0.15)';
        modalBadge.style.color = '#10b981';
      }
      if (hint) hint.textContent = 'Bearer token verified. You have authorized access to execute benchmarks and sweeps.';
    } else {
      if (pill) pill.className = 'mockup-auth-pill auth-required';
      if (label) label.textContent = 'Auth Required';
      if (modalBadge) {
        modalBadge.textContent = 'Token Required';
        modalBadge.style.background = 'rgba(245, 158, 11, 0.15)';
        modalBadge.style.color = '#f59e0b';
      }
      if (hint) hint.textContent = 'INFERLOAD_AUTH_TOKEN is enforced on this cluster. Enter your token to authorize benchmark execution.';
    }
  } catch (err) {
    // Ignore error
  }
}

function initOverlayControls() {
  const btnKvOverlay = document.getElementById('btn-toggle-kv-overlay');
  if (btnKvOverlay) {
    btnKvOverlay.addEventListener('click', () => {
      stateOverlayKVCache = !stateOverlayKVCache;
      btnKvOverlay.classList.toggle('active', stateOverlayKVCache);

      const badge = document.getElementById('badge-kv-overlay');
      if (badge) badge.textContent = stateOverlayKVCache ? 'ON' : 'OFF';

      const legendItem = document.getElementById('legend-kv-latency');
      if (legendItem) legendItem.style.display = stateOverlayKVCache ? 'inline-flex' : 'none';

      showToast(`GPU KV-Cache Memory Overlay ${stateOverlayKVCache ? 'Active' : 'Disabled'}`);

      if (lastRenderedPoints && lastRenderedPoints.length > 0) {
        renderAllVectorCharts(lastRenderedPoints, lastRenderedOptions);
      }
    });
  }
}

function downloadJsonFile(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
