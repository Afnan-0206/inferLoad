/* ============================================================
   InferLoad — Modern Engineering Laboratory Console Logic
   Full-featured multi-view router, live logs, SRE-grade telemetry
   ============================================================ */

let currentJobId = null;
let pollInterval = null;
let activeExperimentData = null;
let discoveredModels = [];
let cachedHistory = [];

document.addEventListener('DOMContentLoaded', () => {
  initViewRouter();
  initHealth();
  initConfigTabs();
  initFormControls();
  initGraphFilters();
  initHistoryControls();
  initReportsView();
  initSettingsControls();
  loadRecentExperiments();
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
   1. VIEW ROUTER
   ══════════════════════════════════════════════ */
function initViewRouter() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetView = item.dataset.view;
      if (targetView) switchView(targetView);
    });
  });
}

function switchView(viewId) {
  // Update nav item active states
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId);
  });

  // Toggle visible view containers
  const views = [
    { id: 'view-benchmark', container: 'view-benchmark' },
    { id: 'view-history', container: 'view-history-container' },
    { id: 'view-reports', container: 'view-reports-container' },
    { id: 'view-settings', container: 'view-settings-container' },
  ];

  views.forEach(v => {
    const el = document.getElementById(v.container);
    if (el) {
      el.style.display = (v.id === viewId) ? 'block' : 'none';
      if (v.id === viewId) el.classList.add('active');
      else el.classList.remove('active');
    }
  });

  // Update top bar title
  const pageTitle = document.getElementById('page-title');
  const pageSub = document.getElementById('page-subtitle');
  if (viewId === 'view-benchmark') {
    pageTitle.textContent = 'Benchmark Laboratory';
    pageSub.textContent = 'Configure workloads, set SLO constraints, and measure real inference performance';
  } else if (viewId === 'view-history') {
    pageTitle.textContent = 'Experiments History Archive';
    pageSub.textContent = 'Search, inspect, and compare all historical benchmark sweep artifacts';
    loadFullHistoryArchive();
  } else if (viewId === 'view-reports') {
    pageTitle.textContent = 'Performance Reports';
    pageSub.textContent = 'Read comprehensive markdown audit reports and capacity assessments';
    populateReportsSelector();
  } else if (viewId === 'view-settings') {
    pageTitle.textContent = 'Environment & Diagnostics';
    pageSub.textContent = 'Audit local Ollama models, host runtime specs, and telemetry settings';
  }
}

/* ══════════════════════════════════════════════
   2. HEALTH & ENVIRONMENT DISCOVERY
   ══════════════════════════════════════════════ */
async function initHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const data = await res.json();

    const env = data.environment || {};
    const ollama = data.ollama || {};

    // Specs in Right Sidebar
    setEl('env-os', `${env.os_system || '—'} ${env.os_release || ''}`);
    setEl('env-python', env.python_version || '—');
    setEl('env-cpu', `${env.cpu_architecture || '—'} (${env.cpu_cores || '?'}c)`);
    setEl('env-ram', env.ram_total_gb ? `${env.ram_total_gb} GB` : '—');
    setEl('env-gpu', env.gpu_info || 'None detected');
    setEl('env-cuda', env.cuda_version || 'None');
    setEl('env-inferload', `v${data.inferload_version || '0.1.0'}`);

    // Top bar version badge
    setEl('version-badge', `v${data.inferload_version || '0.1.0'}`);

    // Nav Footer status
    const navDot = document.getElementById('nav-server-status-dot');
    if (ollama.available) {
      navDot.className = 'status-indicator-dot dot-green';
      setEl('nav-env-label', `Ollama Online (${ollama.models ? ollama.models.length : 0} models)`);
    } else {
      navDot.className = 'status-indicator-dot dot-gray';
      setEl('nav-env-label', `${env.os_system || 'Host'} | ${env.cpu_cores || '?'} cores`);
    }

    // Populate Ollama models
    if (ollama.available && ollama.models && ollama.models.length > 0) {
      discoveredModels = ollama.models;
      buildModelDropdown(ollama.models);
      buildSettingsOllamaInventory(ollama);
    } else {
      const invBox = document.getElementById('ollama-inventory-status');
      if (invBox) invBox.textContent = 'Ollama is not currently running locally on port 11434.';
    }

    // Server URL label
    const baseUrlInput = document.getElementById('target-base-url');
    if (baseUrlInput) {
      setEl('server-url-label', baseUrlInput.value);
      baseUrlInput.addEventListener('input', () => {
        setEl('server-url-label', baseUrlInput.value);
      });
    }
  } catch (err) {
    console.warn('Health check request failed:', err);
  }
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function buildModelDropdown(models) {
  const dropdown = document.getElementById('model-dropdown');
  if (!dropdown) return;
  dropdown.innerHTML = '';

  models.forEach(m => {
    const opt = document.createElement('div');
    opt.className = 'model-option';
    opt.textContent = m;
    opt.addEventListener('click', () => {
      document.getElementById('target-model').value = m;
      dropdown.classList.remove('open');
      showToast(`Selected model: ${m}`);
    });
    dropdown.appendChild(opt);
  });

  const modelInput = document.getElementById('target-model');
  modelInput.addEventListener('focus', () => {
    if (dropdown.children.length > 0) dropdown.classList.add('open');
  });
  modelInput.addEventListener('blur', () => {
    setTimeout(() => dropdown.classList.remove('open'), 200);
  });
}

function buildSettingsOllamaInventory(ollama) {
  const invBox = document.getElementById('ollama-inventory-status');
  if (invBox) {
    invBox.textContent = `Ollama service is active with ${ollama.models.length} model(s) ready.`;
    invBox.style.color = '#34d399';
  }
  const tagsList = document.getElementById('ollama-models-list');
  if (tagsList) {
    tagsList.innerHTML = '';
    ollama.models.forEach(m => {
      const chip = document.createElement('span');
      chip.className = 'model-tag-chip';
      chip.textContent = m;
      tagsList.appendChild(chip);
    });
  }
}

/* ══════════════════════════════════════════════
   3. CONFIG SUB-TABS
   ══════════════════════════════════════════════ */
function initConfigTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const pane = document.getElementById(tab.dataset.ctab);
      if (pane) pane.classList.add('active');
    });
  });
}

/* ══════════════════════════════════════════════
   4. FORM CONTROLS & VALIDATION
   ══════════════════════════════════════════════ */
function initFormControls() {
  // Add prompt
  const btnAddPrompt = document.getElementById('btn-add-prompt');
  if (btnAddPrompt) {
    btnAddPrompt.addEventListener('click', () => {
      const container = document.getElementById('prompts-container');
      const entry = document.createElement('div');
      entry.className = 'prompt-entry';
      entry.innerHTML = `
        <input type="text" class="prompt-input" placeholder="Enter benchmark prompt..." required>
        <button type="button" class="btn-remove-prompt" title="Remove">&times;</button>
      `;
      container.appendChild(entry);
    });
  }

  // Remove prompt (delegated)
  const promptsContainer = document.getElementById('prompts-container');
  if (promptsContainer) {
    promptsContainer.addEventListener('click', (e) => {
      if (e.target.classList.contains('btn-remove-prompt')) {
        if (promptsContainer.children.length > 1) {
          e.target.closest('.prompt-entry').remove();
        } else {
          showToast('At least one prompt is required.');
        }
      }
    });
  }

  // Arrival mode toggle
  const arrivalSelect = document.getElementById('arrival-mode');
  if (arrivalSelect) {
    arrivalSelect.addEventListener('change', (e) => {
      const rateGroup = document.getElementById('open-loop-rate-group');
      if (rateGroup) {
        rateGroup.style.display = e.target.value === 'rate' ? 'grid' : 'none';
      }
    });
  }

  // Telemetry toggle
  const telemToggle = document.getElementById('telemetry-enable');
  if (telemToggle) {
    telemToggle.addEventListener('change', (e) => {
      const telemFields = document.getElementById('telemetry-fields');
      if (telemFields) {
        telemFields.style.display = e.target.checked ? 'block' : 'none';
      }
    });
  }

  // Validate Button
  const btnValidate = document.getElementById('btn-validate');
  if (btnValidate) {
    btnValidate.addEventListener('click', validateConfigAction);
  }

  // Reset Button
  const btnReset = document.getElementById('btn-reset');
  if (btnReset) {
    btnReset.addEventListener('click', resetFormDefaults);
  }

  // Benchmark Form Submit (Run Benchmark)
  const form = document.getElementById('benchmark-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      await runBenchmarkAction();
    });
  }

  // Dismiss Error
  const btnDismissError = document.getElementById('btn-dismiss-error');
  if (btnDismissError) {
    btnDismissError.addEventListener('click', () => {
      document.getElementById('error-card').style.display = 'none';
    });
  }

  // Copy Markdown Report Button
  const btnCopyReport = document.getElementById('btn-copy-report');
  if (btnCopyReport) {
    btnCopyReport.addEventListener('click', () => {
      const text = document.getElementById('report-markdown-view').textContent;
      navigator.clipboard.writeText(text).then(() => showToast('Report copied to clipboard!'));
    });
  }

  // Terminal actions
  const btnCopyLogs = document.getElementById('btn-copy-logs');
  if (btnCopyLogs) {
    btnCopyLogs.addEventListener('click', () => {
      const text = document.getElementById('terminal-output').textContent;
      navigator.clipboard.writeText(text).then(() => showToast('Terminal logs copied!'));
    });
  }

  const btnClearLogs = document.getElementById('btn-clear-logs');
  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', () => {
      document.getElementById('terminal-output').textContent = '[System] Logs cleared.';
    });
  }

  // Right sidebar quick actions
  const actReport = document.getElementById('action-report');
  if (actReport) {
    actReport.addEventListener('click', () => {
      const details = document.querySelectorAll('.collapsible-section');
      if (details[0]) {
        details[0].open = true;
        details[0].scrollIntoView({ behavior: 'smooth' });
      }
    });
  }

  const actArtifacts = document.getElementById('action-artifacts');
  if (actArtifacts) {
    actArtifacts.addEventListener('click', () => {
      const details = document.querySelectorAll('.collapsible-section');
      if (details[1]) {
        details[1].open = true;
        details[1].scrollIntoView({ behavior: 'smooth' });
      }
    });
  }

  const actPlots = document.getElementById('action-plots');
  if (actPlots) {
    actPlots.addEventListener('click', () => {
      const section = document.querySelector('.graphs-section');
      if (section) section.scrollIntoView({ behavior: 'smooth' });
    });
  }

  const btnViewAllHistory = document.getElementById('btn-view-all-history');
  if (btnViewAllHistory) {
    btnViewAllHistory.addEventListener('click', () => {
      switchView('view-history');
    });
  }

  // Raw run selector
  const rawSelector = document.getElementById('raw-run-selector');
  if (rawSelector) {
    rawSelector.addEventListener('change', async (e) => {
      const runId = e.target.value;
      if (!runId || !activeExperimentData) return;
      const jsonOut = document.getElementById('raw-json-output');
      jsonOut.textContent = 'Loading trial record...';
      try {
        const jobId = activeExperimentData.jobId;
        const res = await fetch(`/api/experiments/${jobId}/artifacts/raw/${runId}.json`);
        if (res.ok) {
          const data = await res.json();
          jsonOut.textContent = JSON.stringify(data, null, 2);
        } else {
          jsonOut.textContent = `Could not load trial record for '${runId}'.`;
        }
      } catch (err) {
        jsonOut.textContent = `Error: ${err.message}`;
      }
    });
  }
}

function collectFormData() {
  const concInput = document.getElementById('sweep-concurrency').value;
  const concList = concInput.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n) && n > 0);
  const promptInputs = Array.from(document.querySelectorAll('.prompt-input'));
  const prompts = promptInputs.map(i => i.value.trim()).filter(p => p.length > 0);
  const arrivalMode = document.getElementById('arrival-mode').value;

  return {
    name: 'web-sweep',
    description: 'InferLoad benchmark sweep',
    output_dir: 'results',
    base_url: document.getElementById('target-base-url').value.trim(),
    model: document.getElementById('target-model').value.trim(),
    timeout: parseFloat(document.getElementById('target-timeout').value) || 60.0,
    api_key: document.getElementById('target-api-key').value.trim() || null,
    prompts: prompts.length ? prompts : ['What is a database index?'],
    max_tokens: parseInt(document.getElementById('workload-max-tokens').value, 10) || 32,
    temperature: parseFloat(document.getElementById('workload-temperature').value) || 0.0,
    seed: parseInt(document.getElementById('workload-seed').value, 10) || 42,
    stream: document.getElementById('workload-stream').checked,
    concurrency: concList.length ? concList : [1, 2, 4],
    repetitions: parseInt(document.getElementById('sweep-repetitions').value, 10) || 2,
    requests_per_point: parseInt(document.getElementById('sweep-requests').value, 10) || 5,
    warmup_requests: parseInt(document.getElementById('exec-warmup').value, 10) || 1,
    arrival_mode: arrivalMode,
    requests_per_second: arrivalMode === 'rate' ? parseFloat(document.getElementById('arrival-rate').value) : null,
    slo: {
      max_ttft_p95_ms: parseFloat(document.getElementById('slo-ttft').value) || null,
      max_total_latency_p95_ms: parseFloat(document.getElementById('slo-latency').value) || null,
      max_error_rate_pct: parseFloat(document.getElementById('slo-error').value) || null,
      min_throughput_req_per_sec: parseFloat(document.getElementById('slo-throughput').value) || null,
    },
    telemetry_enabled: document.getElementById('telemetry-enable').checked,
    telemetry_url: document.getElementById('telemetry-url').value.trim() || null,
    telemetry_timeout: 2.0
  };
}

async function validateConfigAction() {
  const payload = collectFormData();
  const notice = document.getElementById('validation-notice');
  const btn = document.getElementById('btn-validate');
  btn.disabled = true;
  btn.textContent = 'Validating...';

  try {
    const res = await fetch('/api/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    notice.style.display = 'block';
    if (data.valid) {
      notice.className = 'validation-banner success';
      const reachability = data.endpoint_reachable
        ? `Endpoint verified (${data.endpoint_detail})`
        : `Note: Endpoint ${data.endpoint_detail}`;
      notice.innerHTML = `<strong>Configuration Valid!</strong> ${reachability}. Workload sweep is ready to execute.`;
      showToast('Configuration is valid!');
    } else {
      notice.className = 'validation-banner error';
      const errors = data.errors || ['Configuration is invalid'];
      notice.innerHTML = `<strong>Validation Failed:</strong><ul>${errors.map(e => `<li>${e}</li>`).join('')}</ul>`;
      showToast('Validation failed');
    }
  } catch (err) {
    notice.style.display = 'block';
    notice.className = 'validation-banner error';
    notice.textContent = `Validation network error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Validate Config`;
  }
}

function resetFormDefaults() {
  document.getElementById('target-base-url').value = 'http://127.0.0.1:11434/v1';
  document.getElementById('target-model').value = discoveredModels[0] || 'qwen2.5:0.5b';
  document.getElementById('sweep-concurrency').value = '1, 2, 4';
  document.getElementById('sweep-repetitions').value = '2';
  document.getElementById('sweep-requests').value = '5';
  document.getElementById('exec-warmup').value = '1';
  document.getElementById('workload-max-tokens').value = '32';
  document.getElementById('workload-temperature').value = '0.0';
  document.getElementById('workload-seed').value = '42';
  document.getElementById('workload-stream').checked = true;
  document.getElementById('arrival-mode').value = 'closed';
  document.getElementById('open-loop-rate-group').style.display = 'none';
  document.getElementById('slo-ttft').value = '1000';
  document.getElementById('slo-latency').value = '2500';
  document.getElementById('slo-error').value = '1.0';
  document.getElementById('slo-throughput').value = '1.0';
  document.getElementById('telemetry-enable').checked = false;
  document.getElementById('telemetry-fields').style.display = 'none';
  document.getElementById('validation-notice').style.display = 'none';

  const container = document.getElementById('prompts-container');
  container.innerHTML = `
    <div class="prompt-entry">
      <input type="text" class="prompt-input" value="What is a database index?" required>
      <button type="button" class="btn-remove-prompt" title="Remove">&times;</button>
    </div>
  `;
  showToast('Configuration reset to defaults.');
}

/* ══════════════════════════════════════════════
   5. BENCHMARK EXECUTION & LOG POLLING
   ══════════════════════════════════════════════ */
async function runBenchmarkAction() {
  const payload = collectFormData();
  const notice = document.getElementById('validation-notice');
  notice.style.display = 'none';

  const btnRun = document.getElementById('btn-run');
  btnRun.disabled = true;
  btnRun.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> Launching...`;

  try {
    const res = await fetch('/api/experiments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      const msgs = errData.detail?.errors || [errData.detail || 'Validation failed'];
      notice.className = 'validation-banner error';
      notice.innerHTML = `<strong>Validation Failed:</strong><ul>${msgs.map(e => `<li>${e}</li>`).join('')}</ul>`;
      notice.style.display = 'block';
      resetRunBtn();
      return;
    }

    const data = await res.json();
    currentJobId = data.job_id;
    showToast('Benchmark experiment launched!');
    startJobTracking(currentJobId);
  } catch (err) {
    notice.style.display = 'block';
    notice.className = 'validation-banner error';
    notice.textContent = `Launch error: ${err.message}`;
    resetRunBtn();
  }
}

function resetRunBtn() {
  const btn = document.getElementById('btn-run');
  btn.disabled = false;
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Run Benchmark`;
}

function startJobTracking(jobId) {
  const progressCard = document.getElementById('progress-card');
  const emptyState = document.getElementById('empty-state');
  const resultsView = document.getElementById('results-view');
  const errorCard = document.getElementById('error-card');
  const terminal = document.getElementById('terminal-output');

  emptyState.style.display = 'none';
  resultsView.style.display = 'none';
  errorCard.style.display = 'none';
  progressCard.style.display = 'flex';
  terminal.textContent = '[System] Job registered. Initializing client and target endpoint...\n';

  // Stepper reset
  resetStepper();
  setStep('step-validation', 'completed');
  setStep('step-running', 'active');

  const startTime = Date.now();
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const mm = Math.floor(elapsed / 60);
    const ss = elapsed % 60;
    setEl('progress-timer', `${mm}m ${ss}s`);

    try {
      // 1. Fetch job state
      const res = await fetch(`/api/experiments/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();

      const current = job.progress_current || 0;
      const total = job.progress_total || 1;
      const pct = Math.min(100, Math.round((current / total) * 100));

      const bar = document.getElementById('progress-bar-fill');
      if (bar) bar.style.width = `${pct}%`;
      setEl('progress-trials', `${current} / ${total} trials`);
      if (job.current_trial) {
        setEl('progress-trial-id', job.current_trial);
      }

      // 2. Fetch job real-time logs
      const logRes = await fetch(`/api/experiments/${jobId}/logs`);
      if (logRes.ok) {
        const logData = await logRes.json();
        if (logData.logs && logData.logs.length > 0) {
          terminal.textContent = logData.logs.join('\n');
          const autoscroll = document.getElementById('terminal-autoscroll');
          if (autoscroll && autoscroll.checked) {
            terminal.scrollTop = terminal.scrollHeight;
          }
        }
      }

      // 3. Completion check
      if (job.status === 'completed') {
        clearInterval(pollInterval);
        setStep('step-running', 'completed');
        setStep('step-analysis', 'completed');
        setStep('step-complete', 'completed');
        if (bar) bar.style.width = '100%';

        setTimeout(() => {
          progressCard.style.display = 'none';
          resetRunBtn();
          renderCompletedExperiment(job);
          showToast('Benchmark sweep completed!');
          loadRecentExperiments();
        }, 600);

      } else if (job.status === 'failed') {
        clearInterval(pollInterval);
        progressCard.style.display = 'none';
        resetRunBtn();
        setEl('error-card-msg', job.error || 'Unknown benchmark execution error');
        errorCard.style.display = 'block';
      }
    } catch (err) {
      console.warn('Polling error:', err);
    }
  }, 750);
}

function resetStepper() {
  ['step-validation', 'step-running', 'step-analysis', 'step-complete'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'stepper-step';
  });
}

function setStep(id, state) {
  const el = document.getElementById(id);
  if (el) el.className = `stepper-step ${state}`;
}

/* ══════════════════════════════════════════════
   6. RENDER COMPLETED EXPERIMENT RESULTS
   ══════════════════════════════════════════════ */
function renderCompletedExperiment(jobData) {
  activeExperimentData = {
    jobId: jobData.job_id,
    expId: jobData.experiment_id,
    artifactsDir: jobData.artifacts_dir,
    isHistorical: false,
    dirName: null,
  };

  const res = jobData.result || {};
  const cap = jobData.capacity || {};
  const points = res.points || [];

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('progress-card').style.display = 'none';
  document.getElementById('results-view').style.display = 'flex';

  // Enable Quick Actions
  ['action-report', 'action-artifacts', 'action-plots'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = false;
  });

  // Capacity Hero
  const highestConc = cap.highest_compliant_concurrency;
  const heroVal = document.getElementById('hero-capacity-value');
  const heroBadge = document.getElementById('hero-capacity-badge');

  if (highestConc !== null && highestConc !== undefined) {
    heroVal.textContent = highestConc;
    heroBadge.textContent = 'SLO COMPLIANT';
    heroBadge.className = 'badge-compliance';
  } else {
    heroVal.textContent = 'None';
    heroBadge.textContent = 'ALL VIOLATED';
    heroBadge.className = 'badge-compliance violation';
  }

  // KPIs
  const compPoint = cap.compliant_point || {};
  setKPI('hero-kpi-throughput', compPoint.throughput_rps, 2);
  setKPI('hero-kpi-ttft', compPoint.ttft_p95_ms, 1);
  setKPI('hero-kpi-latency', compPoint.total_latency_p95_ms, 1);
  setEl('hero-kpi-errors', `${(compPoint.error_rate_pct || 0).toFixed(2)}%`);

  // Tested Concurrencies Table
  const sweepBody = document.getElementById('sweep-table-body');
  sweepBody.innerHTML = '';
  const testedPts = cap.tested_points || [];

  points.forEach(p => {
    const tp = testedPts.find(t => t.concurrency === p.concurrency);
    const isComp = tp ? tp.compliant : true;
    const statusHtml = isComp
      ? '<span class="badge-status compliant">COMPLIANT</span>'
      : '<span class="badge-status violation">VIOLATION</span>';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${p.concurrency}</strong></td>
      <td>${p.repetitions}</td>
      <td>${p.requests_per_point}</td>
      <td>${fmt(p.ttft_p50?.mean, 1)} ms</td>
      <td><strong>${fmt(p.ttft_p95?.mean, 1)} ms</strong></td>
      <td><strong>${fmt(p.latency_p95?.mean, 1)} ms</strong></td>
      <td><strong>${fmt(p.throughput?.mean, 2)} req/s</strong></td>
      <td>${((p.error_rate?.mean || 0) * 100).toFixed(2)}%</td>
      <td>${statusHtml}</td>
    `;
    sweepBody.appendChild(tr);
  });

  // SLO Evaluation Table
  const sloBody = document.getElementById('slo-table-body');
  sloBody.innerHTML = '';
  testedPts.forEach(pt => {
    const isComp = pt.compliant;
    const statusHtml = isComp
      ? '<span class="badge-status compliant">COMPLIANT</span>'
      : '<span class="badge-status violation">VIOLATION</span>';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${pt.concurrency}</strong></td>
      <td>${pt.ttft_p95_ms ? `${pt.ttft_p95_ms.toFixed(1)} ms` : '—'}</td>
      <td>${pt.total_latency_p95_ms ? `${pt.total_latency_p95_ms.toFixed(1)} ms` : '—'}</td>
      <td>${pt.throughput_rps ? `${pt.throughput_rps.toFixed(2)} req/s` : '—'}</td>
      <td>${pt.error_rate_pct.toFixed(2)}%</td>
      <td>${statusHtml}</td>
    `;
    sloBody.appendChild(tr);
  });

  // Saturation
  const satSection = document.getElementById('saturation-section');
  const satFindings = res.saturation_findings || [];
  if (satFindings.length > 0) {
    satSection.style.display = 'block';
    const container = document.getElementById('saturation-findings');
    container.innerHTML = '';
    satFindings.forEach(f => {
      const div = document.createElement('div');
      div.className = 'form-desc-text';
      div.innerHTML = `
        <strong>${f.from_concurrency || '?'} → ${f.to_concurrency || '?'} Concurrency:</strong>
        Throughput change: ${f.throughput_change_pct !== undefined ? f.throughput_change_pct.toFixed(1) + '%' : '—'} |
        Latency p95 change: ${f.latency_change_pct !== undefined ? '+' + f.latency_change_pct.toFixed(1) + '%' : '—'}
      `;
      container.appendChild(div);
    });
  } else {
    satSection.style.display = 'none';
  }

  // Load Graphs
  const ts = Date.now();
  const isHistorical = activeExperimentData.isHistorical;
  let plotBase;
  if (isHistorical && activeExperimentData.dirName) {
    plotBase = `/results/${activeExperimentData.dirName}/plots`;
  } else {
    plotBase = `/api/experiments/${jobData.job_id}/artifacts/plots`;
  }

  setImg('plot-ttft', `${plotBase}/concurrency_vs_ttft_p95.png?t=${ts}`);
  setImg('plot-latency', `${plotBase}/concurrency_vs_total_latency_p95.png?t=${ts}`);
  setImg('plot-throughput', `${plotBase}/concurrency_vs_throughput.png?t=${ts}`);
  setImg('plot-errors', `${plotBase}/concurrency_vs_error_rate.png?t=${ts}`);

  // Load Full Markdown Report
  loadReportMarkdown(jobData.job_id);

  // Render Artifacts Grid
  renderArtifactLinks(jobData.job_id, res.raw_run_ids || []);

  // Update Right-rail Telemetry Status
  const telemDot = document.getElementById('telem-dot');
  const telemText = document.getElementById('telemetry-status-text');
  const telemNote = document.getElementById('telemetry-note');
  if (res.telemetry_before || res.telemetry_after) {
    telemDot.className = 'status-indicator-dot dot-green';
    telemText.textContent = 'Polled';
    telemNote.textContent = 'Prometheus telemetry captured before and after sweep.';
  } else {
    telemDot.className = 'status-indicator-dot dot-gray';
    telemText.textContent = 'Not Enabled';
    telemNote.textContent = 'Telemetry was not enabled for this benchmark run.';
  }
}

function setKPI(id, val, dec) {
  const el = document.getElementById(id);
  if (!el) return;
  if (val !== null && val !== undefined && !isNaN(val)) {
    el.textContent = val.toFixed(dec);
  } else {
    el.textContent = '—';
  }
}

function fmt(val, dec) {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return val.toFixed(dec);
}

function setImg(id, src) {
  const el = document.getElementById(id);
  if (el) el.src = src;
}

async function loadReportMarkdown(jobId) {
  try {
    const res = await fetch(`/api/experiments/${jobId}/report`);
    if (res.ok) {
      const data = await res.json();
      setEl('report-markdown-view', data.report_markdown || 'Report empty.');
    } else {
      setEl('report-markdown-view', 'Report unavailable for this experiment.');
    }
  } catch (err) {
    setEl('report-markdown-view', `Failed to load report: ${err.message}`);
  }
}

function renderArtifactLinks(jobId, rawRunIds) {
  const container = document.getElementById('artifact-links-list');
  if (!container) return;
  container.innerHTML = '';

  const artifacts = [
    { name: 'summary.json', desc: 'Summary metrics & data', file: 'summary.json' },
    { name: 'points.csv', desc: 'Tabular trials CSV', file: 'points.csv' },
    { name: 'report.md', desc: 'Audit Markdown report', file: 'report.md' },
    { name: 'TTFT p95 plot', desc: 'TTFT scaling curve', file: 'plots/concurrency_vs_ttft_p95.png' },
    { name: 'Throughput plot', desc: 'Throughput curve', file: 'plots/concurrency_vs_throughput.png' },
  ];

  artifacts.forEach(art => {
    const a = document.createElement('a');
    a.className = 'artifact-card-link';
    a.href = `/api/experiments/${jobId}/artifacts/${art.file}`;
    a.target = '_blank';
    a.download = art.name;
    a.innerHTML = `
      <span class="artifact-link-name">${art.name}</span>
      <span class="artifact-link-desc">${art.desc}</span>
    `;
    container.appendChild(a);
  });

  const selector = document.getElementById('raw-run-selector');
  if (selector) {
    selector.innerHTML = '<option value="">Select trial to inspect...</option>';
    rawRunIds.forEach(id => {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = `Trial: ${id}`;
      selector.appendChild(opt);
    });
  }
}

/* ══════════════════════════════════════════════
   7. PERFORMANCE GRAPH FILTER TABS
   ══════════════════════════════════════════════ */
function initGraphFilters() {
  const btns = document.querySelectorAll('.filter-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const mode = btn.dataset.graph;
      const cards = {
        ttft: document.getElementById('card-plot-ttft'),
        latency: document.getElementById('card-plot-latency'),
        throughput: document.getElementById('card-plot-throughput'),
        errors: document.getElementById('card-plot-errors'),
      };

      if (mode === 'all') {
        Object.values(cards).forEach(c => { if (c) c.style.display = 'flex'; });
        document.getElementById('plots-grid').style.gridTemplateColumns = '1fr 1fr';
      } else {
        Object.entries(cards).forEach(([key, card]) => {
          if (card) {
            card.style.display = (key === mode) ? 'flex' : 'none';
          }
        });
        document.getElementById('plots-grid').style.gridTemplateColumns = '1fr';
      }
    });
  });
}

/* ══════════════════════════════════════════════
   8. RECENT EXPERIMENTS & HISTORY ARCHIVE
   ══════════════════════════════════════════════ */
async function loadRecentExperiments() {
  const container = document.getElementById('recent-experiments');
  if (!container) return;
  container.innerHTML = '<p class="rail-muted">Scanning...</p>';

  try {
    const res = await fetch('/api/history');
    if (!res.ok) return;
    cachedHistory = await res.json();

    if (cachedHistory.length === 0) {
      container.innerHTML = '<p class="rail-muted">No runs found in results/</p>';
      return;
    }

    container.innerHTML = '';
    cachedHistory.slice(0, 5).forEach(item => {
      const card = document.createElement('div');
      card.className = 'recent-run-item';
      card.innerHTML = `
        <div class="run-item-top">
          <span class="run-item-name">${item.name || 'sweep'}</span>
          <span class="badge-status compliant">${item.highest_compliant_concurrency !== null ? `C=${item.highest_compliant_concurrency}` : 'N/A'}</span>
        </div>
        <div class="run-item-date">${formatDate(item.timestamp)}</div>
        <div class="run-item-meta">${item.model || 'model'} • conc [${(item.concurrency_levels || []).join(',')}]</div>
      `;
      card.addEventListener('click', () => {
        loadHistoricalRun(item.dir_name);
        switchView('view-benchmark');
      });
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<p class="rail-muted">Error: ${err.message}</p>`;
  }
}

async function loadHistoricalRun(dirName) {
  try {
    const res = await fetch(`/api/history/${dirName}`);
    if (!res.ok) {
      showToast('Failed to load experiment data.');
      return;
    }
    const data = await res.json();

    const adaptedJob = {
      job_id: `historical-${dirName}`,
      experiment_id: data.experiment_id,
      artifacts_dir: data.artifacts_dir,
      result: data.result,
      capacity: data.capacity,
      plots: data.plots,
    };

    activeExperimentData = {
      jobId: adaptedJob.job_id,
      expId: data.experiment_id,
      artifactsDir: data.artifacts_dir,
      isHistorical: true,
      dirName: dirName,
    };

    renderCompletedExperiment(adaptedJob);

    if (data.report_markdown) {
      setEl('report-markdown-view', data.report_markdown);
    }

    showToast(`Loaded benchmark: ${dirName}`);
  } catch (err) {
    showToast(`Error: ${err.message}`);
  }
}

function initHistoryControls() {
  const searchInput = document.getElementById('history-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      filterFullHistoryTable(e.target.value.trim().toLowerCase());
    });
  }

  const btnRefresh = document.getElementById('btn-refresh-history');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', loadFullHistoryArchive);
  }
}

async function loadFullHistoryArchive() {
  const tbody = document.getElementById('full-history-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" class="text-center">Scanning results directory...</td></tr>';

  try {
    const res = await fetch('/api/history');
    if (!res.ok) return;
    cachedHistory = await res.json();

    if (cachedHistory.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center">No experiments found in results/</td></tr>';
      return;
    }

    renderFullHistoryTable(cachedHistory);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center">Error: ${err.message}</td></tr>`;
  }
}

function renderFullHistoryTable(items) {
  const tbody = document.getElementById('full-history-tbody');
  tbody.innerHTML = '';

  items.forEach(item => {
    const tr = document.createElement('tr');
    tr.dataset.search = `${item.dir_name} ${item.model} ${item.name}`.toLowerCase();

    const capText = item.highest_compliant_concurrency !== null && item.highest_compliant_concurrency !== undefined
      ? `<span class="badge-status compliant">${item.highest_compliant_concurrency}</span>`
      : `<span class="badge-status violation">None</span>`;

    tr.innerHTML = `
      <td>${formatDate(item.timestamp)}</td>
      <td><strong>${item.dir_name}</strong></td>
      <td>${item.model || '—'}</td>
      <td>[${(item.concurrency_levels || []).join(', ')}]</td>
      <td>${item.repetitions || 1}</td>
      <td>${item.requests_per_point || '—'}</td>
      <td>${capText}</td>
      <td>
        <button type="button" class="btn-micro btn-inspect-row">Inspect</button>
        <button type="button" class="btn-micro btn-load-row">Load Config</button>
      </td>
    `;

    tr.querySelector('.btn-inspect-row').addEventListener('click', () => {
      loadHistoricalRun(item.dir_name);
      switchView('view-benchmark');
    });

    tr.querySelector('.btn-load-row').addEventListener('click', () => {
      if (item.model) document.getElementById('target-model').value = item.model;
      if (item.concurrency_levels) document.getElementById('sweep-concurrency').value = item.concurrency_levels.join(', ');
      if (item.repetitions) document.getElementById('sweep-repetitions').value = item.repetitions;
      if (item.requests_per_point) document.getElementById('sweep-requests').value = item.requests_per_point;
      switchView('view-benchmark');
      showToast('Config populated from experiment.');
    });

    tbody.appendChild(tr);
  });
}

function filterFullHistoryTable(query) {
  const rows = document.querySelectorAll('#full-history-tbody tr');
  rows.forEach(r => {
    if (!query) {
      r.style.display = '';
      return;
    }
    const searchData = r.dataset.search || '';
    r.style.display = searchData.includes(query) ? '' : 'none';
  });
}

/* ══════════════════════════════════════════════
   9. DEDICATED REPORTS VIEWER
   ══════════════════════════════════════════════ */
function initReportsView() {
  const selector = document.getElementById('report-exp-selector');
  if (selector) {
    selector.addEventListener('change', async (e) => {
      const dirName = e.target.value;
      if (!dirName) return;
      await displayDedicatedReport(dirName);
    });
  }

  const btnCopy = document.getElementById('btn-copy-dedicated-report');
  if (btnCopy) {
    btnCopy.addEventListener('click', () => {
      const canvas = document.getElementById('dedicated-report-markdown');
      navigator.clipboard.writeText(canvas.textContent).then(() => {
        showToast('Report copied to clipboard!');
      });
    });
  }
}

async function populateReportsSelector() {
  const selector = document.getElementById('report-exp-selector');
  if (!selector) return;

  if (cachedHistory.length === 0) {
    try {
      const res = await fetch('/api/history');
      if (res.ok) cachedHistory = await res.json();
    } catch {}
  }

  selector.innerHTML = '<option value="">Select an experiment...</option>';
  cachedHistory.forEach(item => {
    const opt = document.createElement('option');
    opt.value = item.dir_name;
    opt.textContent = `${item.dir_name} (${item.model || 'model'})`;
    selector.appendChild(opt);
  });

  if (cachedHistory.length > 0) {
    selector.value = cachedHistory[0].dir_name;
    displayDedicatedReport(cachedHistory[0].dir_name);
  }
}

async function displayDedicatedReport(dirName) {
  const canvas = document.getElementById('dedicated-report-markdown');
  const sub = document.getElementById('report-view-subtitle');
  canvas.textContent = `Loading report for ${dirName}...`;

  try {
    const res = await fetch(`/api/experiments/historical-${dirName}/report`);
    if (res.ok) {
      const data = await res.json();
      canvas.textContent = data.report_markdown || 'Report content empty.';
      if (sub) sub.textContent = `Report: ${dirName}`;
    } else {
      canvas.textContent = `Report not found for ${dirName}.`;
    }
  } catch (err) {
    canvas.textContent = `Error loading report: ${err.message}`;
  }
}

/* ══════════════════════════════════════════════
   10. SETTINGS & TELEMETRY TESTING
   ══════════════════════════════════════════════ */
function initSettingsControls() {
  const btnTest = document.getElementById('btn-test-telemetry');
  if (btnTest) {
    btnTest.addEventListener('click', async () => {
      const url = document.getElementById('settings-telemetry-url').value.trim();
      const feedback = document.getElementById('telemetry-test-result');
      feedback.textContent = 'Testing connection...';
      feedback.style.color = '#94a3b8';

      try {
        const t0 = performance.now();
        const res = await fetch(url, { method: 'HEAD', mode: 'no-cors' });
        const latency = Math.round(performance.now() - t0);
        feedback.textContent = `Reachable (${latency}ms)`;
        feedback.style.color = '#34d399';
        showToast('Telemetry endpoint reachable!');
      } catch (err) {
        feedback.textContent = `Connection refused (${err.message})`;
        feedback.style.color = '#f87171';
      }
    });
  }
}

/* ── Date Formatter ── */
function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return isoStr.substring(0, 16);
  }
}
