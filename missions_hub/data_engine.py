# i:\TuminhAgi\missions_hub\data_engine.py
"""
Data Engine — Powerful SQL & Python Data Processor.
================================================
Handles DuckDB queries and Pandas operations on local files.
"""

import argparse
import pandas as pd
import duckdb
import json
import sys
import os
from pathlib import Path

def run_sql(query: str, db_path: str = None):
    """Executes a DuckDB query, potentially on local files."""
    try:
        if db_path:
            con = duckdb.connect(db_path)
        else:
            con = duckdb.connect(database=':memory:')
            
        # DuckDB can directly query CSV/Parquet files in the working directory
        result = con.execute(query).df()
        print(result.to_string(index=False))
        return result
    except Exception as e:
        print(f"SQL Error: {e}", file=sys.stderr)
        return None

def run_pandas(python_code: str):
    """Executes a Pandas-based Python script safely (as possible)."""
    try:
        # We provide a clean context with pd and np
        import numpy as np
        local_scope = {"pd": pd, "np": np, "result": None}
        
        # Execute the code - it's expected to set the 'result' variable
        exec(python_code, {}, local_scope)
        
        res = local_scope.get("result")
        if res is not None:
            if isinstance(res, (pd.DataFrame, pd.Series)):
                print(res.to_string())
            else:
                print(res)
        return res
    except Exception as e:
        print(f"Python/Pandas Error: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TuminhAGI Data Engine")
    parser.add_argument("--sql", type=str, help="DuckDB SQL query to execute")
    parser.add_argument("--code", type=str, help="Python/Pandas code to execute")
    parser.add_argument("--file", type=str, help="Path to a file (CSV/Parquet) for quick statistics")
    
    args = parser.parse_args()
    
    if args.sql:
        run_sql(args.sql)
    elif args.code:
        run_pandas(args.code)
    elif args.file:
        # Quick summary mode
        path = Path(args.file)
        if path.suffix == ".csv":
            df = pd.read_csv(path)
            print(f"--- Summary of {path.name} ---")
            print(df.describe().to_string())
            print(f"\nTotal Records: {len(df)}")
        else:
            print(f"Unsupported file type for quick summary: {path.suffix}", file=sys.stderr)
    else:
        print("Usage: python data_engine.py [--sql QUERY | --code CODE | --file PATH]")
