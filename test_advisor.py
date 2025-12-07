import subprocess
import os
import sys
import json
import urllib.request
import urllib.error
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich import box
from rich.syntax import Syntax

# 初始化 Rich Console
console = Console()

# --- DeepSeek API 配置 ---
DEEPSEEK_API_KEY = "sk-onjbfk7nV3bpqi8hZD9stZ8AFlJ9eUu0dyP1iAEpeWdrlTAo"
# 注意: 这里的 URL 必须是完整的 API 终端地址
DEEPSEEK_API_URL = "https://www.chataiapi.com/v1/chat/completions"
# DeepSeek-V3 (指向 deepseek-chat) 是目前最强、最适合 RAG 的模型
DEEPSEEK_MODEL = "deepseek-chat" 
USE_DEEPSEEK_API = True

def get_git_diff():
    """·
    获取 Git Diff 信息
    策略:
    1. 检查最近一次提交 (Last Commit) 的变更 (git diff HEAD^ HEAD)
    2. 如果最近一次提交没有 Java 变更，则向前追溯最近一次修改 Java 的提交
    """
    try:
        # 1. 检查最近一次提交
        console.print("[Info] 检查最近一次提交 (Last Commit)...", style="dim")
        
        # 先检查 HEAD^ HEAD 是否有 Java 变更
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

        # 3. 如果最近一次提交也没改 Java (可能只改了脚本/文档)，则向前追溯最近一次修改 Java 的提交
        console.print("[Info] 最近一次提交未修改 Java 文件，正在追溯最近的 Java 变更记录...", style="dim")
        
        # 获取最近一次修改 *.java 的 commit hash
        cmd_find_java_commit = ["git", "log", "-1", "--format=%H", "--", "*.java"]
        result_find = subprocess.run(
            cmd_find_java_commit,
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            check=True
        )
        
        last_java_commit_hash = result_find.stdout.strip()
        
        if last_java_commit_hash:
            console.print(f"[Info] 定位到最近一次 Java 变更提交: [bold cyan]{last_java_commit_hash[:7]}[/bold cyan]", style="dim")
            # 获取该 commit 的 diff (与它的父节点对比)
            cmd_java_diff = ["git", "diff", f"{last_java_commit_hash}^", last_java_commit_hash, "--", "*.java"]
            result_java_diff = subprocess.run(
                cmd_java_diff,
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                check=True
            )
            if result_java_diff.stdout and result_java_diff.stdout.strip():
                return result_java_diff.stdout

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
                raw_filename = parts[-1]
                # 安全移除 b/ 前缀
                if raw_filename.startswith("b/"):
                    current_file = raw_filename[2:]
                else:
                    current_file = raw_filename
                
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
                content = result['choices'][0]['message']['content']
                usage = result.get('usage', {})
                return content, usage
            else:
                print("API 返回结果异常:", result)
                return None, None
            
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} - {e.read().decode('utf-8')}")
        return None, None
    except Exception as e:
        print(f"Request Error: {e}")
        return None, None

def print_code_comparison(diff_text):
    """
    打印直观的代码对比
    """
    console.print(Panel("Code Diff: 变更代码对比", style="bold cyan", expand=False))
    
    # 过滤 Git 元数据头，只保留差异内容
    lines = diff_text.splitlines()
    clean_lines = []
    for line in lines:
        # 忽略 Git 元数据行
        if line.startswith("diff --git") or \
           line.startswith("index ") or \
           line.startswith("--- ") or \
           line.startswith("+++ ") or \
           line.startswith("new file mode") or \
           line.startswith("deleted file mode"):
            continue
        clean_lines.append(line)
    
    clean_diff = "\n".join(clean_lines)
    
    # 使用 Rich 的 Syntax 组件来高亮显示 Diff
    # theme="monokai" 提供类似 IDE 的暗色主题体验
    # background_color="default" 保持与终端背景一致
    syntax = Syntax(clean_diff, "diff", theme="monokai", line_numbers=True, word_wrap=True)
    console.print(syntax)
    
    console.print("-" * 80, style="dim")

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
    console.print(f"[bold blue][Link Analysis][/bold blue] 正在搜索全项目对接口 '[yellow]{api_path}[/yellow]' 的调用...")
    
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
    
    panel_content = f"[bold]发现潜在下游调用方:[/bold]\n{downstream_info}"
    console.print(Panel(panel_content, title="Link Analysis", border_style="blue", expand=False))
    # ---------------------------

    console.print(f"\n[AI Analysis] 正在使用 DeepSeek ({DEEPSEEK_MODEL}) 分析 {filename} ...", style="bold magenta")
    
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
    
    請严格按照以下 JSON 格式返回：
    {{
        "code_review_warning": "代码审查警示",
        "change_intent": "变更意图",
        "risk_level": "CRITICAL/HIGH/MEDIUM/LOW",
        "cross_service_impact": "跨服务影响分析",
        "functional_impact": "详细的功能影响分析。请务必包含：1. 直接受影响的功能点；2. 潜在受影响的关联业务；3. 建议的回归测试范围。",
        "downstream_dependency": "受影响的下游服务/组件列表",
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
    
    response_content, usage = call_deepseek_api(messages)
    
    if not response_content:
        return None
    
    if usage:
        total = usage.get('total_tokens', 0)
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        console.print(f"[dim]DeepSeek Token Usage: Total {total} (Prompt {prompt_tokens} + Completion {completion_tokens})[/dim]")
        
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

def save_markdown_report(filename, report):
    """
    将分析结果保存为 Markdown 文件
    """
    safe_name = os.path.basename(filename).replace('.java', '')
    report_file = f"TEST_REPORT_{safe_name}.md"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# 精准测试分析报告: {os.path.basename(filename)}\n\n")
            
            warning = report.get('code_review_warning')
            if warning:
                f.write(f"> ⚠️ **CODE REVIEW 警示**: {warning}\n\n")
            
            f.write("## 1. 变更分析\n")
            f.write(f"- **意图推测**: {format_field(report.get('change_intent', 'N/A'))}\n")
            f.write(f"- **风险等级**: **{format_field(report.get('risk_level', 'N/A'))}**\n")
            f.write(f"- **跨服务影响**: {format_field(report.get('cross_service_impact', 'N/A'))}\n")
            f.write(f"- **影响功能**: {format_field(report.get('functional_impact', 'N/A'))}\n")
            f.write(f"- **下游依赖**: {format_field(report.get('downstream_dependency', 'N/A'))}\n\n")
            
            f.write("## 2. 测试策略矩阵\n")
            f.write("| 优先级 | 场景标题 | Payload示例 | 验证点 |\n")
            f.write("|---|---|---|---|\n")
            
            for s in report.get('test_strategy', []):
                prio = s.get('priority', '-')
                title = s.get('title', '-')
                payload = str(s.get('payload', '-')).replace('\n', ' ')
                val = s.get('validation', '-')
                f.write(f"| {prio} | {title} | `{payload}` | {val} |\n")
                
        console.print(f"[dim]已保存测试报告至文件: [link=file://{os.getcwd()}/{report_file}]{report_file}[/link][/dim]")
        
    except Exception as e:
        console.print(f"[red]保存 Markdown 报告失败: {e}[/red]")

def format_field(value):
    """
    格式化字段值，如果是字典或列表，转换为字符串
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)

def main():
    console.rule("[bold blue]精准测试分析助手 (DeepSeek版)[/bold blue]")
    
    # 1. 获取 Diff
    diff_text = get_git_diff()
    if not diff_text:
        console.print("[yellow]未检测到 Java 文件的变更 (Git Diff 为空)。[/yellow]")
        console.print("提示：请确保你已经 commit 了你的代码变更。")
        return

    # 2. 解析 Diff
    files_map = parse_diff(diff_text)
    console.print(f"[green]检测到 {len(files_map)} 个 Java 文件发生变更。[/green]\n")

    # 3. 逐个分析
    for filename, content in files_map.items():
        if USE_DEEPSEEK_API:
            report = analyze_with_llm(filename, content)
        else:
            # Fallback (如果不使用 API)
            console.print("API 开关未打开")
            continue
            
        if report:
            console.print("\n")
            console.rule(f"【精准测试作战手册】: {filename}")
            
            warning = report.get('code_review_warning')
            if warning:
                console.print(Panel(f"[bold red]CODE REVIEW 警示:[/bold red] {warning}", border_style="red"))
            
            # Change Analysis
            grid = Table.grid(expand=True)
            grid.add_column(style="bold yellow", justify="right")
            grid.add_column(justify="left")
            grid.add_row("意图推测:", format_field(report.get('change_intent', 'N/A')))
            grid.add_row("风险等级:", format_field(report.get('risk_level', 'N/A')))
            grid.add_row("跨服务影响:", format_field(report.get('cross_service_impact', 'N/A')))
            grid.add_row("影响功能:", format_field(report.get('functional_impact', 'N/A')))
            grid.add_row("下游依赖:", format_field(report.get('downstream_dependency', 'N/A')))
            
            console.print(Panel(grid, title="[Change Analysis] 变更分析", border_style="green"))

            # Test Strategy Table
            strategies = report.get('test_strategy', [])
            if strategies:
                table = Table(title="[Test Strategy] 测试策略矩阵", show_header=True, header_style="bold magenta", box=box.ROUNDED, expand=True)
                table.add_column("优先级", style="cyan", width=8)
                table.add_column("场景标题", style="bold")
                table.add_column("Payload示例", style="dim")
                table.add_column("验证点", style="green")

                for s in strategies:
                    prio = s.get('priority', '-')
                    title = s.get('title', '-')
                    payload = str(s.get('payload', '-')).replace('\n', '')
                    # Truncate payload if too long for display
                    if len(payload) > 40:
                        payload = payload[:37] + "..."
                    
                    val = s.get('validation', '-')
                    # 格式化验证点：将 "1. xxx 2. xxx" 格式化为多行显示
                    if isinstance(val, str):
                         # 使用正则在数字列表项前添加换行 (排除开头的数字)
                        val = re.sub(r'(?<!^)(\d+\.)', r'\n\1', val)
                    
                    table.add_row(prio, title, payload, val)
                
                console.print(table)
            
            # --- 保存 Markdown 报告 ---
            save_markdown_report(filename, report)

            console.print("=" * 80)

if __name__ == "__main__":
    main()
