(() => {
  const agentSelect = document.getElementById('agentSelect');
  const timeRangeSelect = document.getElementById('timeRangeSelect');
  const refreshBtn = document.getElementById('refreshBtn');
  const openAgentPage = document.getElementById('openAgentPage');
  const kpiTotal = document.getElementById('kpiTotal');
  const kpiSuccess = document.getElementById('kpiSuccess');
  const kpiErrors = document.getElementById('kpiErrors');
  const kpiAgent = document.getElementById('kpiAgent');
  const agentsTable = document.getElementById('agentsTable');
  const runsTable = document.getElementById('runsTable');
  const runDetail = document.getElementById('runDetail');
  const searchInput = document.getElementById('searchInput');
  const statusSelect = document.getElementById('statusSelect');
  let latencyChart;
  let statusChart;

  // Agent configuration with colors and metadata
  const AGENTS = {
    'rumor': { name: 'Rumor', color: '#8b5cf6', className: 'agent-rumor', icon: '📰' },
    'triage': { name: 'Triage', color: '#06b6d4', className: 'agent-triage', icon: '⚕️' },
    'mental_health': { name: 'Mental Health', color: '#ec4899', className: 'agent-mental', icon: '🧠' },
    'qa': { name: 'Q&A', color: '#f59e0b', className: 'agent-qa', icon: '❓' }
  };

  function getAgentInfo(runName) {
    const name = runName?.toLowerCase() || '';
    for (const [key, info] of Object.entries(AGENTS)) {
      if (name.includes(key.toLowerCase())) {
        return info;
      }
    }
    return { name: 'Other', color: '#6b7280', className: 'agent-other', icon: '⚙️' };
  }

  const prefsKey = 'langsmith_dashboard_prefs';
  function loadPrefs() {
    try {
      const raw = localStorage.getItem(prefsKey);
      if (!raw) return {};
      return JSON.parse(raw);
    } catch { return {}; }
  }
  function savePrefs(p) {
    try { localStorage.setItem(prefsKey, JSON.stringify(p)); } catch {}
  }
  const prefs = loadPrefs();
  if (prefs.timeRange) timeRangeSelect.value = prefs.timeRange;
  if (prefs.agent) kpiAgent.textContent = prefs.agent;
  if (openAgentPage) {
    openAgentPage.addEventListener('click', (e) => {
      e.preventDefault();
      const ag = agentSelect.value;
      if (ag) window.location.href = `/chat/dashboard/langsmith/agent/${encodeURIComponent(ag)}/`;
    });
  }

  async function fetchJSON(url) {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    return await res.json();
  }

  function formatNumber(n) { return (n || 0).toLocaleString('en-US'); }
  function round(n, d=1) { return Math.round((n || 0) * Math.pow(10, d)) / Math.pow(10, d); }

  async function loadStats() {
    console.time('loadStats_total');
    const tr = timeRangeSelect.value;
    console.time('fetch_stats');
    const data = await fetchJSON(`/chat/api/langsmith/stats/?time_range=${encodeURIComponent(tr)}`);
    console.timeEnd('fetch_stats');
    if (!data.available) {
      kpiTotal.textContent = 'N/A';
      kpiSuccess.textContent = 'N/A';
      kpiErrors.textContent = 'N/A';
      agentsTable.innerHTML = `<tr><td colspan="5" class="p-2">${data.reason || 'LangSmith indisponible'}</td></tr>`;
      return;
    }
    kpiTotal.textContent = formatNumber(data.total_runs);
    kpiSuccess.textContent = formatNumber(data.success);
    kpiErrors.textContent = formatNumber(data.errors);

    const agents = data.agents || [];
    agentSelect.innerHTML = '<option value="">All</option>' + agents.map(a => `<option value="${a.name}">${a.name}</option>`).join('');
    if (prefs.agent) agentSelect.value = prefs.agent;

    agentsTable.innerHTML = agents.map(a => `
      <tr class="hover:bg-gray-50 transition-all">
        <td class="p-2 text-gray-900">${a.name}</td>
        <td class="p-2 text-right text-gray-900">${formatNumber(a.count)}</td>
        <td class="p-2 text-right ${a.errors>0?'status-err':'status-ok'}">${formatNumber(a.errors)}</td>
        <td class="p-2 text-right text-gray-900">${round(a.avg_latency_ms, 0)}</td>
        <td class="p-2 text-right text-gray-900">${round(a.avg_total_tokens, 1)}</td>
      </tr>
    `).join('');

    const labels = agents.map(a => a.name);
    const latencies = agents.map(a => round(a.avg_latency_ms, 0));
    const ctx1 = document.getElementById('latencyChart').getContext('2d');
    if (latencyChart) latencyChart.destroy();
    latencyChart = new Chart(ctx1, {
      type: 'bar',
      data: { 
        labels, 
        datasets: [{ 
          label: 'Latency (ms)', 
          data: latencies, 
          backgroundColor: labels.map(l => {
            const ag = Object.values(AGENTS).find(a => l.includes(a.name));
            return ag ? ag.color : '#6b7280';
          }),
          borderColor: '#e5e7eb',
          borderWidth: 1
        }] 
      },
      options: { 
        responsive: true, 
        maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { color: '#6b7280' }, grid: { color: 'rgba(229,231,235,0.5)' } },
          x: { ticks: { color: '#6b7280' }, grid: { display: false } }
        }
      }
    });

    const ctx2 = document.getElementById('statusChart').getContext('2d');
    if (statusChart) statusChart.destroy();
    statusChart = new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: ['Success', 'Errors'],
        datasets: [{ 
          data: [data.success, data.errors], 
          backgroundColor: ['#10b981', '#ef4444'],
          borderColor: '#1e293b',
          borderWidth: 2
        }]
      },
        options: { 
          responsive: true,
          maintainAspectRatio: true,
          plugins: { legend: { labels: { color: '#2d3748', font: { size: 12 } } } }
        }
    });

    if (agentSelect.value) {
      await loadAgent(agentSelect.value);
    }

    await loadRuns();
    console.timeEnd('loadStats_total');
  }

  async function loadAgent(name) {
    const tr = timeRangeSelect.value;
    const data = await fetchJSON(`/chat/api/langsmith/agent/${encodeURIComponent(name)}/stats/?time_range=${encodeURIComponent(tr)}`);
    if (!data.available) return;
    kpiAgent.textContent = data.agent;
    if (document.body.dataset.agent) {
      const sel = document.getElementById('agentSelect');
      if (sel) sel.disabled = true;
      const charts = document.getElementById('overviewCharts');
      const summary = document.getElementById('agentsSummarySection');
      if (charts) charts.classList.add('hidden');
      if (summary) summary.classList.add('hidden');
    }
  }

  async function loadRuns() {
    console.time('loadRuns_total');
    const tr = timeRangeSelect.value;
    const ag = agentSelect.value;
    const st = statusSelect.value;
    console.time('fetch_runs');
    const resp = await fetchJSON(`/chat/api/langsmith/runs/?time_range=${encodeURIComponent(tr)}&agent=${encodeURIComponent(ag||'')}&status=${encodeURIComponent(st||'')}&limit=200&with_io=false`);
    console.timeEnd('fetch_runs');
    if (!resp.available) {
      runsTable.innerHTML = `<tr><td colspan="6" class="p-2 text-center text-gray-500">${resp.reason||'Unavailable'}</td></tr>`;
      console.timeEnd('loadRuns_total');
      return;
    }
    const q = (searchInput.value||'').toLowerCase();
    const rows = (resp.runs||[]).filter(r => {
      if (!q) return true;
      const s = `${r.name} ${r.agent}`.toLowerCase();
      return s.includes(q);
    });
    
    runsTable.innerHTML = rows.map(r => {
      const agentInfo = getAgentInfo(r.agent);
      const statusClass = r.status === 'success' ? 'success' : r.status === 'error' ? 'error' : 'pending';
      return `
        <tr class="cursor-pointer hover:bg-gray-50 transition-all" data-id="${r.id}">
          <td class="p-2">
            <div class="flex items-center gap-2">
              <span>${agentInfo.icon}</span>
              <span class="text-gray-900">${r.name}</span>
            </div>
          </td>
          <td class="p-2">
            <span class="agent-badge ${agentInfo.className}">
              ${agentInfo.name}
            </span>
          </td>
          <td class="p-2 text-right">
            <span class="status-badge ${statusClass}">
              <span class="status-dot ${statusClass}"></span>
              ${r.status}
            </span>
          </td>
          <td class="p-2 text-right text-amber-600 font-semibold">${round(r.latency_ms,0)} ms</td>
          <td class="p-2 text-right text-blue-600">${formatNumber(r.total_tokens||0)}</td>
          <td class="p-2 text-right text-gray-600">${r.end_time? new Date(r.end_time).toLocaleString('en-US'):''}</td>
        </tr>
      `;
    }).join('');
    
    runsTable.querySelectorAll('tr[data-id]').forEach(trEl => {
      trEl.addEventListener('click', () => {
        const id = trEl.getAttribute('data-id');
        loadRunDetail(id);
      });
    });
    console.timeEnd('loadRuns_total');
  }

  async function loadRunDetail(id) {
    console.time('loadRunDetail_total');
    console.time('fetch_run_detail');
    const resp = await fetchJSON(`/chat/api/langsmith/runs/${encodeURIComponent(id)}/?with_io=true`);
    console.timeEnd('fetch_run_detail');
    if (!resp.available) {
      runDetail.innerHTML = `<div class="text-red-400">⚠️ ${resp.reason||'Unavailable'}</div>`;
      console.timeEnd('loadRunDetail_total');
      return;
    }
    const r = resp.run;
    const agentInfo = getAgentInfo(r.agent);
    const statusClass = r.status === 'success' ? 'success' : r.status === 'error' ? 'error' : 'pending';
    
    // Build trace/flow visualization
    const traceHtml = (r.nodes||[]).length > 0 ? `
      <div class="run-detail-section">
        <div class="run-detail-section-title">⚡ Waterfall - Execution</div>
        <div class="trace-container">
          ${r.nodes.map((n, idx) => `
            <div class="trace-item" style="border-left-color: ${agentInfo.color}">
              <div class="trace-item-name">${idx + 1}. ${n.name}</div>
              <div class="trace-item-time">Latency: ${round(n.latency_ms, 1)} ms</div>
              ${n.status ? `<span class="trace-item-status status-${n.status}">${n.status.toUpperCase()}</span>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    ` : '';

    const io = `
      <div class="run-detail-section">
        <div class="run-detail-section-title">📥 Input</div>
        <div class="run-detail-content">${escapeHtml(JSON.stringify(r.inputs||{}, null, 2))}</div>
      </div>
      <div class="run-detail-section">
        <div class="run-detail-section-title">📤 Output</div>
        <div class="run-detail-content">${escapeHtml(JSON.stringify(r.outputs||{}, null, 2))}</div>
      </div>
    `;
    
    runDetail.innerHTML = `
      <div class="run-detail-header" style="border-left-color: ${agentInfo.color}">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span style="font-size: 1.5rem">${agentInfo.icon}</span>
            <span class="agent-badge ${agentInfo.className}">${agentInfo.name}</span>
          </div>
          <span class="status-badge ${statusClass}">
            <span class="status-dot ${statusClass}"></span>
            ${r.status ? r.status.toUpperCase() : 'UNKNOWN'}
          </span>
        </div>
        <div class="text-sm text-gray-500">${r.name}</div>
      </div>
      
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div>
          <div class="text-xs text-gray-500 mb-1">LATENCY</div>
          <div class="text-lg font-bold text-amber-600">${round(r.latency_ms, 1)} ms</div>
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">TOKENS</div>
          <div class="text-lg font-bold text-blue-600">${formatNumber(r.total_tokens||0)}</div>
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">STATUS</div>
          <div class="text-lg font-bold" style="color: ${statusClass === 'success' ? '#10b981' : statusClass === 'error' ? '#ef4444' : '#f59e0b'}">${r.status ? r.status.toUpperCase() : 'N/A'}</div>
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">TIME</div>
          <div class="text-lg font-bold text-gray-700">${r.end_time ? new Date(r.end_time).toLocaleString('en-US') : 'N/A'}</div>
        </div>
      </div>
      
      ${traceHtml}
      ${io}
    `;
    console.timeEnd('loadRunDetail_total');
  }

  function escapeHtml(s){
    return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  }

  refreshBtn.addEventListener('click', loadStats);
  agentSelect.addEventListener('change', async () => {
    prefs.agent = agentSelect.value;
    savePrefs(prefs);
    if (agentSelect.value) await loadAgent(agentSelect.value);
    await loadRuns();
  });
  timeRangeSelect.addEventListener('change', () => {
    prefs.timeRange = timeRangeSelect.value;
    savePrefs(prefs);
    loadStats();
  });
  statusSelect.addEventListener('change', () => { loadRuns(); });
  searchInput.addEventListener('input', () => { loadRuns(); });

  let interval;
  function setupAutoRefresh() {
    const ms = prefs.refreshMs || 30000;
    if (interval) clearInterval(interval);
    interval = setInterval(loadStats, ms);
  }
  setupAutoRefresh();
  const presetAgent = window.__AGENT__ || document.body.dataset.agent || '';
  if (presetAgent) {
    agentSelect.innerHTML = `<option value="${presetAgent}">${presetAgent}</option>`;
    agentSelect.value = presetAgent;
    loadAgent(presetAgent);
  }
  loadStats();
})();