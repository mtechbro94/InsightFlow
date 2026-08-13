import os
import json
import pandas as pd
from fpdf import FPDF

def generate_html_dashboard(df, cleaned_df, metadata, eda_results, insights, kpis, plotly_json_charts, output_path):
    """
    Generates a single standalone HTML dashboard containing the data, styling, and interactive scripting.
    Loads Tailwind CSS and Plotly.js from CDNs. Allows client-side filtering, sorting, and dynamic charts.
    """
    # Serialize data to embed directly in the HTML
    cleaned_records = cleaned_df.to_dict(orient='records')
    cleaned_json = json.dumps(cleaned_records, default=str)
    kpis_json = json.dumps(kpis)
    insights_json = json.dumps(insights)
    profiles_json = json.dumps(metadata['columns'])
    charts_json = json.dumps(plotly_json_charts)

    # HTML Template
    html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Data Analysis Dashboard - {metadata.get('filename', 'Dataset')}</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Plotly.js CDN -->
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        slate: {{
                            850: '#1e293b',
                            950: '#020617',
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: #020617;
        }}
        ::-webkit-scrollbar-thumb {{
            background: #1e293b;
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #334155;
        }}
    </style>
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen flex flex-col">

    <!-- Top Navigation Bar -->
    <header class="bg-slate-900 border-b border-slate-800 py-4 px-6 flex justify-between items-center shadow-lg">
        <div class="flex items-center space-x-3">
            <div class="bg-indigo-600 text-white p-2 rounded-lg font-bold tracking-wider text-sm shadow-md shadow-indigo-600/30">
                ADA
            </div>
            <div>
                <h1 class="text-xl font-bold tracking-tight">Automated Analysis Dashboard</h1>
                <p class="text-xs text-slate-400">Dataset: <span class="text-indigo-400 font-medium">{metadata.get('filename', 'Dataset')}</span></p>
            </div>
        </div>
        <div class="text-xs text-slate-400 text-right">
            <div>Records: <span id="header-records-count" class="text-slate-200 font-semibold">{metadata.get('num_records', 0):,}</span></div>
            <div>Features: <span class="text-slate-200 font-semibold">{metadata.get('num_features', 0)}</span></div>
        </div>
    </header>

    <div class="flex flex-1 overflow-hidden">
        <!-- Sidebar Filters -->
        <aside class="w-80 bg-slate-900 border-r border-slate-800 p-6 flex flex-col space-y-6 overflow-y-auto shrink-0">
            <div>
                <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Dashboard Filters</h2>
                
                <!-- Reset Button -->
                <button onclick="resetFilters()" class="w-full mb-4 py-2 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-sm rounded-lg transition-all border border-slate-700">
                    Reset All Filters
                </button>

                <div id="filter-controls-container" class="space-y-4">
                    <!-- JavaScript will inject filters here -->
                </div>
            </div>
        </aside>

        <!-- Main Content Area -->
        <main class="flex-1 p-8 overflow-y-auto space-y-8">
            
            <!-- Section 1: KPI Cards -->
            <section>
                <h2 class="text-lg font-bold tracking-tight mb-4 flex items-center">
                    <span class="w-1.5 h-6 bg-indigo-600 rounded-full mr-2"></span> Key Performance Indicators
                </h2>
                <div id="kpi-cards-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <!-- JS will populate cards -->
                </div>
            </section>

            <!-- Section 2: Insights Summary -->
            <section class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <!-- Insight Deck -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col">
                    <div class="flex justify-between items-center mb-6">
                        <h3 class="text-lg font-bold flex items-center">
                            <svg class="w-5 h-5 text-indigo-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 .364l-.707 .707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548 .547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                            Automated Data Insights
                        </h3>
                        <div class="flex space-x-1" id="insight-tabs">
                            <button onclick="switchInsightTab('business')" id="tab-business" class="px-3 py-1 text-xs rounded-md bg-indigo-600 text-white font-medium">Business</button>
                            <button onclick="switchInsightTab('trend')" id="tab-trend" class="px-3 py-1 text-xs rounded-md bg-slate-800 text-slate-400 hover:text-slate-200">Trends</button>
                            <button onclick="switchInsightTab('relationship')" id="tab-relationship" class="px-3 py-1 text-xs rounded-md bg-slate-800 text-slate-400 hover:text-slate-200">Relations</button>
                            <button onclick="switchInsightTab('quality')" id="tab-quality" class="px-3 py-1 text-xs rounded-md bg-slate-800 text-slate-400 hover:text-slate-200">Quality</button>
                        </div>
                    </div>
                    
                    <div class="flex-1 overflow-y-auto max-h-[300px] pr-2">
                        <ul id="insights-list" class="space-y-3">
                            <!-- JS will inject insights list -->
                        </ul>
                    </div>
                </div>

                <!-- Data Quality Profile -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <h3 class="text-lg font-bold flex items-center mb-6">
                        <svg class="w-5 h-5 text-emerald-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        Data Quality Summary
                    </h3>
                    <div class="space-y-4">
                        <div class="flex justify-between items-center py-2 border-b border-slate-800">
                            <span class="text-slate-400">Total Rows Analyzed</span>
                            <span class="font-semibold text-slate-200">{metadata.get('num_records', 0):,}</span>
                        </div>
                        <div class="flex justify-between items-center py-2 border-b border-slate-800">
                            <span class="text-slate-400">Total Columns</span>
                            <span class="font-semibold text-slate-200">{metadata.get('num_features', 0)}</span>
                        </div>
                        <div class="flex justify-between items-center py-2 border-b border-slate-800">
                            <span class="text-slate-400">Missing Values</span>
                            <span class="font-semibold {'text-red-400' if metadata.get('total_missing', 0) > 0 else 'text-emerald-400'}">{metadata.get('total_missing', 0):,}</span>
                        </div>
                        <div class="flex justify-between items-center py-2 border-b border-slate-800">
                            <span class="text-slate-400">Duplicate Rows Removed</span>
                            <span class="font-semibold text-slate-200">{metadata.get('duplicate_count', 0):,}</span>
                        </div>
                        <div class="flex justify-between items-center py-2">
                            <span class="text-slate-400">Inferred Types Summary</span>
                            <span class="text-xs font-semibold px-2 py-1 bg-slate-800 rounded text-indigo-400" id="inferred-summary-badge"></span>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Section 3: Visual Analytics Panel -->
            <section>
                <h2 class="text-lg font-bold tracking-tight mb-4 flex items-center">
                    <span class="w-1.5 h-6 bg-pink-500 rounded-full mr-2"></span> Visual Analysis
                </h2>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <!-- Standard charts will render here -->
                    <div id="chart-panel-1" class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl min-h-[400px]"></div>
                    <div id="chart-panel-2" class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl min-h-[400px]"></div>
                    <div id="chart-panel-3" class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl min-h-[400px]"></div>
                    <div id="chart-panel-4" class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl min-h-[400px]"></div>
                </div>
            </section>

            <!-- Section 4: Detailed Data Explorer -->
            <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 space-y-4 md:space-y-0">
                    <div>
                        <h2 class="text-lg font-bold tracking-tight flex items-center">
                            <span class="w-1.5 h-6 bg-emerald-500 rounded-full mr-2"></span> Detailed Data Explorer
                        </h2>
                        <p class="text-xs text-slate-400">View, search, and navigate your cleaned dataset.</p>
                    </div>
                    <div class="flex items-center space-x-2">
                        <input type="text" id="explorer-search" oninput="handleTableSearch(this.value)" placeholder="Search table..." class="bg-slate-800 text-slate-100 text-sm px-4 py-2 rounded-lg border border-slate-700 focus:outline-none focus:border-indigo-500 transition-colors w-64">
                    </div>
                </div>

                <!-- Table Wrapper -->
                <div class="overflow-x-auto w-full border border-slate-800 rounded-lg">
                    <table class="w-full text-sm text-left text-slate-300">
                        <thead class="text-xs text-slate-400 uppercase bg-slate-800/50 border-b border-slate-800">
                            <tr id="explorer-thead">
                                <!-- JS Header injection -->
                            </tr>
                        </thead>
                        <tbody id="explorer-tbody" class="divide-y divide-slate-800">
                            <!-- JS Row injection -->
                        </tbody>
                    </table>
                </div>

                <!-- Table Pagination -->
                <div class="flex justify-between items-center mt-4">
                    <span class="text-xs text-slate-400">Showing <span id="table-showing-range" class="font-medium text-slate-200">1 - 10</span> of <span id="table-total-records" class="font-medium text-slate-200">0</span> records</span>
                    <div class="flex space-x-2">
                        <button onclick="changePage(-1)" id="btn-prev-page" class="px-3 py-1 bg-slate-800 text-slate-300 text-xs rounded hover:bg-slate-700 disabled:opacity-50">Previous</button>
                        <button onclick="changePage(1)" id="btn-next-page" class="px-3 py-1 bg-slate-800 text-slate-300 text-xs rounded hover:bg-slate-700 disabled:opacity-50">Next</button>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <!-- Embedded Scripts -->
    <script>
        // Embedded Dataset Variables
        const rawDataset = {cleaned_json};
        const originalKpis = {kpis_json};
        const insights = {insights_json};
        const columnProfiles = {profiles_json};
        const plotlyCharts = {charts_json};

        // UI State variables
        let filteredData = [...rawDataset];
        let activeFilters = {{}};
        let currentInsightTab = 'business';
        
        // Table Pagination variables
        let tablePage = 0;
        const pageSize = 10;
        let tableQuery = '';

        window.onload = function() {{
            buildFilters();
            renderKpiCards();
            renderInsights();
            renderDataQualityBadge();
            renderCharts();
            renderExplorerTable();
        }};

        // 1. Build Filter sidebar dynamically
        function buildFilters() {{
            const container = document.getElementById('filter-controls-container');
            container.innerHTML = '';

            for (const [colName, profile] of Object.entries(columnProfiles)) {{
                const type = profile.inferred_type;
                if (type === 'categorical' || type === 'boolean') {{
                    // Categorical filter
                    const uniqueVals = Array.from(new Set(rawDataset.map(d => d[colName]))).filter(v => v !== null && v !== undefined && v !== 'Unknown');
                    if (uniqueVals.length > 0 && uniqueVals.length <= 15) {{
                        const block = document.createElement('div');
                        block.className = 'space-y-1.5';
                        block.innerHTML = `
                            <label class="block text-xs font-semibold text-slate-300">${{colName}}</label>
                            <select onchange="applyFilter('${{colName}}', this.value)" class="w-full text-xs bg-slate-800 text-slate-200 py-2 px-3 rounded-lg border border-slate-700 focus:outline-none focus:border-indigo-500">
                                <option value="">All</option>
                                \${{uniqueVals.map(val => `<option value="\${{val}}">\${{val}}</option>`).join('')}}
                            </select>
                        `;
                        container.appendChild(block);
                    }}
                }}
            }}
        }}

        // 2. Handle filter values changes
        function applyFilter(column, value) {{
            if (value === "") {{
                delete activeFilters[column];
            }} else {{
                activeFilters[column] = value;
            }}
            
            // Re-filter dataset
            filteredData = rawDataset.filter(row => {{
                for (const [col, val] of Object.entries(activeFilters)) {{
                    if (String(row[col]) !== String(val)) return false;
                }}
                return true;
            }});

            // Update Counts and Widgets
            document.getElementById('header-records-count').textContent = filteredData.length.toLocaleString();
            
            tablePage = 0;
            renderKpiCards();
            renderCharts();
            renderExplorerTable();
        }}

        function resetFilters() {{
            activeFilters = {{}};
            filteredData = [...rawDataset];
            
            // Reset dropdown DOM values
            const selectElements = document.querySelectorAll('#filter-controls-container select');
            selectElements.forEach(select => select.value = "");
            
            document.getElementById('header-records-count').textContent = filteredData.length.toLocaleString();
            
            tablePage = 0;
            renderKpiCards();
            renderCharts();
            renderExplorerTable();
        }}

        // 3. Render KPIs
        function renderKpiCards() {{
            const grid = document.getElementById('kpi-cards-grid');
            grid.innerHTML = '';
            
            // Calculate dynamic KPI values based on filters
            originalKpis.forEach(kpi => {{
                let displayVal = kpi.value;
                
                // If it is an aggregatable KPI, calculate it dynamically from filteredData
                if (kpi.column !== 'N/A' && filteredData.length < rawDataset.length) {{
                    const col = kpi.column;
                    const cleanVals = filteredData.map(r => Number(r[col])).filter(v => !isNaN(v));
                    
                    if (kpi.type === 'business_sum') {{
                        const sum = cleanVals.reduce((a, b) => a + b, 0);
                        displayVal = formatLargeNumber(sum);
                    }} else if (kpi.type === 'business_avg' || kpi.type === 'generic_avg') {{
                        const avg = cleanVals.length > 0 ? (cleanVals.reduce((a, b) => a + b, 0) / cleanVals.length) : 0;
                        displayVal = formatLargeNumber(avg);
                    }} else if (kpi.type === 'business_qty') {{
                        const qtySum = cleanVals.reduce((a, b) => a + b, 0);
                        displayVal = qtySum.toLocaleString(undefined, {{maximumFractionDigits:0}});
                    }} else if (kpi.type === 'business_count') {{
                        const dist = new Set(filteredData.map(r => r[col])).size;
                        displayVal = dist.toLocaleString();
                    }}
                }} else if (kpi.name === 'Total Records') {{
                    displayVal = filteredData.length.toLocaleString();
                }}

                const card = document.createElement('div');
                card.className = 'bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 shadow-lg flex flex-col justify-between transition-all duration-300 hover:-translate-y-1';
                card.innerHTML = `
                    <span class="text-xs text-slate-400 font-semibold tracking-wider uppercase mb-2">\${{kpi.name}}</span>
                    <span class="text-3xl font-extrabold text-white tracking-tight">\${{displayVal}}</span>
                `;
                grid.appendChild(card);
            }});
        }}

        function formatLargeNumber(num) {{
            const abs_num = Math.abs(num);
            const sign = num < 0 ? "-" : "";
            if (abs_num >= 1000000000) {{
                return `\${{sign}}₹\${{(abs_num / 1000000000).toFixed(2)}}B`;
            }} else if (abs_num >= 1000000) {{
                return `\${{sign}}₹\${{(abs_num / 1000000).toFixed(2)}}M`;
            }} else if (abs_num >= 1000) {{
                return `\${{sign}}₹\${{(abs_num / 1000).toFixed(2)}}K`;
            }} else {{
                return `\${{sign}}₹\${{num.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
            }}
        }}

        // 4. Render Insights
        function renderInsights() {{
            const list = document.getElementById('insights-list');
            list.innerHTML = '';
            
            const activeInsights = insights[currentInsightTab] || [];
            
            if (activeInsights.length === 0) {{
                list.innerHTML = `<li class="text-slate-400 text-sm">No insights available for this category.</li>`;
                return;
            }}

            activeInsights.forEach(insight => {{
                const li = document.createElement('li');
                li.className = 'flex items-start text-sm text-slate-300 space-x-2.5 bg-slate-850/30 p-3 rounded-lg border border-slate-800/50';
                li.innerHTML = `
                    <span class="text-indigo-500 mt-1 select-none font-bold">▪</span>
                    <span>\${{insight}}</span>
                `;
                list.appendChild(li);
            }});
        }}

        function switchInsightTab(tabId) {{
            // Deactivate old tab style
            document.getElementById(`tab-\${{currentInsightTab}}`).className = "px-3 py-1 text-xs rounded-md bg-slate-800 text-slate-400 hover:text-slate-200";
            // Activate new tab
            currentInsightTab = tabId;
            document.getElementById(`tab-\${{tabId}}`).className = "px-3 py-1 text-xs rounded-md bg-indigo-600 text-white font-medium";
            
            renderInsights();
        }}

        function renderDataQualityBadge() {{
            let typeCounts = {{}};
            for (const col of Object.values(columnProfiles)) {{
                typeCounts[col.inferred_type] = (typeCounts[col.inferred_type] || 0) + 1;
            }}
            const summaryString = Object.entries(typeCounts).map(([type, count]) => `\${{type}}: \${{count}}`).join(' | ');
            document.getElementById('inferred-summary-badge').textContent = summaryString;
        }}

        // 5. Render Plotly Charts (Handles redrawing on filter changes)
        function renderCharts() {{
            // Target Chart Div IDs
            const targets = ['chart-panel-1', 'chart-panel-2', 'chart-panel-3', 'chart-panel-4'];
            
            // Map charts to targets
            let chartKeys = [];
            if (plotlyCharts.correlation_heatmap) chartKeys.push('correlation_heatmap');
            if (plotlyCharts.scatter_relation) chartKeys.push('scatter_relation');
            
            // Gather distributions
            if (plotlyCharts.distributions) {{
                Object.keys(plotlyCharts.distributions).forEach(k => chartKeys.push(`distributions__\${{k}}`));
            }}
            if (plotlyCharts.categorical) {{
                Object.keys(plotlyCharts.categorical).forEach(k => chartKeys.push(`categorical__\${{k}}`));
            }}
            if (plotlyCharts.time_series) {{
                Object.keys(plotlyCharts.time_series).forEach(k => chartKeys.push(`time_series__\${{k}}`));
            }}

            // Render up to 4 charts
            targets.forEach((targetId, idx) => {{
                const targetEl = document.getElementById(targetId);
                targetEl.innerHTML = '';
                
                if (idx < chartKeys.length) {{
                    const key = chartKeys[idx];
                    let plotData = null;

                    if (key === 'correlation_heatmap') {{
                        plotData = plotlyCharts.correlation_heatmap;
                    }} else if (key === 'scatter_relation') {{
                        plotData = plotlyCharts.scatter_relation;
                    }} else if (key.startsWith('distributions__')) {{
                        const colName = key.split('__')[1];
                        plotData = plotlyCharts.distributions[colName];
                    }} else if (key.startsWith('categorical__')) {{
                        const colName = key.split('__')[1];
                        plotData = plotlyCharts.categorical[colName];
                    }} else if (key.startsWith('time_series__')) {{
                        const colName = key.split('__')[1];
                        plotData = plotlyCharts.time_series[colName];
                    }}

                    if (plotData) {{
                        // Clone data to avoid mutations
                        let finalPlotData = JSON.parse(JSON.stringify(plotData));
                        
                        // Regenerate chart values dynamically if filtered
                        if (filteredData.length < rawDataset.length) {{
                            finalPlotData = adjustChartData(key, finalPlotData);
                        }}

                        Plotly.newPlot(targetId, finalPlotData.data, finalPlotData.layout, {{responsive: true}});
                    }}
                }} else {{
                    targetEl.innerHTML = `<div class="flex items-center justify-center h-full text-slate-500 text-sm">No analysis chart generated for this slot</div>`;
                }}
            }});
        }}

        // Helper to adjust plotly chart arrays dynamically based on current client filters
        function adjustChartData(chartKey, plotObj) {{
            if (chartKey.startsWith('distributions__')) {{
                const colName = chartKey.split('__')[1];
                const vals = filteredData.map(d => d[colName]).filter(v => v !== null && v !== undefined);
                if (plotObj.data && plotObj.data[0]) {{
                    plotObj.data[0].x = vals;
                }}
            }} else if (chartKey.startsWith('categorical__')) {{
                const colName = chartKey.split('__')[1];
                
                // Recalculate frequencies
                let counts = {{}};
                filteredData.forEach(d => {{
                    const val = String(d[colName]);
                    counts[val] = (counts[val] || 0) + 1;
                }});
                
                // Sort categories
                const sortedKeys = Object.keys(counts).sort((a, b) => counts[b] - counts[a]).slice(0, 10);
                const x_vals = sortedKeys;
                const y_vals = sortedKeys.map(k => counts[k]);
                
                if (plotObj.data && plotObj.data[0]) {{
                    if (plotObj.data[0].orientation === 'h') {{
                        plotObj.data[0].x = y_vals;
                        plotObj.data[0].y = x_vals;
                    }} else {{
                        plotObj.data[0].x = x_vals;
                        plotObj.data[0].y = y_vals;
                    }}
                }}
            }} else if (chartKey.startsWith('time_series__')) {{
                const colName = chartKey.split('__')[1];
                
                // We will aggregate filtered data by date
                const dateCol = Object.keys(columnProfiles).find(c => columnProfiles[c].inferred_type === 'datetime');
                if (dateCol) {{
                    let dateSums = {{}};
                    filteredData.forEach(d => {{
                        const dtStr = String(d[dateCol]);
                        // extract date prefix for aggregation
                        let dateKey = dtStr;
                        if (dtStr.length >= 10) dateKey = dtStr.substring(0, 10); // Standardize string check
                        
                        dateSums[dateKey] = (dateSums[dateKey] || 0) + Number(d[colName] || 0);
                    }});
                    
                    const sortedDates = Object.keys(dateSums).sort();
                    if (plotObj.data && plotObj.data[0]) {{
                        plotObj.data[0].x = sortedDates;
                        plotObj.data[0].y = sortedDates.map(d => dateSums[d]);
                    }}
                }}
            }} else if (chartKey === 'scatter_relation') {{
                const x_col = plotObj.layout.xaxis.title.text;
                const y_col = plotObj.layout.yaxis.title.text;
                
                if (plotObj.data && plotObj.data[0]) {{
                    plotObj.data[0].x = filteredData.map(d => d[x_col]);
                    plotObj.data[0].y = filteredData.map(d => d[y_col]);
                }}
                
                // Remove OLS trendline on filtering for simplicity, as computing OLS client-side is complex
                if (plotObj.data && plotObj.data[1]) {{
                    plotObj.data.splice(1, 1);
                }}
            }}
            return plotObj;
        }}

        // 6. Data Explorer Table logic
        function renderExplorerTable() {{
            const thead = document.getElementById('explorer-thead');
            const tbody = document.getElementById('explorer-tbody');
            
            thead.innerHTML = '';
            tbody.innerHTML = '';

            const cols = Object.keys(columnProfiles);
            
            // Build headers
            cols.forEach(col => {{
                thead.innerHTML += `<th scope="col" class="px-6 py-3 font-semibold text-slate-200">\${{col}}</th>`;
            }});

            // Filter by search text
            let tableData = [...filteredData];
            if (tableQuery) {{
                const q = tableQuery.toLowerCase();
                tableData = tableData.filter(row => {{
                    return cols.some(col => String(row[col]).toLowerCase().includes(q));
                }});
            }}

            document.getElementById('table-total-records').textContent = tableData.length.toLocaleString();

            const startIdx = tablePage * pageSize;
            const endIdx = Math.min(startIdx + pageSize, tableData.length);
            
            document.getElementById('table-showing-range').textContent = `\${{tableData.length > 0 ? startIdx + 1 : 0}} - \${{endIdx}}`;
            
            // Manage button states
            document.getElementById('btn-prev-page').disabled = tablePage === 0;
            document.getElementById('btn-next-page').disabled = endIdx >= tableData.length;

            const slice = tableData.slice(startIdx, endIdx);
            
            if (slice.length === 0) {{
                tbody.innerHTML = `<tr><td colspan="\${{cols.length}}" class="px-6 py-8 text-center text-slate-500">No matching records found.</td></tr>`;
                return;
            }}

            slice.forEach(row => {{
                let tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/30 transition-colors';
                
                cols.forEach(col => {{
                    let val = row[col];
                    if (val === null || val === undefined) val = '-';
                    tr.innerHTML += `<td class="px-6 py-4 whitespace-nowrap text-slate-300 font-medium">\${{val}}</td>`;
                }});
                tbody.appendChild(tr);
            }});
        }}

        function handleTableSearch(val) {{
            tableQuery = val;
            tablePage = 0;
            renderExplorerTable();
        }}

        function changePage(direction) {{
            tablePage += direction;
            renderExplorerTable();
        }}
    </script>
</body>
</html>
""";
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

class PDFReport(FPDF):
    def clean_text(self, text):
        if isinstance(text, str):
            # Replace ₹ with Rs. and replace other non-latin-1 characters with ?
            return text.replace('₹', 'Rs.').encode('latin-1', 'replace').decode('latin-1')
        return text

    def cell(self, w, h=0, txt="", border=0, ln=0, align="", fill=False, link="", **kwargs):
        if w == 0:
            w = self.epw
        txt = self.clean_text(txt)
        if 'text' in kwargs:
            kwargs['text'] = self.clean_text(kwargs['text'])
        return super().cell(w, h, txt, border, ln, align, fill, link, **kwargs)

    def multi_cell(self, w, h=None, txt="", border=0, align="J", fill=False, **kwargs):
        if w == 0:
            w = self.epw
        txt = self.clean_text(txt)
        if 'text' in kwargs:
            kwargs['text'] = self.clean_text(kwargs['text'])
        return super().multi_cell(w, h, txt, border, align, fill, **kwargs)

    def header(self):
        # Draw top colored banner
        self.set_fill_color(15, 23, 42) # Slate-900
        self.rect(0, 0, 210, 30, 'F')
        
        # White Text in Banner
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(255, 255, 255)
        self.set_y(10)
        self.cell(0, 10, "AUTOMATED ANALYTICAL DATA REPORT", align='C', new_x="LMARGIN", new_y="NEXT")
        
        # Spacer
        self.set_y(35)
        
    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 116, 139) # slate text
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Generated automatically by ADA Tool", align='C')

def generate_pdf_report(metadata, eda_results, insights, kpis, static_charts_paths, output_pdf_path):
    """
    Generates a professional multi-page PDF analytical report from computed metrics and static charts.
    """
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.alias_nb_pages()
    
    # PAGE 1: Cover Page / Exec Summary
    pdf.add_page()
    pdf.set_text_color(15, 23, 42) # Slate dark text
    
    pdf.set_font('Helvetica', 'B', 22)
    pdf.cell(0, 15, "EXECUTIVE ANALYSIS REPORT", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, f"Report Target Filename: {metadata.get('filename')}", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Total Features: {metadata.get('num_features')} | Total Records Count: {metadata.get('num_records'):,}", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Horizontal line
    pdf.set_draw_color(100, 116, 139)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)
    
    # Executive Summary Paragraph
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, "1. Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font('Helvetica', '', 10)
    
    # Calculate some dynamic content for Exec Summary
    total_records = metadata.get('num_records', 0)
    num_features = metadata.get('num_features', 0)
    missing_str = f"The dataset features high completeness, with only {metadata.get('total_missing', 0):,} missing cells identified and corrected." if metadata.get('total_missing', 0) == 0 else f"A total of {metadata.get('total_missing', 0):,} missing elements were detected and prepared during data ingestion."
    
    summary_text = (
        f"This report presents an automated structural audit and exploratory analysis of the "
        f"uploaded dataset '{metadata.get('filename')}' containing {total_records:,} records "
        f"and {num_features} individual attributes. {missing_str} The tool has evaluated "
        f"all numerical distributions, computed core statistical moments, categorized cardinal groupings, "
        f"and compiled chronological trends to isolate critical business findings.\n\n"
        f"A total of {len(kpis)} Key Performance Indicators were computed. The rest of this document "
        f"outlines data preparation logs, statistical summaries, visual indicators, and strategic suggestions."
    )
    pdf.multi_cell(0, 6, summary_text)
    pdf.ln(5)
    
    # Core KPIs Section
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, "2. Key Metrics & KPIs", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Draw KPI Table headers
    pdf.set_fill_color(241, 245, 249) # pale slate table header
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(90, 8, " KPI Descriptor", border=1, fill=True)
    pdf.cell(50, 8, " Value", border=1, fill=True)
    pdf.cell(50, 8, " Column Association", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    
    # Populate rows
    pdf.set_font('Helvetica', '', 10)
    for kpi in kpis[:8]: # limit table size
        pdf.cell(90, 7, f" {kpi['name']}", border=1)
        pdf.cell(50, 7, f" {kpi['value']}", border=1)
        pdf.cell(50, 7, f" {kpi['column']}", border=1, new_x="LMARGIN", new_y="NEXT")
        
    # PAGE 2: Data Quality Assessment & Insights
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, "3. Data Quality & Cleaning Logs", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Missing/duplicates summary
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"- Total duplicate rows removed: {metadata.get('duplicate_count', 0):,}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"- Total empty fields found: {metadata.get('total_missing', 0):,}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Insights Section
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, "4. Key Analytical Insights", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Write categorized insights
    for category, list_of_insights in insights.items():
        if list_of_insights:
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 6, f"{category.replace('_', ' ').title()} Insights:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Helvetica', '', 9.5)
            for ins in list_of_insights[:3]: # keep top 3 per category to fit page nicely
                pdf.multi_cell(0, 5, f"  - {ins}")
                pdf.ln(1)
            pdf.ln(2)

    # PAGE 3: Visualizations
    if static_charts_paths:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 8, "5. Exploratory Visualizations", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        
        # Embed the generated Matplotlib PNGs
        y_pos = pdf.get_y()
        for idx, (chart_name, path) in enumerate(static_charts_paths.items()):
            if os.path.exists(path):
                # Put 2 charts per page to avoid overflow
                if idx > 0 and idx % 2 == 0:
                    pdf.add_page()
                    pdf.set_font('Helvetica', 'B', 14)
                    pdf.cell(0, 8, "5. Exploratory Visualizations (Cont.)", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(4)
                    y_pos = pdf.get_y()
                
                pdf.image(path, x=15, y=pdf.get_y(), w=180, h=90)
                pdf.ln(95) # Move cursor past the image size + padding
                
    # Recommendations & Conclusion Page
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, "6. Strategic Recommendations", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Write business insights as recommendations
    pdf.set_font('Helvetica', '', 10)
    biz_rec = insights.get('business', [])
    if biz_rec:
        for rec in biz_rec:
            pdf.multi_cell(0, 6, f"▪ {rec}")
            pdf.ln(3)
    else:
        pdf.multi_cell(0, 6, "▪ Focus operations around high-performing category variables and leverage strongly correlated attributes to optimize business outcomes.")
        pdf.ln(3)
        pdf.multi_cell(0, 6, "▪ Set up continuous data logging with structured schema layouts to eliminate missing/null data cells prior to automated audits.")
        pdf.ln(3)

    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, "7. Conclusion", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 6, 
        "The automated execution pipeline successfully completed all ingestion, auditing, and processing phases. "
        "The standardized dataset has been extracted and the interactive single-page dashboard can be opened "
        "offline to execute dynamic filtering and drill-down operations. For queries, contact the development admin."
    )

    pdf.output(output_pdf_path)
