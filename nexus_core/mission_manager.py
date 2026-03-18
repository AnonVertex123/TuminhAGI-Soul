# i:\TuminhAgi\nexus_core\mission_manager.py
"""
Mission Manager — The Execution Hub of TuminhAGI.
================================================
Handles discovery and execution of modular "Missions" in missions_hub/.
"""

import os
import sys
import logging
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional

from config import MISSIONS_HUB_DIR

# Logger Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MissionManager")

class MissionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MissionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self.missions_dir = Path(MISSIONS_HUB_DIR)
        self.missions_dir.mkdir(parents=True, exist_ok=True)
        self.registry: Dict[str, Path] = {}
        self.scan_missions()
        self._initialized = True

    def scan_missions(self):
        """Scans the missions_hub/ folder for .py files."""
        self.registry = {}
        for file in self.missions_dir.glob("*.py"):
            if file.name.startswith("__"):
                continue
            mission_name = file.stem
            self.registry[mission_name] = file
        logger.info(f"Mission Registry updated: {list(self.registry.keys())}")

    def get_available_missions(self) -> List[str]:
        self.scan_missions()
        return list(self.registry.keys())

    def execute_mission(self, mission_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Executes a specific mission script and returns the result."""
        if mission_name not in self.registry:
            return {"status": "error", "message": f"Mission '{mission_name}' not found."}

        script_path = self.registry[mission_name]
        logger.info(f"Executing mission: {mission_name} from {script_path}")

        try:
            # We use subprocess for isolation, but for internal functions we could import
            # For "Expert Scripts", subprocess is safer to avoid polluting the main namespace
            import subprocess
            
            # Setup command
            venv_python = Path(sys.executable)
            cmd = [str(venv_python), str(script_path)]
            if args:
                cmd.extend(args)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300 # 5 minutes timeout
            )

            if result.returncode == 0:
                return {
                    "status": "success",
                    "output": result.stdout,
                    "mission": mission_name
                }
            else:
                return {
                    "status": "error",
                    "message": result.stderr,
                    "output": result.stdout,
                    "mission": mission_name
                }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Mission timed out.", "mission": mission_name}
        except Exception as e:
            logger.error(f"Execution crash: {e}")
            return {"status": "error", "message": str(e), "mission": mission_name}

    def match_mission(self, user_input: str) -> Optional[str]:
        """Simple heuristic to match user input to a mission name."""
        user_input_lower = user_input.lower()
        available = self.get_available_missions()
        
        # Check for direct naming (e.g. "run youtube_pipeline")
        for m in available:
            if m in user_input_lower:
                return m
                
        # More advanced matching could go here (e.g. semantic match)
        return None
