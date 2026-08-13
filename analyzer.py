import os
import re
import json
import numpy as np
import pandas as pd
import scipy.stats as stats
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def convert_to_csv(file_path, original_filename):
    """
    Detects file format and converts to a standardized CSV format if necessary.
    Supports CSV, Excel (xlsx, xls), JSON, and TSV.
    """
    _, ext = os.path.splitext(original_filename.lower())
    target_csv = file_path + "_standardized.csv"

    try:
        if ext == '.csv':
            # Detect delimiter and encoding
            # Try parsing with default first, fallback to common encodings
            encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
            df = None
            for encoding in encodings:
                try:
                    # Sniff delimiter
                    with open(file_path, 'r', encoding=encoding) as f:
                        first_line = f.readline()
                        delimiter = ','
                        if '\t' in first_line:
                            delimiter = '\t'
                        elif ';' in first_line:
                            delimiter = ';'
                    df = pd.read_csv(file_path, encoding=encoding, sep=delimiter)
                    break
                except Exception:
                    continue
            
            if df is None:
                raise ValueError("Could not parse CSV file. Please ensure it has a valid encoding and format.")
            
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, engine='openpyxl')
            
        elif ext == '.tsv':
            df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
            
        elif ext == '.json':
            df = pd.read_json(file_path)
            
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Supported formats: CSV, Excel, JSON, TSV.")

        # Drop completely empty columns (all NaN)
        df = df.dropna(how='all', axis=1)
        
        # Drop columns that start with "Unnamed:" and are mostly empty or have <= 1 unique value
        unnamed_cols = [c for c in df.columns if str(c).startswith('Unnamed:') and (df[c].isnull().sum() / len(df) > 0.5 or df[c].nunique() <= 1)]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)

        # Validate that the conversion resulted in a non-empty dataframe
        if df.empty:
            raise ValueError("The uploaded dataset contains no records.")

        # Save standardized CSV
        df.to_csv(target_csv, index=False, encoding='utf-8')
        return target_csv, df

    except Exception as e:
        raise ValueError(f"File parsing/conversion failed: {str(e)}")

def profile_dataset(df):
    """
    Analyzes the structure, column types, and basic statistics of a dataset.
    Intelligently infers column semantic types rather than just raw pandas dtypes.
    """
    num_records, num_features = df.shape
    columns_info = {}
    
    # Missing and duplicate summaries
    total_missing = int(df.isnull().sum().sum())
    duplicate_count = int(df.duplicated().sum())
    
    memory_usage = df.memory_usage(deep=True).sum()
    if memory_usage < 1024:
        memory_str = f"{memory_usage} Bytes"
    elif memory_usage < 1024 * 1024:
        memory_str = f"{memory_usage / 1024:.2f} KB"
    else:
        memory_str = f"{memory_usage / (1024 * 1024):.2f} MB"

    for col in df.columns:
        series = df[col]
        non_null_series = series.dropna()
        null_count = int(series.isnull().sum())
        null_pct = float((null_count / num_records) * 100) if num_records > 0 else 0.0
        unique_count = int(series.nunique())
        
        # Simple sample values
        sample_vals = non_null_series.head(10).tolist()
        sample_vals = [str(v) for v in sample_vals]
        
        original_dtype = str(series.dtype)
        inferred_type = 'text' # Default fallback
        
        # Check if column is completely null
        if len(non_null_series) == 0:
            inferred_type = 'empty'
        else:
            # Let's perform semantic inference
            col_name_lower = col.lower()
            
            # 1. ID Column check
            is_id_name = any(x in col_name_lower for x in ['id', 'key', 'code', 'num', 'uuid', 'index'])
            is_all_unique = (unique_count == len(non_null_series))
            if (is_id_name and unique_count > 1) or (is_all_unique and unique_count > 5 and original_dtype in ['object', 'int64']):
                inferred_type = 'id'
            
            # 2. Boolean check
            elif original_dtype == 'bool' or (unique_count <= 2 and set(non_null_series.unique()).issubset({0, 1, 0.0, 1.0, '0', '1', 'True', 'False', 'true', 'false', 'T', 'F', 'Y', 'N', 'yes', 'no', 'Yes', 'No'})):
                inferred_type = 'boolean'
                
            # 3. Datetime check
            elif 'date' in col_name_lower or 'time' in col_name_lower or 'year' in col_name_lower or 'month' in col_name_lower or 'day' in col_name_lower:
                # Try parsing as datetime
                try:
                    pd.to_datetime(non_null_series.head(100), errors='raise')
                    inferred_type = 'datetime'
                except Exception:
                    pass
            
            # If still not classified, check numerical vs categorical
            if inferred_type in ['text', 'empty']:
                if pd.api.types.is_numeric_dtype(series):
                    # Numerical column but with very low cardinality could be categorical
                    if unique_count <= 10:
                        inferred_type = 'categorical'
                    else:
                        inferred_type = 'numeric'
                else:
                    # Let's check if it parses as dates
                    try:
                        # sample check
                        pd.to_datetime(non_null_series.head(10), errors='raise')
                        inferred_type = 'datetime'
                    except Exception:
                        # Check cardinality
                        if unique_count <= 25 or (unique_count / num_records < 0.05):
                            inferred_type = 'categorical'
                        else:
                            inferred_type = 'text'

        columns_info[col] = {
            'original_dtype': original_dtype,
            'inferred_type': inferred_type,
            'null_count': null_count,
            'null_pct': null_pct,
            'unique_count': unique_count,
            'sample_values': sample_vals
        }

    return {
        'num_records': num_records,
        'num_features': num_features,
        'total_missing': total_missing,
        'duplicate_count': duplicate_count,
        'memory_usage': memory_str,
        'columns': columns_info
    }

def clean_dataset(df, columns_info, imputation_strategy='auto', drop_duplicates=True, outlier_multiplier=1.5):
    """
    Cleans the dataset by removing duplicates, imputing missing values,
    and identifying numerical outliers.
    """
    cleaned_df = df.copy()
    cleaning_log = []
    
    # 1. Remove duplicates
    if drop_duplicates:
        dups = int(cleaned_df.duplicated().sum())
        if dups > 0:
            cleaned_df = cleaned_df.drop_duplicates().reset_index(drop=True)
            cleaning_log.append(f"Removed {dups} exact duplicate rows.")
            
    # 2. Impute missing values column by column
    for col in cleaned_df.columns:
        info = columns_info.get(col, {})
        inf_type = info.get('inferred_type')
        null_count = int(cleaned_df[col].isnull().sum())
        
        if null_count == 0:
            continue
            
        # If column is mostly null (> 80%), log warning
        null_pct = (null_count / len(df)) * 100
        if null_pct > 80:
            cleaning_log.append(f"Warning: Column '{col}' is {null_pct:.1f}% empty.")

        # Skip ID/Text columns for aggressive imputation, fill with 'Unknown'
        if inf_type in ['id', 'text', 'empty']:
            cleaned_df[col] = cleaned_df[col].fillna("Unknown")
            cleaning_log.append(f"Filled {null_count} missing values in text/ID column '{col}' with 'Unknown'.")
        
        elif inf_type == 'numeric':
            if imputation_strategy == 'disabled':
                # Skip numeric imputation
                continue
            elif imputation_strategy in ['auto', 'mean']:
                mean_val = cleaned_df[col].mean()
                # If int column, round the mean
                if cleaned_df[col].dtype in ['int64', 'int32']:
                    mean_val = round(mean_val)
                cleaned_df[col] = cleaned_df[col].fillna(mean_val)
                cleaning_log.append(f"Imputed {null_count} missing values in numerical column '{col}' using mean ({mean_val:.2f}).")
            elif imputation_strategy == 'median':
                med_val = cleaned_df[col].median()
                cleaned_df[col] = cleaned_df[col].fillna(med_val)
                cleaning_log.append(f"Imputed {null_count} missing values in numerical column '{col}' using median ({med_val:.2f}).")
                
        elif inf_type in ['categorical', 'boolean']:
            mode_series = cleaned_df[col].mode()
            if not mode_series.empty:
                mode_val = mode_series[0]
                cleaned_df[col] = cleaned_df[col].fillna(mode_val)
                cleaning_log.append(f"Imputed {null_count} missing values in categorical/boolean column '{col}' using mode ('{mode_val}').")
            else:
                cleaned_df[col] = cleaned_df[col].fillna("Unknown")
                cleaning_log.append(f"Filled {null_count} missing values in column '{col}' with 'Unknown'.")
                
        elif inf_type == 'datetime':
            # Forward and backward fill for ordered time-series data
            cleaned_df[col] = cleaned_df[col].ffill().bfill()
            cleaning_log.append(f"Imputed {null_count} missing values in datetime column '{col}' using forward/backward fill.")

    # 3. Outlier profiling (Does not delete, just flags)
    outliers_info = {}
    for col in cleaned_df.columns:
        info = columns_info.get(col, {})
        if info.get('inferred_type') == 'numeric':
            col_series = pd.to_numeric(cleaned_df[col], errors='coerce').dropna()
            if len(col_series) > 0:
                q1 = col_series.quantile(0.25)
                q3 = col_series.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - outlier_multiplier * iqr
                upper_bound = q3 + outlier_multiplier * iqr
                
                outlier_mask = (col_series < lower_bound) | (col_series > upper_bound)
                num_outliers = int(outlier_mask.sum())
                pct_outliers = float((num_outliers / len(cleaned_df)) * 100)
                
                if num_outliers > 0:
                    outliers_info[col] = {
                        'count': num_outliers,
                        'pct': pct_outliers,
                        'lower_bound': float(lower_bound),
                        'upper_bound': float(upper_bound),
                        'min': float(col_series.min()),
                        'max': float(col_series.max())
                    }
                    cleaning_log.append(f"Detected {num_outliers} outliers ({pct_outliers:.1f}%) in numerical column '{col}' using IQR method (bounds: [{lower_bound:.2f}, {upper_bound:.2f}] with {outlier_multiplier}x sensitivity).")

    return cleaned_df, cleaning_log, outliers_info

def detect_kpis(df, columns_info):
    """
    Dynamically identifies business KPIs or creates generic analytical KPIs.
    Returns details of target KPI columns and aggregate stats.
    """
    kpis = []
    
    # Priority mapping for columns
    kpi_terms = {
        'revenue': ['revenue', 'sales_amount', 'sales', 'turnover', 'invoice_val'],
        'sales_qty': ['quantity', 'qty', 'volume', 'units_sold', 'units'],
        'profit': ['profit', 'margin', 'net_profit', 'earnings'],
        'cost': ['cost', 'spend', 'expense', 'expenses', 'budget'],
        'customers': ['customer_id', 'cust_id', 'client_id', 'user_id', 'customer', 'user', 'buyer'],
        'products': ['product_id', 'prod_id', 'item_id', 'product', 'item', 'sku'],
        'orders': ['order_id', 'transaction_id', 'trans_id', 'order_no', 'invoice_id', 'order']
    }

    # Match columns to KPIs
    matched_cols = {}
    for col in df.columns:
        col_lower = col.lower()
        for kpi_type, terms in kpi_terms.items():
            if any(term == col_lower or col_lower.startswith(term + '_') or col_lower.endswith('_' + term) for term in terms):
                matched_cols[kpi_type] = col
                break

    # 1. Total Records (Always generic KPI)
    kpis.append({
        'name': 'Total Records',
        'value': f"{len(df):,}",
        'column': 'N/A',
        'type': 'generic',
        'raw_value': len(df)
    })

    # 2. Add matched business KPIs
    for kpi_type, col in matched_cols.items():
        series = df[col]
        inf_type = columns_info.get(col, {}).get('inferred_type')
        
        if kpi_type in ['revenue', 'profit', 'cost'] and inf_type == 'numeric':
            total_val = float(series.sum())
            avg_val = float(series.mean())
            
            # Formatting large numbers
            formatted_val = format_large_number(total_val)
            formatted_avg = format_large_number(avg_val)
            
            kpis.append({
                'name': f"Total {col}",
                'value': formatted_val,
                'column': col,
                'type': 'business_sum',
                'raw_value': total_val
            })
            kpis.append({
                'name': f"Average {col}",
                'value': formatted_avg,
                'column': col,
                'type': 'business_avg',
                'raw_value': avg_val
            })
            
        elif kpi_type == 'sales_qty' and inf_type == 'numeric':
            total_qty = float(series.sum())
            kpis.append({
                'name': f"Total Quantity ({col})",
                'value': f"{total_qty:,.0f}",
                'column': col,
                'type': 'business_qty',
                'raw_value': total_qty
            })
            
        elif kpi_type in ['customers', 'products', 'orders']:
            distinct_count = int(series.nunique())
            name_map = {
                'customers': 'Total Customers',
                'products': 'Total Products',
                'orders': 'Total Transactions'
            }
            kpis.append({
                'name': name_map[kpi_type],
                'value': f"{distinct_count:,}",
                'column': col,
                'type': 'business_count',
                'raw_value': distinct_count
            })

    # 3. If no business KPIs are detected, generate numeric averages
    if len(kpis) <= 1:
        numeric_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'numeric']
        for col in numeric_cols[:3]: # limit to top 3
            avg_val = float(df[col].mean())
            kpis.append({
                'name': f"Average {col}",
                'value': f"{avg_val:,.2f}",
                'column': col,
                'type': 'generic_avg',
                'raw_value': avg_val
            })
            
    # Include features count
    kpis.append({
        'name': 'Total Features',
        'value': str(len(df.columns)),
        'column': 'N/A',
        'type': 'generic',
        'raw_value': len(df.columns)
    })

    return kpis

def format_large_number(num):
    """Formats float values to K, M, B for dashboards."""
    abs_num = abs(num)
    sign = "-" if num < 0 else ""
    if abs_num >= 1_000_000_000:
        return f"{sign}₹{abs_num / 1_000_000_000:.2f}B"
    elif abs_num >= 1_000_000:
        return f"{sign}₹{abs_num / 1_000_000:.2f}M"
    elif abs_num >= 1_000:
        return f"{sign}₹{abs_num / 1_000:.2f}K"
    else:
        return f"{sign}₹{num:,.2f}"

def run_eda(df, columns_info):
    """
    Performs full exploratory data analysis (numerical, categorical, correlations, time series, relationships).
    """
    eda = {
        'numerical': {},
        'categorical': {},
        'relationships': {
            'correlations': {},
            'categorical_numerical': {},
            'categorical_categorical': {}
        },
        'time_series': None
    }

    # Extract column lists by inferred types
    numeric_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'numeric']
    cat_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'categorical']
    bool_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'boolean']
    date_cols = [c for c, info in columns_info.items() if info.get('inferred_type') == 'datetime']

    # 1. Numerical Analysis
    for col in numeric_cols:
        col_series = pd.to_numeric(df[col], errors='coerce').dropna()
        if len(col_series) == 0:
            continue
            
        desc = col_series.describe()
        skewVal = float(stats.skew(col_series)) if len(col_series) > 2 else 0.0
        kurtVal = float(stats.kurtosis(col_series)) if len(col_series) > 2 else 0.0
        mode_series = col_series.mode()
        modeVal = float(mode_series[0]) if not mode_series.empty else float(col_series.median())
        
        eda['numerical'][col] = {
            'count': int(desc['count']),
            'mean': float(desc['mean']),
            'median': float(col_series.median()),
            'mode': modeVal,
            'min': float(desc['min']),
            'max': float(desc['max']),
            'range': float(desc['max'] - desc['min']),
            'std': float(desc['std']) if not pd.isna(desc['std']) else 0.0,
            'var': float(col_series.var()) if len(col_series) > 1 else 0.0,
            'q25': float(desc['25%']),
            'q50': float(desc['50%']),
            'q75': float(desc['75%']),
            'skewness': skewVal,
            'kurtosis': kurtVal
        }

    # 2. Categorical & Boolean Analysis
    for col in cat_cols + bool_cols:
        col_series = df[col].astype(str).fillna("Missing")
        val_counts = col_series.value_counts()
        total_counts = int(val_counts.sum())
        
        # High cardinality handling (group into 'Others')
        top_n = val_counts.head(10)
        remaining = val_counts.iloc[10:]
        
        distributions = {}
        for category, count in top_n.items():
            distributions[str(category)] = {
                'count': int(count),
                'pct': float((count / total_counts) * 100)
            }
            
        if not remaining.empty:
            others_sum = int(remaining.sum())
            distributions['Others'] = {
                'count': others_sum,
                'pct': float((others_sum / total_counts) * 100)
            }

        eda['categorical'][col] = {
            'unique_categories': int(col_series.nunique()),
            'most_common': {
                'category': str(val_counts.index[0]) if not val_counts.empty else 'N/A',
                'count': int(val_counts.iloc[0]) if not val_counts.empty else 0,
                'pct': float((val_counts.iloc[0] / total_counts) * 100) if not val_counts.empty else 0.0
            },
            'least_common': {
                'category': str(val_counts.index[-1]) if not val_counts.empty else 'N/A',
                'count': int(val_counts.iloc[-1]) if not val_counts.empty else 0,
                'pct': float((val_counts.iloc[-1] / total_counts) * 100) if not val_counts.empty else 0.0
            },
            'distribution': distributions
        }

    # 3. Relationships (Numerical vs Numerical Correlations)
    if len(numeric_cols) > 1:
        corr_matrix = df[numeric_cols].corr(method='pearson')
        # Convert to records format for JS consumption
        matrix_dict = {}
        for col1 in corr_matrix.columns:
            matrix_dict[col1] = {}
            for col2 in corr_matrix.index:
                val = corr_matrix.loc[col1, col2]
                matrix_dict[col1][col2] = float(val) if not pd.isna(val) else 0.0
        
        # Pull out strong relationships
        strong_pairs = []
        for i in range(len(numeric_cols)):
            for j in range(i+1, len(numeric_cols)):
                col1 = numeric_cols[i]
                col2 = numeric_cols[j]
                coef = corr_matrix.loc[col1, col2]
                if not pd.isna(coef) and abs(coef) >= 0.4:
                    strong_pairs.append({
                        'col1': col1,
                        'col2': col2,
                        'coefficient': float(coef),
                        'direction': 'positive' if coef > 0 else 'negative',
                        'strength': 'strong' if abs(coef) >= 0.7 else 'moderate'
                    })
                    
        eda['relationships']['correlations'] = {
            'matrix': matrix_dict,
            'strong_relationships': sorted(strong_pairs, key=lambda x: abs(x['coefficient']), reverse=True)[:10]
        }

    # 4. Relationships (Categorical vs Numerical)
    # Analyze how key numerical columns vary across main categorical columns
    key_numerics = numeric_cols[:3] # limit comparisons
    key_categoricals = cat_cols[:3]
    
    if key_numerics and key_categoricals:
        cat_num_summary = {}
        for cat in key_categoricals:
            cat_num_summary[cat] = {}
            for num in key_numerics:
                # Group by and calculate mean, median, sum
                grouped = df.groupby(cat)[num].agg(['mean', 'median', 'sum', 'count']).dropna()
                # Sort by mean value descending
                grouped = grouped.sort_values(by='mean', ascending=False)
                
                cat_num_summary[cat][num] = []
                # Keep top 10 categories to avoid dashboard clutter
                for category, row in grouped.head(10).iterrows():
                    cat_num_summary[cat][num].append({
                        'category': str(category),
                        'mean': float(row['mean']),
                        'median': float(row['median']),
                        'sum': float(row['sum']),
                        'count': int(row['count'])
                    })
        eda['relationships']['categorical_numerical'] = cat_num_summary

    # 5. Relationships (Categorical vs Categorical)
    # Compute cross-tabulation for top 2 categorical columns
    if len(key_categoricals) >= 2:
        cat1 = key_categoricals[0]
        cat2 = key_categoricals[1]
        crosstab = pd.crosstab(df[cat1], df[cat2])
        
        crosstab_list = []
        for index, row in crosstab.iterrows():
            for col, count in row.items():
                if count > 0:
                    crosstab_list.append({
                        'cat1_val': str(index),
                        'cat2_val': str(col),
                        'count': int(count)
                    })
        eda['relationships']['categorical_categorical'] = {
            'cat1': cat1,
            'cat2': cat2,
            'data': crosstab_list[:30] # Top 30 cross tabs
        }

    # 6. Time-Series Analysis
    if date_cols:
        # Pick the first date column
        date_col = date_cols[0]
        try:
            # Parse dates and sort
            ts_df = df.copy()
            ts_df[date_col] = pd.to_datetime(ts_df[date_col], errors='coerce')
            ts_df = ts_df.dropna(subset=[date_col]).sort_values(by=date_col)
            
            if not ts_df.empty:
                min_date = ts_df[date_col].min()
                max_date = ts_df[date_col].max()
                delta = max_date - min_date
                
                # Dynamically choose granularity
                # > 3 years -> Year; > 3 months -> Month; else -> Day
                if delta.days > 3 * 365:
                    granularity = 'YE' # Year end
                    date_format = '%Y'
                elif delta.days > 90:
                    granularity = 'ME' # Month end
                    date_format = '%Y-%m'
                else:
                    granularity = 'D' # Daily
                    date_format = '%Y-%m-%d'

                # Set date index
                ts_df = ts_df.set_index(date_col)
                
                # Pick numeric columns to aggregate (up to 3)
                target_ts_cols = numeric_cols[:2]
                
                ts_results = {
                    'date_column': date_col,
                    'granularity': 'Yearly' if granularity == 'YE' else 'Monthly' if granularity == 'ME' else 'Daily',
                    'series': {}
                }
                
                for t_col in target_ts_cols:
                    # Resample and aggregate
                    resampled = ts_df[t_col].resample(granularity).agg(['sum', 'mean', 'count']).dropna()
                    
                    if not resampled.empty:
                        data_points = []
                        for dt, row in resampled.iterrows():
                            data_points.append({
                                'date': dt.strftime(date_format),
                                'sum': float(row['sum']),
                                'mean': float(row['mean']),
                                'count': int(row['count'])
                            })
                            
                        # Growth calculation
                        pct_change = 0.0
                        if len(resampled) > 1:
                            first_val = resampled['sum'].iloc[0]
                            last_val = resampled['sum'].iloc[-1]
                            if first_val != 0:
                                pct_change = float(((last_val - first_val) / first_val) * 100)
                                
                        # Moving average
                        resampled['ma'] = resampled['sum'].rolling(window=min(3, len(resampled))).mean()
                        
                        peaks = resampled.loc[resampled['sum'] == resampled['sum'].max()]
                        lows = resampled.loc[resampled['sum'] == resampled['sum'].min()]
                        
                        ts_results['series'][t_col] = {
                            'data': data_points,
                            'total_growth_pct': pct_change,
                            'peak': {
                                'date': peaks.index[0].strftime(date_format) if not peaks.empty else 'N/A',
                                'value': float(peaks['sum'].iloc[0]) if not peaks.empty else 0.0
                            },
                            'low': {
                                'date': lows.index[0].strftime(date_format) if not lows.empty else 'N/A',
                                'value': float(lows['sum'].iloc[0]) if not lows.empty else 0.0
                            }
                        }
                
                eda['time_series'] = ts_results
        except Exception as e:
            print(f"Time-series analysis failed: {str(e)}")

    return eda

def generate_insights(df, eda_results, columns_info, cleaning_log, outliers_info, kpis):
    """
    Main entry point for generating descriptive and analytical insights.
    Queries xAI's Grok API if API Key is configured, otherwise runs local heuristics.
    """
    grok_api_key = os.getenv('GROK_API_KEY') or os.getenv('XAI_API_KEY')
    
    if grok_api_key:
        try:
            return generate_grok_insights(grok_api_key, eda_results, columns_info, cleaning_log, outliers_info, kpis)
        except Exception as e:
            print(f"Grok API call failed, falling back to rule-based insights: {str(e)}")
            
    return generate_rule_based_insights(df, eda_results, columns_info, cleaning_log, outliers_info, kpis)

def generate_grok_insights(api_key, eda_results, columns_info, cleaning_log, outliers_info, kpis):
    """
    Queries xAI Grok API for professional business analysis insights based on statistical data.
    """
    # Build a concise data summary for the prompt to save tokens
    summary_data = {
        'kpis': [{k['name']: k['value']} for k in kpis],
        'columns': {c: {'type': info['inferred_type'], 'null_pct': info['null_pct']} for c, info in columns_info.items()},
        'clean_actions': cleaning_log[:8],
        'outliers': {c: f"{info['count']} outliers ({info['pct']:.1f}%)" for c, info in outliers_info.items()},
        'correlations': eda_results['relationships'].get('correlations', {}).get('strong_relationships', [])[:5],
        'cat_numerical': {}
    }
    
    # Pack top categorical groupings
    cat_num = eda_results['relationships'].get('categorical_numerical', {})
    for cat_col, num_cols in cat_num.items():
        summary_data['cat_numerical'][cat_col] = {}
        for num_col, group_data in num_cols.items():
            summary_data['cat_numerical'][cat_col][num_col] = [
                {'category': item['category'], 'mean': f"{item['mean']:.2f}", 'sum': f"{item['sum']:.2f}"}
                for item in group_data[:3]
            ]
            
    # Pack Time-Series Trend
    ts = eda_results.get('time_series')
    if ts:
        summary_data['time_series'] = {
            'granularity': ts['granularity'],
            'metrics': {}
        }
        for metric, data in ts['series'].items():
            summary_data['time_series']['metrics'][metric] = {
                'total_growth_pct': f"{data['total_growth_pct']:.2f}%",
                'peak': {'date': data['peak']['date'], 'val': f"{data['peak']['value']:.2f}"},
                'low': {'date': data['low']['date'], 'val': f"{data['low']['value']:.2f}"}
            }

    system_prompt = (
        "You are an expert financial and business data analyst. Analyze the provided dataset metadata and statistics "
        "and return a JSON response containing detailed natural-language insights. Do not hallucinate or guess. "
        "Every single insight MUST be directly traceable to the stats provided.\n\n"
        "Your output must be a valid JSON object matching this structure EXACTLY:\n"
        "{\n"
        "  \"data_quality\": [\"Insight 1...\", \"Insight 2...\"],\n"
        "  \"descriptive\": [\"Insight 1...\", \"Insight 2...\"],\n"
        "  \"trend\": [\"Insight 1...\", \"Insight 2...\"],\n"
        "  \"relationship\": [\"Insight 1...\", \"Insight 2...\"],\n"
        "  \"business\": [\"Insight 1...\", \"Insight 2...\", \"Business recommendation 1...\"]\n"
        "}"
    )

    user_prompt = f"Here is the statistical summary of the dataset:\n\n{json.dumps(summary_data, indent=2)}\n\nGenerate insights."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "grok-2-latest", # standard Grok 2 API model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    # Custom endpoint for Grok API
    url = "https://api.xai.com/v1/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=25)
    
    if response.status_code == 200:
        result_json = response.json()
        content = result_json['choices'][0]['message']['content']
        return json.loads(content)
    else:
        raise ValueError(f"Grok API returned status code {response.status_code}: {response.text}")

def generate_rule_based_insights(df, eda_results, columns_info, cleaning_log, outliers_info, kpis):
    """
    Pure Python rule-based insight generation engine using statistical formulas and heuristics.
    Ensures correct structure and 100% data trace accuracy.
    """
    insights = {
        'data_quality': [],
        'descriptive': [],
        'trend': [],
        'relationship': [],
        'business': []
    }

    # 1. Data Quality Insights
    total_records = len(df)
    null_cols = [c for c, info in columns_info.items() if info['null_count'] > 0]
    
    if not null_cols:
        insights['data_quality'].append("Data is highly clean: 0 missing values detected in the entire dataset.")
    else:
        for col in null_cols[:3]:
            info = columns_info[col]
            insights['data_quality'].append(f"Approximately {info['null_pct']:.1f}% of records contain missing values in the '{col}' column (imputed successfully).")

    if outliers_info:
        for col, o_data in list(outliers_info.items())[:2]:
            insights['data_quality'].append(f"Significant outliers flagged in '{col}': {o_data['count']} values ({o_data['pct']:.1f}%) lie outside normal IQR limits.")
    else:
        insights['data_quality'].append("Outlier analysis shows all numeric columns are within standard statistical boundaries.")

    if len(cleaning_log) > 0:
        insights['data_quality'].append(f"Automatic preparation successfully processed the dataset, logging {len(cleaning_log)} cleaning actions.")

    # 2. Descriptive Insights
    for col, data in list(eda_results['numerical'].items())[:2]:
        skew_desc = "fairly symmetric"
        if data['skewness'] > 1:
            skew_desc = "highly right-skewed (tail on the right)"
        elif data['skewness'] < -1:
            skew_desc = "highly left-skewed (tail on the left)"
        
        insights['descriptive'].append(
            f"The numerical average for '{col}' is {data['mean']:,.2f} with a median of {data['median']:,.2f}. "
            f"The column shows a {skew_desc} distribution (skewness: {data['skewness']:.2f})."
        )

    for col, data in list(eda_results['categorical'].items())[:2]:
        insights['descriptive'].append(
            f"The category '{data['most_common']['category']}' is the most common in feature '{col}', "
            f"representing {data['most_common']['count']:,} records ({data['most_common']['pct']:.1f}% of total)."
        )

    # 3. Relationship Insights
    strong_corrs = eda_results['relationships'].get('correlations', {}).get('strong_relationships', [])
    if strong_corrs:
        for rel in strong_corrs[:2]:
            insights['relationship'].append(
                f"A strong {rel['direction']} correlation ({rel['coefficient']:.2f}) exists between '{rel['col1']}' and '{rel['col2']}'."
            )
    else:
        insights['relationship'].append("Correlation matrix shows no strongly linear correlation among numeric features.")

    cat_num = eda_results['relationships'].get('categorical_numerical', {})
    if cat_num:
        # Get the first category vs numeric comparison
        cat_col = list(cat_num.keys())[0]
        num_col = list(cat_num[cat_col].keys())[0]
        groupings = cat_num[cat_col][num_col]
        if len(groupings) >= 2:
            highest = groupings[0]
            lowest = groupings[-1]
            insights['relationship'].append(
                f"Categorical analysis reveals '{highest['category']}' has the highest average {num_col} ({highest['mean']:,.2f}), "
                f"while '{lowest['category']}' exhibits the lowest ({lowest['mean']:,.2f})."
            )

    # 4. Trend Insights
    ts = eda_results.get('time_series')
    if ts and ts['series']:
        for metric, data in ts['series'].items():
            direction = "increased" if data['total_growth_pct'] >= 0 else "decreased"
            insights['trend'].append(
                f"{metric} {direction} by {abs(data['total_growth_pct']):.1f}% over the tracked time window."
            )
            insights['trend'].append(
                f"Peak performance for '{metric}' occurred on {data['peak']['date']} reaching a sum of {format_large_number(data['peak']['value'])}, "
                f"while lowest index was on {data['low']['date']}."
            )
    else:
        insights['trend'].append("No chronological date structure could be established to extract time-series trend insights.")

    # 5. Business Insights / Recommendations
    # Heuristic recommendations based on dataset findings
    if ts and ts['series']:
        for metric, data in ts['series'].items():
            if data['total_growth_pct'] < 0:
                insights['business'].append(
                    f"Action Required: Investigate operational issues causing a {abs(data['total_growth_pct']):.1f}% decline in '{metric}'."
                )
            else:
                insights['business'].append(
                    f"Operational Tip: Capitalize on growth momentum of {data['total_growth_pct']:.1f}% observed in '{metric}'."
                )
                
    if cat_num:
        cat_col = list(cat_num.keys())[0]
        num_col = list(cat_num[cat_col].keys())[0]
        groupings = cat_num[cat_col][num_col]
        if len(groupings) >= 2:
            highest = groupings[0]
            lowest = groupings[-1]
            
            insights['business'].append(
                f"Marketing Recommendation: Allocate more resource/focus on segment '{highest['category']}' "
                f"as it yields the highest average '{num_col}' ({format_large_number(highest['mean'])})."
            )
            insights['business'].append(
                f"Auditing Advice: Inspect performance blockers in '{lowest['category']}' "
                f"due to low average '{num_col}' ({format_large_number(lowest['mean'])})."
            )

    if outliers_info:
        for col in list(outliers_info.keys())[:1]:
            insights['business'].append(
                f"Risk Assessment: Standardize transaction monitoring in column '{col}' to prevent anomalies from skewing performance averages."
            )
            
    if not insights['business']:
        insights['business'].append("Strategy: Focus operations around high-performing categories and explore correlation pathways to increase performance metrics.")

    return insights
