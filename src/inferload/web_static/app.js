/* ============================================================
   InferLoad — Web Console Frontend Logic
   Drives the 3-column engineering dashboard: nav, center, right
   ============================================================ */

let currentJobId = null;
let pollInterval = null;
let activeExperimentData = null;
let discoveredModels = [];

document.addEventListener('DOMContentLoaded', () => {
  initHealth();
  initConfigTabs();
  initFormControls();
  initPerfTabs();
  loadRecentExperiments();
});

/* ── Toast ── */
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

/* ══════════════════════════════════════
   1. HEALTH & ENVIRONMENT DISCOVERY
   ══════════════════════════════════════ */
async function initHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const data = await res.json();

    const env = data.environment || {};
    const ollama = data.ollama || {};

    // Right sidebar environment
    setEnv('env-os', `${env.os_system || '—'} (${env.os_version || ''})`);
    setEnv('env-python', env.python_version || '—');
    setEnv('env-cpu', `${env.cpu_architecture || '—'} (${env.cpu_cores || '—'} cores)`);
    setEnv('env-ram', env.ram_total_gb ? `${env.ram_total_gb} GB` : '—');
    setEnv('env-gpu', env.gpu_info || 'Unavailable');
    setEnv('env-cuda', env.cuda_version || 'Unavailable');
    setEnv('env-inferload', `v${data.inferload_version || '0.1.0'}`);

    // Version badge
    document.getElementById('version-badge').textContent = `v${data.inferload_version || '0.1.0'}`;

    // Nav footer
    document.getElementById('nav-env-label').textContent = `${env.os_system || 'Host'} | ${env.cpu_cores || '?'} cores`;

    // Model dropdown
    if (ollama.available && ollama.models && ollama.models.length > 0) {
      discoveredModels = ollama.models;
      buildModelDropdown(ollama.models);
    }

    // Server URL label
    const baseUrl = document.getElementById('target-base-url').value;
    document.getElementById('server-url-label').textContent = baseUrl;
  } catch (err) {
    console.error('Health check failed:', err);
  }
}

function setEnv(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function buildModelDropdown(models) {
  const dropdown = document.getElementById('model-dropdown');
  dropdown.innerHTML = '';
  models.forEach(m => {
    const opt = document.createElement('div');
    opt.className = 'model-option';
    opt.textContent = m;
    opt.addEventListener('click', () => {
      document.getElementById('target-model').value = m;
      dropdown.classList.remove('open');
      showToast(`Model selected: ${m}`);
    });
    dropdown.appendChild(opt);
  });

  const modelInput = document.getElementById('target-model');
  modelInput.addEventListener('focus', () => {
    if (dropdown.children.length > 0) dropdown.classList.add('open');
  });
  modelInput.addEventListener('blur', () => {
    setTimeout(() => dropdown.classList.remove('open'), 150);
  });
}

/* ══════════════════════════════════════
   2. CONFIG TABS
   ══════════════════════════════════════ */
function initConfigTabs() {
  const tabs = document.querySelectorAll('.config-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.config-tab-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const pane = document.getElementById(tab.dataset.ctab);
      if (pane) pane.classList.add('active');
    });
  });
}

/* ══════════════════════════════════════
   3. PERF GRAPH TABS
   ══════════════════════════════════════ */
function initPerfTabs() {
  const tabs = document.querySelectorAll('.perf-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      // All plots are shown in 4-column grid; tabs just highlight active
      // We could toggle visibility but showing all is more useful
    });
  });
}

/* ══════════════════════════════════════
   4. FORM CONTROLS
   ══════════════════════════════════════ */
function initFormControls() {
  // Add prompt
  document.getElementById('btn-add-prompt').addEventListener('click', () => {
    const container = document.getElementById('prompts-container');
    const entry = document.createElement('div');
    entry.className = 'prompt-entry';
    entry.innerHTML = `
      <input type="text" class="prompt-input" placeholder="Enter benchmark prompt..." required>
      <button type="button" class="btn-remove-prompt" title="Remove">&times;</button>
    `;
    entry.querySelector('.btn-remove-prompt').addEventListener('click', () => {
      if (container.children.length > 1) entry.remove();
      else showToast('At least one prompt is required.');
    });
    container.appendChild(entry);
  });

  // Remove prompt (delegated)
  document.getElementById('prompts-container').addEventListener('click', (e) => {
    if (e.target.classList.contains('btn-remove-prompt')) {
      const container = document.getElementById('prompts-container');
      if (container.children.length > 1) {
        e.target.closest('.prompt-entry').remove();
      } else {
        showToast('At least one prompt is required.');
      }
    }
  });

  // Arrival mode
  document.getElementById('arrival-mode').addEventListener('change', (e) => {
    document.getElementById('open-loop-rate-group').style.display =
      e.target.value === 'rate' ? 'flex' : 'none';
  });

  // Telemetry toggle
  document.getElementById('telemetry-enable').addEventListener('change', (e) => {
    document.getElementById('telemetry-fields').style.display =
      e.target.checked ? 'block' : 'none';
  });

  // Form submit (all 3 run buttons trigger same form submit)
  document.getElementById('benchmark-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    await runBenchmark();
  });

  // Dismiss error
  document.getElementById('btn-dismiss-error').addEventListener('click', () => {
    document.getElementById('error-card').style.display = 'none';
  });

  // Copy report
  document.getElementById('btn-copy-report').addEventListener('click', () => {
    const text = document.getElementById('report-markdown-view').textContent;
    navigator.clipboard.writeText(text).then(() => showToast('Report copied to clipboard!'));
  });

  // Quick Actions
  document.getElementById('action-report').addEventListener('click', () => {
    const details = document.querySelectorAll('.results-detail-section');
    if (details[0]) { details[0].open = true; details[0].scrollIntoView({ behavior: 'smooth' }); }
  });
  document.getElementById('action-artifacts').addEventListener('click', () => {
    const details = document.querySelectorAll('.results-detail-section');
    if (details[1]) { details[1].open = true; details[1].scrollIntoView({ behavior: 'smooth' }); }
  });
  document.getElementById('action-plots').addEventListener('click', () => {
    const section = document.querySelector('.perf-graphs-section');
    if (section) section.scrollIntoView({ behavior: 'smooth' });
  });

  // View All History
  document.getElementById('btn-view-all-history').addEventListener('click', loadRecentExperiments);

  // Raw run selector
  document.getElementById('raw-run-selector').addEventListener('change', async (e) => {
    const runId = e.target.value;
    if (!runId || !activeExperimentData) return;
    const jsonOut = document.getElementById('raw-json-output');
    jsonOut.textContent = 'Loading trial records...';
    try {
      const artifactUrl = `/api/experiments/${activeExperimentData.jobId}/artifacts/raw/${runId}.json`;
      const res = await fetch(artifactUrl);
      if (res.ok) {
        const data = await res.json();
        jsonOut.textContent = JSON.stringify(data, null, 2);
      } else {
        jsonOut.textContent = `Could not load raw record for ${runId}.`;
      }
    } catch (err) {
      jsonOut.textContent = `Failed: ${err.message}`;
    }
  });
}

/* ══════════════════════════════════════
   5. COLLECT FORM DATA
   ══════════════════════════════════════ */
function collectFormData() {
  const concInput = document.getElementById('sweep-concurrency').value;
  const concList = concInput.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n) && n > 0);
  const promptInputs = Array.from(document.querySelectorAll('.prompt-input'));
  const prompts = promptInputs.map(i => i.value.trim()).filter(p => p.length > 0);
  const arrivalMode = document.getElementById('arrival-mode').value;

  return {
    name: 'web-sweep',
    description: 'InferLoad benchmark launched via browser UI',
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

/* ══════════════════════════════════════
   6. RUN BENCHMARK
   ══════════════════════════════════════ */
async function runBenchmark() {
  const payload = collectFormData();
  const valBox = document.getElementById('validation-errors');
  valBox.style.display = 'none';

  const btnRun = document.getElementById('btn-run');
  btnRun.disabled = true;
  btnRun.innerHTML = `<span style="animation:spin 1s linear infinite;display:inline-block">⏳</span> Launching...`;

  try {
    const res = await fetch('/api/experiments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      const msgs = errData.detail?.errors || [errData.detail || 'Validation failed'];
      valBox.innerHTML = `<strong>Validation Errors:</strong><ul>${msgs.map(e => `<li>${e}</li>`).join('')}</ul>`;
      valBox.style.display = 'block';
      resetRunButton();
      return;
    }

    const data = await res.json();
    currentJobId = data.job_id;
    showToast('Benchmark experiment started!');
    startJobTracking(currentJobId);
  } catch (err) {
    valBox.textContent = `Launch error: ${err.message}`;
    valBox.style.display = 'block';
    resetRunButton();
  }
}

function resetRunButton() {
  const btn = document.getElementById('btn-run');
  btn.disabled = false;
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Run Benchmark`;
}

/* ══════════════════════════════════════
   7. JOB TRACKING & PROGRESS
   ══════════════════════════════════════ */
function startJobTracking(jobId) {
  const progressCard = document.getElementById('progress-card');
  const emptyState = document.getElementById('empty-state');
  const resultsView = document.getElementById('results-view');
  const errorCard = document.getElementById('error-card');

  emptyState.style.display = 'none';
  resultsView.style.display = 'none';
  errorCard.style.display = 'none';
  progressCard.style.display = 'block';

  // Reset stepper
  resetStepper();
  setStepState('step-validation', 'completed', '1s');
  setStepState('step-running', 'active');

  const startTime = Date.now();
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const mm = Math.floor(elapsed / 60);
    const ss = elapsed % 60;
    document.getElementById('progress-timer').textContent = `${mm}m ${ss}s`;
    document.getElementById('step-running-time').textContent = `${mm}m ${ss}s`;

    try {
      const res = await fetch(`/api/experiments/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();

      const current = job.progress_current || 0;
      const total = job.progress_total || 1;
      const pct = Math.min(100, Math.round((current / total) * 100));

      document.getElementById('progress-bar-fill').style.width = `${pct}%`;
      document.getElementById('progress-trials').textContent = `${current} / ${total} trials`;
      if (job.current_trial) {
        document.getElementById('progress-trial-id').textContent = job.current_trial;
      }

      if (job.status === 'completed') {
        clearInterval(pollInterval);
        const totalElapsed = Math.floor((Date.now() - startTime) / 1000);
        setStepState('step-running', 'completed', `${Math.floor(totalElapsed * 0.85)}s`);
        setStepState('step-analysis', 'completed', `${Math.floor(totalElapsed * 0.1)}s`);
        setStepState('step-complete', 'completed', `${mm}m ${ss}s`);

        document.getElementById('progress-bar-fill').style.width = '100%';

        // Brief delay to show completion animation
        setTimeout(() => {
          const statusHeader = document.querySelector('.status-header');
          const dot = statusHeader.querySelector('.dot');
          dot.classList.remove('dot-pulse', 'dot-blue');
          dot.classList.add('dot-green');
          document.querySelector('.status-label').textContent = `Benchmark Completed (${mm}m ${ss}s)`;

          setTimeout(() => {
            progressCard.style.display = 'none';
            resetRunButton();
            renderCompletedExperiment(job);
            showToast('Benchmark completed successfully!');
            loadRecentExperiments();
          }, 800);
        }, 300);

      } else if (job.status === 'failed') {
        clearInterval(pollInterval);
        progressCard.style.display = 'none';
        resetRunButton();
        document.getElementById('error-card-msg').textContent = job.error || 'Unknown error';
        errorCard.style.display = 'block';
      }
    } catch (err) {
      console.error('Polling error:', err);
    }
  }, 750);
}

function resetStepper() {
  ['step-validation', 'step-running', 'step-analysis', 'step-complete'].forEach(id => {
    const el = document.getElementById(id);
    el.className = 'step';
    const time = el.querySelector('.step-time');
    if (time) time.textContent = '';
  });
}

function setStepState(id, state, timeText) {
  const el = document.getElementById(id);
  el.className = `step ${state}`;
  if (timeText) {
    const time = el.querySelector('.step-time');
    if (time) time.textContent = timeText;
  }
}

/* ══════════════════════════════════════
   8. RENDER COMPLETED EXPERIMENT
   ══════════════════════════════════════ */
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
  document.getElementById('results-view').style.display = 'block';

  // Enable quick actions
  document.getElementById('action-report').disabled = false;
  document.getElementById('action-artifacts').disabled = false;
  document.getElementById('action-plots').disabled = false;

  // Capacity Hero
  const highestConc = cap.highest_compliant_concurrency;
  const heroValue = document.getElementById('hero-capacity-value');
  const heroBadge = document.getElementById('hero-capacity-badge');

  if (highestConc !== null && highestConc !== undefined) {
    heroValue.textContent = highestConc;
    heroBadge.textContent = 'SLO COMPLIANT';
    heroBadge.className = 'hero-badge';
  } else {
    heroValue.textContent = 'None';
    heroBadge.textContent = 'ALL VIOLATED';
    heroBadge.className = 'hero-badge violation';
  }

  // Quick Results KPIs
  const compPoint = cap.compliant_point || {};
  setKPI('hero-kpi-throughput', compPoint.throughput_rps, 2);
  setKPI('hero-kpi-ttft', compPoint.ttft_p95_ms, 1);
  setKPI('hero-kpi-latency', compPoint.total_latency_p95_ms, 1);
  document.getElementById('hero-kpi-errors').textContent = `${((compPoint.error_rate_pct || 0.0)).toFixed(2)}%`;

  // Sweep Results Table
  const sweepBody = document.getElementById('sweep-table-body');
  sweepBody.innerHTML = '';
  const testedPts = cap.tested_points || [];

  points.forEach(p => {
    const tp = testedPts.find(t => t.concurrency === p.concurrency);
    const isComp = tp ? tp.compliant : true;
    const statusHtml = isComp
      ? '<span class="status-compliant">COMPLIANT</span>'
      : '<span class="status-violation">VIOLATION</span>';

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

  // SLO Compliance Table
  const sloBody = document.getElementById('slo-table-body');
  sloBody.innerHTML = '';
  testedPts.forEach(pt => {
    const isComp = pt.compliant;
    const statusHtml = isComp
      ? '<span class="status-compliant">COMPLIANT</span>'
      : '<span class="status-violation">VIOLATION</span>';
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
      div.className = 'sat-finding';
      div.innerHTML = `
        <div class="sat-finding-title">${f.from_concurrency || '?'} → ${f.to_concurrency || '?'} concurrency</div>
        <div class="sat-finding-detail">
          • Throughput: ${f.throughput_change_pct !== undefined ? f.throughput_change_pct.toFixed(1) + '%' : '—'}<br>
          • p95 latency: ${f.latency_change_pct !== undefined ? '+' + f.latency_change_pct.toFixed(1) + '%' : '—'}<br>
          <em>Possible contention; requires server telemetry.</em>
        </div>
      `;
      container.appendChild(div);
    });
  } else {
    satSection.style.display = 'none';
  }

  // Plots
  const ts = Date.now();
  const isHistorical = activeExperimentData.isHistorical;
  let plotBase;
  if (isHistorical && activeExperimentData.dirName) {
    plotBase = `/results/${activeExperimentData.dirName}/plots`;
  } else {
    plotBase = `/api/experiments/${jobData.job_id}/artifacts/plots`;
  }
  document.getElementById('plot-ttft').src = `${plotBase}/concurrency_vs_ttft_p95.png?t=${ts}`;
  document.getElementById('plot-latency').src = `${plotBase}/concurrency_vs_total_latency_p95.png?t=${ts}`;
  document.getElementById('plot-throughput').src = `${plotBase}/concurrency_vs_throughput.png?t=${ts}`;
  document.getElementById('plot-errors').src = `${plotBase}/concurrency_vs_error_rate.png?t=${ts}`;

  // Report
  loadReport(jobData.job_id, isHistorical);

  // Artifacts
  renderArtifacts(jobData.job_id, jobData.artifacts_dir, res.raw_run_ids || []);

  // Telemetry status
  const telemStatus = document.getElementById('telemetry-status');
  const telemNote = document.getElementById('telemetry-note');
  if (res.telemetry_before || res.telemetry_after) {
    telemStatus.innerHTML = '<span class="dot dot-green"></span><span>Available</span>';
    telemNote.textContent = 'Prometheus telemetry was polled for this run.';
  } else {
    telemStatus.innerHTML = '<span class="dot dot-red"></span><span>Not Available</span>';
    telemNote.textContent = 'Telemetry was not enabled for this benchmark run.';
  }
}

function setKPI(id, value, decimals) {
  const el = document.getElementById(id);
  if (value !== null && value !== undefined && !isNaN(value)) {
    el.textContent = value.toFixed(decimals);
  } else {
    el.textContent = '—';
  }
}

function fmt(val, dec) {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return val.toFixed(dec);
}

async function loadReport(jobId, isHistorical) {
  try {
    if (isHistorical) return; // report was loaded via history endpoint
    const res = await fetch(`/api/experiments/${jobId}/report`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('report-markdown-view').textContent = data.report_markdown || 'Report empty.';
    }
  } catch (err) {
    document.getElementById('report-markdown-view').textContent = 'Failed to load report.';
  }
}

function renderArtifacts(jobId, artifactsDir, rawRunIds) {
  const container = document.getElementById('artifact-links-list');
  container.innerHTML = '';

  const artifacts = [
    { name: 'summary.json', desc: 'Machine-readable results', file: 'summary.json' },
    { name: 'points.csv', desc: 'Tabular per-trial data', file: 'points.csv' },
    { name: 'report.md', desc: 'Full Markdown report', file: 'report.md' },
    { name: 'TTFT p95 plot', desc: 'Concurrency scaling', file: 'plots/concurrency_vs_ttft_p95.png' },
    { name: 'Throughput plot', desc: 'Throughput scaling', file: 'plots/concurrency_vs_throughput.png' },
  ];

  artifacts.forEach(art => {
    const a = document.createElement('a');
    a.className = 'artifact-card';
    a.href = `/api/experiments/${jobId}/artifacts/${art.file}`;
    a.target = '_blank';
    a.download = art.name;
    a.innerHTML = `
      <span class="artifact-name">${art.name}</span>
      <span class="artifact-desc">${art.desc}</span>
    `;
    container.appendChild(a);
  });

  const selector = document.getElementById('raw-run-selector');
  selector.innerHTML = '<option value="">Select trial to inspect...</option>';
  rawRunIds.forEach(id => {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = `Trial: ${id}`;
    selector.appendChild(opt);
  });
}

/* ══════════════════════════════════════
   9. RECENT EXPERIMENTS (RIGHT SIDEBAR)
   ══════════════════════════════════════ */
async function loadRecentExperiments() {
  const container = document.getElementById('recent-experiments');
  container.innerHTML = '<p class="rs-muted">Scanning...</p>';

  try {
    const res = await fetch('/api/history');
    if (!res.ok) return;
    const history = await res.json();

    if (history.length === 0) {
      container.innerHTML = '<p class="rs-muted">No experiments found in results/</p>';
      return;
    }

    container.innerHTML = '';
    // Show latest 5
    history.slice(0, 5).forEach(item => {
      const card = document.createElement('div');
      card.className = 'recent-exp-card';
      card.innerHTML = `
        <div class="recent-exp-top">
          <span class="recent-exp-name">${item.name || 'sweep'}</span>
          <span class="recent-exp-status completed">Completed</span>
        </div>
        <div class="recent-exp-date">${formatDate(item.timestamp)}</div>
        <div class="recent-exp-detail">${item.model || 'model'} • ${(item.concurrency_levels || []).join(', ')} • ${item.repetitions || 1} reps</div>
      `;
      card.addEventListener('click', () => loadHistoricalRun(item.dir_name));
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<p class="rs-muted">Error: ${err.message}</p>`;
  }
}

async function loadHistoricalRun(dirName) {
  try {
    const res = await fetch(`/api/history/${dirName}`);
    if (!res.ok) {
      showToast('Failed to load experiment');
      return;
    }
    const data = await res.json();

    // Adapt to renderCompletedExperiment structure
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

    // Load report from history endpoint
    if (data.report_markdown) {
      document.getElementById('report-markdown-view').textContent = data.report_markdown;
    }

    // Fix plot paths for historical
    const ts = Date.now();
    document.getElementById('plot-ttft').src = `/results/${dirName}/plots/concurrency_vs_ttft_p95.png?t=${ts}`;
    document.getElementById('plot-latency').src = `/results/${dirName}/plots/concurrency_vs_total_latency_p95.png?t=${ts}`;
    document.getElementById('plot-throughput').src = `/results/${dirName}/plots/concurrency_vs_throughput.png?t=${ts}`;
    document.getElementById('plot-errors').src = `/results/${dirName}/plots/concurrency_vs_error_rate.png?t=${ts}`;

    showToast(`Loaded: ${dirName}`);
  } catch (err) {
    showToast(`Error: ${err.message}`);
  }
}

/* ── Helpers ── */
function formatDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return isoStr.substring(0, 16);
  }
}

/* Spin keyframes for loading button */
const style = document.createElement('style');
style.textContent = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
document.head.appendChild(style);
