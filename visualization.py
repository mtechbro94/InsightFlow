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

def generate_interactive_plots(df, eda_results, columns_info):
    """
    Generates interactive Plotly visualizations and returns them as dictionaries
    that can be serialized to JSON and rendered on the client side using Plotly.js.
    """
    plots = {}
    
    numeric_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'numeric']
    cat_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'categorical']
    date_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'datetime']

    # 1. Numerical Distributions (Histograms)
    plots['distributions'] = {}
    for col in numeric_cols[:3]: # Limit to top 3 numerical columns
        fig = px.histogram(
            df, x=col, 
            title=f"Distribution of {col}", 
            template="plotly_dark",
            color_discrete_sequence=['#6366f1'] # Premium Indigo
        )
        fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
        plots['distributions'][col] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 2. Outlier Box Plots
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

    # 3. Categorical Distributions (Bar/Horizontal Bar)
    plots['categorical'] = {}
    for col in cat_cols[:3]:
        cat_data = eda_results['numerical'].get(col) # check if in numeric summaries
        # Draw value distribution
        val_counts = df[col].astype(str).value_counts().head(10)
        
        # Determine orientation based on labels length or count
        orientation = 'h' if len(val_counts) > 5 or val_counts.index.str.len().max() > 10 else 'v'
        
        if orientation == 'h':
            fig = px.bar(
                x=val_counts.values, y=val_counts.index,
                orientation='h',
                title=f"Top 10 Categories in {col}",
                template="plotly_dark",
                color_discrete_sequence=['#10b981'],
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

    # 4. Correlation Heatmap
    corr_info = eda_results['relationships'].get('correlations', {})
    if corr_info and 'matrix' in corr_info:
        matrix = corr_info['matrix']
        cols = list(matrix.keys())
        z_values = [[matrix[c1][c2] for c2 in cols] for c1 in cols]
        
        fig = go.Figure(data=go.Heatmap(
            z=z_values,
            x=cols,
            y=cols,
            colorscale='RdBu',
            zmin=-1, zmax=1,
            text=np.round(z_values, 2),
            texttemplate="%{text}",
            hoverongaps = False
        ))
        fig.update_layout(
            title="Correlation Matrix",
            template="plotly_dark",
            margin=dict(l=40, r=40, t=50, b=40),
            xaxis={'tickangle': -45}
        )
        plots['correlation_heatmap'] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 5. Scatter Plot (Top Correlated Numerical Pair)
    strong_corrs = corr_info.get('strong_relationships', [])
    if strong_corrs:
        top_corr = strong_corrs[0]
        fig = px.scatter(
            df, x=top_corr['col1'], y=top_corr['col2'],
            title=f"Scatter Plot: {top_corr['col1']} vs {top_corr['col2']} (r = {top_corr['coefficient']:.2f})",
            template="plotly_dark",
            color_discrete_sequence=['#3b82f6']
        )
        fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
        plots['scatter_relation'] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 6. Categorical vs Numerical Relationships (Bar/Comparison)
    cat_num = eda_results['relationships'].get('categorical_numerical', {})
    plots['cat_num_relationships'] = {}
    
    if cat_num:
        for cat_col, num_cols in cat_num.items():
            plots['cat_num_relationships'][cat_col] = {}
            for num_col, group_data in num_cols.items():
                group_df = pd.DataFrame(group_data)
                if not group_df.empty:
                    fig = px.bar(
                        group_df, x='category', y='mean',
                        title=f"Average {num_col} by {cat_col}",
                        template="plotly_dark",
                        color_discrete_sequence=['#8b5cf6'],
                        labels={'category': cat_col, 'mean': f"Avg {num_col}"}
                    )
                    fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
                    plots['cat_num_relationships'][cat_col][num_col] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    # 7. Time-Series Trends
    ts_data = eda_results.get('time_series')
    plots['time_series'] = {}
    if ts_data and ts_data.get('series'):
        for metric, data in ts_data['series'].items():
            pts = data['data']
            if pts:
                ts_df = pd.DataFrame(pts)
                fig = px.line(
                    ts_df, x='date', y='sum',
                    title=f"{ts_data['granularity']} Trend for Total {metric}",
                    template="plotly_dark",
                    color_discrete_sequence=['#ec4899'],
                    labels={'date': ts_data['date_column'], 'sum': f"Sum of {metric}"}
                )
                fig.update_layout(margin=dict(l=40, r=40, t=50, b=40))
                plots['time_series'][metric] = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))

    return plots

def generate_static_plots(df, eda_results, columns_info, output_dir):
    """
    Generates static PNG plots to embed in the PDF analytical report.
    Colors are optimized for light-background print/PDF display.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    numeric_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'numeric']
    cat_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'categorical']
    
    # Set styling parameters for report aesthetics
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']

    # 1. Numerical Distributions (Save 1 combined image)
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

    # 2. Categorical Distributions (Save 1 combined image)
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

    # 3. Correlation Heatmap (Save 1 image)
    corr_info = eda_results['relationships'].get('correlations', {})
    if corr_info and 'matrix' in corr_info:
        matrix_dict = corr_info['matrix']
        cols = list(matrix_dict.keys())
        matrix_data = [[matrix_dict[c1][c2] for c2 in cols] for c1 in cols]
        
        fig, ax = plt.subplots(figsize=(8, 6))
        cax = ax.matshow(matrix_data, cmap='RdBu', vmin=-1, vmax=1)
        fig.colorbar(cax)
        
        ax.set_xticks(np.arange(len(cols)))
        ax.set_yticks(np.arange(len(cols)))
        ax.set_xticklabels(cols, rotation=45, ha='left')
        ax.set_yticklabels(cols)
        
        # Add labels
        for (i, j), z in np.ndenumerate(matrix_data):
            ax.text(j, i, f'{z:.2f}', ha='center', va='center',
                    bbox=dict(boxstyle='round', facecolor='white', edgecolor='0.8', alpha=0.8))
            
        plt.title("Correlation Matrix", pad=20, fontsize=12, fontweight='bold')
        plt.tight_layout()
        heatmap_path = os.path.join(output_dir, "correlation_heatmap.png")
        plt.savefig(heatmap_path, dpi=200, bbox_inches='tight')
        plt.close()
        paths['correlation_heatmap'] = heatmap_path

    # 4. Time Series Trend (Save 1 image)
    ts_data = eda_results.get('time_series')
    if ts_data and ts_data.get('series'):
        fig, ax = plt.subplots(figsize=(10, 4))
        for metric, data in ts_data['series'].items():
            pts = data['data']
            if pts:
                ts_df = pd.DataFrame(pts)
                ax.plot(ts_df['date'], ts_df['sum'], marker='o', label=f"Total {metric}", color='#ec4899', linewidth=2)
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

    return paths
