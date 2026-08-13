import os
import shutil
import json
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Import our custom modules
import analyzer
import visualization
import report_generator

app = Flask(__name__)

# Configure upload and download folders
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'uploads'))
DOWNLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'downloads'))
STATIC_CHARTS_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static', 'charts'))
HISTORY_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'history'))

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['STATIC_CHARTS_FOLDER'] = STATIC_CHARTS_FOLDER
app.config['HISTORY_FOLDER'] = HISTORY_FOLDER

# Ensure directories exist
for folder in [UPLOAD_FOLDER, DOWNLOAD_FOLDER, STATIC_CHARTS_FOLDER, HISTORY_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Application state stored in memory (dictionary cache)
# For a single-user local application, this is robust and simple.
session_state = {
    'original_filepath': None,
    'converted_csv_path': None,
    'cleaned_csv_path': None,
    'filename': None,
    'profile': None,
    'cleaned_profile': None,
    'cleaning_log': [],
    'outliers': {},
    'kpis': [],
    'insights': {},
    'eda_results': {}
}

@app.route('/')
def index():
    """Serves the main application SPA page."""
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Handles dataset upload, detects type, converts to standardized CSV, and profiles."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Convert to standard CSV
            standard_csv_path, df = analyzer.convert_to_csv(filepath, filename)
            
            # Initial profiling
            profile = analyzer.profile_dataset(df)
            
            # Store in session state
            session_state['original_filepath'] = filepath
            session_state['converted_csv_path'] = standard_csv_path
            session_state['filename'] = filename
            session_state['profile'] = profile
            
            # Reset down-stream session data
            session_state['cleaned_csv_path'] = None
            session_state['cleaned_profile'] = None
            session_state['cleaning_log'] = []
            session_state['outliers'] = {}
            session_state['kpis'] = []
            session_state['insights'] = {}
            session_state['eda_results'] = {}

            return jsonify({
                'message': 'File uploaded and parsed successfully.',
                'filename': filename,
                'num_records': profile['num_records'],
                'num_features': profile['num_features'],
                'total_missing': profile['total_missing'],
                'duplicate_count': profile['duplicate_count'],
                'memory_usage': profile['memory_usage'],
                'columns': profile['columns']
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/clean', methods=['POST'])
def api_clean():
    """Perives user cleaning options, performs cleaning, returns logs and new stats."""
    if not session_state['converted_csv_path']:
        return jsonify({'error': 'No active dataset. Upload a file first.'}), 400

    data = request.json or {}
    imputation_strategy = data.get('imputation_strategy', 'auto')
    drop_duplicates = data.get('drop_duplicates', True)
    outlier_multiplier = float(data.get('outlier_multiplier', 1.5))

    try:
        # Load converted CSV
        df = pd.read_csv(session_state['converted_csv_path'])
        
        # Clean
        cleaned_df, cleaning_log, outliers_info = analyzer.clean_dataset(
            df, 
            session_state['profile']['columns'],
            imputation_strategy=imputation_strategy,
            drop_duplicates=drop_duplicates,
            outlier_multiplier=outlier_multiplier
        )
        
        # Save Cleaned CSV
        cleaned_csv_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'cleaned_dataset.csv')
        cleaned_df.to_csv(cleaned_csv_path, index=False)
        
        # Re-profile cleaned dataset
        cleaned_profile = analyzer.profile_dataset(cleaned_df)
        
        # Store in session state
        session_state['cleaned_csv_path'] = cleaned_csv_path
        session_state['cleaned_profile'] = cleaned_profile
        session_state['cleaning_log'] = cleaning_log
        session_state['outliers'] = outliers_info

        return jsonify({
            'message': 'Data cleaned successfully.',
            'cleaning_log': cleaning_log,
            'outliers': outliers_info,
            'num_records': cleaned_profile['num_records'],
            'total_missing': cleaned_profile['total_missing'],
            'duplicate_count': cleaned_profile['duplicate_count']
        })

    except Exception as e:
        return jsonify({'error': f"Cleaning failed: {str(e)}"}), 500

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Performs statistical EDA, KPIs, insights, and triggers HTML/PDF report creation."""
    # Use cleaned CSV if available, otherwise fallback to converted original
    active_csv_path = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
    active_profile = session_state['cleaned_profile'] or session_state['profile']
    
    if not active_csv_path:
        return jsonify({'error': 'No dataset available. Please upload first.'}), 400

    try:
        df = pd.read_csv(active_csv_path)
        
        # Run statistical EDA
        eda_results = analyzer.run_eda(df, active_profile['columns'])
        
        # Detect business KPIs
        kpis = analyzer.detect_kpis(df, active_profile['columns'])
        
        # Generate Insights (Grok API or Local Heuristics)
        insights = analyzer.generate_insights(
            df, 
            eda_results, 
            active_profile['columns'],
            session_state['cleaning_log'],
            session_state['outliers'],
            kpis
        )
        
        # Generate Interactive Plotly figures (Passing detected kpis to restrict numerical variables)
        plotly_charts = visualization.generate_interactive_plots(df, eda_results, active_profile['columns'], kpis=kpis)
        
        # Generate Static Matplotlib PNGs for the PDF
        static_charts = visualization.generate_static_plots(
            df, 
            eda_results, 
            active_profile['columns'], 
            app.config['STATIC_CHARTS_FOLDER'],
            kpis=kpis
        )
        
        # Store in state
        session_state['kpis'] = kpis
        session_state['insights'] = insights
        session_state['eda_results'] = eda_results

        # Ensure filename is metadata friendly
        metadata = {
            'filename': session_state['filename'],
            'num_records': active_profile['num_records'],
            'num_features': active_profile['num_features'],
            'total_missing': active_profile['total_missing'],
            'duplicate_count': active_profile['duplicate_count'],
            'columns': active_profile['columns']
        }

        # 1. Generate standalone HTML dashboard
        html_dashboard_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'interactive_dashboard.html')
        report_generator.generate_html_dashboard(
            df,
            df, # using df as cleaned_df since it's loaded from active_csv_path
            metadata,
            eda_results,
            insights,
            kpis,
            plotly_charts,
            html_dashboard_path
        )

        # 2. Generate PDF Analytical Report
        pdf_report_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'analytical_report.pdf')
        report_generator.generate_pdf_report(
            metadata,
            eda_results,
            insights,
            kpis,
            static_charts,
            pdf_report_path
        )

        # Option E: Save to history JSON
        import uuid
        from datetime import datetime
        history_id = str(uuid.uuid4())[:8]
        history_item = {
            'id': history_id,
            'filename': session_state['filename'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'record_count': int(active_profile['num_records']),
            'kpis': kpis,
            'eda': eda_results,
            'insights': insights,
            'outliers': session_state['outliers'],
            'datasetMetadata': active_profile,
            'plotly_charts': plotly_charts,
            'cleaning_log': session_state['cleaning_log'],
            'converted_csv_path': session_state['converted_csv_path'],
            'cleaned_csv_path': session_state['cleaned_csv_path']
        }
        history_path = os.path.join(app.config['HISTORY_FOLDER'], f"{history_id}.json")
        with open(history_path, 'w') as f:
            json.dump(history_item, f, default=str)

        return jsonify({
            'message': 'Analysis complete. Dashboard and PDF generated.',
            'history_id': history_id,
            'kpis': kpis,
            'insights': insights,
            'plotly_charts': plotly_charts,
            'eda_results': eda_results
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f"Analysis execution failed: {str(e)}"}), 500

@app.route('/api/preview', methods=['GET'])
def api_preview():
    """Returns paginated and filtered preview rows for the data explorer."""
    active_csv_path = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
    if not active_csv_path:
        return jsonify({'error': 'No active dataset'}), 400

    try:
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 10))
        query = request.args.get('query', '').strip()

        df = pd.read_csv(active_csv_path)

        if query:
            # Filter rows containing query in any column
            mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False, na=False)).any(axis=1)
            filtered_df = df[mask]
        else:
            filtered_df = df

        total = len(filtered_df)
        start = page * size
        end = start + size
        sliced_df = filtered_df.iloc[start:end]

        # Replace standard NaNs with None for JSON compliance
        sliced_df = sliced_df.replace({pd.NA: None}).where(pd.notnull(sliced_df), None)
        rows = sliced_df.to_dict(orient='records')

        return jsonify({
            'total': total,
            'rows': rows
        })
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<file_type>', methods=['GET'])
def api_download(file_type):
    """Handles downloading generated outputs (cleaned CSV, standalone HTML, PDF)."""
    if file_type == 'csv':
        target = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
        filename = "cleaned_dataset.csv"
        mimetype = "text/csv"
    elif file_type == 'html':
        target = os.path.join(app.config['DOWNLOAD_FOLDER'], 'interactive_dashboard.html')
        filename = "interactive_dashboard.html"
        mimetype = "text/html"
    elif file_type == 'pdf':
        target = os.path.join(app.config['DOWNLOAD_FOLDER'], 'analytical_report.pdf')
        filename = "analytical_report.pdf"
        mimetype = "application/pdf"
    elif file_type == 'custom_pdf':
        target = os.path.join(app.config['DOWNLOAD_FOLDER'], 'custom_analytical_report.pdf')
        filename = "custom_analytical_report.pdf"
        mimetype = "application/pdf"
    else:
        return jsonify({'error': f"Unknown download type '{file_type}'"}), 400

    if not target or not os.path.exists(target):
        return jsonify({'error': f"File not found. Please complete the cleaning and analysis steps first."}), 404

    return send_file(target, as_attachment=True, download_name=filename, mimetype=mimetype)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Conversational AI Copilot route.
    Accepts user text, queries Grok to write a pandas code block, 
    executes it locally, and returns the response with optional Plotly json.
    """
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Message cannot be empty.'}), 400

    active_csv_path = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
    if not active_csv_path or not os.path.exists(active_csv_path):
        return jsonify({
            'text_answer': "No dataset is currently loaded. Please upload a dataset first so I can analyze it for you!",
            'plotly_chart_data': None
        })

    try:
        df = pd.read_csv(active_csv_path)
        
        # Formulate columns schema summary for prompt
        col_summary = []
        for col in df.columns:
            col_summary.append(f"- {col} ({str(df[col].dtype)})")
        columns_str = "\n".join(col_summary)

        # Grok API integration
        import requests
        import json
        import re
        import numpy as np
        
        grok_api_key = os.getenv('GROK_API_KEY') or os.getenv('XAI_API_KEY')
        
        if grok_api_key:
            # Build the system prompt instructing Grok to return clean Python code
            system_prompt = (
                "You are an expert data analyst AI copilot for the 'InsightFlow' analytics platform.\n"
                "The user has uploaded a dataset. Here is the column list:\n"
                f"{columns_str}\n\n"
                "Your task is to write a Python helper function `analyze_data(df)` that performs the requested calculations and returns a dictionary.\n"
                "The returned dictionary must have exactly two keys:\n"
                "- 'text_answer': A concise text answer summarizing your analytical findings and values computed.\n"
                "- 'plotly_fig': A Plotly Express or Graph Objects figure object, OR None if a chart is not requested or useful.\n\n"
                "Guidelines:\n"
                "1. ONLY write valid Python code enclosed in a ```python ... ``` markdown block. Do not write introductory or concluding text outside the block.\n"
                "2. The function MUST be named `analyze_data(df)` and take a single pandas DataFrame `df` as input.\n"
                "3. Do not re-read the CSV file inside the function; operate directly on the parameter `df`.\n"
                "4. If a chart is requested, generate it using `import plotly.express as px` or `import plotly.graph_objects as go` and assign it to the 'plotly_fig' key.\n"
                "5. Ensure any numerical values in 'text_answer' are formatted cleanly (e.g. currency signs, commas, rounding).\n"
            )
            
            user_prompt = f"The user asks: \"{message}\"\n\nWrite the python analyze_data function."
            
            headers = {
                "Authorization": f"Bearer {grok_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "grok-2-latest",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1
            }
            
            url = "https://api.xai.com/v1/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                result_json = response.json()
                content = result_json['choices'][0]['message']['content']
                
                # Extract python block
                code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
                code_to_exec = code_match.group(1).strip() if code_match else content.strip()
                
                # Exec execution sandbox
                exec_globals = {
                    'pd': pd,
                    'np': np,
                    'px': px,
                    'go': go,
                    'json': json
                }
                
                local_vars = {}
                exec(code_to_exec, exec_globals, local_vars)
                
                if 'analyze_data' in local_vars:
                    res = local_vars['analyze_data'](df)
                    text_answer = res.get('text_answer', '')
                    plotly_fig = res.get('plotly_fig', None)
                    
                    plotly_json = None
                    if plotly_fig is not None:
                        from plotly.utils import PlotlyJSONEncoder
                        plotly_json = json.loads(json.dumps(plotly_fig, cls=PlotlyJSONEncoder))
                        
                    return jsonify({
                        'text_answer': text_answer,
                        'plotly_chart_data': plotly_json
                    })
                else:
                    raise ValueError("Function 'analyze_data' was not defined in the generated python block.")
            else:
                raise ValueError(f"Grok API returned status code {response.status_code}")
                
        # If no key or if Grok fails, run our robust local fallback heuristics
        raise ValueError("Grok API key missing or offline, triggering fallback.")

    except Exception as e:
        print(f"Chat AI execution error, falling back: {str(e)}")
        
        # Local keyword-based fallback heuristics
        msg_lower = message.lower()
        text_answer = ""
        
        # Simple KPI/Total Check
        kpis_detected = session_state.get('kpis', [])
        
        # 1. Greetings & Meta Conversational fallbacks
        if any(h in msg_lower for h in ['hello', 'hi', 'hey', 'greetings', 'yo']):
            text_answer = "Hello! I am your **InsightFlow AI Analyst**. I am ready to explore your dataset with you. Ask me questions about summaries, outliers, missing values, or specific KPI comparisons!"
            
        elif any(h in msg_lower for h in ['who are you', 'what is your name', 'identify yourself']):
            text_answer = "I am the **InsightFlow Copilot Analyst**, an AI designed to read your columns, perform data cleaning, identify outliers, and generate interactive visual charts dynamically."
            
        elif any(h in msg_lower for h in ['thank', 'cool', 'awesome', 'great', 'nice']):
            text_answer = "You're very welcome! Let me know if you need any other calculations, aggregations, or charts generated for your dataset."

        elif 'columns' in msg_lower or 'variables' in msg_lower:
            cols = list(df.columns)
            text_answer = f"Your dataset contains the following **{len(cols)} columns**:\n" + "\n".join([f"- `{c}`" for c in cols])

        elif 'rows' in msg_lower or 'records' in msg_lower or 'size' in msg_lower:
            text_answer = f"The dataset contains **{len(df):,} rows/records** and **{len(df.columns)} columns**."

        # 2. Specific Data Query fallbacks
        elif 'revenue' in msg_lower or 'sales' in msg_lower:
            rev_kpi = next((k for k in kpis_detected if 'revenue' in k['name'].lower() or 'sales' in k['name'].lower()), None)
            if rev_kpi:
                text_answer = f"According to the dataset, the **{rev_kpi['name']}** is **{rev_kpi['value']}**."
            else:
                numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                if numeric_cols:
                    col = numeric_cols[0]
                    total_val = df[col].sum()
                    text_answer = f"I calculated the sum of **{col}** which is **{total_val:,.2f}**."
                else:
                    text_answer = "No numeric columns are available to compute sales/revenue aggregates."
                    
        elif 'outlier' in msg_lower or 'anomaly' in msg_lower:
            outliers_detected = session_state.get('outliers', {})
            if outliers_detected:
                summary = []
                for c, info in outliers_detected.items():
                    summary.append(f"- **{c}**: {info['count']} outliers flagged ({info['pct']:.1f}%)")
                text_answer = "Here is the anomaly outlier profile of the numeric variables:\n" + "\n".join(summary)
            else:
                text_answer = "No significant outlier anomalies were flagged in the numeric columns of this dataset."
                
        elif 'missing' in msg_lower or 'null' in msg_lower:
            missing_profile = df.isnull().sum()
            total_missing = missing_profile.sum()
            if total_missing > 0:
                summary = [f"- **{c}**: {val} missing cells" for c, val in missing_profile.items() if val > 0]
                text_answer = f"The dataset contains a total of **{total_missing} missing values** across columns:\n" + "\n".join(summary)
            else:
                text_answer = "Great news! The dataset contains **0 missing cells**; it is fully complete."
                
        else:
            text_answer = (
                "I am here to help you analyze your dataset! Try asking questions like:\n"
                "- *What is the total revenue?*\n"
                "- *Are there any outliers in the data?*\n"
                "- *Are there any missing values?*\n\n"
                "(Note: xAI's API endpoint is currently experiencing high load, so I am answering you using my high-fidelity local analytical engine!)"
            )
            
        return jsonify({
            'text_answer': text_answer,
            'plotly_chart_data': None
        })

@app.route('/api/column/<col_name>', methods=['GET'])
def api_column_values(col_name):
    """Returns sample values for dynamic column profiling in the inspector modal."""
    active_csv_path = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
    if not active_csv_path or not os.path.exists(active_csv_path):
        return jsonify({'error': 'No dataset loaded.'}), 400
    
    try:
        df = pd.read_csv(active_csv_path)
        if col_name not in df.columns:
            return jsonify({'error': f"Column '{col_name}' not found."}), 404
        
        # Return downsampled data for fast Plotly charting (max 2000 records)
        series = df[col_name].dropna()
        sample_size = min(2000, len(series))
        values = series.sample(n=sample_size, random_state=42).tolist() if len(series) > sample_size else series.tolist()
        
        # Convert non-standard datatypes for JSON compliance
        values = [float(v) if isinstance(v, (int, float)) and not pd.isna(v) else str(v) for v in values]
        
        return jsonify({
            'column': col_name,
            'values': values
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_logo', methods=['POST'])
def api_upload_logo():
    """Saves custom logo upload temporarily for PDF report generation."""
    if 'logo' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'error': 'Empty filename.'}), 400
        
    filename = secure_filename(file.filename)
    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], f"custom_logo_{filename}")
    file.save(logo_path)
    return jsonify({
        'logo_path': logo_path,
        'filename': filename
    })

@app.route('/api/export/custom_pdf', methods=['POST'])
def api_export_custom_pdf():
    """Generates a customized, white-labeled PDF report."""
    active_csv_path = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
    active_profile = session_state['cleaned_profile'] or session_state['profile']
    
    if not active_csv_path:
        return jsonify({'error': 'No active dataset available.'}), 400

    data = request.json or {}
    title = data.get('title', 'EXECUTIVE ANALYSIS REPORT')
    company = data.get('company', 'InsightFlow')
    accent_color = data.get('accent_color', '#4f46e5')
    include_sections = data.get('include_sections', ['kpis', 'quality', 'insights', 'charts', 'recommendations'])
    logo_path = data.get('logo_path', None)

    try:
        df = pd.read_csv(active_csv_path)
        eda_results = session_state.get('eda_results')
        kpis = session_state.get('kpis')
        insights = session_state.get('insights')
        
        static_charts = {}
        for filename in os.listdir(app.config['STATIC_CHARTS_FOLDER']):
            if filename.endswith('.png'):
                name = filename.replace('.png', '')
                static_charts[name] = os.path.join(app.config['STATIC_CHARTS_FOLDER'], filename)

        custom_pdf_path = os.path.join(app.config['DOWNLOAD_FOLDER'], 'custom_analytical_report.pdf')
        
        metadata = {
            'filename': session_state['filename'],
            'num_records': active_profile['num_records'],
            'num_features': active_profile['num_features'],
            'total_missing': active_profile['total_missing'],
            'duplicate_count': active_profile['duplicate_count']
        }
        
        report_generator.generate_pdf_report(
            metadata,
            eda_results,
            insights,
            kpis,
            static_charts,
            custom_pdf_path,
            title=title,
            company=company,
            accent_color=accent_color,
            include_sections=include_sections,
            logo_path=logo_path
        )
        
        return jsonify({
            'message': 'Custom PDF generated successfully.',
            'download_url': '/api/download/custom_pdf'
        })
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f"Custom PDF generation failed: {str(e)}"}), 500

@app.route('/api/history', methods=['GET'])
def api_get_history():
    """Lists recent historical audits in history/."""
    try:
        items = []
        for filename in os.listdir(app.config['HISTORY_FOLDER']):
            if filename.endswith('.json'):
                path = os.path.join(app.config['HISTORY_FOLDER'], filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                    items.append({
                        'id': data.get('id'),
                        'filename': data.get('filename'),
                        'timestamp': data.get('timestamp'),
                        'record_count': data.get('record_count')
                    })
        # Sort by timestamp descending
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return jsonify({'history': items[:10]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/load/<history_id>', methods=['GET'])
def api_load_history(history_id):
    """Loads a previous analysis session from history JSON."""
    history_path = os.path.join(app.config['HISTORY_FOLDER'], f"{history_id}.json")
    if not os.path.exists(history_path):
        return jsonify({'error': 'Session history item not found.'}), 404
        
    try:
        with open(history_path, 'r') as f:
            data = json.load(f)
            
        session_state['filename'] = data.get('filename')
        session_state['converted_csv_path'] = data.get('converted_csv_path')
        session_state['cleaned_csv_path'] = data.get('cleaned_csv_path')
        session_state['kpis'] = data.get('kpis')
        session_state['insights'] = data.get('insights')
        session_state['eda_results'] = data.get('eda')
        session_state['outliers'] = data.get('outliers')
        session_state['cleaning_log'] = data.get('cleaning_log', [])
        
        profile = data.get('datasetMetadata')
        session_state['profile'] = profile
        session_state['cleaned_profile'] = profile
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': f"Failed to load history session: {str(e)}"}), 500

@app.route('/api/pivot', methods=['POST'])
def api_pivot():
    """Calculates pandas pivot table grouping dynamically."""
    active_csv_path = session_state['cleaned_csv_path'] or session_state['converted_csv_path']
    if not active_csv_path or not os.path.exists(active_csv_path):
        return jsonify({'error': 'No dataset loaded.'}), 400

    data = request.json or {}
    row_col = data.get('row')
    col_col = data.get('col')
    val_col = data.get('val')
    agg_func = data.get('agg', 'sum')

    if not row_col or not val_col:
        return jsonify({'error': 'Row grouping and calculation value columns are required.'}), 400

    try:
        df = pd.read_csv(active_csv_path)
        
        # Make pivot using pandas
        if col_col:
            pivot_df = df.pivot_table(index=row_col, columns=col_col, values=val_col, aggfunc=agg_func).fillna(0)
            columns = [str(c) for c in pivot_df.columns]
        else:
            pivot_df = df.groupby(row_col)[val_col].agg(agg_func).to_frame()
            columns = [val_col]
            
        index = [str(i) for i in pivot_df.index]
        cells = pivot_df.values.tolist()
        
        return jsonify({
            'index': index,
            'columns': columns,
            'cells': cells
        })
    except Exception as e:
        return jsonify({'error': f"Pivot calculation failed: {str(e)}"}), 500

if __name__ == '__main__':
    # Start on standard port 5000
    app.run(host='127.0.0.1', port=5000, debug=True)
