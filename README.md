# 📊 InsightFlow: Automated Data Analysis Agent

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask-indigo.svg)](https://flask.palletsprojects.com/)
[![Plotly](https://img.shields.io/badge/Charts-Plotly.js-pink.svg)](https://plotly.com/javascript/)
[![xAI Grok](https://img.shields.io/badge/LLM-Grok--2-orange.svg)](https://x.ai/api)

**InsightFlow** is a production-grade, end-to-end **Automated Data Analysis Agent** that transforms raw, messy datasets into interactive dashboards and professional PDF reports with zero manual configuration. 

Drop in any CSV, TSV, Excel, or JSON file, and the agent automatically infers column types, handles missing values, flags outliers, computes statistical distributions, and extracts natural-language insights using **xAI's Grok API**.

---

## 🌟 Key Features

*   **Intelligent Input Handling & Conversion**: Automatically detects encoding and delimiters. Converted from raw Excel (`.xlsx`, `.xls`), JSON, or TSV formats into standard CSV.
*   **Semantic Data Profiling**: Moves beyond raw pandas types to detect semantic column roles—such as IDs, booleans, datetimes, textual review content, or numeric measurements.
*   **Automated Data Preparation & Audit**: 
    *   Imputes numeric missing cells using statistical mean/median strategies.
    *   Imputes categorical missing cells using dataset mode.
    *   Applies forward/backward filling for ordered time-series.
    *   Removes duplicate rows and logs all cleaning operations.
    *   Flags distribution outliers using the Interquartile Range (IQR) method.
*   **Statistical EDA Engine**: Calculates numerical moments (skewness, kurtosis, quartiles), value frequencies, Pearson correlation matrices, categorical-numerical comparisons, and resampled time-series trends.
*   **xAI Grok-Powered Insights**: Queries Grok (`grok-2-latest`) to generate business, trend, and data-quality insights. Includes a local, rule-based heuristic engine fallback in case of API limits or server downtime.
*   **Dual Exporters**:
    1.  **Standalone HTML Dashboard**: A single, self-contained HTML page featuring interactive filters, Plotly.js charts, and a detailed data explorer that operates fully offline.
    2.  **Professional PDF Report**: A multi-page analytical document (cover page, executive summary, KPI tables, and charts) styled for printing.

---

## 🛠️ Technology Stack

*   **Backend & Processing**: Python 3.11, Pandas, NumPy, SciPy
*   **Web Framework**: Flask
*   **Visualization**: Plotly.js (client-side), Matplotlib (server-side for PDF)
*   **PDF Generation**: FPDF2
*   **Frontend UI**: Tailwind CSS (CDN), Vanilla JS

---

## 📂 Project Structure

```text
Automate_Analysis/
├── app.py                  # Flask web controller & API routes
├── analyzer.py             # Parser, data profiler, cleaning, & insights engine
├── visualization.py        # Plotly & Matplotlib chart generation
├── report_generator.py     # HTML standalone dashboard & PDF report compiler
├── requirements.txt        # Python dependency list
├── .env                    # Environment variables (Grok API key)
├── templates/
│   └── index.html          # Frontend drag-and-drop wizard UI
└── static/
    ├── css/
    │   └── styles.css      # Dark mode stylesheet & transitions
    └── js/
        └── app.js          # API orchestrator & interactive preview client
```

---

## 🚀 Installation & Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/insight-flow.git
cd insight-flow
```

### 2. Install Dependencies
Make sure you have Python installed, then run:
```bash
python -m pip install -r requirements.txt
```

### 3. Add Your Grok API Key
Create or edit the `.env` file in the root directory:
```env
GROK_API_KEY=your_xai_grok_api_key_here
```
*(If left blank, the system automatically runs the rule-based statistical insight engine fallback.)*

### 4. Start the Application
```bash
python app.py
```
Open your browser and navigate to **`http://127.0.0.1:5000`**.

---

## 📊 How the Pipeline Works

```text
Upload File (CSV/Excel/JSON/TSV)
      │
      ▼
Format Conversion & Data Profiling
      │
      ▼
Automated Data Cleaning (Impute & Deduplicate)
      │
      ▼
Exploratory Data Analysis (EDA) & KPI Detection
      │
      ▼
Grok LLM Insights (Fallback to Rule-Based Engine)
      │
      ▼
Export Assets (Cleaned CSV, Standalone HTML, PDF Report)
```

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request for any feature enhancements, visual improvements, or additional file format parsers.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more details.
