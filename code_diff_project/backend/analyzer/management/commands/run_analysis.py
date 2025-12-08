import subprocess
import os
import sys
import json
import urllib.request
import json
import requests
import re
import traceback
from django.core.management.base import BaseCommand
from django.conf import settings
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich import box
from rich.syntax import Syntax
from analyzer.models import AnalysisReport, AnalysisTask
from analyzer.static_parser import LightStaticAnalyzer

# 初始化 Rich Console
console = Console()

# --- DeepSeek API 配置 ---
DEEPSEEK_API_KEY = "sk-onjbfk7nV3bpqi8hZD9stZ8AFlJ9eUu0dyP1iAEpeWdrlTAo"
DEEPSEEK_API_URL = "https://www.chataiapi.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
USE_DEEPSEEK_API = True

class Command(BaseCommand):
    help = '运行精准测试分析并保存报告'

    def add_arguments(self, parser):
        parser.add_argument('--project-root', type=str, help='项目根目录路径')
        parser.add_argument('--base-ref', type=str, help='基准版本 (e.g. master, HEAD^)', default='HEAD^')
        parser.add_argument('--target-ref', type=str, help='目标版本 (e.g. feature, HEAD)', default='HEAD')
        parser.add_argument('--task-id', type=int, help='关联的任务ID', default=None)

    def update_task_log(self, task_id, message):
        if not task_id: return
        try:
            task = AnalysisTask.objects.get(id=task_id)
            task.log_details = (task.log_details or "") + message + "\n"
            task.save()
        except:
            pass

    def handle(self, *args, **options):
        # 1. 确定项目根目录
        project_root = options.get('project_root')
        base_ref = options.get('base_ref')
        target_ref = options.get('target_ref')
        task_id = options.get('task_id')

        if not project_root:
            project_root = os.path.abspath(os.path.join(settings.BASE_DIR, '..', '..'))
        
        console.print(f"[Info] 项目根目录: {project_root}", style="dim")
        console.print(f"[Info] 比对版本: {base_ref} ... {target_ref}", style="dim")
        self.update_task_log(task_id, f"[Info] 项目根目录: {project_root}")
        self.update_task_log(task_id, f"[Info] 比对版本: {base_ref} ... {target_ref}")
        
        # 切换工作目录以便 git 命令生效
        os.chdir(project_root)

        console.rule("[bold blue]精准测试分析助手 (DeepSeek版)[/bold blue]")
        
        # 2. 获取 Diff
        try:
            diff_text = self.get_git_diff(base_ref, target_ref)
            if not diff_text:
                msg = f"[yellow]未检测到 Java/XML/SQL/Config 文件的变更 ({base_ref} vs {target_ref})。[/yellow]"
                console.print(msg)
                self.update_task_log(task_id, msg)
                return

            # 3. 解析 Diff
            files_map = self.parse_diff(diff_text)
            msg = f"[green]检测到 {len(files_map)} 个核心文件 (Java/XML/SQL/Config) 发生变更。[/green]"
            console.print(msg + "\n")
            self.update_task_log(task_id, msg)

            # 4. 逐个分析
            for filename, content in files_map.items():
                self.update_task_log(task_id, f"正在分析文件: {filename} ...")
                if USE_DEEPSEEK_API:
                    report = self.analyze_with_llm(filename, content, project_root, task_id)
                    
                    if report is None: 
                        self.update_task_log(task_id, f"文件 {filename} 分析失败，生成基础占位报告。")
                        # Create a fallback report so the file still appears in the list
                        report = {
                            "change_intent": "AI 分析失败 (API Error or Timeout)",
                            "risk_level": "UNKNOWN",
                            "cross_service_impact": "无法分析",
                            "functional_impact": "无法分析",
                            "downstream_dependency": [],
                            "test_strategy": []
                        }
                else:
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
                    grid.add_row("意图推测:", self.format_field(report.get('change_intent', 'N/A')))
                    grid.add_row("风险等级:", self.format_field(report.get('risk_level', 'N/A')))
                    grid.add_row("跨服务影响:", self.format_field(report.get('cross_service_impact', 'N/A')))
                    grid.add_row("影响功能:", self.format_field(report.get('functional_impact', 'N/A')))
                    grid.add_row("下游依赖:", self.format_field(report.get('downstream_dependency', 'N/A')))
                    
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
                            prio = self.format_field(s.get('priority', '-'))
                            title = self.format_field(s.get('title', '-'))
                            payload = self.format_field(s.get('payload', '-')).replace('\n', '')
                            if len(payload) > 40:
                                payload = payload[:37] + "..."
                            
                            val = s.get('validation', '-')
                            if isinstance(val, str):
                                val = re.sub(r'(?<!^)(\d+\.)', r'\n\1', val)
                            else:
                                val = self.format_field(val)
                            
                            table.add_row(prio, title, payload, val)
                        
                        console.print(table)
                    
                    # --- 保存至数据库 ---
                    project_name = os.path.basename(project_root)
                    self.save_to_db(filename, report, content, project_name=project_name, task_id=task_id)
                    self.update_task_log(task_id, f"文件 {filename} 分析完成并保存。")

        except Exception as e:
            error_msg = f"Unexpected error in run_analysis: {str(e)}\n{traceback.format_exc()}"
            console.print(f"[red]{error_msg}[/red]")
            self.update_task_log(task_id, error_msg)
            # Re-raise so views.py can also catch it if needed, or just let it be failed.
            if task_id:
                try:
                    task = AnalysisTask.objects.get(id=task_id)
                    task.status = 'FAILED'
                    task.save()
                except: pass
            raise e

    def save_to_db(self, filename, report, diff_content, project_name="Unknown", task_id=None):
        """
        直接保存到 Django 数据库
        """
        try:
            task_obj = None
            if task_id:
                try:
                    task_obj = AnalysisTask.objects.get(id=task_id)
                except: pass

            AnalysisReport.objects.create(
                project_name=project_name,
                task=task_obj,
                file_name=os.path.basename(filename),
                change_intent=self.format_field(report.get('change_intent', '')),
                risk_level=str(report.get('risk_level', 'UNKNOWN')),
                report_json=report,
                diff_content=diff_content
            )
            console.print(f"[bold green]✓[/bold green] [dim]已保存至数据库[/dim]")
        except Exception as e:
            console.print(f"[red]保存数据库失败: {e}[/red]")

    def get_git_diff(self, base_ref, target_ref):
        try:
            # Resolve refs to hashes for clarity
            base_hash = subprocess.check_output(["git", "rev-parse", "--short", base_ref], text=True).strip()
            target_hash = subprocess.check_output(["git", "rev-parse", "--short", target_ref], text=True).strip()
            console.print(f"[Info] 执行 Diff: {base_ref}({base_hash}) ... {target_ref}({target_hash})", style="bold cyan")
            
            # 使用三点对比 (Triple Dot Diff) A...B
            # 找出 A 和 B 的共同祖先，对比 B 和 共同祖先 的差异。
            # 这样可以忽略 A 分支（如 master）后续更新带来的干扰，只关注 B 分支（Feature）的净变更。
            diff_range = f"{base_ref}...{target_ref}"
            console.print(f"[Info] 执行 Diff (Smart Mode): {diff_range}", style="bold cyan")
            
            file_patterns = ["*.java", "*.xml", "*.sql", "*.yml", "*.yaml", "*.properties"]
            # git diff base...target -- files
            cmd_commit = ["git", "diff", diff_range, "--"] + file_patterns
            result_commit = subprocess.run(cmd_commit, capture_output=True, text=True, encoding='utf-8')
            
            if result_commit.returncode != 0:
                console.print(f"[red]Git Diff Error: {result_commit.stderr}[/red]")
                return None

            if result_commit.stdout and result_commit.stdout.strip():
                return result_commit.stdout

            console.print("[Info] 指定版本间未检测到变更。", style="dim")
            return None
        except Exception as e:
            console.print(f"Error: {e}")
            return None

    def parse_diff(self, diff_text):
        files_diff = {}
        current_file = None
        buffer = []
        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                if current_file:
                    files_diff[current_file] = "\n".join(buffer)
                parts = line.split()
                if len(parts) >= 4:
                    raw_filename = parts[-1]
                    current_file = raw_filename[2:] if raw_filename.startswith("b/") else raw_filename
                    buffer = []
            buffer.append(line)
        if current_file:
            files_diff[current_file] = "\n".join(buffer)
        return files_diff

    def analyze_with_llm(self, filename, diff_content, root_dir, task_id=None):
        self.print_code_comparison(diff_content)
        project_structure = self.get_project_structure(root_dir)
        api_info_list = self.extract_api_info(diff_content)
        downstream_callers = []
        
        if api_info_list:
            for api_info in api_info_list:
                callers = self.search_api_usages(root_dir, api_info, filename)
                if callers:
                    downstream_callers.extend(callers)
        
        unique_callers = {}
        for caller in downstream_callers:
            key = f"{caller['path']}:{caller['target_api']}"
            if key not in unique_callers:
                unique_callers[key] = caller
        downstream_callers = list(unique_callers.values())
        
        downstream_info = "未检测到明显的跨服务调用引用。"
        if downstream_callers:
            info_lines = []
            for c in downstream_callers:
                info_lines.append(f"- [调用 {c['target_api']}] 服务: {c['service']}")
                info_lines.append(f"  文件: {c['path']} (Line {c['line']})")
                info_lines.append(f"  代码: {c['snippet']}")
            downstream_info = "\n".join(info_lines)
        
        console.print(Panel(f"[bold]发现潜在下游调用方:[/bold]\n{downstream_info}", title="Link Analysis", border_style="blue", expand=False))
        self.update_task_log(task_id, f"[Link Analysis] 发现 {len(downstream_callers)} 个潜在下游调用点。")
        
        # Static Analysis Integration
        static_context = ""
        static_usages = []
        try:
            if filename.endswith(".java"):
                full_path = os.path.join(root_dir, filename)
                analyzer = LightStaticAnalyzer(root_dir)
                # Unpack the tuple: (text_context, usages_list)
                static_context, static_usages = analyzer.get_context_for_file(full_path)
                
                if static_context:
                    console.print(Panel(static_context.strip(), title="Static Analysis", border_style="green"))
                    self.update_task_log(task_id, "[Static Analysis] 静态分析上下文获取成功。")
                
                # Merge static usages into downstream_callers
                if static_usages:
                    for usage in static_usages:
                        downstream_callers.append({
                            "service": usage['service'],
                            "file": usage['file_name'],
                            "path": usage['path'],
                            "line": usage.get('line', 0),
                            "snippet": usage.get('snippet', f"Detected by Static Analysis ({usage['type']})"),
                            "target_api": "Class Dependency"
                        })
                        
        except Exception as e:
            console.print(f"[yellow]Static analysis skipped: {e}[/yellow]")
            self.update_task_log(task_id, f"[Warning] Static analysis skipped: {e}")

        # Re-deduplicate after merging static usages
        unique_callers = {}
        
        # Determine current service name from filename (assuming first folder is service name)
        current_service = filename.split('/')[0] if '/' in filename else filename.split('\\')[0]
        
        filtered_callers = []
        final_callers = []

        for caller in downstream_callers:
            key = f"{caller['path']}:{caller['target_api']}"
            if key not in unique_callers:
                caller['target_service'] = current_service
                unique_callers[key] = caller
                
                # Check if internal
                if caller['service'] == current_service:
                    caller['is_internal'] = True
                    filtered_callers.append(caller)
                else:
                    caller['is_internal'] = False
                
                # We now keep ALL callers for the AI context, just marked
                final_callers.append(caller)

        downstream_callers = final_callers
        
        if filtered_callers:
            count = len(filtered_callers)
            console.print(f"[Info] 检测到 {count} 个同服务内部调用 (Internal Calls)，将包含在分析上下文中。", style="dim")
            self.update_task_log(task_id, f"[Link Analysis] 检测到 {count} 个同服务内部调用。")
        
        downstream_info = "未检测到明显的调用引用。"
        if downstream_callers:
            info_lines = []
            for c in downstream_callers:
                type_tag = "[内部调用]" if c.get('is_internal') else "[跨服务调用]"
                info_lines.append(f"- {type_tag} 服务: {c['service']}")
                info_lines.append(f"  文件: {c['path']}")
                info_lines.append(f"  说明: {c['snippet']} (Line: {c.get('line', 'N/A')})")
            downstream_info = "\n".join(info_lines)
        
        console.print(Panel(f"[bold]发现潜在下游调用方 (Combined & Filtered):[/bold]\n{downstream_info}", title="Link Analysis", border_style="blue", expand=False))
        self.update_task_log(task_id, f"[Link Analysis] 发现 {len(downstream_callers)} 个潜在跨服务调用点。")

        console.print(f"\n[AI Analysis] 正在使用 DeepSeek ({DEEPSEEK_MODEL}) 分析 {filename} ...", style="bold magenta")
        self.update_task_log(task_id, f"[AI Analysis] 正在请求 AI 分析...")
        
        prompt = f"""
        # Role
        你是一名资深的 Java 测试架构师，精通微服务调用链路分析。
        
        # Static Analysis Hints (Hard Facts - 静态分析结果)
        {static_context}
        注意: "Class A is used by B" 意味着 B 依赖 A (B -> A)，即 B 是调用方 (Consumer)，A 是被调用方 (Provider)。
        
        # Context
        这是一个基于 Spring Cloud 的微服务项目 (Monorepo)。
        项目包含的真实服务模块列表: [{project_structure}]
        被修改的文件 (Provider): {filename}
        所属服务: {current_service}
        
        # Cross-Service Impact (关键!)
        脚本检测到该变更可能影响以下下游服务（调用方/Consumer）:
        {downstream_info}
        
        # Git Diff
        {diff_content}
        
        # Requirement
        请基于代码变更和**跨服务调用关系**，生成《微服务精准测试手册》。
        如果存在跨服务调用，请重点分析接口契约变更带来的风险。
        
        IMPORTANT:
        1. 在分析“跨服务影响” (Cross-Service Impact) 时，**必须严格基于** 上面提供的 `Cross-Service Impact` 列表。
        2. **严禁**将代码中引用的类（如 `PointClient`，这是上游依赖/被调用方）误认为是下游调用方。
           - 如果代码里用了 `PointClient`，那是本服务在调用别人，属于依赖，而不是别人受我影响（除非我改了接口定义）。
           - 只有在 `Cross-Service Impact` 列表中明确列出的服务，才是真正的受影响方。
        3. 在分析“下游依赖”或“影响功能”时，请务必基于上述提供的【项目包含的真实服务模块列表】。
        4. 禁止编造不存在的服务名称。
        5. 如果上面的 Cross-Service Impact 中没有跨服务调用（只有内部调用或无），`cross_service_impact` 字段请填 "无" 或 null。
        6. 不要直接复制下面的 JSON 模板值，请根据实际分析内容填写。
        
        請严格按照以下 JSON 格式返回：
        {{
            "code_review_warning": "<代码审查警示>",
            "change_intent": "<变更详情：请分点总结变更内容。如果是新增类，请将该类的方法作为子项列出，体现层级关系。例如：1. 新增了XX类，包含以下方法：(1) methodA: ... (2) methodB: ...>",
            "risk_level": "CRITICAL/HIGH/MEDIUM/LOW",
            "cross_service_impact": "<跨服务影响分析>",
            "functional_impact": "<详细的功能影响分析>",
            "downstream_dependency": [
                {{
                    "service_name": "<服务名>",
                    "file_path": "<文件路径>",
                    "line_number": "<行号>",
                    "caller_class": "<调用方类名>",
                    "caller_method": "<调用方方法签名>",
                    "target_method": "<被调用的目标方法/API>",
                    "call_snippet": "<调用处的代码片段>",
                    "impact_description": "<该调用点可能受到的具体影响>"
                }}
            ],
            "test_strategy": [
                {{
                    "title": "<测试场景>",
                    "priority": "P0/P1",
                    "steps": "<步骤>",
                    "payload": "<Payload示例 (必须是JSON格式)>",
                    "validation": "<验证点>"
                }}
            ]
        }}
        """
        
        messages = [
            {"role": "system", "content": "你是一个能够进行精准测试分析的AI助手。请只输出 JSON。"},
            {"role": "user", "content": prompt}
        ]
        
        response_content, usage = self.call_deepseek_api(messages)
        
        if not response_content:
            return None
        
        if usage:
            total = usage.get('total_tokens', 0)
            console.print(f"[dim]DeepSeek Token Usage: Total {total}[/dim]")
            
        try:
            cleaned_content = response_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            elif cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            return json.loads(cleaned_content.strip())
        except json.JSONDecodeError:
            console.print(f"[red]解析 AI 响应失败[/red]")
            return None

    def call_deepseek_api(self, messages):
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
            # Switch to requests library for better SSL/Error handling
            response = requests.post(DEEPSEEK_API_URL, json=data, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content'], result.get('usage', {})
            else:
                console.print(f"[red]API Error Status: {response.status_code} - {response.text}[/red]")
            
            return None, None
        except Exception as e:
            console.print(f"[red]API Connection Error: {e}[/red]")
            return None, None

    def print_code_comparison(self, diff_text):
        lines = diff_text.splitlines()
        clean_lines = [line for line in lines if not (line.startswith("diff --git") or line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ ") or line.startswith("new file mode") or line.startswith("deleted file mode"))]
        syntax = Syntax("\n".join(clean_lines), "diff", theme="monokai", line_numbers=True, word_wrap=True)
        console.print(Panel("Code Diff: 变更代码对比", style="bold cyan", expand=False))
        console.print(syntax)
        console.print("-" * 80, style="dim")

    def extract_api_info(self, diff_text):
        api_info_list = []
        lines = diff_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("+") or line.startswith(" "):
                path_match = re.search(r'@(?:Request|Post|Get|Put|Delete)Mapping\s*\(.*?(?:value\s*=\s*)?"([^"]+)".*?\)', line)
                if path_match:
                    api_path = path_match.group(1)
                    method_name = None
                    for j in range(1, 5):
                        if i + j < len(lines):
                            next_line = lines[i+j]
                            if "@" in next_line: continue
                            method_match = re.search(r'\s+([a-zA-Z0-9_]+)\s*\(', next_line)
                            if method_match:
                                method_name = method_match.group(1)
                                if method_name[0].islower(): break
                    if api_path:
                        api_info_list.append({'path': api_path, 'method': method_name})
        return api_info_list

    def search_api_usages(self, root_dir, api_info, exclude_file):
        usages = []
        api_path = api_info.get('path')
        method_name = api_info.get('method')
        
        search_term = f"API '{api_path}'"
        if method_name: search_term += f" 或方法 '{method_name}'"
        console.print(f"[bold blue][Link Analysis][/bold blue] 正在搜索全项目对 {search_term} 的调用...")
        
        for root, dirs, files in os.walk(root_dir):
            if ".git" in dirs: dirs.remove(".git")
            if "target" in dirs: dirs.remove("target")
            if "code_diff_project" in dirs: dirs.remove("code_diff_project") # 排除自己
            
            for file in files:
                if file.endswith(".java"):
                    full_path = os.path.join(root, file)
                    if os.path.abspath(full_path) == os.path.abspath(exclude_file): continue
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            found = False
                            if api_path and api_path in content: found = True
                            if not found and method_name and method_name in content:
                                if re.search(r'\b' + re.escape(method_name) + r'\b', content): found = True
                            
                            best_snippet = None
                            best_line = 0
                            
                            for idx, line_content in enumerate(content.splitlines()):
                                if (api_path and api_path in line_content) or (method_name and method_name in line_content and re.search(r'\b' + re.escape(method_name) + r'\b', line_content)):
                                    
                                    # Skip imports
                                    if line_content.strip().startswith("import "): continue
                                    
                                    # Candidate
                                    current_snippet = line_content.strip()
                                    current_line = idx + 1
                                    
                                    # Heuristic: Prefer method calls (has '(') over declarations (has 'private/public' but no '(' or just ';')
                                    # If we haven't found anything yet, take it.
                                    if best_snippet is None:
                                        best_snippet = current_snippet
                                        best_line = current_line
                                    
                                    # If current is a method call, it's better than a declaration
                                    is_call = '(' in current_snippet and not current_snippet.startswith(('private ', 'public ', 'protected '))
                                    is_decl = current_snippet.startswith(('private ', 'public ', 'protected ')) or ('(' not in current_snippet)
                                    
                                    if is_call:
                                        best_snippet = current_snippet
                                        best_line = current_line
                                        # If we found a call, we can stop or keep looking for more calls? 
                                        # Let's keep looking in case there are multiple, but usually one is enough to show usage.
                                        # Actually, for this specific request, the user wants the CALL.
                                        found = True
                                        
                            if best_snippet:
                                usages.append({
                                    "service": service_name,
                                    "file": os.path.basename(file),
                                    "path": rel_path,
                                    "line": best_line,
                                    "snippet": best_snippet[:100],
                                    "target_api": api_path or method_name
                                })
                    except: pass
        return usages

    def get_project_structure(self, root_dir):
        services = []
        try:
            for item in os.listdir(root_dir):
                if os.path.isdir(os.path.join(root_dir, item)) and not item.startswith('.') and item != "code_diff_project":
                    services.append(item)
        except: pass
        return ", ".join(services)

    def format_field(self, value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)
