import os
import sys
# Adjust path to include backend
sys.path.append(os.path.join(os.getcwd(), 'code_diff_project', 'backend'))

from analyzer.static_parser import LightStaticAnalyzer

project_root = r"D:\cloudE-master\code_diff_project\workspace\cloudeE-master"
recharge_provider_path = os.path.join(project_root, "cloudE-ucenter-provider", "src", "main", "java", "com", "cloudE", "ucenter", "provider", "RechargeProvider.java")
user_manager_path = os.path.join(project_root, "cloudE-ucenter-provider", "src", "main", "java", "com", "cloudE", "ucenter", "manager", "UserManager.java")

print(f"Checking RechargeProvider path: {os.path.exists(recharge_provider_path)}")
print(f"Checking UserManager path: {os.path.exists(user_manager_path)}")

analyzer = LightStaticAnalyzer(project_root)

# 1. Parse UserManager to get full name
full_name, class_name, base_path = analyzer.parse_java_file(user_manager_path)
print(f"Parsed UserManager: Full={full_name}, Class={class_name}, Base={base_path}")

# 2. Check usages
if full_name:
    usages = analyzer.find_usages(full_name)
    print(f"Found usages count: {len(usages)}")
    for u in usages:
        print(f"Usage: {u['file_name']} (Line {u.get('line')})")
else:
    print("Failed to parse UserManager")

