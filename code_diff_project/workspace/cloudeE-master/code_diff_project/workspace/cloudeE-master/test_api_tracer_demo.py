import os
import sys

# Ensure backend directory is in path
backend_path = os.path.join(os.getcwd(), 'code_diff_project', 'backend')
if backend_path not in sys.path:
    sys.path.append(backend_path)

from analyzer.api_tracer import ApiUsageTracer
from loguru import logger

def main():
    # Force loguru to print to stderr
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    # Hardcoded path based on your environment
    project_root = r"D:\cloudE-master\code_diff_project\workspace\cloudeE-master"
    
    print(f"DEBUG: Current CWD: {os.getcwd()}")
    print(f"DEBUG: Using project_root: {project_root}")
    
    if not os.path.exists(project_root):
        print(f"ERROR: Project root does not exist: {project_root}")
        # Try a fallback or list directory
        fallback = os.path.join(os.getcwd(), "cloudE-ucenter-provider") # Try detecting if we are inside root
        if os.path.exists(fallback):
             project_root = os.getcwd()
             print(f"DEBUG: Fallback to current dir: {project_root}")
        else:
             return

    tracer = ApiUsageTracer(project_root)
    
    # Test Case: Cross-Service Call via Feign Client
    # PointClient is in 'cloudE-pay-api'
    # RechargeProvider is in 'cloudE-ucenter-provider' and calls pointClient.addPoint(...)
    target_class = "PointClient"
    target_method = "addPoint"
    
    print(f"\nScanning for APIs calling {target_class}.{target_method}...")
    apis = tracer.find_affected_apis(target_class, target_method)
    
    if apis:
        print(f"[SUCCESS] Found {len(apis)} affected APIs:")
        for api in apis:
            print(f" - {api}")
    else:
        print("[INFO] No APIs found (Check logs above for details).")

if __name__ == "__main__":
    main()
