/* ============================================================
   InferLoad — Modern Studio Dark Frontend Engine
   Full 5-view router, live log streaming, SRE-grade telemetry
   ============================================================ */

let currentJobId = null;
let pollInterval = null;
let timerInterval = null;
let benchmarkStartTime = null;
let activeExperimentData = null;
let discoveredModels = [];
let cachedHistory = [];

document.addEventListener('DOMContentLoaded', () => {
  initNavRouter();
  initPresets();
  initFormControls();
  initPromptsManager();
  initTerminalActions();
  initGraphFilters();
  initHistoryControls();
  initReportsViewer();
  initDiagnostics();
  initHealth();
  loadRecentHistory();
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

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
   7. BENCHMARK SUBMISSION & POLLING
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

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

    // Poll status
    pollInterval = setInterval(() => pollJobStatus(currentJobId), 1000);
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

async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`/api/experiments/${jobId}`);
    if (!res.ok) return;

    const data = await res.json();
    updateExecutionHUD(data);

    if (data.status === 'completed') {
      clearInterval(pollInterval);
      stopTimer();
      updateStepper('step-complete');
      onBenchmarkSuccess(data);
    } else if (data.status === 'failed') {
      clearInterval(pollInterval);
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

function renderFullAnalyticsView(summary, jobId) {
  // Hero Verdict
  const capVal = summary.highest_compliant_concurrency;
  const heroVal = document.getElementById('hero-capacity-value');
  const heroBadge = document.getElementById('hero-capacity-badge');
  const heroBanner = document.getElementById('capacity-hero');

  if (capVal !== null) {
    heroVal.textContent = `${capVal} concurrent`;
    heroBadge.textContent = 'SLO COMPLIANT';
    heroBadge.className = 'badge-verdict-status compliant';
    heroBanner.className = 'verdict-banner';
  } else {
    heroVal.textContent = 'None';
    heroBadge.textContent = 'SLO VIOLATION';
    heroBadge.className = 'badge-verdict-status violation';
    heroBanner.className = 'verdict-banner violation';
  }

  // 4 Primary KPI Tiles
  const rows = summary.results || [];
  if (rows.length > 0) {
    let sumTput = 0, sumTtft = 0, sumLat = 0, sumErr = 0;
    rows.forEach(r => {
      sumTput += (r.throughput_tokens_per_sec || r.throughput_req_per_sec || 0);
      sumTtft += (r.ttft_ms_p95 || 0);
      sumLat += (r.total_latency_ms_p95 || 0);
      sumErr += (r.error_rate_pct || 0);
    });

    const count = rows.length;
    document.getElementById('hero-kpi-throughput').textContent = (sumTput / count).toFixed(1);
    document.getElementById('hero-kpi-ttft').textContent = (sumTtft / count).toFixed(1);
    document.getElementById('hero-kpi-latency').textContent = (sumLat / count).toFixed(1);
    document.getElementById('hero-kpi-errors').textContent = `${(sumErr / count).toFixed(2)}%`;
  }

  // Concurrency Matrix Table
  const sweepTbody = document.getElementById('sweep-table-body');
  if (sweepTbody) {
    sweepTbody.innerHTML = '';
    rows.forEach(r => {
      const isCompliant = r.slo_compliant;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${r.concurrency}</strong></td>
        <td>${r.repetitions || 1}</td>
        <td>${r.total_requests || '—'}</td>
        <td>${r.ttft_ms_p50 ? r.ttft_ms_p50.toFixed(1) + ' ms' : '—'}</td>
        <td>${r.ttft_ms_p95 ? r.ttft_ms_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${r.total_latency_ms_p95 ? r.total_latency_ms_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${(r.throughput_tokens_per_sec || r.throughput_req_per_sec || 0).toFixed(1)}</td>
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

  // SLO Table
  const sloTbody = document.getElementById('slo-table-body');
  if (sloTbody) {
    sloTbody.innerHTML = '';
    const sloEvals = summary.slo_evaluation || summary.results || [];
    sloEvals.forEach(e => {
      const tr = document.createElement('tr');
      const isComp = e.compliant !== undefined ? e.compliant : e.slo_compliant;
      tr.innerHTML = `
        <td><strong>${e.concurrency}</strong></td>
        <td>${e.ttft_ms_p95 ? e.ttft_ms_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${e.total_latency_ms_p95 ? e.total_latency_ms_p95.toFixed(1) + ' ms' : '—'}</td>
        <td>${(e.throughput_tokens_per_sec || e.throughput_req_per_sec || 0).toFixed(1)} req/s</td>
        <td>
          <span class="status-badge ${isComp ? 'compliant' : 'violation'}">
            ${isComp ? 'Pass' : 'Fail'}
          </span>
        </td>
      `;
      sloTbody.appendChild(tr);
    });
  }

  // Scaling Plots
  const timestamp = Date.now();
  ['ttft', 'latency', 'throughput', 'errors'].forEach(metric => {
    const img = document.getElementById(`plot-${metric}`);
    if (img) {
      img.src = `/api/experiments/${jobId}/artifacts/plot_${metric}.png?t=${timestamp}`;
      img.onerror = () => {
        img.style.display = 'none';
        const card = document.getElementById(`card-plot-${metric}`);
        if (card) {
          const note = card.querySelector('.plot-placeholder') || document.createElement('div');
          note.className = 'plot-placeholder';
          note.style.color = 'var(--text-dim)';
          note.style.fontSize = '11px';
          note.style.padding = '20px';
          note.textContent = 'Plot requires multiple concurrency sweep data points.';
          card.appendChild(note);
        }
      };
      img.onload = () => {
        img.style.display = 'block';
      };
    }
  });

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
      const cards = {
        ttft: document.getElementById('card-plot-ttft'),
        latency: document.getElementById('card-plot-latency'),
        throughput: document.getElementById('card-plot-throughput'),
        errors: document.getElementById('card-plot-errors'),
      };

      Object.entries(cards).forEach(([key, card]) => {
        if (!card) return;
        if (target === 'all' || target === key) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
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
    if (!res.ok) return;
    cachedHistory = await res.json();
  } catch (e) {
    // Ignore error
  }
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

    tr.querySelector('.btn-inspect').addEventListener('click', () => inspectExperiment(item.experiment_id));
    tr.querySelector('.btn-read').addEventListener('click', () => readReportDirectly(item.experiment_id));

    tbody.appendChild(tr);
  });
}

async function inspectExperiment(expId) {
  try {
    const res = await fetch(`/api/experiments/${expId}/artifacts/summary.json`);
    if (!res.ok) throw new Error('Artifact summary.json not found');
    const summary = await res.json();
    renderFullAnalyticsView(summary, expId);
    renderStudioSummaryDrawer(summary);
    switchView('tab-results');
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
