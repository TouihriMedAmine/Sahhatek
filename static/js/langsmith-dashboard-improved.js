(() => {
  // Cache DOM elements
  const elements = {
    agentSelect: document.getElementById('agentSelect'),
    timeRangeSelect: document.getElementById('timeRangeSelect'),
    refreshBtn: document.getElementById('refreshBtn'),
    openAgentPage: document.getElementById('openAgentPage'),
    kpiTotal: document.getElementById('kpiTotal'),
    kpiSuccess: document.getElementById('kpiSuccess'),
    kpiErrors: document.getElementById('kpiErrors'),
    kpiAgent: document.getElementById('kpiAgent'),
    agentsTable: document.getElementById('agentsTable'),
    runsTable: document.getElementById('runsTable'),
    runDetail: document.getElementById('runDetail'),
    searchInput: document.getElementById('searchInput'),
    statusSelect: document.getElementById('statusSelect')
  };

  let latencyChart = null;
  let statusChart = null;
  let runsDataCache = null;
  let statsDataCache = null;
  
  // Request cache with TTL
  const requestCache = new Map();
  const CACHE_TTL = 10000; // 10 seconds cache

  // Agent configuration
  const AGENTS = {
    'rumor': { name: 'Rumor', color: '#8b5cf6', className: 'agent-rumor', icon: '📰' },
    'triage': { name: 'Triage', color: '#06b6d4', className: 'agent-triage', icon: '⚕️' },
    'mental_health': { name: 'Mental Health', color: '#ec4899', className: 'agent-mental', icon: '🧠' },
    'qa': { name: 'Q&A', color: '#f59e0b', className: 'agent-qa', icon: '❓' }
  };

  // Prefs management
  const prefsKey = 'langsmith_dashboard_prefs';
  const prefs = (() => {
    try {
      const raw = localStorage.getItem(prefsKey);
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  })();

  // Initialize UI from prefs
  if (prefs.timeRange && elements.timeRangeSelect) {
    elements.timeRangeSelect.value = prefs.timeRange;
  }
  if (prefs.agent && elements.kpiAgent) {
    elements.kpiAgent.textContent = prefs.agent;
  }

  // Utility functions
  function getAgentInfo(runName) {
    if (!runName) return { name: 'Other', color: '#6b7280', className: 'agent-other', icon: '⚙️' };
    
    const name = runName.toLowerCase();
    for (const [key, info] of Object.entries(AGENTS)) {
      if (name.includes(key.toLowerCase())) {
        return info;
      }
    }
    return { name: runName, color: '#6b7280', className: 'agent-other', icon: '⚙️' };
  }

  function formatNumber(n) { 
    return (n || 0).toLocaleString('en-US'); 
  }

  function round(n, d = 1) { 
    return Math.round((n || 0) * Math.pow(10, d)) / Math.pow(10, d); 
  }

  // Optimized fetch with caching
  async function fetchJSON(url, useCache = true) {
    const now = Date.now();
    
    // Check cache
    if (useCache && requestCache.has(url)) {
      const cached = requestCache.get(url);
      if (now - cached.timestamp < CACHE_TTL) {
        return cached.data;
      }
    }
    
    try {
      const res = await fetch(url, { 
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(10000) // 10 second timeout
      });
      
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      
      const data = await res.json();
      
      // Cache the response
      if (useCache) {
        requestCache.set(url, {
          data,
          timestamp: now
        });
      }
      
      return data;
    } catch (error) {
      console.error('Fetch error:', error);
      return { available: false, reason: 'Network error' };
    }
  }

  // Save prefs
  function savePrefs(p) {
    try { 
      localStorage.setItem(prefsKey, JSON.stringify(p)); 
    } catch (e) {
      console.error('Failed to save prefs:', e);
    }
  }

  // Parallel loading functions
  async function loadDataParallel() {
    console.time('loadDataParallel_total');
    
    // Show loading state
    setLoadingState(true);
    
    const timeRange = elements.timeRangeSelect.value;
    const agent = elements.agentSelect.value;
    const status = elements.statusSelect.value;
    const searchQuery = elements.searchInput.value;
    
    try {
      // Load stats and runs in parallel
      const [statsData, runsData] = await Promise.all([
        fetchJSON(`/chat/api/langsmith/stats/?time_range=${encodeURIComponent(timeRange)}`),
        fetchJSON(`/chat/api/langsmith/runs/?time_range=${encodeURIComponent(timeRange)}&agent=${encodeURIComponent(agent || '')}&status=${encodeURIComponent(status || '')}&limit=50&with_io=false`)
      ]);
      
      // Cache the data
      statsDataCache = statsData;
      runsDataCache = runsData;
      
      // Update UI components
      updateStats(statsData);
      updateRunsTable(runsData, searchQuery);
      updateCharts(statsData);
      
      // Load agent-specific data if needed
      if (agent) {
        await loadAgentData(agent);
      }
      
    } catch (error) {
      console.error('Parallel load error:', error);
      showErrorState('Failed to load data. Please try again.');
    } finally {
      setLoadingState(false);
      console.timeEnd('loadDataParallel_total');
    }
  }

  function updateStats(data) {
    if (!data.available) {
      elements.kpiTotal.textContent = 'N/A';
      elements.kpiSuccess.textContent = 'N/A';
      elements.kpiErrors.textContent = 'N/A';
      elements.agentsTable.innerHTML = `<tr><td colspan="5" class="p-2 text-center text-gray-500">${data.reason || 'Service unavailable'}</td></tr>`;
      return;
    }
    
    elements.kpiTotal.textContent = formatNumber(data.total_runs);
    elements.kpiSuccess.textContent = formatNumber(data.success);
    elements.kpiErrors.textContent = formatNumber(data.errors);
    
    // Update agent select
    const agents = data.agents || [];
    const agentSelectHtml = '<option value="">All</option>' + 
      agents.map(a => `<option value="${a.name}" ${prefs.agent === a.name ? 'selected' : ''}>${a.name}</option>`).join('');
    
    if (elements.agentSelect) {
      elements.agentSelect.innerHTML = agentSelectHtml;
    }
    
    // Update agents table
    elements.agentsTable.innerHTML = agents.map(a => `
      <tr class="hover:bg-gray-50 transition-colors animate-fade-in">
        <td class="p-3 text-gray-900 font-medium">${a.name}</td>
        <td class="p-3 text-right text-gray-900">${formatNumber(a.count)}</td>
        <td class="p-3 text-right">
          <span class="px-2 py-1 rounded-full text-xs ${a.errors > 0 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}">
            ${formatNumber(a.errors)}
          </span>
        </td>
        <td class="p-3 text-right text-gray-900 font-medium">${round(a.avg_latency_ms, 0)} ms</td>
        <td class="p-3 text-right text-gray-900">${round(a.avg_total_tokens, 1)}</td>
      </tr>
    `).join('');
  }

  function updateRunsTable(data, searchQuery = '') {
    if (!data.available || !data.runs || data.runs.length === 0) {
      elements.runsTable.innerHTML = `
        <tr>
          <td colspan="6" class="p-8 text-center text-gray-500">
            <i class="fas fa-inbox text-2xl mb-2 text-gray-400"></i>
            <p>No runs found</p>
          </td>
        </tr>
      `;
      return;
    }
    
    const query = (searchQuery || '').toLowerCase().trim();
    const filteredRuns = query ? 
      data.runs.filter(r => {
        const searchText = `${r.name || ''} ${r.agent || ''}`.toLowerCase();
        return searchText.includes(query);
      }) : 
      data.runs;
    
    if (filteredRuns.length === 0) {
      elements.runsTable.innerHTML = `
        <tr>
          <td colspan="6" class="p-8 text-center text-gray-500">
            <i class="fas fa-search text-2xl mb-2 text-gray-400"></i>
            <p>No matching runs found</p>
          </td>
        </tr>
      `;
      return;
    }
    
    elements.runsTable.innerHTML = filteredRuns.map(run => {
      const agentInfo = getAgentInfo(run.agent);
      const statusClass = run.status === 'success' ? 'bg-green-100 text-green-800 border-green-200' : 
                         run.status === 'error' ? 'bg-red-100 text-red-800 border-red-200' : 
                         'bg-yellow-100 text-yellow-800 border-yellow-200';
      
      return `
        <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer" 
            onclick="window.loadRunDetail('${run.id}')">
          <td class="p-3">
            <div class="flex items-center gap-2">
              <span class="text-lg">${agentInfo.icon}</span>
              <span class="font-medium text-gray-900 truncate max-w-[180px]" title="${run.name || 'Unnamed'}">
                ${run.name || 'Unnamed'}
              </span>
            </div>
          </td>
          <td class="p-3">
            <span class="px-2 py-1 rounded-full text-xs border ${agentInfo.className}" style="background-color: ${agentInfo.color}20; color: ${agentInfo.color}; border-color: ${agentInfo.color}40">
              ${agentInfo.name}
            </span>
          </td>
          <td class="p-3">
            <span class="px-2 py-1 rounded-full text-xs border ${statusClass}">
              ${run.status === 'success' ? '✅ Success' : run.status === 'error' ? '❌ Error' : '⏳ Pending'}
            </span>
          </td>
          <td class="p-3 text-right font-medium ${run.latency_ms < 1000 ? 'text-green-600' : run.latency_ms < 3000 ? 'text-amber-600' : 'text-red-600'}">
            ${round(run.latency_ms, 0)} ms
          </td>
          <td class="p-3 text-right text-blue-600 font-medium">
            ${formatNumber(run.total_tokens || 0)}
          </td>
          <td class="p-3 text-right text-gray-500 text-sm">
            ${run.end_time ? new Date(run.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
          </td>
        </tr>
      `;
    }).join('');
  }

  async function loadAgentData(agentName) {
    try {
      const data = await fetchJSON(`/chat/api/langsmith/agent/${encodeURIComponent(agentName)}/stats/?time_range=${encodeURIComponent(elements.timeRangeSelect.value)}`);
      
      if (data.available && elements.kpiAgent) {
        elements.kpiAgent.textContent = data.agent;
        
        // If this is an agent-specific page, hide unnecessary sections
        if (window.__AGENT__ || document.body.dataset.agent) {
          const charts = document.getElementById('overviewCharts');
          const summary = document.getElementById('agentsSummarySection');
          if (charts) charts.classList.add('hidden');
          if (summary) summary.classList.add('hidden');
          if (elements.agentSelect) elements.agentSelect.disabled = true;
        }
      }
    } catch (error) {
      console.error('Agent data load error:', error);
    }
  }

  function updateCharts(data) {
    if (!data.available || !data.agents) return;
    
    const agents = data.agents;
    const labels = agents.map(a => a.name);
    const latencies = agents.map(a => round(a.avg_latency_ms, 0));
    
    // Update latency chart
    const ctx1 = document.getElementById('latencyChart')?.getContext('2d');
    if (ctx1) {
      if (latencyChart) latencyChart.destroy();
      
      latencyChart = new Chart(ctx1, {
        type: 'bar',
        data: { 
          labels, 
          datasets: [{ 
            label: 'Average Latency (ms)', 
            data: latencies, 
            backgroundColor: labels.map(label => {
              const agentInfo = getAgentInfo(label);
              return agentInfo.color + '80'; // 50% opacity
            }),
            borderColor: labels.map(label => {
              const agentInfo = getAgentInfo(label);
              return agentInfo.color;
            }),
            borderWidth: 1,
            borderRadius: 4
          }] 
        },
        options: { 
          responsive: true, 
          maintainAspectRatio: false,
          plugins: { 
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => `${context.dataset.label}: ${context.parsed.y}ms`
              }
            }
          },
          scales: {
            y: { 
              beginAtZero: true,
              ticks: { color: '#6b7280', font: { size: 11 } }, 
              grid: { color: 'rgba(229, 231, 235, 0.5)' } 
            },
            x: { 
              ticks: { color: '#6b7280', font: { size: 11 } }, 
              grid: { display: false }
            }
          }
        }
      });
    }
    
    // Update status chart
    const ctx2 = document.getElementById('statusChart')?.getContext('2d');
    if (ctx2) {
      if (statusChart) statusChart.destroy();
      
      statusChart = new Chart(ctx2, {
        type: 'doughnut',
        data: {
          labels: ['Success', 'Errors'],
          datasets: [{ 
            data: [data.success, data.errors], 
            backgroundColor: ['#10b98180', '#ef444480'],
            borderColor: ['#10b981', '#ef4444'],
            borderWidth: 2
          }]
        },
        options: { 
          responsive: true,
          maintainAspectRatio: false,
          plugins: { 
            legend: { 
              position: 'bottom',
              labels: { 
                color: '#374151', 
                font: { size: 12 },
                padding: 15
              } 
            }
          },
          cutout: '65%'
        }
      });
    }
  }

  // Run detail loading (exposed globally for click handlers)
  window.loadRunDetail = async function(id) {
    try {
      setLoadingState(true);
      
      const data = await fetchJSON(`/chat/api/langsmith/runs/${encodeURIComponent(id)}/?with_io=true`, false); // Don't cache detail views
      
      if (!data.available || !data.run) {
        elements.runDetail.innerHTML = `
          <div class="p-6 text-center text-gray-500">
            <i class="fas fa-exclamation-triangle text-2xl mb-3 text-gray-400"></i>
            <p>Unable to load run details</p>
          </div>
        `;
        return;
      }
      
      const run = data.run;
      const agentInfo = getAgentInfo(run.agent);
      const statusClass = run.status === 'success' ? 'bg-green-100 text-green-800 border-green-200' : 
                         run.status === 'error' ? 'bg-red-100 text-red-800 border-red-200' : 
                         'bg-yellow-100 text-yellow-800 border-yellow-200';
      
      elements.runDetail.innerHTML = `
        <div class="space-y-4 animate-fade-in">
          <div class="p-4 rounded-lg bg-gradient-to-r from-gray-50 to-white border-l-4" style="border-left-color: ${agentInfo.color}">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-3">
                <span class="text-2xl">${agentInfo.icon}</span>
                <div>
                  <h4 class="font-bold text-gray-900">${run.name || 'Unnamed Execution'}</h4>
                  <p class="text-xs text-gray-500">${agentInfo.name} • ${new Date(run.end_time).toLocaleString()}</p>
                </div>
              </div>
              <span class="px-3 py-1 rounded-full text-sm border ${statusClass} font-medium">
                ${run.status === 'success' ? '✅ Success' : run.status === 'error' ? '❌ Error' : '⏳ Pending'}
              </span>
            </div>
          </div>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="p-3 rounded-lg bg-blue-50">
              <p class="text-xs text-gray-600 mb-1">LATENCY</p>
              <p class="text-lg font-bold text-blue-700">${round(run.latency_ms, 0)} ms</p>
            </div>
            <div class="p-3 rounded-lg bg-green-50">
              <p class="text-xs text-gray-600 mb-1">TOKENS</p>
              <p class="text-lg font-bold text-green-700">${formatNumber(run.total_tokens || 0)}</p>
            </div>
            <div class="p-3 rounded-lg bg-purple-50">
              <p class="text-xs text-gray-600 mb-1">STATUS</p>
              <p class="text-lg font-bold" style="color: ${run.status === 'success' ? '#10b981' : run.status === 'error' ? '#ef4444' : '#f59e0b'}">
                ${run.status?.toUpperCase() || 'N/A'}
              </p>
            </div>
            <div class="p-3 rounded-lg bg-gray-50">
              <p class="text-xs text-gray-600 mb-1">DURATION</p>
              <p class="text-lg font-bold text-gray-700">${round(run.latency_ms / 1000, 1)}s</p>
            </div>
          </div>
          
          ${run.nodes?.length > 0 ? `
            <div class="p-4 rounded-lg bg-gray-50">
              <h5 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <i class="fas fa-stream"></i> Execution Trace
              </h5>
              <div class="space-y-2">
                ${run.nodes.map((node, idx) => `
                  <div class="flex items-center justify-between p-2 bg-white rounded border">
                    <span class="text-sm">${idx + 1}. ${node.name}</span>
                    <span class="text-xs text-gray-500">${round(node.latency_ms || 0, 1)} ms</span>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}
          
          <div class="p-4 rounded-lg bg-gray-50">
            <h5 class="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <i class="fas fa-code"></i> Input & Output
            </h5>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p class="text-xs text-gray-600 mb-2 font-medium">INPUT</p>
                <pre class="text-xs bg-white p-3 rounded border overflow-auto max-h-40">${JSON.stringify(run.inputs || {}, null, 2)}</pre>
              </div>
              <div>
                <p class="text-xs text-gray-600 mb-2 font-medium">OUTPUT</p>
                <pre class="text-xs bg-white p-3 rounded border overflow-auto max-h-40">${JSON.stringify(run.outputs || {}, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>
      `;
      
    } catch (error) {
      console.error('Run detail error:', error);
      elements.runDetail.innerHTML = `
        <div class="p-6 text-center text-red-500">
          <i class="fas fa-exclamation-circle text-2xl mb-3"></i>
          <p>Failed to load run details</p>
        </div>
      `;
    } finally {
      setLoadingState(false);
    }
  };

  // UI state management
  function setLoadingState(loading) {
    if (loading) {
      document.body.classList.add('loading');
      // Add a subtle loading indicator to refresh button
      if (elements.refreshBtn) {
        elements.refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Loading...';
        elements.refreshBtn.disabled = true;
      }
    } else {
      document.body.classList.remove('loading');
      if (elements.refreshBtn) {
        elements.refreshBtn.innerHTML = '🔄 Refresh';
        elements.refreshBtn.disabled = false;
      }
    }
  }

  function showErrorState(message) {
    if (elements.kpiTotal) elements.kpiTotal.textContent = '—';
    if (elements.kpiSuccess) elements.kpiSuccess.textContent = '—';
    if (elements.kpiErrors) elements.kpiErrors.textContent = '—';
    
    // Show error in runs table
    if (elements.runsTable) {
      elements.runsTable.innerHTML = `
        <tr>
          <td colspan="6" class="p-8 text-center text-gray-500">
            <i class="fas fa-exclamation-triangle text-2xl mb-2 text-yellow-500"></i>
            <p>${message}</p>
          </td>
        </tr>
      `;
    }
  }

  // Event listeners
  function setupEventListeners() {
    if (elements.refreshBtn) {
      elements.refreshBtn.addEventListener('click', loadDataParallel);
    }
    
    if (elements.agentSelect) {
      elements.agentSelect.addEventListener('change', async () => {
        prefs.agent = elements.agentSelect.value;
        savePrefs(prefs);
        
        if (elements.agentSelect.value) {
          await loadAgentData(elements.agentSelect.value);
        }
        
        // Filter cached runs data
        if (runsDataCache) {
          updateRunsTable(runsDataCache, elements.searchInput?.value || '');
        }
      });
    }
    
    if (elements.timeRangeSelect) {
      elements.timeRangeSelect.addEventListener('change', () => {
        prefs.timeRange = elements.timeRangeSelect.value;
        savePrefs(prefs);
        
        // Clear cache when time range changes
        requestCache.clear();
        loadDataParallel();
      });
    }
    
    if (elements.statusSelect) {
      elements.statusSelect.addEventListener('change', debounce(() => {
        // Filter cached data
        if (runsDataCache) {
          updateRunsTable(runsDataCache, elements.searchInput?.value || '');
        }
      }, 300));
    }
    
    if (elements.searchInput) {
      elements.searchInput.addEventListener('input', debounce(() => {
        // Filter cached data
        if (runsDataCache) {
          updateRunsTable(runsDataCache, elements.searchInput.value);
        }
      }, 300));
    }
    
    if (elements.openAgentPage) {
      elements.openAgentPage.addEventListener('click', (e) => {
        e.preventDefault();
        const agent = elements.agentSelect?.value;
        if (agent) {
          window.location.href = `/chat/dashboard/langsmith/agent/${encodeURIComponent(agent)}/`;
        }
      });
    }
  }

  // Debounce utility
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // Auto-refresh setup
  let refreshInterval = null;
  function setupAutoRefresh() {
    const intervalMs = prefs.refreshMs || 30000;
    
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
    
    refreshInterval = setInterval(() => {
      if (!document.hidden) {
        loadDataParallel();
      }
    }, intervalMs);
  }

  // Initialize
  function init() {
    console.time('dashboard_init');
    
    setupEventListeners();
    setupAutoRefresh();
    
    // Check for pre-selected agent
    const presetAgent = window.__AGENT__ || document.body.dataset.agent || '';
    if (presetAgent && elements.agentSelect) {
      elements.agentSelect.value = presetAgent;
      elements.agentSelect.disabled = true;
    }
    
    // Initial load
    loadDataParallel();
    
    console.timeEnd('dashboard_init');
  }

  // Start initialization when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();