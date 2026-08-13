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
        cardBg: '#0f172a'
    },
    emerald: {
        primary: '#10b981',
        secondary: '#14b8a6',
        grid: '#064e3b',
        text: '#a7f3d0',
        bodyBg: '#021e17',
        cardBg: '#022c22'
    },
    retro: {
        primary: '#f59e0b',
        secondary: '#d97706',
        grid: '#292524',
        text: '#f7fee7',
        bodyBg: '#141210',
        cardBg: '#1c1917'
    },
    slate: {
        primary: '#cbd5e1',
        secondary: '#94a3b8',
        grid: '#334155',
        text: '#cbd5e1',
        bodyBg: '#0f172a',
        cardBg: '#1e293b'
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
