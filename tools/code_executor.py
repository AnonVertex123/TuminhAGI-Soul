import subprocess
import tempfile
import sys
import time
from pathlib import Path

class CodeExecutor:
    def execute(self, code: str, timeout: int = 10) -> dict:
        forbidden = ["import os", "import sys", "open("]
        for fbd in forbidden:
            if fbd in code:
                return {
                    "success": False, 
                    "output": "", 
                    "error": f"Security Error: '{fbd}' not allowed.",
                    "execution_time": 0
                }
                
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            tmp_path = f.name
            
        start_time = time.time()
        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            exec_time = time.time() - start_time
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "execution_time": exec_time
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"Execution timed out after {timeout} seconds",
                "execution_time": timeout
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time": time.time() - start_time
            }
        finally:
            try:
                Path(tmp_path).unlink()
            except:
                pass
