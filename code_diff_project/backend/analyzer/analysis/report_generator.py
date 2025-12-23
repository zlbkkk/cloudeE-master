import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from analyzer.models import AnalysisReport, AnalysisTask

console = Console()


def format_field(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def save_to_db(filename, report, diff_content, project_name="Unknown", task_id=None):
    """
    直接保存到 Django 数据库
    """
    try:
        task_obj = None
        if task_id:
            try:
                task_obj = AnalysisTask.objects.get(id=task_id)
            except: pass

        # 风险等级中文化
        risk_map = {
            "CRITICAL": "严重",
            "HIGH": "高",
            "MEDIUM": "中",
            "LOW": "低"
        }
        raw_risk = str(report.get('risk_level', 'UNKNOWN')).upper()
        chinese_risk = risk_map.get(raw_risk, raw_risk)

        # Extract usage info if present
        usage = report.pop('_usage', {})
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)

        AnalysisReport.objects.create(
            project_name=project_name,
            task=task_obj,
            file_name=os.path.basename(filename),
            change_intent=format_field(report.get('change_intent', '')),
            risk_level=chinese_risk,
            report_json=report,
            diff_content=diff_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
        console.print(f"[bold green]✓[/bold green] [dim]已保存至数据库 (Tokens: {total_tokens})[/dim]")
    except Exception as e:
        console.print(f"[red]保存数据库失败: {e}[/red]")


def refine_report_with_static_analysis(report, root_dir):
    """
    Post-process the AI report to verify and correct line numbers using local static analysis.
    
    改进逻辑：
    1. 总是尝试通过 call_snippet 或 target_method 搜索真实行号
    2. 如果搜索到的行号存在：
       - 如果和 AI 返回的不一致，使用搜索到的（修正错误）
       - 如果一致，保留 AI 返回的（验证通过）
    3. 如果搜索不到，保留 AI 返回的行号
    """
    if not report or 'downstream_dependency' not in report:
        return report

    dependencies = report.get('downstream_dependency', [])
    if not dependencies:
        return report

    console.print("[Info] Verifying and refining line numbers with local code search...", style="dim")
    
    for dep in dependencies:
        file_path = dep.get('file_path')
        target_method = dep.get('target_method')
        call_snippet = dep.get('call_snippet')
        ai_line_num = dep.get('line_number')  # AI 返回的行号
        
        if not file_path:
            continue

        # Try to locate the file
        local_path = None
        if os.path.exists(file_path):
            local_path = file_path
        else:
            # 1. Try relative path from root_dir
            candidate = os.path.join(root_dir, file_path)
            if os.path.exists(candidate):
                local_path = candidate
            else:
                # 2. Search by filename
                filename = os.path.basename(file_path)
                for root, dirs, files in os.walk(root_dir):
                    if filename in files:
                        local_path = os.path.join(root, filename)
                        break
        
        if local_path:
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                found_line = None
                
                # Strategy 1: Search for snippet
                if call_snippet and call_snippet not in ['无', 'N/A', '']:
                    clean_snippet = call_snippet.strip().replace(';', '')
                    for i, line in enumerate(lines):
                        if clean_snippet in line:
                            found_line = i + 1
                            break
                
                # Strategy 2: Search for target method call
                if not found_line and target_method:
                    # Extract simple method name: com.example.Class.method(args) -> method
                    simple_method = target_method.split('(')[0].split('.')[-1]
                    for i, line in enumerate(lines):
                        if simple_method in line and '(' in line:
                            found_line = i + 1
                            break
                
                # 决定使用哪个行号
                if found_line:
                    # 检查 AI 返回的行号是否有效
                    ai_line_valid = ai_line_num and str(ai_line_num).strip() not in ['无', 'N/A', '0', '-', '']
                    
                    if ai_line_valid:
                        try:
                            ai_line_int = int(ai_line_num)
                            if ai_line_int != found_line:
                                # AI 返回的行号和搜索到的不一致，使用搜索到的
                                dep['line_number'] = found_line
                                console.print(
                                    f"[Corrected] {os.path.basename(local_path)}: AI={ai_line_int} -> Actual={found_line}", 
                                    style="yellow"
                                )
                            else:
                                # 行号一致，验证通过
                                console.print(
                                    f"[Verified] {os.path.basename(local_path)}: Line {found_line} ✓", 
                                    style="green"
                                )
                        except (ValueError, TypeError):
                            # AI 返回的不是有效数字，使用搜索到的
                            dep['line_number'] = found_line
                            console.print(
                                f"[Fixed] {os.path.basename(local_path)}: Invalid AI line -> {found_line}", 
                                style="yellow"
                            )
                    else:
                        # AI 没有返回有效行号，使用搜索到的
                        dep['line_number'] = found_line
                        console.print(
                            f"[Added] {os.path.basename(local_path)}: Line {found_line}", 
                            style="green"
                        )
                    
                    # 如果 call_snippet 为空，补充代码片段
                    if not call_snippet or call_snippet in ['无', 'N/A', '']:
                        dep['call_snippet'] = lines[found_line-1].strip()
                else:
                    # 搜索不到，保留 AI 返回的行号
                    if ai_line_num and str(ai_line_num).strip() not in ['无', 'N/A', '0', '-', '']:
                        console.print(
                            f"[Kept] {os.path.basename(local_path)}: Using AI line {ai_line_num} (search failed)", 
                            style="dim"
                        )

            except Exception as e:
                console.print(f"[Warning] Failed to verify {file_path}: {e}", style="yellow")

    return report


def print_code_comparison(diff_text, base_ref=None, target_ref=None):
    lines = diff_text.splitlines()
    clean_lines = [line for line in lines if not (line.startswith("diff --git") or line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ ") or line.startswith("new file mode") or line.startswith("deleted file mode"))]
    syntax = Syntax("\n".join(clean_lines), "diff", theme="monokai", line_numbers=True, word_wrap=True)
    
    title = "Code Diff: 变更代码对比"
    if base_ref and target_ref:
        title += f" ({base_ref} -> {target_ref})"
    
    console.print(Panel(title, style="bold cyan", expand=False))
    console.print(syntax)
    console.print("-" * 80, style="dim")
