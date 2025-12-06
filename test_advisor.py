import subprocess
import os
import sys
import json
import urllib.request
import urllib.error

# --- DeepSeek API 配置 ---
DEEPSEEK_API_KEY = "sk-onjbfk7nV3bpqi8hZD9stZ8AFlJ9eUu0dyP1iAEpeWdrlTAo"
# 注意: 这里的 URL 必须是完整的 API 终端地址
DEEPSEEK_API_URL = "https://www.chataiapi.com/v1/chat/completions"
# DeepSeek-V3 (指向 deepseek-chat) 是目前最强、最适合 RAG 的模型
DEEPSEEK_MODEL = "deepseek-chat" 
USE_DEEPSEEK_API = True

def get_git_diff():
    """
    获取 Git Diff 信息
    策略:
    1. 优先获取暂存区 (Staged) 的变更 (git diff --cached)
    2. 如果暂存区为空，则获取最近一次提交的变更 (git diff HEAD^ HEAD)
    """
    try:
        # 1. 尝试获取暂存区 (已 git add 但未 commit) 的 Java 变更
        # --cached 表示获取暂存区的变更
        cmd_staged = ["git", "diff", "--cached", "--", "*.java"]
        result_staged = subprocess.run(
            cmd_staged, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            check=True
        )
        
        if result_staged.stdout and result_staged.stdout.strip():
            print("[Info] 检测到暂存区 (Staged) 有代码变更，正在分析...")
            return result_staged.stdout

        # 2. 如果暂存区没有 Java 变更，尝试获取最近一次提交
        print("[Info] 暂存区无 Java 变更，尝试检查最近一次提交 (Last Commit)...")
        cmd_commit = ["git", "diff", "HEAD^", "HEAD", "--", "*.java"]
        result_commit = subprocess.run(
            cmd_commit, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            check=True
        )
        
        if result_commit.stdout and result_commit.stdout.strip():
            return result_commit.stdout
            
        return None

    except subprocess.CalledProcessError:
        print("Error: 无法获取 Git Diff，请确保这是一个 Git 仓库。")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def parse_diff(diff_text):
    """
    简单的 Diff 解析，按文件拆分
    """
    files_diff = {}
    current_file = None
    buffer = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files_diff[current_file] = "\n".join(buffer)
            
            # 提取文件名 a/path/to/File.java b/path/to/File.java
            parts = line.split()
            if len(parts) >= 4:
                # 取 b/ 路径
                current_file = parts[-1].lstrip("b/")
                buffer = []
        
        buffer.append(line)
    
    # 最后一个文件
    if current_file:
        files_diff[current_file] = "\n".join(buffer)
        
    return files_diff

def call_deepseek_api(messages):
    """
    调用 DeepSeek API
    使用标准库 urllib 避免依赖
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.1
    }
    
    try:
        req = urllib.request.Request(
            DEEPSEEK_API_URL, 
            data=json.dumps(data).encode('utf-8'), 
            headers=headers, 
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                print("API 返回结果异常:", result)
                return None
            
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

def print_code_comparison(diff_text):
    """
    打印直观的代码对比
    """
    print("\n[Code Diff] 变更代码对比:")
    print("-" * 80)
    
    lines = diff_text.splitlines()
    for line in lines:
        # 忽略 git diff 的元数据头
        if line.startswith("diff --git") or line.startswith("index ") or line.startswith("---") or line.startswith("+++"):
            continue
            
        if line.startswith("@@"):
            # 提取行号信息，增加可读性
            print(f"\n[Line] {line}")
            continue
            
        if line.startswith("-"):
            # 删除的行 (OLD)
            print(f"[-] {line[1:]}")
        elif line.startswith("+"):
            # 新增的行 (NEW)
            print(f"[+] {line[1:]}")
        else:
            # 上下文行
            print(f"    {line}")
    print("-" * 80)

import re

# ... (Previous imports)

def extract_api_paths(diff_text):
    """
    从 Diff 中简单提取涉及的 API 路径 (基于 Spring 注解)
    返回: set(['/recharge', '/user/get'])
    """
    paths = set()
    # 匹配 @RequestMapping, @PostMapping, @GetMapping 等
    # 简单的正则匹配 value = "/xxx" 或 ("/xxx")
    pattern = re.compile(r'@(?:Request|Post|Get|Put|Delete)Mapping\s*\(.*?(?:value\s*=\s*)?"([^"]+)".*?\)')
    
    # 搜索变更内容（新增或修改的行）
    for line in diff_text.splitlines():
        if line.startswith("+") or line.startswith(" "): # 关注新增行或上下文
            matches = pattern.findall(line)
            for m in matches:
                paths.add(m)
    return paths

def search_api_usages(root_dir, api_path, exclude_file):
    """
    在项目中搜索谁调用了这个 API
    """
    usages = []
    print(f"[Link Analysis] 正在搜索全项目对接口 '{api_path}' 的调用...")
    
    for root, dirs, files in os.walk(root_dir):
        # 忽略 git 目录和 target 目录
        if ".git" in dirs: dirs.remove(".git")
        if "target" in dirs: dirs.remove("target")
        
        for file in files:
            if file.endswith(".java"):
                full_path = os.path.join(root, file)
                # 排除自己
                if os.path.abspath(full_path) == os.path.abspath(exclude_file):
                    continue
                    
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if api_path in content:
                            # 简单的包含匹配，找到调用者
                            # 提取微服务模块名 (假设目录结构是 d:\root\service-name\src\...)
                            rel_path = os.path.relpath(full_path, root_dir)
                            service_name = rel_path.split(os.sep)[0]
                            usages.append(f"服务 [{service_name}] -> 文件 {os.path.basename(file)}")
                except:
                    pass
    return usages

def analyze_with_llm(filename, diff_content):
    # 先打印代码对比
    print_code_comparison(diff_content)
    
    # --- 新增: 跨服务链路分析 ---
    project_root = os.getcwd() # 假设当前在项目根目录
    api_paths = extract_api_paths(diff_content)
    downstream_callers = []
    
    if api_paths:
        for api in api_paths:
            callers = search_api_usages(project_root, api, filename)
            if callers:
                downstream_callers.extend(callers)
    
    downstream_info = "\n".join(downstream_callers) if downstream_callers else "未检测到明显的跨服务调用引用。"
    print(f"[Link Analysis] 发现潜在下游调用方:\n{downstream_info}")
    # ---------------------------

    print(f"\n[AI Analysis] 正在使用 DeepSeek ({DEEPSEEK_MODEL}) 分析 {filename} ...")
    
    prompt = f"""
    # Role
    你是一名资深的 Java 测试架构师，精通微服务调用链路分析。
    
    # Context
    这是一个基于 Spring Cloud 的微服务项目 (Monorepo)。
    被修改的文件: {filename}
    
    # Cross-Service Impact (关键!)
    脚本检测到该变更可能影响以下下游服务（调用方）:
    {downstream_info}
    
    # Git Diff
    {diff_content}
    
    # Requirement
    请基于代码变更和**跨服务调用关系**，生成《微服务精准测试手册》。
    如果存在跨服务调用，请重点分析接口契约变更带来的风险。
    
    请严格按照以下 JSON 格式返回：
    {{
        "code_review_warning": "代码审查警示",
        "change_intent": "变更意图",
        "risk_level": "CRITICAL/HIGH/MEDIUM/LOW",
        "cross_service_impact": "跨服务影响分析 (请详细描述如果接口变了，下游 {downstream_info} 会发生什么故障)",
        "test_strategy": [
            {{
                "title": "测试场景",
                "priority": "P0/P1",
                "steps": "步骤",
                "payload": "Payload",
                "validation": "验证点"
            }}
        ]
    }}
    """
    
    messages = [
        {"role": "system", "content": "你是一个能够进行精准测试分析的AI助手。请只输出 JSON。"},
        {"role": "user", "content": prompt}
    ]
    
    response_content = call_deepseek_api(messages)
    
    if not response_content:
        return None
        
    # 尝试解析 JSON
    try:
        # 清理可能存在的 markdown 标记
        cleaned_content = response_content.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_content)
    except json.JSONDecodeError:
        print("解析 AI 响应失败，原始响应:")
        print(response_content)
        # 如果解析失败，返回原始文本作为 summary，避免程序崩溃
        return {
            "summary": "AI 响应格式解析失败",
            "impact": str(response_content)[:100] + "...",
            "risk_level": "UNKNOWN",
            "test_cases": ["请查看控制台原始输出"]
        }

def main():
    print("=== 精准测试分析助手 (DeepSeek版) ===")
    
    # 1. 获取 Diff
    diff_text = get_git_diff()
    if not diff_text:
        print("未检测到 Java 文件的变更 (Git Diff 为空)。")
        print("提示：请确保你已经 commit 了你的代码变更。")
        return

    # 2. 解析 Diff
    files_map = parse_diff(diff_text)
    print(f"检测到 {len(files_map)} 个 Java 文件发生变更。\n")

    # 3. 逐个分析
    for filename, content in files_map.items():
        if USE_DEEPSEEK_API:
            report = analyze_with_llm(filename, content)
        else:
            # Fallback (如果不使用 API)
            print("API 开关未打开")
            continue
            
        if report:
            print("=" * 80)
            print(f"【精准测试作战手册】: {filename}")
            
            warning = report.get('code_review_warning')
            if warning:
                print(f"\n[WARNING] CODE REVIEW 警示: {warning}")
            
            print(f"\n[Change Analysis] 变更分析:")
            print(f"  * 意图推测: {report.get('change_intent', 'N/A')}")
            print(f"  * 风险等级: {report.get('risk_level', 'N/A')}")
            print(f"  * 跨服务影响: {report.get('cross_service_impact', 'N/A')}")
            
            # 兼容旧字段
            impact = report.get('impact_analysis', {})
            if isinstance(impact, dict):
                print(f"  * 影响功能: {impact.get('functional', '-')}")
                print(f"  * 下游依赖: {impact.get('downstream', '-')}")

            print("\n[Test Strategy] 测试策略矩阵:")
            strategies = report.get('test_strategy', [])
            if strategies:
                print(f"{'优先级':<6} | {'场景标题':<20} | {'Payload示例':<30} | {'验证点'}")
                print("-" * 100)
                for s in strategies:
                    prio = s.get('priority', '-')
                    title = s.get('title', '-')
                    payload = str(s.get('payload', '-')).replace('\n', '')[:30] + "..."
                    val = s.get('validation', '-')
                    print(f"{prio:<6} | {title:<20} | {payload:<30} | {val}")
            
            print("=" * 80)

if __name__ == "__main__":
    main()
