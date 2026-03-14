from tools.code_executor import CodeExecutor

class DataAgent:
    def __init__(self):
        self.executor = CodeExecutor()

    def analyze(self, code: str, data_path: str = None) -> str:
        if data_path:
            setup_code = f"import pandas as pd\ndf = pd.read_csv('{data_path}')\n"
            code = setup_code + code
            
        result = self.executor.execute(code, timeout=15)
        if result.get("success"):
            return f"Kết quả:\n{result.get('output', '')}"
        else:
            return f"Lỗi:\n{result.get('error', '')}"

    def generate_viz_code(self, df_name: str, chart_type: str) -> str:
        return f"""
import matplotlib.pyplot as plt
# plt.figure(figsize=(10,6))
# {df_name}.plot(kind='{chart_type}')
# plt.title('{chart_type} chart')
# plt.show()
"""
