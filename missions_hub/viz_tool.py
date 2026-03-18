# i:\TuminhAgi\missions_hub\viz_tool.py
"""
Visualization Tool — Chart Generator for TuminhAGI.
================================================
Generates PNG charts from data and saves them to workspace/visualizations/.
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import json
import sys
import os
from pathlib import Path

# Set up paths
BASE_DIR = Path("I:/TuminhAgi")
WORKSPACE_VIZ_DIR = BASE_DIR / "workspace" / "visualizations"
WORKSPACE_VIZ_DIR.mkdir(parents=True, exist_ok=True)

# Aesthetic configuration
plt.style.use('ggplot')
plt.rcParams.update({'font.size': 12, 'figure.figsize': (10, 6)})

def create_chart(data_json: str, output_name: str = "chart.png", title: str = "Tuminh Data View"):
    """Creates a chart from JSON data."""
    try:
        config = json.loads(data_json)
        chart_type = config.get("type", "line").lower()
        data = config.get("data", {})
        
        fig, ax = plt.subplots()
        
        if chart_type == "line":
            ax.plot(data.get("x"), data.get("y"), marker='o', linestyle='-', color='#007acc')
        elif chart_type == "bar":
            ax.bar(data.get("x"), data.get("y"), color='#28a745')
        elif chart_type == "scatter":
            ax.scatter(data.get("x"), data.get("y"), color='#e83e8c')
        elif chart_type == "pie":
            ax.pie(data.get("y"), labels=data.get("x"), autopct='%1.1f%%', colors=plt.cm.Paired.colors)
        else:
            print(f"Unknown chart type: {chart_type}", file=sys.stderr)
            return None
            
        ax.set_title(title)
        if chart_type != "pie":
            ax.set_xlabel(config.get("xlabel", "X Axis"))
            ax.set_ylabel(config.get("ylabel", "Y Axis"))
            
        plt.tight_layout()
        
        # Save output
        output_path = WORKSPACE_VIZ_DIR / output_name
        if not output_path.suffix:
            output_path = output_path.with_suffix(".png")
            
        plt.savefig(output_path, dpi=120)
        plt.close()
        
        print(f"✓ Chart successfully saved to: {output_path}")
        return str(output_path)
    except Exception as e:
        print(f"Visualization Error: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TuminhAGI Visualization Tool")
    parser.add_argument("--json", type=str, help="JSON configuration with chart data")
    parser.add_argument("--output", type=str, default="chart.png", help="Output filename")
    parser.add_argument("--title", type=str, default="Data Visualization", help="Chart title")
    
    args = parser.parse_args()
    
    if args.json:
        create_chart(args.json, args.output, args.title)
    else:
        print("Usage: python viz_tool.py --json '{\"type\": \"line\", \"data\": {...}}' [--output FILE] [--title TITLE]")
