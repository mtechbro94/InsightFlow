// UI elements and globally scoped variables for managing active states
let datasetMetadata = null;
let currentCleanLogs = [];
let datasetProfile = null;
let activeDashboardData = null;

// Dashboard Themes configurations
let currentTheme = 'cyberpunk';
const THEMES = {
    cyberpunk: {
        primary: '#6366f1',
        secondary: '#ec4899',
        grid: '#1e293b',
        text: '#94a3b8',
        bodyBg: '#0b0f19',
        cardBg: '#0f172a',
        isLight: false
    },
    emerald: {
        primary: '#10b981',
        secondary: '#14b8a6',
        grid: '#064e3b',
        text: '#a7f3d0',
        bodyBg: '#021e17',
        cardBg: '#022c22',
        isLight: false
    },
    retro: {
        primary: '#f59e0b',
        secondary: '#d97706',
        grid: '#292524',
        text: '#f7fee7',
        bodyBg: '#141210',
        cardBg: '#1c1917',
        isLight: false
    },
    slate: {
        primary: '#cbd5e1',
        secondary: '#94a3b8',
        grid: '#334155',
        text: '#cbd5e1',
        bodyBg: '#0f172a',
        cardBg: '#1e293b',
        isLight: false
    },
    snow: {
        primary: '#4f46e5',
        secondary: '#06b6d4',
        grid: '#e2e8f0',
        text: '#1e293b',
        bodyBg: '#f8fafc',
        cardBg: '#ffffff',
        isLight: true
    }
};

// Dashboard Tab management
let activeInsightTab = 'business';
let activePlotlyCharts = {};
let tableQuery = '';
let tablePage = 0;
const pageSize = 10;

// Global helper: Show/hide spinner modal
function showSpinner(text = "Processing...") {
    document.getElementById('spinner-text').textContent = text;
    document.getElementById('modal-spinner').classList.remove('hidden');
}

function hideSpinner() {
    document.getElementById('modal-spinner').classList.add('hidden');
}

// 1. Ingestion / Upload Phase
async function handleFileUpload(file) {
    if (!file) return;

    const uploader = document.getElementById('step-upload');
    const loading = document.getElementById('upload-loading');
    
    // Toggle loading UI
    loading.classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            alert("Upload failed: " + (result.error || "Unknown error"));
            loading.classList.add('hidden');
            return;
        }

        // Store state
        datasetMetadata = result;
        
        // Setup Step 2 UI
        document.getElementById('clean-filename').textContent = result.filename;
        document.getElementById('profile-rows').textContent = result.num_records.toLocaleString();
        document.getElementById('profile-cols').textContent = result.num_features;
        document.getElementById('profile-dups').textContent = result.duplicate_count.toLocaleString();
        
        // Build Inferred columns cards
        buildColumnsProfileGrid(result.columns);
        
        // Transition Sections
        uploader.classList.add('hidden');
        document.getElementById('step-cleaning').classList.remove('hidden');
        
    } catch (e) {
        alert("Server communication error: " + e.message);
        loading.classList.add('hidden');
    }
}

// Render column profiles inside cards
function buildColumnsProfileGrid(columns) {
    const grid = document.getElementById('columns-profile-grid');
    grid.innerHTML = '';

    for (const [colName, details] of Object.entries(columns)) {
        const card = document.createElement('div');
        card.className = 'column-card flex flex-col justify-between';
        
        // Color typing based on inferred label
        let typeBadgeColor = 'bg-slate-800 text-slate-400';
        if (details.inferred_type === 'numeric') typeBadgeColor = 'bg-indigo-600/20 text-indigo-400';
        else if (details.inferred_type === 'categorical') typeBadgeColor = 'bg-emerald-600/20 text-emerald-400';
        else if (details.inferred_type === 'datetime') typeBadgeColor = 'bg-pink-600/20 text-pink-400';
        else if (details.inferred_type === 'boolean') typeBadgeColor = 'bg-amber-600/20 text-amber-400';
        else if (details.inferred_type === 'id') typeBadgeColor = 'bg-purple-600/20 text-purple-400';

        // Sample values list
        const sampleText = details.sample_values.slice(0, 3).join(', ');

        card.innerHTML = `
            <div>
                <div class="flex justify-between items-start mb-2">
                    <span class="text-sm font-bold truncate text-white max-w-[150px]" title="${colName}">${colName}</span>
                    <span class="text-[10px] px-2 py-0.5 rounded font-semibold uppercase tracking-wider ${typeBadgeColor}">${details.inferred_type}</span>
                </div>
                <div class="text-[11px] text-slate-400 space-y-1 mt-3">
                    <div class="flex justify-between"><span>Nulls:</span> <span class="${details.null_count > 0 ? 'text-red-400 font-semibold' : 'text-slate-300'}">${details.null_count} (${details.null_pct.toFixed(1)}%)</span></div>
                    <div class="flex justify-between"><span>Uniques:</span> <span class="text-slate-300">${details.unique_count}</span></div>
                </div>
            </div>
            <div class="mt-4 pt-3 border-t border-slate-900/50 text-[10px] text-slate-500 italic truncate">
                Samples: ${sampleText || 'None'}
            </div>
        `;
        grid.appendChild(card);
    }
}

// 2. Cleaning Phase
async function executeCleaningPipeline() {
    const imputation = document.getElementById('setting-imputation').value;
    const dropDuplicates = document.getElementById('setting-duplicates').checked;
    const outlierMultiplier = parseFloat(document.getElementById('setting-outliers').value);

    showSpinner("Running Data Cleaning Pipeline...");

    try {
        const response = await fetch('/api/clean', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                imputation_strategy: imputation,
                drop_duplicates: dropDuplicates,
                outlier_multiplier: outlierMultiplier
            })
        });

        const result = await response.json();
        hideSpinner();

        if (!response.ok) {
            alert("Cleaning failed: " + (result.error || "Unknown error"));
            return;
        }

        // Store result logs
        currentCleanLogs = result.cleaning_log;
        
        // Setup Terminal Log UI
        const term = document.getElementById('clean-terminal-output');
        term.innerHTML = '';
        
        // Transition step sections
        document.getElementById('step-cleaning').classList.add('hidden');
        document.getElementById('step-logs').classList.remove('hidden');

        // Play console logging effect
        let logIdx = 0;
        function printNextLog() {
            if (logIdx < currentCleanLogs.length) {
                const line = document.createElement('div');
                line.className = 'mt-1.5 opacity-90 transition-opacity duration-300';
                line.innerHTML = `<span class="text-indigo-400">⚡</span> ${currentCleanLogs[logIdx]}`;
                term.appendChild(line);
                term.scrollTop = term.scrollHeight; // Auto scroll to bottom
                logIdx++;
                setTimeout(printNextLog, 250); // Delay for visual typewriter feel
            } else {
                const finishLine = document.createElement('div');
                finishLine.className = 'mt-3 text-emerald-400 font-bold';
                finishLine.textContent = "> Clean dataset and metadata successfully cached on server. Data is ready for EDA.";
                term.appendChild(finishLine);
                term.scrollTop = term.scrollHeight;
            }
        }
        
        printNextLog();

    } catch (e) {
        hideSpinner();
        alert("Cleaning pipeline crashed: " + e.message);
    }
}

// 3. Analysis / Insight Generation Phase
async function runStatisticalAnalysis() {
    showSpinner("Executing Statistical EDA & Insight Engine...");

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST'
        });

        const result = await response.json();
        hideSpinner();

        if (!response.ok) {
            alert("Analysis failed: " + (result.error || "Unknown error"));
            return;
        }

        // Cache dashboard dataset state
        activeDashboardData = result;
        activePlotlyCharts = result.plotly_charts;
        
        // Hide Logs step and display dynamic dashboard
        document.getElementById('step-logs').classList.add('hidden');
        document.getElementById('step-dashboard').classList.remove('hidden');

        // Render sections
        renderDashboardKPIs();
        renderDashboardInsights();
        renderOutliersWarning();
        renderDashboardCharts();
        
        // Show notifications bell and trigger evaluation
        document.getElementById('navbar-alerts-bell-container').classList.remove('hidden');
        evaluateThresholdAlerts();
        
        // Build interactive Table Explorer
        tablePage = 0;
        tableQuery = '';
        document.getElementById('table-search').value = '';
        renderTableExplorer();

    } catch (e) {
        hideSpinner();
        alert("Exploratory Analysis crashed: " + e.message);
    }
}

// 4. Render Dashboard Widgets
function renderDashboardKPIs() {
    const container = document.getElementById('dash-kpi-grid');
    container.innerHTML = '';

    const kpis = activeDashboardData.kpis || [];
    kpis.forEach(kpi => {
        const card = document.createElement('div');
        card.className = 'bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 shadow-lg flex flex-col justify-between transition-all duration-300 hover:-translate-y-1';
        card.innerHTML = `
            <span class="text-xs text-slate-400 font-semibold tracking-wider uppercase mb-2">${kpi.name}</span>
            <span class="text-3xl font-extrabold text-white tracking-tight">${kpi.value}</span>
        `;
        container.appendChild(card);
    });
}

function renderDashboardInsights() {
    const list = document.getElementById('dash-insights-list');
    list.innerHTML = '';

    const catInsights = activeDashboardData.insights[activeInsightTab] || [];
    if (catInsights.length === 0) {
        list.innerHTML = `<li class="text-slate-400 text-sm italic">No insights computed for this category.</li>`;
        return;
    }

    catInsights.forEach(ins => {
        const li = document.createElement('li');
        li.className = 'flex items-start text-sm text-slate-300 space-x-2.5 bg-slate-950 p-3.5 rounded-xl border border-slate-800/80 hover:border-slate-700 transition-colors';
        li.innerHTML = `
            <span class="text-indigo-500 mt-1 select-none font-bold">▪</span>
            <span>${ins}</span>
        `;
        list.appendChild(li);
    });
}

function switchDashInsight(tabId) {
    // Style adjustments
    document.getElementById(`dash-tab-${activeInsightTab}`).className = "px-3 py-1 text-xs rounded-md bg-slate-800 text-slate-400 hover:text-slate-200";
    activeInsightTab = tabId;
    document.getElementById(`dash-tab-${tabId}`).className = "px-3 py-1 text-xs rounded-md bg-indigo-600 text-white font-medium";

    renderDashboardInsights();
}

function renderOutliersWarning() {
    const container = document.getElementById('dash-outliers-container');
    container.innerHTML = '';
    
    // We get outlier definitions from activeDashboardData or the initial log
    // Wait, let's load outlier metadata
    // We need to fetch outlier summary from the server or load from the activeDashboardData
    // We cached outliers inside the session_state and return them on Clean call.
    // If not visible, look in the logs
    const outliers = activeDashboardData.eda_results.numerical; // descriptive stats
    let outliersFound = false;

    // We can evaluate outliers using skewness or direct values
    for (const [colName, stats] of Object.entries(outliers)) {
        if (Math.abs(stats.skewness) > 1.5) {
            outliersFound = true;
            const card = document.createElement('div');
            card.className = 'p-4 bg-amber-600/5 border border-amber-500/20 rounded-xl flex items-start space-x-3 text-xs text-slate-300';
            
            card.innerHTML = `
                <div class="text-amber-500 mt-0.5">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                </div>
                <div>
                    <span class="font-bold text-amber-400 block">${colName} - Distribution Alert</span>
                    <span class="block mt-1">Highly skewed distribution (skewness: ${stats.skewness.toFixed(2)}). Data range: [${stats.min.toLocaleString()} to ${stats.max.toLocaleString()}]. Standard deviation is high (${stats.std.toFixed(2)}).</span>
                </div>
            `;
            container.appendChild(card);
        }
    }

    if (!outliersFound) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center text-center h-full text-slate-500 text-xs py-8">
                <svg class="w-8 h-8 text-emerald-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                <span>No severe outlier anomalies or skewness warnings flagged in numeric distributions.</span>
            </div>
        `;
    }
}

function renderDashboardCharts() {
    const targets = ['dash-chart-1', 'dash-chart-2', 'dash-chart-3', 'dash-chart-4'];
    
    // Check if Plotly library loaded correctly
    if (typeof Plotly === 'undefined') {
        console.error("Plotly is not loaded");
        targets.forEach(targetId => {
            const container = document.getElementById(targetId);
            if (container) {
                container.innerHTML = `
                    <div class="flex flex-col items-center justify-center h-full text-red-400 text-xs p-6 text-center">
                        <svg class="w-8 h-8 mb-2 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                        <span>Plotly library failed to load. Please verify your internet connection.</span>
                    </div>`;
            }
        });
        return;
    }

    // Design intelligent slots for the 4 charts
    let slots = [null, null, null, null];

    // 1. Time Series / Trend (Slot 1 Priority)
    if (activePlotlyCharts.time_series && Object.keys(activePlotlyCharts.time_series).length > 0) {
        const key = Object.keys(activePlotlyCharts.time_series)[0];
        slots[0] = `time_series__${key}`;
    }

    // 2. Business Category Aggregations (Slot 2 Priority)
    if (activePlotlyCharts.cat_num_relationships && Object.keys(activePlotlyCharts.cat_num_relationships).length > 0) {
        const cat = Object.keys(activePlotlyCharts.cat_num_relationships)[0];
        const num = Object.keys(activePlotlyCharts.cat_num_relationships[cat])[0];
        slots[1] = `cat_num__${cat}__${num}`;
    } else if (activePlotlyCharts.categorical && Object.keys(activePlotlyCharts.categorical).length > 0) {
        const key = Object.keys(activePlotlyCharts.categorical)[0];
        slots[1] = `categorical__${key}`;
    }

    // 3. Correlations & Scatter (Slot 3 Priority)
    if (activePlotlyCharts.correlation_heatmap) {
        slots[2] = 'correlation_heatmap';
    } else if (activePlotlyCharts.scatter_relation) {
        slots[2] = 'scatter_relation';
    } else if (activePlotlyCharts.distributions && Object.keys(activePlotlyCharts.distributions).length > 0) {
        const key = Object.keys(activePlotlyCharts.distributions)[0];
        slots[2] = `distributions__${key}`;
    }

    // 4. Outliers Box Plot / Secondary Distribution (Slot 4 Priority)
    if (activePlotlyCharts.box_plots && Object.keys(activePlotlyCharts.box_plots).length > 0) {
        const key = Object.keys(activePlotlyCharts.box_plots)[0];
        slots[3] = `box_plots__${key}`;
    } else if (activePlotlyCharts.distributions && Object.keys(activePlotlyCharts.distributions).length > 1) {
        const key = Object.keys(activePlotlyCharts.distributions)[1];
        slots[3] = `distributions__${key}`;
    }

    // Accumulate all available charts to backfill empty slots
    let allAvailable = [];
    if (activePlotlyCharts.correlation_heatmap) allAvailable.push('correlation_heatmap');
    if (activePlotlyCharts.scatter_relation) allAvailable.push('scatter_relation');
    if (activePlotlyCharts.time_series) {
        Object.keys(activePlotlyCharts.time_series).forEach(k => allAvailable.push(`time_series__${k}`));
    }
    if (activePlotlyCharts.cat_num_relationships) {
        Object.keys(activePlotlyCharts.cat_num_relationships).forEach(cat => {
            Object.keys(activePlotlyCharts.cat_num_relationships[cat]).forEach(num => {
                allAvailable.push(`cat_num__${cat}__${num}`);
            });
        });
    }
    if (activePlotlyCharts.categorical) {
        Object.keys(activePlotlyCharts.categorical).forEach(k => allAvailable.push(`categorical__${k}`));
    }
    if (activePlotlyCharts.distributions) {
        Object.keys(activePlotlyCharts.distributions).forEach(k => allAvailable.push(`distributions__${k}`));
    }
    if (activePlotlyCharts.box_plots) {
        Object.keys(activePlotlyCharts.box_plots).forEach(k => allAvailable.push(`box_plots__${k}`));
    }

    // Fill in empty slots with unused available charts
    for (let i = 0; i < 4; i++) {
        if (slots[i] === null) {
            const nextUnused = allAvailable.find(k => !slots.includes(k));
            if (nextUnused) {
                slots[i] = nextUnused;
            }
        }
    }

    // Filter out nulls
    const finalSlots = slots.filter(s => s !== null);

    targets.forEach((targetId, idx) => {
        const container = document.getElementById(targetId);
        container.innerHTML = '';

        if (idx < finalSlots.length) {
            const key = finalSlots[idx];
            let chartConfig = null;

            if (key === 'correlation_heatmap') {
                chartConfig = activePlotlyCharts.correlation_heatmap;
            } else if (key === 'scatter_relation') {
                chartConfig = activePlotlyCharts.scatter_relation;
            } else if (key.startsWith('distributions__')) {
                const colName = key.split('__')[1];
                chartConfig = activePlotlyCharts.distributions[colName];
            } else if (key.startsWith('categorical__')) {
                const colName = key.split('__')[1];
                chartConfig = activePlotlyCharts.categorical[colName];
            } else if (key.startsWith('time_series__')) {
                const colName = key.split('__')[1];
                chartConfig = activePlotlyCharts.time_series[colName];
            } else if (key.startsWith('box_plots__')) {
                const colName = key.split('__')[1];
                chartConfig = activePlotlyCharts.box_plots[colName];
            } else if (key.startsWith('cat_num__')) {
                const parts = key.split('__');
                const cat = parts[1];
                const num = parts[2];
                chartConfig = activePlotlyCharts.cat_num_relationships[cat][num];
            }

            if (chartConfig) {
                // Apply theme modifications dynamically on deep-cloned layout/data
                const themedLayout = JSON.parse(JSON.stringify(chartConfig.layout || {}));
                const themedData = JSON.parse(JSON.stringify(chartConfig.data || []));
                
                const theme = THEMES[currentTheme];
                themedLayout.paper_bgcolor = 'rgba(0,0,0,0)';
                themedLayout.plot_bgcolor = 'rgba(0,0,0,0)';
                themedLayout.font = { color: theme.text, family: 'Outfit, sans-serif' };
                
                if (themedLayout.xaxis) {
                    themedLayout.xaxis.gridcolor = theme.grid;
                    themedLayout.xaxis.linecolor = theme.grid;
                }
                if (themedLayout.yaxis) {
                    themedLayout.yaxis.gridcolor = theme.grid;
                    themedLayout.yaxis.linecolor = theme.grid;
                }
                
                themedData.forEach(trace => {
                    if (trace.marker) {
                        if (trace.type === 'heatmap') {
                            if (currentTheme === 'emerald') {
                                trace.colorscale = 'Viridis';
                            } else if (currentTheme === 'retro') {
                                trace.colorscale = 'Hot';
                            } else if (currentTheme === 'slate') {
                                trace.colorscale = 'Greys';
                            } else {
                                trace.colorscale = 'Portland';
                            }
                        } else {
                            trace.marker.color = theme.primary;
                            if (trace.marker.line) {
                                trace.marker.line.color = theme.primary;
                            }
                        }
                    }
                    if (trace.line) {
                        trace.line.color = theme.primary;
                    }
                });
                
                Plotly.newPlot(targetId, themedData, themedLayout, { responsive: true });
            }
        } else {
            container.innerHTML = `
                <div class="flex items-center justify-center h-full text-slate-500 text-xs">
                    <span>No analytical chart available for this slot.</span>
                </div>
            `;
        }
    });
}

// 6. Detailed Data Explorer Table
async function renderTableExplorer() {
    const thead = document.getElementById('thead-row');
    const tbody = document.getElementById('tbody-rows');
    
    thead.innerHTML = '';
    tbody.innerHTML = '';

    // We can query server metadata to render table column names
    if (!datasetMetadata || !datasetMetadata.columns) return;
    const columns = Object.keys(datasetMetadata.columns);
    
    // Draw columns headers (Clickable to inspect)
    columns.forEach(col => {
        const th = document.createElement('th');
        th.className = 'px-6 py-3 font-semibold text-indigo-400 hover:text-indigo-300 cursor-pointer hover:bg-slate-850/50 transition-colors uppercase tracking-wider text-xs';
        th.setAttribute('onclick', `openColumnInspector('${col.replace(/'/g, "\\'")}')`);
        th.innerHTML = `
            <div class="flex items-center space-x-1 justify-between">
                <span>${col}</span>
                <svg class="w-3 h-3 opacity-50 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
            </div>
        `;
        thead.appendChild(th);
    });

    // We need to fetch table rows. To avoid heavy DOM, we load samples or request paginated slice.
    // Since it's a SPA for files, we can request a preview api or write a client side preview.
    // To make it simple, let's write a small API endpoint or load a subset of the DataFrame in the JSON.
    // Wait! Let's write a paginated preview endpoint or pull standard preview rows in the API upload/clean steps.
    // Actually, in app.py we did not expose the raw records in /api/analyze to keep JSON response fast, but we can easily fetch them!
    // Or we can query a `/api/preview?page=0&query=foo` endpoint!
    // Let's implement an endpoint `/api/preview` or fetch preview data in JS.
    // Wait, let's create a quick API preview endpoint to load rows dynamically! This is extremely elegant.
    // Let's implement it! Let's write it in static/js/app.js first assuming `/api/preview` works.
    
    try {
        const res = await fetch(`/api/preview?page=${tablePage}&size=${pageSize}&query=${encodeURIComponent(tableQuery)}`);
        const result = await res.json();
        
        if (!res.ok) {
            tbody.innerHTML = `<tr><td colspan="${columns.length}" class="px-6 py-4 text-center text-slate-500">Failed to load preview data.</td></tr>`;
            return;
        }

        document.getElementById('total-rows').textContent = result.total.toLocaleString();
        
        const start = tablePage * pageSize + 1;
        const end = Math.min(start + pageSize - 1, result.total);
        document.getElementById('showing-range').textContent = `${result.total > 0 ? start : 0}-${end}`;
        
        document.getElementById('btn-prev').disabled = tablePage === 0;
        document.getElementById('btn-next').disabled = end >= result.total;

        if (result.rows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${columns.length}" class="px-6 py-8 text-center text-slate-500">No records match search query.</td></tr>`;
            return;
        }

        result.rows.forEach(row => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/30 transition-colors border-b border-slate-900';
            
            columns.forEach(col => {
                const td = document.createElement('td');
                td.className = 'px-6 py-4 whitespace-nowrap text-slate-300 font-medium';
                let val = row[col];
                if (val === null || val === undefined) val = '-';
                td.textContent = String(val);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="${columns.length}" class="px-6 py-4 text-center text-slate-500">Preview loading exception: ${e.message}</td></tr>`;
    }
}

function handleTableSearch(val) {
    tableQuery = val;
    tablePage = 0;
    renderTableExplorer();
}

function changePage(direction) {
    tablePage += direction;
    renderTableExplorer();
}

// 7. AI Copilot Chat Functions
function quickChatQuery(q) {
    document.getElementById('chat-user-input').value = q;
    sendChatMessage();
}

async function sendChatMessage() {
    const inputEl = document.getElementById('chat-user-input');
    const message = inputEl.value.trim();
    if (!message) return;

    inputEl.value = '';

    const container = document.getElementById('chat-messages-container');

    // Append User Message
    const userMsgDiv = document.createElement('div');
    userMsgDiv.className = 'flex items-start space-x-3 justify-end';
    userMsgDiv.innerHTML = `
        <div class="bg-indigo-600 text-white rounded-2xl px-4 py-2.5 max-w-[85%]">
            ${message}
        </div>
        <div class="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-xs shrink-0">ME</div>
    `;
    container.appendChild(userMsgDiv);
    container.scrollTop = container.scrollHeight;

    // Append Typing Indicator
    const typingDiv = document.createElement('div');
    typingDiv.className = 'flex items-start space-x-3';
    typingDiv.id = 'chat-typing-indicator';
    typingDiv.innerHTML = `
        <div class="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-xs shrink-0 animate-pulse">AI</div>
        <div class="bg-slate-900 border border-slate-800/80 rounded-2xl px-4 py-2.5 text-slate-400 text-xs flex items-center space-x-2">
            <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
            <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
            <span class="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
            <span>Running analysis script...</span>
        </div>
    `;
    container.appendChild(typingDiv);
    container.scrollTop = container.scrollHeight;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        const result = await response.json();

        // Remove typing indicator
        const indicator = document.getElementById('chat-typing-indicator');
        if (indicator) indicator.remove();

        if (!response.ok) {
            appendChatBotMessage("Error: Failed to process your analysis query.");
            return;
        }

        // Render Bot Message
        const botMsgDiv = document.createElement('div');
        botMsgDiv.className = 'flex items-start space-x-3';
        
        // Generate a random unique ID for dynamic Plotly chart inside chat bubble if present
        const chartId = 'chat-chart-' + Math.random().toString(36).substring(2, 9);
        
        let messageHtml = `
            <div class="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-xs shrink-0">AI</div>
            <div class="bg-slate-900 border border-slate-800/80 rounded-2xl px-4 py-2.5 max-w-[85%] text-slate-300 space-y-3 leading-relaxed">
                <div>${formatMarkdownText(result.text_answer)}</div>
                ${result.plotly_chart_data ? `<div id="${chartId}" class="w-full min-h-[220px] bg-slate-950/80 rounded-xl p-2 mt-3 border border-slate-850"></div>` : ''}
            </div>
        `;
        botMsgDiv.innerHTML = messageHtml;
        container.appendChild(botMsgDiv);
        container.scrollTop = container.scrollHeight;

        // If Plotly data is returned, draw the chart inside the chat bubble
        if (result.plotly_chart_data) {
            setTimeout(() => {
                const chartConfig = result.plotly_chart_data;
                // Force a small height and clean margins for chat-bubble aesthetics
                chartConfig.layout.height = 220;
                chartConfig.layout.margin = { l: 35, r: 15, t: 30, b: 35 };
                chartConfig.layout.showlegend = false;
                Plotly.newPlot(chartId, chartConfig.data, chartConfig.layout, { responsive: true, displayModeBar: false });
            }, 50);
        }

    } catch (e) {
        const indicator = document.getElementById('chat-typing-indicator');
        if (indicator) indicator.remove();
        appendChatBotMessage("Communication exception: " + e.message);
    }
}

function appendChatBotMessage(text) {
    const container = document.getElementById('chat-messages-container');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'flex items-start space-x-3';
    msgDiv.innerHTML = `
        <div class="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-xs shrink-0">AI</div>
        <div class="bg-slate-900 border border-slate-800/80 rounded-2xl px-4 py-2.5 max-w-[85%] text-slate-300">
            ${text}
        </div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

// Basic helper to convert markdown bold/bullet indicators in response text
function formatMarkdownText(text) {
    if (!text) return "";
    return text
        .replace(/\*\*(.*?)\*\//g, '<strong>$1</strong>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code class="bg-slate-950 px-1 rounded text-pink-400 font-mono">$1</code>')
        .replace(/\n/g, '<br>');
}

// 8. Column Detail Inspector
async function openColumnInspector(colName) {
    if (!activeDashboardData) return;

    // Show modal
    const modal = document.getElementById('inspector-modal');
    modal.classList.remove('hidden');

    // Get metadata from datasetMetadata
    const metadata = activeDashboardData.datasetMetadata || {};
    const colInfo = metadata.columns ? metadata.columns[colName] : {};
    const inferredType = colInfo.inferred_type || 'Unknown';
    const nullsCount = colInfo.null_count || 0;
    const nullsPct = colInfo.null_pct || 0.0;
    const uniqueCount = colInfo.unique_count || 0;

    // Outlier count
    const outliersObj = activeDashboardData.outliers || {};
    const colOutliers = outliersObj[colName] || null;
    const outlierCount = colOutliers ? colOutliers.count : 0;

    // Populate header & top cards
    document.getElementById('inspector-column-name').innerText = colName;
    document.getElementById('inspector-type').innerText = inferredType.charAt(0).toUpperCase() + inferredType.slice(1);
    document.getElementById('inspector-nulls').innerText = `${nullsCount} (${nullsPct.toFixed(1)}%)`;
    document.getElementById('inspector-unique').innerText = uniqueCount.toLocaleString();
    
    const outlierEl = document.getElementById('inspector-outliers');
    if (outlierCount > 0) {
        outlierEl.innerText = `${outlierCount} flagged`;
        outlierEl.className = 'text-sm font-bold text-amber-400 mt-1 block';
    } else {
        outlierEl.innerText = '0 flagged';
        outlierEl.className = 'text-sm font-bold text-slate-400 mt-1 block';
    }

    // Populate stats table
    const tableBody = document.getElementById('inspector-stats-table');
    tableBody.innerHTML = '';

    const eda = activeDashboardData.eda || {};

    if (inferredType === 'numeric') {
        const stats = eda.numerical ? eda.numerical[colName] : null;
        if (stats) {
            const rows = [
                { name: 'Mean Average', val: stats.mean.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) },
                { name: 'Median Value', val: stats.median.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) },
                { name: 'Minimum', val: stats.min.toLocaleString() },
                { name: 'Maximum', val: stats.max.toLocaleString() },
                { name: 'Range Bounds', val: stats.range.toLocaleString() },
                { name: 'Standard Deviation (Std)', val: stats.std.toFixed(4) },
                { name: 'Variance', val: stats.var.toFixed(4) },
                { name: 'Skewness (Symmetry)', val: stats.skewness ? stats.skewness.toFixed(4) : '0.0000' },
                { name: 'Kurtosis (Peak)', val: stats.kurtosis ? stats.kurtosis.toFixed(4) : '0.0000' }
            ];
            rows.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="px-4 py-2.5 text-left text-slate-400 font-medium">${r.name}</td>
                    <td class="px-4 py-2.5 text-right font-semibold text-slate-200">${r.val}</td>
                `;
                tableBody.appendChild(tr);
            });
        }
    } else if (inferredType === 'categorical' || inferredType === 'boolean') {
        const stats = eda.categorical ? eda.categorical[colName] : null;
        if (stats && stats.distribution) {
            // Sort categories by counts
            const dist = Object.entries(stats.distribution).sort((a, b) => b[1].count - a[1].count);
            dist.forEach(([cat, data]) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="px-4 py-2.5 text-left text-slate-400 font-medium">${cat}</td>
                    <td class="px-4 py-2.5 text-right font-semibold text-slate-200">${data.count.toLocaleString()} (${data.pct.toFixed(1)}%)</td>
                `;
                tableBody.appendChild(tr);
            });
        }
    } else {
        const sampleVals = colInfo.sample_values || [];
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="px-4 py-2.5 text-left text-slate-400 font-medium">Sample Values</td>
            <td class="px-4 py-2.5 text-right font-semibold text-slate-200">${sampleVals.slice(0, 5).join(', ')}</td>
        `;
        tableBody.appendChild(tr);
    }

    // Fetch and plot chart preview
    const chartDiv = document.getElementById('inspector-chart');
    chartDiv.innerHTML = '<span class="text-slate-400 text-xs animate-pulse">Loading distribution data...</span>';

    try {
        const response = await fetch(`/api/column/${encodeURIComponent(colName)}`);
        const result = await response.json();
        
        if (!response.ok) {
            chartDiv.innerHTML = '<span class="text-red-500 text-xs">Failed to load chart data.</span>';
            return;
        }

        const values = result.values;
        chartDiv.innerHTML = ''; // Clear loading text

        let plotlyData = [];
        let plotlyLayout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            height: 240,
            margin: { l: 40, r: 20, t: 20, b: 40 },
            font: { color: '#94a3b8', size: 10 },
            xaxis: { gridcolor: '#1e293b', linecolor: '#1e293b' },
            yaxis: { gridcolor: '#1e293b', linecolor: '#1e293b' }
        };

        if (inferredType === 'numeric') {
            plotlyData = [{
                x: values,
                type: 'histogram',
                marker: { color: '#6366f1', opacity: 0.8 }
            }];
            plotlyLayout.xaxis.title = 'Value Bins';
            plotlyLayout.yaxis.title = 'Frequency';
        } else {
            // Count unique items manually
            const counts = {};
            values.forEach(v => { counts[v] = (counts[v] || 0) + 1; });
            const sortedCounts = Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0, 10);
            
            plotlyData = [{
                x: sortedCounts.map(item => item[0]),
                y: sortedCounts.map(item => item[1]),
                type: 'bar',
                marker: { color: '#ec4899', opacity: 0.8 }
            }];
            plotlyLayout.xaxis.title = 'Categories';
            plotlyLayout.yaxis.title = 'Count';
        }

        Plotly.newPlot('inspector-chart', plotlyData, plotlyLayout, { responsive: true, displayModeBar: false });

    } catch (err) {
        chartDiv.innerHTML = `<span class="text-red-500 text-xs">Error drawing preview: ${err.message}</span>`;
    }
}

function closeColumnInspector() {
    document.getElementById('inspector-modal').classList.add('hidden');
}

// 9. Dashboard Theme Manager
function changeDashboardTheme(themeName) {
    if (!THEMES[themeName]) return;
    currentTheme = themeName;
    const theme = THEMES[themeName];

    // Toggle body light theme class
    if (theme.isLight) {
        document.body.classList.add('light-theme');
    } else {
        document.body.classList.remove('light-theme');
    }

    // Apply color variables to document elements
    document.documentElement.style.setProperty('--body-bg', theme.bodyBg);
    document.documentElement.style.setProperty('--card-bg', theme.cardBg);
    
    // Body background overwrite
    document.body.style.backgroundColor = theme.bodyBg;
    
    // Update all cards, panels, and custom items
    const themeCards = document.querySelectorAll('.bg-slate-900, .bg-slate-955\\/60');
    themeCards.forEach(card => {
        card.style.backgroundColor = theme.cardBg;
    });

    // Re-render dashboard visualizations with new colors
    renderDashboardCharts();
}

// 10. PDF Report Custom Designer (Option D)
function openPdfDesigner() {
    document.getElementById('pdf-designer-modal').classList.remove('hidden');
    if (THEMES[currentTheme]) {
        document.getElementById('pdf-custom-color').value = THEMES[currentTheme].primary;
    }
}

function closePdfDesigner() {
    document.getElementById('pdf-designer-modal').classList.add('hidden');
}

async function generateCustomPdfReport() {
    const title = document.getElementById('pdf-custom-title').value.trim();
    const company = document.getElementById('pdf-custom-company').value.trim();
    const accentColor = document.getElementById('pdf-custom-color').value;
    const logoFile = document.getElementById('pdf-custom-logo').files[0];
    
    const includeSections = [];
    if (document.getElementById('pdf-sec-kpis').checked) includeSections.push('kpis');
    if (document.getElementById('pdf-sec-quality').checked) includeSections.push('quality');
    if (document.getElementById('pdf-sec-insights').checked) includeSections.push('insights');
    if (document.getElementById('pdf-sec-charts').checked) includeSections.push('charts');
    if (document.getElementById('pdf-sec-recs').checked) includeSections.push('recommendations');
    
    closePdfDesigner();
    showSpinner("Compiling customized report assets...");
    
    let uploadedLogoPath = null;
    
    if (logoFile) {
        try {
            const formData = new FormData();
            formData.append('logo', logoFile);
            
            const uploadRes = await fetch('/api/upload_logo', {
                method: 'POST',
                body: formData
            });
            
            const uploadResult = await uploadRes.json();
            if (uploadRes.ok) {
                uploadedLogoPath = uploadResult.logo_path;
            }
        } catch (logoErr) {
            console.warn("Failed to upload logo asset: " + logoErr.message);
        }
    }
    
    try {
        const response = await fetch('/api/export/custom_pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title || 'Executive Analysis Report',
                company: company || 'InsightFlow',
                accent_color: accentColor,
                include_sections: includeSections,
                logo_path: uploadedLogoPath
            })
        });
        
        const result = await response.json();
        hideSpinner();
        
        if (!response.ok) {
            alert("Custom PDF compilation failed: " + (result.error || "Unknown error"));
            return;
        }
        
        window.location.href = result.download_url;
    } catch (e) {
        hideSpinner();
        alert("Report generation crashed: " + e.message);
    }
}

// 11. Recent Analysis History Drawer (Option E)
async function loadHistoryList() {
    const section = document.getElementById('recent-history-section');
    const container = document.getElementById('recent-history-list');
    
    try {
        const response = await fetch('/api/history');
        if (!response.ok) return;
        
        const result = await response.json();
        const items = result.history || [];
        
        if (items.length === 0) {
            section.classList.add('hidden');
            return;
        }
        
        section.classList.remove('hidden');
        container.innerHTML = '';
        
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = "flex items-center justify-between p-4 bg-slate-900 border border-slate-850 hover:border-indigo-500/50 hover:bg-slate-900/80 rounded-2xl cursor-pointer transition-all duration-200 group";
            card.onclick = () => loadHistoryItem(item.id);
            
            card.innerHTML = `
                <div class="flex items-center space-x-3">
                    <div class="p-2.5 bg-indigo-500/10 text-indigo-400 rounded-xl group-hover:scale-105 transition-transform duration-300">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    </div>
                    <div>
                        <h4 class="text-xs font-bold text-white group-hover:text-indigo-300 transition-colors">${item.filename}</h4>
                        <p class="text-[10px] text-slate-500 mt-0.5">${item.record_count.toLocaleString()} rows • ${item.timestamp}</p>
                    </div>
                </div>
                <div class="text-xs text-indigo-400 font-semibold flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span>Load Dashboard</span>
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.warn("Failed to load history items: " + err.message);
    }
}

async function loadHistoryItem(historyId) {
    showSpinner("Restoring analysis history session...");
    
    try {
        const response = await fetch(`/api/history/load/${historyId}`);
        const result = await response.json();
        hideSpinner();
        
        if (!response.ok) {
            alert("Failed to load history project: " + (result.error || "Unknown error"));
            return;
        }
        
        activeDashboardData = result;
        activePlotlyCharts = result.plotly_charts;
        datasetMetadata = result.datasetMetadata;
        datasetProfile = result.datasetMetadata;
        
        document.getElementById('step-upload').classList.add('hidden');
        document.getElementById('step-cleaning').classList.add('hidden');
        document.getElementById('step-logs').classList.add('hidden');
        document.getElementById('step-dashboard').classList.remove('hidden');
        
        renderDashboardKPIs();
        renderDashboardInsights();
        renderOutliersWarning();
        renderDashboardCharts();
        
        document.getElementById('navbar-alerts-bell-container').classList.remove('hidden');
        evaluateThresholdAlerts();
        
        tablePage = 0;
        tableQuery = '';
        document.getElementById('table-search').value = '';
        renderTableExplorer();
    } catch (e) {
        hideSpinner();
        alert("Session recovery failed: " + e.message);
    }
}

// 12. No-Code Pivot Table Grid Orchestrator (Option F)
function switchExplorerTab(tab) {
    const btnRecords = document.getElementById('tab-btn-records');
    const btnPivot = document.getElementById('tab-btn-pivot');
    const btnPredictive = document.getElementById('tab-btn-predictive');
    const btnAlerts = document.getElementById('tab-btn-alerts');
    const viewRecords = document.getElementById('explorer-records-view');
    const viewPivot = document.getElementById('explorer-pivot-view');
    const viewPredictive = document.getElementById('explorer-predictive-view');
    const viewAlerts = document.getElementById('explorer-alerts-view');
    
    btnRecords.className = "px-4 py-2 text-xs rounded-lg font-semibold text-slate-400 hover:text-slate-200 transition-all";
    btnPivot.className = "px-4 py-2 text-xs rounded-lg font-semibold text-slate-400 hover:text-slate-200 transition-all ml-1";
    btnPredictive.className = "px-4 py-2 text-xs rounded-lg font-semibold text-slate-400 hover:text-slate-200 transition-all ml-1";
    btnAlerts.className = "px-4 py-2 text-xs rounded-lg font-semibold text-slate-400 hover:text-slate-200 transition-all ml-1";
    
    viewRecords.classList.add('hidden');
    viewPivot.classList.add('hidden');
    viewPredictive.classList.add('hidden');
    viewAlerts.classList.add('hidden');
    
    if (tab === 'records') {
        btnRecords.className = "px-4 py-2 text-xs rounded-lg font-semibold bg-indigo-600 text-white transition-all";
        viewRecords.classList.remove('hidden');
    } else if (tab === 'pivot') {
        btnPivot.className = "px-4 py-2 text-xs rounded-lg font-semibold bg-indigo-600 text-white transition-all ml-1";
        viewPivot.classList.remove('hidden');
        populatePivotDropdowns();
    } else if (tab === 'predictive') {
        btnPredictive.className = "px-4 py-2 text-xs rounded-lg font-semibold bg-indigo-600 text-white transition-all ml-1";
        viewPredictive.classList.remove('hidden');
        populatePredictiveDropdowns();
    } else if (tab === 'alerts') {
        btnAlerts.className = "px-4 py-2 text-xs rounded-lg font-semibold bg-indigo-600 text-white transition-all ml-1";
        viewAlerts.classList.remove('hidden');
        populateAlertDropdowns();
        loadAlertRules();
    }
}

function populatePivotDropdowns() {
    const meta = datasetMetadata || (activeDashboardData ? activeDashboardData.datasetMetadata : null);
    if (!meta || !meta.columns) return;
    
    const rowSelect = document.getElementById('pivot-row-select');
    const colSelect = document.getElementById('pivot-col-select');
    const valSelect = document.getElementById('pivot-val-select');
    
    rowSelect.innerHTML = '';
    colSelect.innerHTML = '<option value="">(None)</option>';
    valSelect.innerHTML = '';
    
    Object.entries(meta.columns).forEach(([colName, colInfo]) => {
        const type = colInfo.inferred_type;
        
        const opt1 = document.createElement('option');
        opt1.value = colName;
        opt1.textContent = colName;
        rowSelect.appendChild(opt1);
        
        const opt2 = document.createElement('option');
        opt2.value = colName;
        opt2.textContent = colName;
        colSelect.appendChild(opt2);
        
        if (type === 'numeric') {
            const opt3 = document.createElement('option');
            opt3.value = colName;
            opt3.textContent = colName;
            valSelect.appendChild(opt3);
        }
    });
}

async function calculatePivotTable() {
    const row = document.getElementById('pivot-row-select').value;
    const col = document.getElementById('pivot-col-select').value;
    const val = document.getElementById('pivot-val-select').value;
    const agg = document.getElementById('pivot-agg-select').value;
    
    if (!row || !val) {
        alert("Please select both Row grouping and calculation Value fields.");
        return;
    }
    
    showSpinner("Computing pivot matrix...");
    
    try {
        const response = await fetch('/api/pivot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ row, col, val, agg })
        });
        
        const result = await response.json();
        hideSpinner();
        
        if (!response.ok) {
            alert("Pivot calculation failed: " + (result.error || "Unknown error"));
            return;
        }
        
        const thead = document.getElementById('pivot-thead-row');
        const tbody = document.getElementById('pivot-tbody-rows');
        thead.innerHTML = '';
        tbody.innerHTML = '';
        
        const thRowLabel = document.createElement('th');
        thRowLabel.className = "px-6 py-3 text-left font-bold text-slate-200 border-b border-slate-800 bg-slate-950";
        thRowLabel.textContent = `${row} \\ ${col || '(Value)'}`;
        thead.appendChild(thRowLabel);
        
        result.columns.forEach(cName => {
            const th = document.createElement('th');
            th.className = "px-6 py-3 text-right font-bold text-slate-200 border-b border-slate-800 bg-slate-950";
            th.textContent = cName;
            thead.appendChild(th);
        });
        
        result.index.forEach((idxVal, rowIndex) => {
            const tr = document.createElement('tr');
            tr.className = rowIndex % 2 === 0 ? 'bg-slate-900/40 hover:bg-slate-900/60' : 'bg-slate-955/20 hover:bg-slate-900/40';
            
            const tdIndex = document.createElement('td');
            tdIndex.className = "px-6 py-3.5 text-left font-semibold text-slate-300 border-b border-slate-850";
            tdIndex.textContent = idxVal;
            tr.appendChild(tdIndex);
            
            result.cells[rowIndex].forEach(cellVal => {
                const tdVal = document.createElement('td');
                tdVal.className = "px-6 py-3.5 text-right font-mono text-slate-200 border-b border-slate-850";
                
                if (typeof cellVal === 'number') {
                    tdVal.textContent = cellVal.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 2 });
                } else {
                    tdVal.textContent = cellVal;
                }
                tr.appendChild(tdVal);
            });
            tbody.appendChild(tr);
        });
    } catch (e) {
        hideSpinner();
        alert("Server communication crashed during pivot: " + e.message);
    }
}

// 13. Predictive ML Sandbox Builder & Outcome Simulator (Option G)
function togglePredictiveTargetMode(val) {
    const kContainer = document.getElementById('clustering-k-container');
    const button = document.querySelector('button[onclick="trainPredictiveModel()"]');
    const labelMetrics = document.querySelectorAll('#explorer-predictive-view div.grid-cols-3 uppercase');
    
    if (val === '--clustering--') {
        kContainer.classList.remove('hidden');
        button.querySelector('span').textContent = "Run KMeans Clustering";
        labelMetrics[0].textContent = "Silhouette Index";
        labelMetrics[1].textContent = "K clusters size";
        labelMetrics[2].textContent = "WCSS Inertia";
    } else {
        kContainer.classList.add('hidden');
        const meta = datasetMetadata || (activeDashboardData ? activeDashboardData.datasetMetadata : null);
        const colInfo = (meta && meta.columns) ? meta.columns[val] : null;
        const type = colInfo ? colInfo.inferred_type : 'numeric';
        
        if (type === 'numeric') {
            button.querySelector('span').textContent = "Train Regressor Model";
            labelMetrics[0].textContent = "R² Accuracy Score";
            labelMetrics[1].textContent = "Mean Abs Error (MAE)";
            labelMetrics[2].textContent = "Mean Sq Error (MSE)";
        } else {
            button.querySelector('span').textContent = "Train Classifier Model";
            labelMetrics[0].textContent = "Accuracy Score";
            labelMetrics[1].textContent = "Weighted F1-Score";
            labelMetrics[2].textContent = "Precision Score";
        }
    }
}

function populatePredictiveDropdowns() {
    const meta = datasetMetadata || (activeDashboardData ? activeDashboardData.datasetMetadata : null);
    if (!meta || !meta.columns) return;
    
    const targetSelect = document.getElementById('predict-target-select');
    const featuresContainer = document.getElementById('predict-features-container');
    
    targetSelect.innerHTML = '';
    featuresContainer.innerHTML = '';
    
    Object.entries(meta.columns).forEach(([colName, colInfo]) => {
        const type = colInfo.inferred_type;
        const opt = document.createElement('option');
        opt.value = colName;
        opt.textContent = `${colName} (${type})`;
        targetSelect.appendChild(opt);
    });
    
    const optCluster = document.createElement('option');
    optCluster.value = '--clustering--';
    optCluster.textContent = '[Unsupervised KMeans Clustering]';
    targetSelect.appendChild(optCluster);
    
    Object.entries(meta.columns).forEach(([colName, colInfo]) => {
        const type = colInfo.inferred_type;
        
        const wrapper = document.createElement('label');
        wrapper.className = "flex items-center space-x-2 text-slate-300 py-1 cursor-pointer hover:text-white transition-colors";
        
        const checkbox = document.createElement('input');
        checkbox.type = "checkbox";
        checkbox.value = colName;
        checkbox.className = "predict-feature-check w-4 h-4 text-indigo-600 bg-slate-955 border-slate-800 rounded focus:ring-indigo-500";
        checkbox.checked = true;
        
        const labelText = document.createElement('span');
        labelText.textContent = `${colName} (${type})`;
        
        wrapper.appendChild(checkbox);
        wrapper.appendChild(labelText);
        featuresContainer.appendChild(wrapper);
    });
    
    togglePredictiveTargetMode(targetSelect.value);
}

async function trainPredictiveModel() {
    const target = document.getElementById('predict-target-select').value;
    const checkboxes = document.querySelectorAll('.predict-feature-check:checked');
    const nClusters = document.getElementById('predict-k-select').value;
    
    const predictors = [];
    checkboxes.forEach(cb => {
        if (cb.value !== target) {
            predictors.push(cb.value);
        }
    });
    
    if (!target) {
        alert("Please select a target variable or unsupervised clustering.");
        return;
    }
    
    if (predictors.length === 0) {
        alert("Please select at least one predictor feature.");
        return;
    }
    
    showSpinner("Building dynamic machine learning model...");
    
    const nEst = document.getElementById('ml-param-estimators').value;
    const mDepth = document.getElementById('ml-param-depth').value;
    const mSplit = document.getElementById('ml-param-split').value;
    const autoTune = document.getElementById('ml-opt-autotune').checked;
    
    try {
        const response = await fetch('/api/predictive/train', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target,
                predictors,
                n_clusters: parseInt(nClusters),
                n_estimators: parseInt(nEst),
                max_depth: mDepth,
                min_samples_split: parseInt(mSplit),
                autotune: autoTune
            })
        });
        
        const result = await response.json();
        hideSpinner();
        
        if (!response.ok) {
            alert("Model build failed: " + (result.error || "Unknown error"));
            return;
        }
        
        // Show hyperparams status badge
        const badge = document.getElementById('ml-parameters-badge');
        if (badge) {
            badge.classList.remove('hidden');
            const tp = result.tuned_params || {};
            const nest = tp.n_estimators || nEst;
            const depth = tp.max_depth === null ? 'Unlimited' : tp.max_depth;
            const split = tp.min_samples_split || mSplit;
            document.getElementById('ml-parameters-text').textContent = `n_estimators: ${nest} | max_depth: ${depth} | min_split: ${split}`;
            document.getElementById('ml-autotune-status').textContent = autoTune ? "Auto-Tuned" : "Manual";
        }
        
        if (result.mode === 'clustering') {
            document.getElementById('ml-metric-r2').textContent = "N/A";
            document.getElementById('ml-metric-mae').textContent = nClusters;
            document.getElementById('ml-metric-mse').textContent = result.metrics.inertia.toLocaleString(undefined, { maximumFractionDigits: 1 });
            
            const clusters = result.chart_data.map(d => d.cluster);
            const xCoords = result.chart_data.map(d => d.x);
            const yCoords = result.chart_data.map(d => d.y);
            
            const traceClusters = {
                x: xCoords,
                y: yCoords,
                mode: 'markers',
                type: 'scatter',
                text: result.chart_data.map(d => `Row: ${d.label} | Cluster: ${d.cluster}`),
                marker: {
                    color: clusters,
                    colorscale: 'Portland',
                    size: 8,
                    opacity: 0.85,
                    showscale: true,
                    colorbar: { title: 'Cluster ID', thickness: 12 }
                }
            };
            
            const plotLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { l: 40, r: 20, t: 20, b: 40 },
                font: { color: THEMES[currentTheme].text, family: 'Outfit, sans-serif', size: 10 },
                xaxis: { title: 'PCA component 1', gridcolor: THEMES[currentTheme].grid, linecolor: THEMES[currentTheme].grid },
                yaxis: { title: 'PCA component 2', gridcolor: THEMES[currentTheme].grid, linecolor: THEMES[currentTheme].grid },
                showlegend: false
            };
            
            Plotly.newPlot('ml-regression-chart', [traceClusters], plotLayout, { responsive: true, displayModeBar: false });
        }
        else if (result.mode === 'classification') {
            document.getElementById('ml-metric-r2').textContent = result.metrics.accuracy.toFixed(4);
            document.getElementById('ml-metric-mae').textContent = result.metrics.f1_score.toFixed(4);
            document.getElementById('ml-metric-mse').textContent = result.metrics.precision.toFixed(4);
            
            const cm = result.confusion_matrix;
            const traceHeatmap = {
                z: cm.z,
                x: cm.x,
                y: cm.y,
                type: 'heatmap',
                colorscale: 'Portland',
                showscale: true
            };
            
            const plotLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { l: 60, r: 20, t: 20, b: 60 },
                font: { color: THEMES[currentTheme].text, family: 'Outfit, sans-serif', size: 10 },
                xaxis: { title: 'Predicted Class', gridcolor: 'rgba(0,0,0,0)', linecolor: THEMES[currentTheme].grid },
                yaxis: { title: 'Actual Class', gridcolor: 'rgba(0,0,0,0)', linecolor: THEMES[currentTheme].grid }
            };
            
            Plotly.newPlot('ml-regression-chart', [traceHeatmap], plotLayout, { responsive: true, displayModeBar: false });
        }
        else {
            document.getElementById('ml-metric-r2').textContent = result.metrics.r2.toFixed(4);
            document.getElementById('ml-metric-mae').textContent = result.metrics.mae.toLocaleString(undefined, { maximumFractionDigits: 4 });
            document.getElementById('ml-metric-mse').textContent = result.metrics.mse.toLocaleString(undefined, { maximumFractionDigits: 4 });
            
            const actuals = result.actual_vs_predicted.map(d => d.actual);
            const predicted = result.actual_vs_predicted.map(d => d.predicted);
            const minVal = Math.min(...actuals, ...predicted);
            const maxVal = Math.max(...actuals, ...predicted);
            
            const traceScatter = {
                x: actuals,
                y: predicted,
                mode: 'markers',
                name: 'Predictions',
                type: 'scatter',
                marker: {
                    color: THEMES[currentTheme].primary,
                    size: 8,
                    opacity: 0.7,
                    line: { color: THEMES[currentTheme].primary, width: 1 }
                }
            };
            
            const traceLine = {
                x: [minVal, maxVal],
                y: [minVal, maxVal],
                mode: 'lines',
                name: 'y=x line',
                type: 'scatter',
                line: { color: THEMES[currentTheme].secondary || '#ec4899', width: 2, dash: 'dash' }
            };
            
            const plotLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { l: 50, r: 20, t: 20, b: 50 },
                font: { color: THEMES[currentTheme].text, family: 'Outfit, sans-serif', size: 10 },
                xaxis: { title: 'Actual Value', gridcolor: THEMES[currentTheme].grid, linecolor: THEMES[currentTheme].grid },
                yaxis: { title: 'Predicted Value', gridcolor: THEMES[currentTheme].grid, linecolor: THEMES[currentTheme].grid },
                showlegend: false
            };
            
            Plotly.newPlot('ml-regression-chart', [traceScatter, traceLine], plotLayout, { responsive: true, displayModeBar: false });
        }
        
        const simulatorInputs = document.getElementById('ml-simulator-inputs');
        simulatorInputs.innerHTML = '';
        
        Object.entries(result.predictor_meta).forEach(([featureName, featureMeta]) => {
            const inputWrapper = document.createElement('div');
            inputWrapper.className = "bg-slate-900/60 p-4 border border-slate-800/80 rounded-xl space-y-2";
            
            if (featureMeta.type === 'categorical') {
                inputWrapper.innerHTML = `
                    <label class="block text-xs text-slate-400 font-semibold">${featureName}</label>
                    <select class="ml-simulator-val w-full bg-slate-955 border border-slate-850 text-slate-200 rounded-lg p-2.5 text-xs focus:border-indigo-500 focus:outline-none" data-feature="${featureName}">
                        ${featureMeta.categories.map(cat => `<option value="${cat}" ${cat === featureMeta.default ? 'selected' : ''}>${cat}</option>`).join('')}
                    </select>
                `;
            } else {
                const range = featureMeta.max - featureMeta.min;
                const step = range === 0 ? 0.1 : (range / 100);
                inputWrapper.innerHTML = `
                    <div class="flex justify-between items-center">
                        <label class="block text-xs text-slate-400 font-semibold">${featureName}</label>
                        <span class="text-xs font-mono font-bold text-indigo-400" id="slider-val-${featureName}">${featureMeta.default.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                    </div>
                    <input type="range" class="ml-simulator-val w-full h-1.5 bg-slate-955 rounded-lg appearance-none cursor-pointer focus:outline-none accent-indigo-500" 
                           data-feature="${featureName}"
                           min="${featureMeta.min}" 
                           max="${featureMeta.max}" 
                           step="${step}" 
                           value="${featureMeta.default}"
                           oninput="document.getElementById('slider-val-${featureName}').textContent = parseFloat(this.value).toLocaleString(undefined, {maximumFractionDigits: 2})">
                `;
            }
            simulatorInputs.appendChild(inputWrapper);
        });
        
        const simElements = document.querySelectorAll('.ml-simulator-val');
        simElements.forEach(el => {
            el.addEventListener('change', runSimulatorInference);
            el.addEventListener('input', runSimulatorInference);
        });
        
        document.getElementById('ml-simulator-container').classList.remove('hidden');
        
        const outcomeHeader = document.querySelector('#ml-simulator-container span.text-slate-500');
        if (result.mode === 'clustering') {
            outcomeHeader.textContent = "Simulations match features to PCA clusters in real-time.";
            document.querySelector('#ml-simulator-container div.text-slate-400').textContent = "Projected Cluster Belonging";
        } else if (result.mode === 'classification') {
            outcomeHeader.textContent = "Simulations calculate probability distributions on classifier classes.";
            document.querySelector('#ml-simulator-container div.text-slate-400').textContent = "Projected Category & Confidence";
        } else {
            outcomeHeader.textContent = "Simulations are run in real-time on your trained Random Forest regressor.";
            document.querySelector('#ml-simulator-container div.text-slate-400').textContent = "Projected Output Prediction";
        }
        
        runSimulatorInference();
    } catch (e) {
        hideSpinner();
        alert("Server communication crashed during training: " + e.message);
    }
}

let simulatorTimeout = null;
function runSimulatorInference() {
    if (simulatorTimeout) clearTimeout(simulatorTimeout);
    
    simulatorTimeout = setTimeout(async () => {
        const inputs = {};
        const elements = document.querySelectorAll('.ml-simulator-val');
        elements.forEach(el => {
            const feature = el.getAttribute('data-feature');
            inputs[feature] = el.value;
        });
        
        try {
            const response = await fetch('/api/predictive/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ inputs })
            });
            
            if (!response.ok) return;
            
            const result = await response.json();
            const valEl = document.getElementById('ml-projection-value');
            
            const pred = result.prediction;
            if (typeof pred === 'number') {
                valEl.textContent = pred.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            } else {
                valEl.textContent = pred;
            }
        } catch (e) {
            console.warn("Simulator projection failed: " + e.message);
        }
    }, 150);
}

// 14. Multi-Tenant Workspace & Authentication Routes (Option J)
let authMode = 'login';

function showMarketingHome() {
    document.getElementById('marketing-view').classList.remove('hidden');
    document.getElementById('workspace-view').classList.add('hidden');
    document.getElementById('step-cleaning').classList.add('hidden');
    document.getElementById('step-dashboard').classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
    }
}

function openAuthModal(mode = 'login') {
    authMode = mode;
    document.getElementById('auth-modal').classList.remove('hidden');
    document.getElementById('auth-error').classList.add('hidden');
    document.getElementById('auth-username').value = '';
    document.getElementById('auth-password').value = '';
    updateAuthModalUI();
}

function closeAuthModal() {
    document.getElementById('auth-modal').classList.add('hidden');
}

function toggleAuthMode() {
    authMode = (authMode === 'login') ? 'register' : 'login';
    document.getElementById('auth-error').classList.add('hidden');
    updateAuthModalUI();
}

function updateAuthModalUI() {
    const title = document.getElementById('auth-modal-title');
    const desc = document.getElementById('auth-modal-desc');
    const submitBtnSpan = document.getElementById('auth-submit-btn').querySelector('span');
    const prompt = document.getElementById('auth-toggle-prompt');
    
    if (authMode === 'login') {
        title.textContent = "Sign In to InsightFlow";
        desc.textContent = "Access your private multi-tenant workspaces";
        submitBtnSpan.textContent = "Sign In";
        prompt.innerHTML = `Don't have an account? <a href="#" onclick="toggleAuthMode(); return false;" class="text-indigo-400 font-bold hover:underline">Sign Up</a>`;
    } else {
        title.textContent = "Create Workspace Account";
        desc.textContent = "Unlock unlimited projects history and ML models";
        submitBtnSpan.textContent = "Create Account";
        prompt.innerHTML = `Already have an account? <a href="#" onclick="toggleAuthMode(); return false;" class="text-indigo-400 font-bold hover:underline">Sign In</a>`;
    }
}

async function submitAuthForm() {
    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;
    const errEl = document.getElementById('auth-error');
    
    if (!username || !password) {
        errEl.textContent = "Please fill in all credentials.";
        errEl.classList.remove('hidden');
        return;
    }
    
    const url = (authMode === 'login') ? '/api/auth/login' : '/api/auth/register';
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const result = await response.json();
        
        if (!response.ok) {
            errEl.textContent = result.error || "Authentication failed.";
            errEl.classList.remove('hidden');
            return;
        }
        
        closeAuthModal();
        if (authMode === 'register') {
            alert("Registration successful! You can now log in.");
            openAuthModal('login');
        } else {
            await checkAuthStatus();
        }
    } catch (e) {
        errEl.textContent = "Server communication crashed: " + e.message;
        errEl.classList.remove('hidden');
    }
}

async function logout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        datasetMetadata = null;
        activeDashboardData = null;
        await checkAuthStatus();
    } catch (e) {
        console.warn("Logout failed: " + e.message);
    }
}

async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/status');
        const result = await response.json();
        
        const authContainer = document.getElementById('navbar-auth');
        
        if (result.logged_in) {
            authContainer.innerHTML = `
                <div class="flex items-center space-x-3">
                    <span class="text-indigo-300 font-semibold font-mono">Tenant: ${result.username}</span>
                    <button onclick="logout()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-750 font-semibold text-slate-300 rounded-lg transition-colors">Sign Out</button>
                </div>
            `;
            document.getElementById('marketing-view').classList.add('hidden');
            document.getElementById('workspace-view').classList.remove('hidden');
            loadHistoryList();
        } else {
            authContainer.innerHTML = `
                <div class="flex items-center space-x-2">
                    <button onclick="openAuthModal('login')" class="px-3.5 py-1.5 text-slate-300 hover:text-white font-semibold transition-colors">Sign In</button>
                    <button onclick="openAuthModal('register')" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 font-bold text-white rounded-xl shadow-lg shadow-indigo-600/20 transition-all">Sign Up</button>
                </div>
            `;
            document.getElementById('marketing-view').classList.remove('hidden');
            document.getElementById('workspace-view').classList.add('hidden');
            document.getElementById('step-cleaning').classList.add('hidden');
            document.getElementById('step-dashboard').classList.add('hidden');
        }
    } catch (e) {
        console.warn("Auth status lookup failed: " + e.message);
    }
}

// 15. Automated KPI Alerts & Threshold Notifications (Option K)
function populateAlertDropdowns() {
    const colSelect = document.getElementById('alert-col-select');
    if (!colSelect || !activeDashboardData || !activeDashboardData.datasetMetadata) return;
    
    colSelect.innerHTML = '';
    const cols = activeDashboardData.datasetMetadata.columns || [];
    cols.forEach(col => {
        const opt = document.createElement('option');
        opt.value = col.name;
        opt.textContent = `${col.name} (${col.type})`;
        colSelect.appendChild(opt);
    });
}

async function loadAlertRules() {
    const tbody = document.getElementById('alert-rules-tbody');
    if (!tbody) return;
    
    try {
        const response = await fetch('/api/alerts/rules');
        const result = await response.json();
        
        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-rose-500">Failed to load rules.</td></tr>`;
            return;
        }
        
        const rules = result.rules || [];
        if (rules.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500">No active alert rules configured yet.</td></tr>`;
            return;
        }
        
        tbody.innerHTML = '';
        rules.forEach(rule => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-slate-900/50 transition-colors";
            
            const metricLabel = rule.metric.replace('_', ' ').toUpperCase();
            const sevBadge = rule.severity === 'critical' 
                ? `<span class="px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 font-mono text-[10px]">Critical</span>` 
                : `<span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-mono text-[10px]">Warning</span>`;
                
            tr.innerHTML = `
                <td class="px-4 py-3.5 font-semibold text-slate-200 font-mono">${rule.column_name}</td>
                <td class="px-4 py-3.5 text-slate-400">${metricLabel}</td>
                <td class="px-4 py-3.5 text-slate-300 font-mono">${rule.operator} ${rule.value.toLocaleString()}</td>
                <td class="px-4 py-3.5">${sevBadge}</td>
                <td class="px-4 py-3.5 text-right">
                    <button onclick="deleteAlertRule(${rule.id})" class="p-1 text-slate-500 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-rose-500">Error: ${e.message}</td></tr>`;
    }
}

async function addAlertRule() {
    const col = document.getElementById('alert-col-select').value;
    const metric = document.getElementById('alert-metric-select').value;
    const op = document.getElementById('alert-op-select').value;
    const valInput = document.getElementById('alert-val-input');
    const severity = document.getElementById('alert-sev-select').value;
    
    const value = parseFloat(valInput.value);
    if (isNaN(value)) {
        alert("Please enter a valid numeric threshold limit.");
        return;
    }
    
    try {
        const response = await fetch('/api/alerts/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                column_name: col,
                metric: metric,
                operator: op,
                value: value,
                severity: severity
            })
        });
        
        const result = await response.json();
        if (!response.ok) {
            alert("Failed to add threshold rule: " + (result.error || "Unknown error"));
            return;
        }
        
        valInput.value = '';
        await loadAlertRules();
        await evaluateThresholdAlerts();
    } catch (e) {
        alert("Communications error: " + e.message);
    }
}

async function deleteAlertRule(ruleId) {
    if (!confirm("Are you sure you want to remove this alert threshold rule?")) return;
    
    try {
        const response = await fetch(`/api/alerts/rules/${ruleId}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        if (!response.ok) {
            alert("Failed to delete rule: " + (result.error || "Unknown error"));
            return;
        }
        await loadAlertRules();
        await evaluateThresholdAlerts();
    } catch (e) {
        alert("Communications error: " + e.message);
    }
}

let alertsDropdownOpen = false;
function toggleAlertsDropdown() {
    alertsDropdownOpen = !alertsDropdownOpen;
    const drop = document.getElementById('alerts-dropdown');
    if (alertsDropdownOpen) {
        drop.classList.remove('hidden');
    } else {
        drop.classList.add('hidden');
    }
}

async function evaluateThresholdAlerts() {
    const listContainer = document.getElementById('alerts-list-container');
    const badge = document.getElementById('alerts-badge');
    const countEl = document.getElementById('alerts-count');
    
    if (!listContainer) return;
    
    try {
        const response = await fetch('/api/alerts/evaluate');
        const result = await response.json();
        
        if (!response.ok) {
            listContainer.innerHTML = `<div class="text-rose-500 text-center py-2">Evaluation failed.</div>`;
            badge.classList.add('hidden');
            countEl.textContent = '0 alerts';
            return;
        }
        
        const alerts = result.alerts || [];
        countEl.textContent = `${alerts.length} alert${alerts.length === 1 ? '' : 's'}`;
        
        if (alerts.length === 0) {
            listContainer.innerHTML = `<div class="text-slate-500 text-center py-4">No active breaches. All metrics stable.</div>`;
            badge.classList.add('hidden');
            return;
        }
        
        badge.classList.remove('hidden');
        
        listContainer.innerHTML = '';
        alerts.forEach(alert => {
            const div = document.createElement('div');
            const colorClass = alert.severity === 'critical' ? 'border-rose-500/20 bg-rose-500/5' : 'border-amber-500/20 bg-amber-500/5';
            const iconColor = alert.severity === 'critical' ? 'text-rose-400' : 'text-amber-400';
            
            div.className = `p-3 rounded-xl border ${colorClass} flex items-start space-x-2.5`;
            div.innerHTML = `
                <svg class="w-4 h-4 ${iconColor} shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                <div class="leading-relaxed text-[10px]">
                    <span class="font-bold text-slate-200 capitalize block">${alert.severity} Breach</span>
                    <span class="text-slate-400 mt-0.5 block leading-normal">${alert.message}</span>
                </div>
            `;
            listContainer.appendChild(div);
        });
    } catch (e) {
        listContainer.innerHTML = `<div class="text-rose-500 text-center py-2">Error: ${e.message}</div>`;
    }
}

let hyperparamsCollapsed = true;
function toggleHyperparamsCollapse() {
    hyperparamsCollapsed = !hyperparamsCollapsed;
    const fields = document.getElementById('ml-hyperparams-fields');
    const arrow = document.getElementById('hp-arrow');
    if (hyperparamsCollapsed) {
        fields.classList.add('hidden');
        arrow.classList.remove('rotate-180');
    } else {
        fields.classList.remove('hidden');
        arrow.classList.add('rotate-180');
    }
}

// Window load event bindings
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
});

