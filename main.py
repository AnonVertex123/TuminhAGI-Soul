#!/usr/bin/env python3
"""
TuminhAGI — Entry Point
Run: python main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nexus_core.orchestrator import main

if __name__ == "__main__":
    main()
