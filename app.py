import os
import shutil
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import pandas as pd

# Import our custom modules
import analyzer
import visualization
import report_generator

app = Flask(__name__)

# Configure upload and download folders
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'uploads'))
DOWNLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'downloads'))
STATIC_CHARTS_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static', 'charts'))

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['STATIC_CHARTS_FOLDER'] = STATIC_CHARTS_FOLDER

# Ensure directories exist
for folder in [UPLOAD_FOLDER, DOWNLOAD_FOLDER, STATIC_CHARTS_FOLDER]:
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

    try:
        # Load converted CSV
        df = pd.read_csv(session_state['converted_csv_path'])
        
        # Clean
        cleaned_df, cleaning_log, outliers_info = analyzer.clean_dataset(
            df, 
            session_state['profile']['columns'],
            imputation_strategy=imputation_strategy,
            drop_duplicates=drop_duplicates
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
        
        # Generate Interactive Plotly figures
        plotly_charts = visualization.generate_interactive_plots(df, eda_results, active_profile['columns'])
        
        # Generate Static Matplotlib PNGs for the PDF
        static_charts = visualization.generate_static_plots(
            df, 
            eda_results, 
            active_profile['columns'], 
            app.config['STATIC_CHARTS_FOLDER']
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

        return jsonify({
            'message': 'Analysis complete. Dashboard and PDF generated.',
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
    else:
        return jsonify({'error': f"Unknown download type '{file_type}'"}), 400

    if not target or not os.path.exists(target):
        return jsonify({'error': f"File not found. Please complete the cleaning and analysis steps first."}), 404

    return send_file(target, as_attachment=True, download_name=filename, mimetype=mimetype)

if __name__ == '__main__':
    # Start on standard port 5000
    app.run(host='127.0.0.1', port=5000, debug=True)
