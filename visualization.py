import os
import json
import matplotlib
matplotlib.use('Agg')  # Headless backend for Matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

def is_meaningful_column(col_name, info):
    """
    Helper to filter out metadata columns, IDs, zip codes, and sequence numbers.
    """
    col_lower = col_name.lower()
    
    # List of terms representing keys, IDs, sequences, or metadata that are not meaningful for visual analysis
    blacklisted_terms = [
        'id', 'key', 'code', 'uuid', 'index', 'idx', 'serial', 'number', 'no', 'num',
        'phone', 'mobile', 'zip', 'zipcode', 'postal', 'fax', 'url', 'link', 'hash',
        'account', 'seq', 'sequence', 'date', 'time', 'year', 'month', 'day'
    ]
    
    # Check if name contains any blacklisted term as a separate word or standard prefix/suffix
    is_blacklisted = any(
        term == col_lower or 
        col_lower.startswith(term + '_') or 
        col_lower.endswith('_' + term) or 
        col_lower.startswith(term + ' ') or 
        col_lower.endswith(' ' + term)
        for term in blacklisted_terms
    )
    
    # Exclude ID inferred types
    if info.get('inferred_type') in ['id', 'text', 'empty', 'datetime']:
        return False
        
    return not is_blacklisted

def generate_interactive_plots(df, eda_results, columns_info):
    """
    Generates interactive Plotly visualizations, prioritizing business aggregations,
    trends over time, and individual metric distributions. 
    Strictly avoids scatter plots and correlation heatmaps between numerical variables.
    """
    plots = {}
    
    # Filter for meaningful columns
    numeric_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'numeric' and is_meaningful_column(c, info)]
    cat_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'categorical' and is_meaningful_column(c, info)]
    
    # 1. Time-Series Trends (Line charts)
    ts_data = eda_results.get('time_series')
    plots['time_series'] = {}
    if ts_data and ts_data.get('series'):
        for metric, data in ts_data['series'].items():
            # Only plot meaningful metrics
            if is_meaningful_column(metric, columns_info.get(metric, {})):
                pts = data['data']
                if pts:
                    ts_df = pd.DataFrame(pts)
                    fig = px.line(
                        ts_df, x='date', y='sum',
                        title=f"{ts_data['granularity']} Trend for Total {metric}",
                        template="plotly_dark",
                        color_discrete_sequence=['#ec4899'], # Premium pink
                        labels={'date': ts_data['date_column'], 'sum': f"Sum of {metric}"}
                    )
                    fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
                    plots['time_series'][metric] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 2. Categorical vs Numerical Group Averages (Grouped Bar charts)
    cat_num = eda_results['relationships'].get('categorical_numerical', {})
    plots['cat_num_relationships'] = {}
    if cat_num:
        for cat_col, num_cols in cat_num.items():
            if not is_meaningful_column(cat_col, columns_info.get(cat_col, {})):
                continue
                
            plots['cat_num_relationships'][cat_col] = {}
            for num_col, group_data in num_cols.items():
                if not is_meaningful_column(num_col, columns_info.get(num_col, {})):
                    continue
                    
                group_df = pd.DataFrame(group_data)
                if not group_df.empty:
                    fig = px.bar(
                        group_df, x='category', y='mean',
                        title=f"Average {num_col} by {cat_col}",
                        template="plotly_dark",
                        color_discrete_sequence=['#8b5cf6'], # Premium purple
                        labels={'category': cat_col, 'mean': f"Avg {num_col}"}
                    )
                    fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
                    plots['cat_num_relationships'][cat_col][num_col] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 3. Categorical Distributions (Bar/Horizontal Bar)
    plots['categorical'] = {}
    for col in cat_cols[:3]:
        val_counts = df[col].astype(str).value_counts().head(10)
        if val_counts.empty:
            continue
            
        orientation = 'h' if len(val_counts) > 5 or val_counts.index.str.len().max() > 10 else 'v'
        
        if orientation == 'h':
            fig = px.bar(
                x=val_counts.values, y=val_counts.index,
                orientation='h',
                title=f"Top 10 Categories in {col}",
                template="plotly_dark",
                color_discrete_sequence=['#10b981'], # Emerald
                labels={'x': 'Count', 'y': col}
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
        else:
            fig = px.bar(
                x=val_counts.index, y=val_counts.values,
                title=f"Category Distribution in {col}",
                template="plotly_dark",
                color_discrete_sequence=['#10b981'],
                labels={'x': col, 'y': 'Count'}
            )
            
        fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
        plots['categorical'][col] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 4. Numerical Distributions (Histograms)
    plots['distributions'] = {}
    for col in numeric_cols[:3]:
        fig = px.histogram(
            df, x=col, 
            title=f"Distribution of {col}", 
            template="plotly_dark",
            color_discrete_sequence=['#6366f1'] # Premium Indigo
        )
        fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
        plots['distributions'][col] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 5. Outlier Box Plots
    plots['box_plots'] = {}
    for col in numeric_cols[:3]:
        fig = px.box(
            df, y=col,
            title=f"Outlier Analysis for {col}",
            template="plotly_dark",
            color_discrete_sequence=['#f59e0b'] # Warning Amber
        )
        fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
        plots['box_plots'][col] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    return plots

def generate_static_plots(df, eda_results, columns_info, output_dir):
    """
    Generates static PNG plots to embed in the PDF analytical report.
    Only creates meaningful, non-scatter, non-heatmap charts.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    numeric_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'numeric' and is_meaningful_column(c, info)]
    cat_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'categorical' and is_meaningful_column(c, info)]
    
    # Set styling parameters for report aesthetics
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']

    # 1. Time Series Trend
    ts_data = eda_results.get('time_series')
    if ts_data and ts_data.get('series'):
        fig, ax = plt.subplots(figsize=(10, 4))
        has_plots = False
        for metric, data in ts_data['series'].items():
            if is_meaningful_column(metric, columns_info.get(metric, {})):
                pts = data['data']
                if pts:
                    ts_df = pd.DataFrame(pts)
                    ax.plot(ts_df['date'], ts_df['sum'], marker='o', label=f"Total {metric}", color='#ec4899', linewidth=2)
                    has_plots = True
        
        if has_plots:
            ax.set_title(f"{ts_data['granularity']} Trend Analysis", fontsize=12, fontweight='bold')
            ax.set_xlabel(ts_data['date_column'])
            ax.set_ylabel("Sum")
            ax.legend()
            plt.xticks(rotation=30)
            plt.tight_layout()
            ts_path = os.path.join(output_dir, "time_series_trends.png")
            plt.savefig(ts_path, dpi=200, bbox_inches='tight')
            plt.close()
            paths['time_series_trends'] = ts_path
        else:
            plt.close()

    # 2. Categorical vs Numerical Relationships
    cat_num = eda_results['relationships'].get('categorical_numerical', {})
    if cat_num:
        # Find first meaningful comparison
        cat_col = next((c for c in cat_num.keys() if is_meaningful_column(c, columns_info.get(c, {}))), None)
        if cat_col:
            num_col = next((n for n in cat_num[cat_col].keys() if is_meaningful_column(n, columns_info.get(n, {}))), None)
            if num_col:
                group_data = cat_num[cat_col][num_col]
                group_df = pd.DataFrame(group_data)
                if not group_df.empty:
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.bar(group_df['category'], group_df['mean'], color='#8b5cf6', alpha=0.8)
                    ax.set_title(f"Average {num_col} by {cat_col}", fontsize=12, fontweight='bold')
                    ax.set_xlabel(cat_col)
                    ax.set_ylabel(f"Avg {num_col}")
                    plt.xticks(rotation=30)
                    plt.tight_layout()
                    rel_path = os.path.join(output_dir, "categorical_numerical_relationship.png")
                    plt.savefig(rel_path, dpi=200, bbox_inches='tight')
                    plt.close()
                    paths['categorical_numerical_relationship'] = rel_path

    # 3. Numerical Distributions
    if numeric_cols:
        fig, axes = plt.subplots(1, min(3, len(numeric_cols)), figsize=(15, 4), squeeze=False)
        for idx, col in enumerate(numeric_cols[:3]):
            col_series = df[col].dropna()
            axes[0, idx].hist(col_series, bins=20, color='#6366f1', edgecolor='black', alpha=0.7)
            axes[0, idx].set_title(f"Distribution of {col}", fontsize=11, fontweight='bold')
            axes[0, idx].set_xlabel(col)
            axes[0, idx].set_ylabel("Frequency")
        plt.tight_layout()
        hist_path = os.path.join(output_dir, "numerical_distributions.png")
        plt.savefig(hist_path, dpi=200, bbox_inches='tight')
        plt.close()
        paths['numerical_distributions'] = hist_path

    # 4. Categorical Distributions
    if cat_cols:
        fig, axes = plt.subplots(1, min(3, len(cat_cols)), figsize=(15, 4), squeeze=False)
        for idx, col in enumerate(cat_cols[:3]):
            val_counts = df[col].astype(str).value_counts().head(8)
            axes[0, idx].bar(val_counts.index, val_counts.values, color='#10b981', alpha=0.8)
            axes[0, idx].set_title(f"Categories in {col}", fontsize=11, fontweight='bold')
            axes[0, idx].set_ylabel("Count")
            axes[0, idx].tick_params(axis='x', rotation=45)
        plt.tight_layout()
        cat_path = os.path.join(output_dir, "categorical_distributions.png")
        plt.savefig(cat_path, dpi=200, bbox_inches='tight')
        plt.close()
        paths['categorical_distributions'] = cat_path

    return paths
