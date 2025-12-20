import subprocess
import os
import sys
import json
import urllib.request
import json
import requests
import re
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from analyzer.api_tracer import ApiUsageTracer
from analyzer.multi_project_tracer import MultiProjectTracer
from analyzer.mybatis_analyzer import MybatisAnalyzer
from loguru import logger # Add loguru import

# 初始化 Rich Console
console = Console() 

# --- DeepSeek API 配置 ---
DEEPSEEK_API_KEY = "sk-zsoEsAP0th0QH55v22p9JMaedIsbWVe6FjYZ2Rnywua6hcfI"
DEEPSEEK_API_URL = "https://api.chataiapi.com/v1/chat/completions"
DEEPSEEK_MODEL = "gemini-2.5-flash"
# DEEPSEEK_MODEL = "gemini-2.0-flash"
# DEEPSEEK_MODEL = "deepseek-chat"
USE_DEEPSEEK_API = True

class Command(BaseCommand):
    help = '运行精准测试分析并保存报告'

    def add_arguments(self, parser):
        parser.add_argument('--project-root', type=str, help='项目根目录路径')
        parser.add_argument('--base-ref', type=str, help='基准版本 (e.g. master, HEAD^)', default='HEAD^')
        parser.add_argument('--target-ref', type=str, help='目标版本 (e.g. feature, HEAD)', default='HEAD')
        parser.add_argument('--task-id', type=int, help='关联的任务ID', default=None)
        parser.add_argument('--enable-cross-project', action='store_true', help='启用跨项目分析')
        parser.add_argument('--related-projects', type=str, default='[]', help='关联项目配置的 JSON 数组')

    def update_task_log(self, task_id, message):
        if not task_id: return
        try:
            task = AnalysisTask.objects.get(id=task_id)
            task.log_details = (task.log_details or "") + message + "\n"
            task.save()
        except:
            pass
    
    def clone_or_update_project(self, proj_config, workspace_dir, idx, total):
        """
        克隆或更新单个项目的辅助函数，用于并行执行
        
        参数:
            proj_config: 项目配置字典
            workspace_dir: workspace 目录路径
            idx: 项目索引（用于日志）
            total: 总项目数（用于日志）
        
        返回:
            dict: {'success': bool, 'name': str, 'path': str, 'error': str}
        """
        proj_name = proj_config.get('related_project_name', f'project_{idx}')
        proj_git_url = proj_config.get('related_project_git_url', '')
        proj_branch = proj_config.get('related_project_branch', 'master')
        
        result = {
            'success': False,
            'name': proj_name,
            'path': None,
            'error': None
        }
        
        if not proj_git_url:
            result['error'] = 'Missing Git URL'
            return result
        
        project_local_path = os.path.join(workspace_dir, proj_name)
        
        try:
            if not os.path.exists(project_local_path):
                # 项目不存在，执行克隆
                logger.info(f"[{idx}/{total}] 克隆项目: {proj_name} from {proj_git_url}")
                
                clone_cmd = ['git', 'clone', proj_git_url, project_local_path]
                clone_result = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if clone_result.returncode != 0:
                    result['error'] = f"Clone failed: {clone_result.stderr}"
                    return result
                
                logger.info(f"[{idx}/{total}] 克隆成功: {proj_name}")
            else:
                # 项目已存在，执行更新
                logger.info(f"[{idx}/{total}] 更新项目: {proj_name}")
                
                # 先强制清理本地更改，避免冲突
                logger.info(f"[{idx}/{total}] 清理本地更改: {proj_name}")
                
                # 重置所有本地更改
                reset_local_cmd = ['git', '-C', project_local_path, 'reset', '--hard']
                subprocess.run(reset_local_cmd, capture_output=True, text=True)
                
                # 清理未跟踪的文件
                clean_cmd = ['git', '-C', project_local_path, 'clean', '-fd']
                subprocess.run(clean_cmd, capture_output=True, text=True)
                
                # 执行 git fetch
                fetch_cmd = ['git', '-C', project_local_path, 'fetch', '--all', '--prune']
                fetch_result = subprocess.run(
                    fetch_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2分钟超时
                )
                
                if fetch_result.returncode != 0:
                    logger.warning(f"[{idx}/{total}] Fetch 失败: {proj_name} - {fetch_result.stderr}")
                else:
                    logger.info(f"[{idx}/{total}] Fetch 成功: {proj_name}")
            
            # 检查分支是否存在
            check_branch_cmd = ['git', '-C', project_local_path, 'rev-parse', '--verify', f'origin/{proj_branch}']
            check_result = subprocess.run(
                check_branch_cmd,
                capture_output=True,
                text=True
            )
            
            if check_result.returncode != 0:
                logger.warning(f"[{idx}/{total}] 分支 {proj_branch} 不存在，尝试默认分支")
                # 尝试使用 master 或 main
                for default_branch in ['master', 'main']:
                    check_cmd = ['git', '-C', project_local_path, 'rev-parse', '--verify', f'origin/{default_branch}']
                    check_result = subprocess.run(check_cmd, capture_output=True, text=True)
                    if check_result.returncode == 0:
                        proj_branch = default_branch
                        logger.info(f"[{idx}/{total}] 使用默认分支: {default_branch}")
                        break
            
            # 切换分支
            checkout_cmd = ['git', '-C', project_local_path, 'checkout', proj_branch]
            checkout_result = subprocess.run(
                checkout_cmd,
                capture_output=True,
                text=True
            )
            
            if checkout_result.returncode != 0:
                logger.warning(f"[{idx}/{total}] 切换分支失败: {proj_name} - {checkout_result.stderr}")
            else:
                logger.info(f"[{idx}/{total}] 切换到分支: {proj_branch}")
            
            # Reset 到最新提交
            reset_cmd = ['git', '-C', project_local_path, 'reset', '--hard', f'origin/{proj_branch}']
            reset_result = subprocess.run(
                reset_cmd,
                capture_output=True,
                text=True
            )
            
            if reset_result.returncode != 0:
                logger.warning(f"[{idx}/{total}] Reset 失败: {proj_name} - {reset_result.stderr}")
            else:
                logger.info(f"[{idx}/{total}] Reset 到最新提交")
            
            # 成功
            result['success'] = True
            result['path'] = project_local_path
            logger.info(f"[{idx}/{total}] 项目准备完成: {proj_name}")
            
        except subprocess.TimeoutExpired:
            result['error'] = 'Operation timeout'
            logger.error(f"[{idx}/{total}] 操作超时: {proj_name}")
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"[{idx}/{total}] 处理失败: {proj_name} - {str(e)}")
        
        return result

    def handle(self, *args, **options):
        # 1. 确定项目根目录
        project_root = options.get('project_root')
        base_ref = options.get('base_ref')
        target_ref = options.get('target_ref')
        task_id = options.get('task_id')

        if not project_root:
            project_root = os.path.abspath(os.path.join(settings.BASE_DIR, '..', '..'))
        
        # 2. 解析跨项目分析参数
        enable_cross_project = options.get('enable_cross_project', False)
        related_projects_json = options.get('related_projects', '[]')
        
        # 解析关联项目配置
        related_projects = []
        try:
            related_projects = json.loads(related_projects_json)
            if not isinstance(related_projects, list):
                logger.warning(f"related_projects should be a list, got {type(related_projects)}")
                related_projects = []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse related_projects JSON: {e}")
            self.update_task_log(task_id, f"[Error] 解析关联项目配置失败: {e}")
            related_projects = []
        
        # 输出配置信息
        console.print(f"[Info] 项目根目录: {project_root}", style="dim")
        console.print(f"[Info] 比对版本: {base_ref} ... {target_ref}", style="dim")
        console.print(f"[Info] 跨项目分析: {'启用' if enable_cross_project else '禁用'}", style="dim")
        
        if enable_cross_project and related_projects:
            console.print(f"[Info] 关联项目数量: {len(related_projects)}", style="dim")
            for idx, proj in enumerate(related_projects, 1):
                proj_name = proj.get('related_project_name', 'Unknown')
                proj_branch = proj.get('related_project_branch', 'master')
                console.print(f"[Info]   {idx}. {proj_name} (分支: {proj_branch})", style="dim")
        
        # 记录到任务日志
        self.update_task_log(task_id, f"[Info] 项目根目录: {project_root}")
        self.update_task_log(task_id, f"[Info] 比对版本: {base_ref} ... {target_ref}")
        self.update_task_log(task_id, f"[Info] 跨项目分析: {'启用' if enable_cross_project else '禁用'}")
        
        if enable_cross_project:
            if related_projects:
                self.update_task_log(task_id, f"[Info] 关联项目数量: {len(related_projects)}")
                for idx, proj in enumerate(related_projects, 1):
                    proj_name = proj.get('related_project_name', 'Unknown')
                    proj_git_url = proj.get('related_project_git_url', 'Unknown')
                    proj_branch = proj.get('related_project_branch', 'master')
                    self.update_task_log(task_id, f"[Info]   {idx}. {proj_name}")
                    self.update_task_log(task_id, f"[Info]      Git URL: {proj_git_url}")
                    self.update_task_log(task_id, f"[Info]      分支: {proj_branch}")
            else:
                self.update_task_log(task_id, f"[Warning] 跨项目分析已启用，但未配置关联项目")
                logger.warning("Cross-project analysis enabled but no related projects configured")
        
        # 3. 克隆/更新关联项目（如果启用跨项目分析）
        scan_roots = [project_root]  # 默认只包含主项目
        
        if enable_cross_project and related_projects:
            console.print("\n[bold blue]开始克隆/更新关联项目...[/bold blue]")
            self.update_task_log(task_id, "\n[Info] 开始克隆/更新关联项目...")
            
            # 创建 workspace 目录
            workspace_dir = os.path.join(os.path.dirname(project_root), 'workspace')
            if not os.path.exists(workspace_dir):
                os.makedirs(workspace_dir)
                console.print(f"[Info] 创建 workspace 目录: {workspace_dir}", style="dim")
                self.update_task_log(task_id, f"[Info] 创建 workspace 目录: {workspace_dir}")
            
            # 克隆/更新关联项目（并行执行）
            successful_projects = []
            failed_projects = []
            
            # 使用 ThreadPoolExecutor 并行执行克隆/更新操作
            # 限制并发数为 4，避免资源耗尽
            max_workers = min(4, len(related_projects))
            
            console.print(f"[Info] 使用 {max_workers} 个并发线程处理 {len(related_projects)} 个项目", style="dim")
            self.update_task_log(task_id, f"[Info] 使用 {max_workers} 个并发线程处理 {len(related_projects)} 个项目")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_proj = {}
                for idx, proj in enumerate(related_projects, 1):
                    future = executor.submit(
                        self.clone_or_update_project,
                        proj,
                        workspace_dir,
                        idx,
                        len(related_projects)
                    )
                    future_to_proj[future] = proj
                
                # 收集结果
                for future in as_completed(future_to_proj):
                    proj = future_to_proj[future]
                    try:
                        result = future.result()
                        
                        if result['success']:
                            successful_projects.append(result['path'])
                            scan_roots.append(result['path'])
                            console.print(f"[Success] 项目 {result['name']} 准备完成", style="bold green")
                            self.update_task_log(task_id, f"[Success] 项目 {result['name']} 准备完成")
                        else:
                            failed_projects.append({
                                'name': result['name'],
                                'error': result['error']
                            })
                            console.print(f"[Error] 项目 {result['name']} 处理失败: {result['error']}", style="red")
                            self.update_task_log(task_id, f"[Error] 项目 {result['name']} 处理失败: {result['error']}")
                    
                    except Exception as e:
                        proj_name = proj.get('related_project_name', 'Unknown')
                        error_msg = f"Future execution failed: {str(e)}"
                        failed_projects.append({
                            'name': proj_name,
                            'error': error_msg
                        })
                        console.print(f"[Error] 项目 {proj_name} 执行异常: {error_msg}", style="red")
                        self.update_task_log(task_id, f"[Error] 项目 {proj_name} 执行异常: {error_msg}")
            
            # 输出汇总信息
            console.print(f"\n[bold]关联项目处理完成:[/bold]", style="cyan")
            console.print(f"  成功: {len(successful_projects)}", style="green")
            console.print(f"  失败: {len(failed_projects)}", style="red" if failed_projects else "dim")
            
            self.update_task_log(task_id, f"\n[Info] 关联项目处理完成:")
            self.update_task_log(task_id, f"[Info]   成功: {len(successful_projects)}")
            self.update_task_log(task_id, f"[Info]   失败: {len(failed_projects)}")
            
            if failed_projects:
                console.print("\n[bold red]失败的项目:[/bold red]")
                self.update_task_log(task_id, "\n[Warning] 失败的项目:")
                for failed in failed_projects:
                    msg = f"  - {failed['name']}: {failed['error']}"
                    console.print(msg, style="red")
                    self.update_task_log(task_id, f"[Warning] {msg}")
            
            if successful_projects:
                console.print("\n[bold green]成功的项目将被包含在分析中[/bold green]")
                self.update_task_log(task_id, "\n[Info] 成功的项目将被包含在分析中")
        
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

            # 4. 初始化追踪器（单项目或多项目模式）
            tracer = None
            try:
                if len(scan_roots) > 1:
                    # 多项目模式：使用 MultiProjectTracer
                    console.print(f"[Info] 初始化多项目追踪器，扫描 {len(scan_roots)} 个项目...", style="dim")
                    self.update_task_log(task_id, f"[Info] 初始化多项目追踪器，扫描 {len(scan_roots)} 个项目")
                    
                    for idx, root in enumerate(scan_roots, 1):
                        proj_name = os.path.basename(root)
                        console.print(f"[Info]   {idx}. {proj_name}: {root}", style="dim")
                        self.update_task_log(task_id, f"[Info]   {idx}. {proj_name}: {root}")
                    
                    tracer = MultiProjectTracer(scan_roots)
                    console.print(f"[Success] 多项目追踪器初始化完成", style="green")
                    self.update_task_log(task_id, f"[Success] 多项目追踪器初始化完成")
                else:
                    # 单项目模式：使用 ApiUsageTracer
                    console.print("[Info] 初始化单项目索引 (Project Index)...", style="dim")
                    self.update_task_log(task_id, "[Info] 初始化单项目索引")
                    tracer = ApiUsageTracer(project_root)
                    console.print(f"[Success] 单项目索引初始化完成", style="green")
                    self.update_task_log(task_id, f"[Success] 单项目索引初始化完成")
            
            except Exception as e:
                error_msg = f"[Warning] 追踪器初始化失败: {e}"
                console.print(error_msg, style="yellow")
                self.update_task_log(task_id, error_msg)
                logger.error(f"Tracer initialization failed: {e}\n{traceback.format_exc()}")

            # 5. 逐个分析变更文件

            for filename, content in files_map.items():
                self.update_task_log(task_id, f"正在分析文件: {filename} ...")
                if USE_DEEPSEEK_API:
                    report = self.analyze_with_llm(filename, content, project_root, task_id, base_ref, target_ref, tracer=tracer, scan_roots=scan_roots)
                    
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
                    
                    # --- Generate Log for Task Details ---
                    log_msg = f"\n╭──────────────── 【精准测试作战手册】 ────────────────╮\n"
                    log_msg += f"│ 文件: {filename}\n"
                    log_msg += f"╰──────────────────────────────────────────────────────╯\n"
                    
                    if warning:
                        log_msg += f"\n[CODE REVIEW 警示]\n{warning}\n"
                    
                    log_msg += "\n[Change Analysis] 变更分析\n"
                    log_msg += f"• 意图推测:\n  {self.format_field(report.get('change_intent', 'N/A')).replace(chr(10), chr(10)+'  ')}\n"
                    log_msg += f"• 风险等级: {self.format_field(report.get('risk_level', 'N/A'))}\n"
                    log_msg += f"• 跨服务影响:\n  {self.format_field(report.get('cross_service_impact', 'N/A')).replace(chr(10), chr(10)+'  ')}\n"
                    log_msg += f"• 影响功能:\n  {self.format_field(report.get('functional_impact', 'N/A')).replace(chr(10), chr(10)+'  ')}\n"
                    
                    deps = report.get('downstream_dependency', [])
                    if deps:
                         log_msg += f"\n[Downstream Dependencies] 下游依赖\n"
                         if isinstance(deps, list):
                             for d in deps:
                                 if isinstance(d, dict):
                                     log_msg += f"  - 服务: {d.get('service_name', 'N/A')}\n"
                                     log_msg += f"    文件: {d.get('file_path', 'N/A')}\n"
                                     log_msg += f"    说明: {d.get('impact_description', 'N/A')}\n"
                                     log_msg += f"    --------------------------------------------------\n"
                                 else:
                                     log_msg += f"  - {d}\n"
                         else:
                             log_msg += f"  {deps}\n"

                    if strategies:
                        log_msg += "\n[Test Strategy] 测试策略矩阵\n"
                        log_msg += f"╭{'─'*8}┬{'─'*30}┬{'─'*35}╮\n"
                        log_msg += f"│{'优先级':<6}│{'场景标题':<28}│{'验证点':<33}│\n"
                        log_msg += f"├{'─'*8}┼{'─'*30}┼{'─'*35}┤\n"
                        
                        for s in strategies:
                            prio = str(s.get('priority', '-'))
                            title = str(s.get('title', '-')).replace('\n', ' ')
                            val = str(s.get('validation', '-')).replace('\n', ' ')
                            
                            # Clean and truncate
                            if len(title) > 28: title = title[:25] + "..."
                            if len(val) > 33: val = val[:30] + "..."
                            
                            log_msg += f"│{prio:<6}│{title:<28}│{val:<33}│\n"
                        log_msg += f"╰{'─'*8}┴{'─'*30}┴{'─'*35}╯\n"

                    self.update_task_log(task_id, log_msg)

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
                change_intent=self.format_field(report.get('change_intent', '')),
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

    def refine_report_with_static_analysis(self, report, root_dir):
        """
        Post-process the AI report to fill in missing details (like line numbers) using local static analysis.
        """
        if not report or 'downstream_dependency' not in report:
            return report

        dependencies = report.get('downstream_dependency', [])
        if not dependencies:
            return report

        console.print("[Info] Refining report with local code search...", style="dim")
        
        for dep in dependencies:
            # Check if line_number is missing or invalid
            line_num = dep.get('line_number')
            is_invalid_line = not line_num or str(line_num).strip() in ['无', 'N/A', '0', '-']
            
            if is_invalid_line:
                file_path = dep.get('file_path')
                target_method = dep.get('target_method')
                call_snippet = dep.get('call_snippet')
                
                if not file_path: continue

                # Try to find the file locally
                # AI might return relative path or full path or just filename
                # We search for it
                local_path = None
                
                # 1. Try direct join
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
                        if call_snippet and call_snippet not in ['无', 'N/A']:
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
                                    # Heuristic: if line also contains variable name from caller_class, better
                                    break
                        
                        if found_line:
                            dep['line_number'] = found_line
                            console.print(f"[Success] Refined line number for {os.path.basename(local_path)}: {found_line}", style="green")
                            
                            # Also refine snippet if empty
                            if not call_snippet or call_snippet in ['无', 'N/A']:
                                dep['call_snippet'] = lines[found_line-1].strip()

                    except Exception as e:
                        console.print(f"[Warning] Failed to refine {file_path}: {e}", style="yellow")

        return report

    def analyze_with_llm(self, filename, diff_content, root_dir, task_id=None, base_ref=None, target_ref=None, tracer=None, scan_roots=None):
        self.print_code_comparison(diff_content, base_ref, target_ref)
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
        self.update_task_log(task_id, f"[Link Analysis] 发现 {len(downstream_callers)} 个潜在下游调用点。\n{downstream_info}")
        
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
                    self.update_task_log(task_id, f"[Static Analysis] 静态分析上下文获取成功。\n{static_context.strip()}")
                
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
        self.update_task_log(task_id, f"[Link Analysis] 发现 {len(downstream_callers)} 个潜在跨服务调用点。\n{downstream_info}")

        # --- ApiUsageTracer Integration (New) ---
        affected_api_endpoints = []
        if filename.endswith(".java") or filename.endswith(".xml"):
            try:
                console.print(f"[Info] 正在执行深度 API 链路追踪 (ApiUsageTracer)...", style="bold blue")
                # Use passed tracer or create new one
                current_tracer = tracer if tracer else ApiUsageTracer(root_dir)
                
                # 1. Identify changed methods
                full_path = os.path.join(root_dir, filename)
                changed_methods = self.extract_changed_methods(diff_content, full_path, project_root=root_dir)
                console.print(f"[Info] 识别到的变更方法 (SQL ID / Java Method): {changed_methods}", style="dim")
                
                # 2. Also try to get class name
                # We can use static_parser's result if we had access to the class name easily, 
                # but filename usually gives a hint, or just use simple class name from filename.
                simple_class_name = os.path.basename(filename).replace(".java", "").replace(".xml", "")
                
                # 3. Trace each method
                for method in changed_methods:
                    apis = current_tracer.find_affected_apis(simple_class_name, method)
                    if apis:
                        for api_item in apis:
                            if isinstance(api_item, dict):
                                api_str = api_item.get('api')
                                # Avoid duplicates
                                is_dup = False
                                for existing in affected_api_endpoints:
                                    if isinstance(existing, dict) and existing.get('api') == api_str:
                                        is_dup = True
                                        break
                                if not is_dup:
                                    affected_api_endpoints.append(api_item)
                            elif api_item not in affected_api_endpoints:
                                affected_api_endpoints.append(api_item)
            except Exception as e:
                console.print(f"[yellow]ApiUsageTracer failed: {e}[/yellow]")

        affected_apis_str = "未检测到受影响的 API 入口。"
        controller_params_info = ""  # 用于存储 Controller 参数信息
        
        if affected_api_endpoints:
            # Format list for prompt
            lines = []
            for item in affected_api_endpoints:
                if isinstance(item, dict):
                    lines.append(f"- {item.get('api')} (Call Chain: {item.get('caller_class')}.{item.get('caller_method')})")
                else:
                    lines.append(f"- {item}")
            affected_apis_str = "\n".join(lines)
            
            # Extract Controller parameters if this is an internal method change
            # Check if current file is a Service/Manager/Mapper (not a Controller)
            is_internal_method = filename.endswith(".java") and not any(
                keyword in filename.lower() for keyword in ["controller", "provider", "rest"]
            )
            
            if is_internal_method and affected_api_endpoints:
                controller_params_info = self._extract_controller_params(affected_api_endpoints, root_dir)
            
            console.print(Panel(f"[bold green]深度追踪发现受影响 API:[/bold green]\n{affected_apis_str}", title="Deep API Trace", border_style="green"))
            self.update_task_log(task_id, f"[Deep API Trace] 深度追踪发现受影响 API:\n{affected_apis_str}")
            
            # --- MERGE INTO CROSS-SERVICE IMPACT ---
            if downstream_info == "未检测到明显的跨服务调用引用。" or downstream_info == "未检测到明显的调用引用。":
                downstream_info = ""
            
            downstream_info += "\n\n[Deep API Trace - Confirmed API Impacts]:\n"
            for item in affected_api_endpoints:
                if isinstance(item, dict):
                    api_val = item.get('api')
                    caller_file = item.get('file', 'Unknown')
                    caller_line = item.get('line', 'Unknown')
                    caller_snippet = item.get('snippet', 'Code snippet not available')
                    
                    downstream_info += f"- [API Impact] Endpoint: {api_val}\n"
                    downstream_info += f"  Caller File: {caller_file}\n"
                    downstream_info += f"  Line: {caller_line}\n"
                    downstream_info += f"  Code: {caller_snippet}\n"
                    downstream_info += f"  Risk: High (Direct external entry point)\n"
                else:
                    downstream_info += f"- [API Impact] Endpoint: {item}\n"
                    downstream_info += f"  Risk: High (Direct external entry point)\n"
        else:
            console.print("[Info] 深度追踪未发现受影响的 API 入口。", style="dim")

        console.print(f"\n[AI Analysis] 正在使用 DeepSeek ({DEEPSEEK_MODEL}) 分析 {filename} ...", style="bold magenta")
        self.update_task_log(task_id, f"[AI Analysis] 正在请求 AI 分析...")
        
        prompt = f"""
        # Role
        你是一名资深的 Java 测试架构师，精通微服务调用链路分析、代码变更影响评估、测试策略设计。

        # Static Analysis Hints (Hard Facts - 静态分析结果)
        {static_context}
        注意: 
        1. "Class A is used by B" 意味着 B 依赖 A（调用关系：B -> A）；
        2. B 是「调用方（Consumer）」，A 是「被调用方（Provider）」；
        3. 仅当 A 发生接口/逻辑变更时，B 才会受影响（即 B 是 A 的下游受影响方）；反之，B 变更不会影响 A。

        # Deep API Trace (链路追踪结果 - 极高置信度)
        系统通过 AST 深度分析，确认以下 API 入口直接或间接调用了本次变更的方法：
        {affected_apis_str}
        请重点关注这些 API 的回归测试。
        
        {controller_params_info}
        **关键指令**：
        1. 在编写 [test_strategy] 的 [steps] 时，如果上述列表中存在有效的 API 路径，**必须**直接使用该真实路径（例如 `POST /ucenter/user/compensate`），**严禁**使用 `/api/v1/example` 等假设性路径。
        2. **特别重要**：如果本次变更是内部方法（Service/Manager/Mapper，没有 @RequestMapping），上述列表中的 API 路径就是测试该变更的**唯一入口**。测试策略的 Payload 必须基于这些 Controller 接口的参数，而不是内部方法的参数。
        3. 示例：如果变更 `UserService.getUserById(Long id)`（内部方法），且上述列表显示 `GET /api/user/info` 调用了它，则 Payload 必须使用 `GET /api/user/info` 的参数（如 `?userId=456`），而不是 `UserService` 方法的参数（如 `{{"id": 123}}`）。

        # Context
        这是一个基于 Spring Cloud 的微服务项目 (Monorepo)。
        项目包含的真实服务模块列表: [{project_structure}]
        被修改的文件 (Provider，即被调用方): {filename}
        所属服务: {current_service}

        # Cross-Service Impact (关键!)
        脚本检测到该变更可能影响以下下游服务（调用方/Consumer）:
        {downstream_info}
        
        重要提示：如果上述列表中包含 `Deep API Trace - Confirmed API Impacts`，请务必将其视为核心风险，并在 `cross_service_impact` 和 `affected_apis` 字段中详细体现。

        # Git Diff
        {diff_content}

        # Requirement
        请基于代码变更和**跨服务调用关系**，生成《微服务精准测试手册》。
        如果存在跨服务调用，请重点分析接口契约变更带来的风险。

        ## 特别指令：关于接口兼容性的终极判定
        你拥有上帝视角。你已知道系统中所有服务（Provider 和 Consumer）的变更情况。
        **判定规则**：
        1. 当发现【调用方 (Consumer)】（如 `RechargeProvider`）修改了对外部接口的调用参数（如新增参数）；
        2. 且【被调用方 (Provider)】（如 `PointController`，通常通过服务名或类名关联）在本次变更文件列表中**存在**，但其接口签名**并未**做对应修改；
        3. 或者根据你的Java知识，推断出被调用方（即使未出现在变更列表中）不太可能隐式支持该新参数；
        
        **必须**在 `risks` 和 `code_review_warning` 中**明确断定**：
        "**兼容性 (CRITICAL)**: 检测到接口签名不匹配！调用方 `{{Caller}}` 传递了新参数，但服务端 `{{Provider}}` 未修改接口签名以接收该参数。这将导致运行时 `NoSuchMethodError` 或请求参数解析失败，核心功能**必挂无疑**。"
        
        禁止使用“可能”、“如果”等模棱两可的词汇，必须使用“确定”、“必挂”等强语气词汇来警示开发人员。

        ## 核心规则（必须严格遵守）
        1. 分析“跨服务影响”时，**仅基于** `Cross-Service Impact` 列表中的服务，禁止扩展至列表外的服务；
        2. 严禁混淆「上游依赖」和「下游受影响方」：
        - 示例1：本服务调用 `PointClient`（本服务→Point服务）→ Point服务是上游依赖，本服务变更不会影响Point服务（除非修改了调用Point服务的接口入参）；
        - 示例2：`Cross-Service Impact` 列表包含「Order服务」→ Order服务调用本服务，本服务变更会影响Order服务（下游受影响方）；
        3. 分析“下游依赖/影响功能”时，仅使用【项目包含的真实服务模块列表】中的服务名称，禁止编造；
        4. 若 `Cross-Service Impact` 无跨服务调用（仅内部调用/无），`cross_service_impact` 字段填“无”；
        5. 禁止直接复制模板值，所有内容需基于实际代码变更填充；
        6. 风险等级判定规则：
        - 严重：导致核心业务中断（如转账资金不一致）、数据丢失、大面积服务不可用；
        - 高：影响核心功能正确性（如积分计算错误），需紧急修复；
        - 中：影响非核心功能（如日志打印异常），不影响主流程；
        - 低：仅格式/注释变更，无功能影响；
        7. 字段无数据时的兜底规则：
        - line_number/call_snippet 无数据 → 填“无”；
        - affected_apis 无受影响API → 数组留空（[]）；
        - downstream_dependency 无依赖 → 数组留空（[]）。

        ## 字段约束（必须严格遵守）
        ### 1. functional_impact 字段
        必须是结构化JSON对象（非字符串），每个子字段需满足：
        - business_scenario：具体到“触发条件+业务动作+结果”，禁止笼统描述（如禁止“转账业务”，需写“用户发起账户间转账且金额≥1000元时，系统新增风控预校验流程，校验不通过则拒绝转账”）；
        - data_flow：按步骤详细描述数据流转过程，必须使用序号（1. 2. 3.）分步说明，禁止使用箭头（→）简单连接。每一步需包含：涉及的方法/组件、关键逻辑判断、数据变更（如字段状态变化）。示例：“1. 用户调用 /api/transfer 接口，传入 amount=100... 2. TransferController 接收请求，调用 UserManager.initiateTransfer()... 3. 校验余额充足后，扣减 A 账户余额...”）；
        - api_impact：详细分析API及方法层面的影响。需包含：1. 具体变更的方法及其内部逻辑变化（如“UserManager.initiateTransfer方法内部逻辑变更，新增了对PointClient.addPoint的调用”）；2. 该变更带来的额外业务影响/连带变更（禁止使用“副作用”一词，需直白描述，如“在转账成功的同时，系统将额外自动执行积分增加操作”）；3. 接口契约（URL、参数、返回值）是否发生物理变更；4. 若涉及跨服务调用，明确说明作为调用方的影响（如“不影响下游服务接口契约，但引入了新的依赖”）。禁止简单一句话描述。
        - risks：必须返回一个详细的字符串数组，每项代表一个具体的风险点。格式要求：使用 "**风险类别**: 详细描述" 的形式。**建议考虑（但不限于）以下维度，请根据实际变更灵活调整**：**数据一致性**（如分布式事务）、**幂等性**、**性能影响**（RT增加）、**可用性**（依赖风险）、**错误处理**（回滚/补偿）、**安全风险**、**兼容性**。示例：“**数据一致性**: 若 pointClient 调用超时，本地事务已提交，导致数据不一致...”。禁止简单的单行描述。
        - entry_points：列出代码/接口层面的具体入口（如“API Endpoint: POST /api/v1/user/transfer”、“Java方法: com.user.service.TransferService.initiateTransfer(String fromUserId, String toUserId, BigDecimal amount)”）。

        ### 2. 其他字段约束
        - business_rules：**这是测试人员验收的核心依据**。请识别代码逻辑变化，并**以对比表格形式**呈现。
          - 目标：清晰展示“变更前 vs 变更后”的业务规则差异，消除测试人员的脑补成本。
          - 格式：对象数组，每个对象包含：
            - `scenario`: 业务场景（如“普通用户积分上限”、“VIP奖金策略”）。
            - `old_rule`: 变更前的规则（如“2000分”、“无限制”、“N/A (新增)”）。
            - `new_rule`: 变更后的规则（如“3000分”、“>10000 拒绝”）。
            - `impact`: 变更带来的具体影响（如“⬆️ 额度提升”、“🛡️ 新增风控”、“⚠️ 需人工审核”）。
            - `related_file`: 关联文件名。
          - **关键要求**：
            1. **必须包含数值对比**：如果涉及阈值变化，必须写出具体数字（如 2000 -> 3000）。
            2. **针对新增规则**：`old_rule` 填 "无 (新增逻辑)"，`new_rule` 填具体规则。
            3. **针对删除规则**：`old_rule` 填具体规则，`new_rule` 填 "已移除"。
            4. **禁止笼统描述**：不要写“修改了逻辑”，要写“从同步执行改为异步执行”。

        - code_review_warning：从“代码规范、性能、安全、兼容性、事务一致性”维度分析（如“转账方法未加幂等校验，可能导致重复扣减余额”）；
        - change_intent：变更详情。请返回一个对象数组，每个对象包含 "summary"（核心变更点）和 "details"（详细说明列表）。
          - **details 要求**：必须深入到**代码实现层面**。不要只说“优化了性能”，要说“将同步锁 `synchronized` 替换为 `ReentrantLock` 以提升高并发下的吞吐量”。不要只说“增加了日志”，要说“在 `catch` 块中增加了 `log.error` 打印堆栈信息”。
        - affected_apis：仅列出本次变更直接影响的API，包含method/url/description，无则留空数组；
        - downstream_dependency：仅列出`Cross-Service Impact`中的服务，字段需精准（如caller_method需包含参数类型，如“transfer(String, BigDecimal)”）；
        - test_strategy：payload示例需贴合代码变更的真实参数，标注必填/选填，验证点需可量化。
          - **关键要求（测试步骤）**：
            1. **必须黑盒化**：测试人员无法直接“创建DTO”或“调用Java方法”。必须将内部代码逻辑映射为**外部可调用的 HTTP API**。
            2. **如果变更是内部类/DTO**：你必须结合 [Link Analysis] 和 [Deep API Trace] 找到触发该逻辑的上游 API（例如 `POST /ucenter/recharge`）。
            3. **格式要求**：步骤必须写成“调用接口 A -> 传入参数 B -> 验证结果 C”。
            4. **禁止**：“模拟业务场景”、“创建实例”、“调用set方法”等开发术语。
            5. **示例**：
               - ❌ 错误：在 PointManager 中创建 DTO，设置 riskLevel="HIGH"。
               - ✅ 正确：调用接口 `POST /ucenter/recharge/compensate`，传入参数 `amount=1000`（该金额会触发 HIGH 风险等级），验证响应成功。
          
          - **特殊情况：内部方法变更（无 HTTP 接口）**：
            **当变更是 Service/Manager/Mapper 等内部方法（没有 @RequestMapping/@GetMapping 等注解）时**：
            1. **必须使用 [Deep API Trace] 中识别到的 Controller 接口**：
               - [Deep API Trace] 会列出所有调用该内部方法的 Controller 接口（如 `GET /api/user/info`）
               - **Payload 必须基于 Controller 接口的参数**（@RequestParam/@PathVariable/@RequestBody），而不是内部方法的参数
               - 测试步骤应描述：调用 Controller 接口 → 该接口内部会调用变更的方法 → 验证结果
            
            1.1. **参数提取规则（重要）**：
               - **如果 Controller 代码在本次 Git Diff 中**：直接从 Diff 中提取参数（@RequestParam/@PathVariable/@RequestBody）
               - **如果 Controller 代码不在本次 Diff 中**：
                 * **优先使用系统自动提取的参数信息**：如果 Prompt 中提供了 "Controller 参数信息" 部分，**必须直接使用其中的参数来生成 Payload，严禁写"需查看"、"需确认"等提示性文字**
                 * **如果系统提供了参数信息（如 `@RequestParam String orderId`）**：
                   - ✅ **必须直接生成 Payload**：`?orderId=12345`（GET 请求）或 `{{"orderId": "12345"}}`（POST + @RequestBody）
                   - ❌ **严禁写**："需查看 `RechargeProvider.java` 中 `checkRechargeStatus` 方法的参数来确定"
                   - ❌ **严禁写**："例如: `?orderId=12345` (需确认)"
                   - ✅ **正确写法**：直接写 `?orderId=12345` 或 `{{"orderId": "12345"}}`
                 * 如果系统未提供参数信息，必须查看 [Deep API Trace] 中提到的 Controller 文件路径
                 * 从调用链信息（如 `RechargeProvider.checkRechargeStatus`）推断 Controller 类和方法
                 * 如果确实无法确定参数，Payload 应写为："需查看 Controller 代码确认参数（建议查看 [Deep API Trace] 中提到的 Controller 文件）"
               - **严禁**因为看不到 Controller 代码就写"无参数"，这是错误的
               - **关键**：如果系统提供了 "Controller 参数信息"，必须严格按照其中的参数名和类型生成 Payload，不得自行推断或修改参数名，**更不得写任何"需查看"的提示**
            
            2. **示例场景**：
               - 变更：`UserService.getUserById(Long id)`（内部方法，无 HTTP 接口）
               - [Deep API Trace] 发现：`GET /api/user/info` 调用了此方法
               - Controller 定义：`@GetMapping("/api/user/info") public Result getUserInfo(@RequestParam String userId)`
               - ✅ 正确 Payload：`?userId=456`（使用 Controller 的参数 `userId`）
               - ❌ 错误 Payload：`{{"id": 123}}`（使用了内部方法的参数 `id`）
               - ✅ 正确步骤：`调用 GET /api/user/info?userId=456，该接口内部会调用 UserService.getUserById(456L)`
            
            3. **如果 [Deep API Trace] 未找到 Controller 接口**：
               - 说明该内部方法可能未被外部接口调用，或调用链追踪失败
               - Payload 标注为"无外部接口"或"需确认调用方"
               - 测试步骤说明：该变更可能影响内部逻辑，需通过集成测试验证
            
            4. **关键原则**：
               - **永远基于 Controller 接口生成 Payload**，而不是内部方法的参数
               - 内部方法的参数（如 `username`）是**实现细节**，测试人员无法直接传入
               - 测试人员只能通过 Controller 接口的参数（如 `orderId`）来触发内部逻辑
            
          - **关键要求（参数名和格式）**：
            1. **参数名必须从代码中提取**：
               - `@RequestParam String orderId` → 参数名必须是 **"orderId"**（严禁改为 "rechargeId" 或其他推测名称）
               - `@PathVariable Long userId` → 参数名必须是 **"userId"**
               - `@RequestBody RechargeDTO dto` → 从 DTO 类的字段中提取（如 `dto.amount` → "amount"）
               - **严禁**根据接口路径（如 `/api/user/info` → `userId`）或业务语义推测参数名
               - **严禁**编造不存在的参数名，如果代码中没有明确参数，则标注为"无参数"或"参数待确认"
            
            2. **参数格式必须与 HTTP 方法匹配**：
               - **GET/DELETE 请求**：
                 * 参数通过 **URL Query String** 传递
                 * Payload 格式：`?orderId=12345` 或 `?userId=100&status=active`
                 * 测试步骤：`调用 GET /api/path?orderId=12345`
                 * ❌ 错误：`{{"orderId": "12345"}}`（JSON Body 格式）
                 * ✅ 正确：`?orderId=12345`（Query String 格式）
             
               - **POST/PUT 请求**：
                 * 如果使用 `@RequestParam`：参数通过 **Query String** 或 **Form Data** 传递
                 * 如果使用 `@RequestBody`：参数通过 **JSON Body** 传递
                 * Payload 格式：
                   - `@RequestParam` → `?key=value` 或 Form Data
                   - `@RequestBody` → `{{"key": "value"}}`（JSON 对象）
                 * 测试步骤：`调用 POST /api/path，Body 为 {{"orderId": "12345"}}`
            
            3. **Payload 示例格式规范**：
               - GET/DELETE + `@RequestParam` → `?paramName=value`（Query String）
               - POST/PUT + `@RequestParam` → `?paramName=value` 或 Form Data
               - POST/PUT + `@RequestBody` → `{{"fieldName": "value"}}`（JSON 对象）
               - 必须标注必填/选填：`{{"orderId": "12345" (必填, 示例值)}}`
               - 如果参数在 URL 路径中（`@PathVariable`），在 steps 中说明，payload 中不重复
            
            4. **验证示例**：
               - 代码：`@GetMapping("/status") public Result checkStatus(@RequestParam String orderId)`
               - ✅ 正确 Payload：`?orderId=12345`（Query String）
               - ❌ 错误 Payload：`{{"rechargeId": "12345"}}`（参数名错误 + 格式错误）
               - ✅ 正确步骤：`调用 GET /api/status?orderId=12345`

        ## 禁止示例（以下回答无效）
        1. functional_impact 字段为字符串："functional_impact": "修改了转账逻辑，可能影响用户系统"；
        2. business_scenario 笼统描述："业务场景：影响转账业务"；
        3. risks 泛泛而谈："风险：可能影响数据一致性"；
        4. business_rules 笼统描述："修改了积分规则"（必须写出具体规则，如“积分获取上限从 1000 调整为 5000”）；
        5. 编造不存在的服务名称："service_name": "PaymentService"（不在项目服务列表中）；
        6. **参数名错误**：
           - 代码：`@RequestParam String orderId` → ❌ 错误 Payload：`{{"rechargeId": "12345"}}`（参数名错误）
           - 代码：`@GetMapping("/status")` + `@RequestParam String orderId` → ❌ 错误 Payload：`{{"orderId": "12345"}}`（GET 请求不应使用 JSON Body，应使用 Query String：`?orderId=12345`）
           - ✅ 正确：从代码中提取准确参数名 `orderId`，GET 请求使用 `?orderId=12345` 格式。
        
        7. **内部方法变更时使用错误的参数**：
           - 变更：`UserService.getUserById(Long id)`（内部方法，无 HTTP 接口）
           - [Deep API Trace] 发现：`GET /api/user/info` 调用了此方法
           - Controller：`@GetMapping("/api/user/info") public Result getUserInfo(@RequestParam String userId)`
           - ❌ 错误 Payload：`{{"id": 123}}`（使用了内部方法的参数 `id`，而不是 Controller 的参数 `userId`）
           - ✅ 正确 Payload：`?userId=456`（使用 Controller 接口的参数 `userId`）

        请严格按照以下 JSON 格式返回（字段不可缺失，值为字符串的需用双引号包裹）：
        {{
            "code_review_warning": "<代码审查警示>",
            "change_intent": [
                {{
                    "summary": "<核心变更点1>",
                    "details": ["<技术实现细节1>", "<技术实现细节2>"]
                }}
            ],
            "business_rules": [
                {{
                    "scenario": "<业务场景>",
                    "old_rule": "<变更前规则>",
                    "new_rule": "<变更后规则>",
                    "impact": "<变更影响>",
                    "related_file": "<关联文件名>"
                }}
            ],
            "risk_level": "严重/高/中/低",
            "cross_service_impact": ["<跨服务影响点1: 明确指出受影响的服务和原因>", "<跨服务影响点2: 详细描述风险和后果>"],
            "cross_service_impact_summary": "<跨服务影响的一句话总结（精简，<50字）>",
            "functional_impact": {{
                "business_scenario": "...",
                "data_flow": "1. 步骤一描述...\n2. 步骤二描述...",
                "api_impact": "...",
                "risks": ["..."],
                "entry_points": ["..."]
            }},
            "affected_apis": [
                {{
                    "method": "GET/POST/PUT/DELETE",
                    "url": "/api/v1/example",
                    "description": "接口说明"
                }}
            ],
            "downstream_dependency": [
                {{
                    "service_name": "<服务名>",
                    "file_path": "<文件路径>",
                    "line_number": "<行号>",
                    "caller_class": "<调用方类名>",
                    "caller_method": "<调用方方法签名（含参数类型）>",
                    "target_method": "<被调用的目标方法/API>",
                    "call_snippet": "<调用处的代码片段>",
                    "impact_description": "<该调用点可能受到的具体影响>"
                }}
            ],
            "test_strategy": [
                {{
                    "title": "<测试场景（如：正常转账-金额100元）>",
                    "priority": "P0/P1",
                    "steps": "<详细测试步骤：包含前置条件、操作步骤（如接口调用、参数设置）。**务必使用 [Deep API Trace] 中识别到的真实 API 路径**>",
                    "payload": "<Payload示例：**如果系统提供了 Controller 参数信息，必须直接使用其中的参数名生成 Payload**。GET/DELETE请求使用Query String格式（如 ?orderId=12345），POST/PUT请求根据@RequestParam或@RequestBody使用对应格式。参数名必须与代码中的变量名完全一致，严禁编造。**严禁写"需查看"、"需确认"等提示性文字，必须直接生成实际的 Payload**。标注必填/选填>",
                    "validation": "<可量化的验证点>"
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
            self.update_task_log(task_id, f"DeepSeek Token Usage: Total {total}")
            
        try:
            cleaned_content = response_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            elif cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            
            report_json = json.loads(cleaned_content.strip())
            console.print(f"[Debug] AI Response Keys: {list(report_json.keys())}", style="dim")
            if 'business_rules' in report_json:
                console.print(f"[Debug] Business Rules count: {len(report_json['business_rules'])}", style="green")
            else:
                console.print(f"[Warning] AI did NOT return 'business_rules' field!", style="red")

            # Post-process refinement
            report_json = self.refine_report_with_static_analysis(report_json, root_dir)
            
            # Inject Usage Info for DB storage
            if usage:
                report_json['_usage'] = usage

            return report_json
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
        
        max_retries = 2
        retry_delay = 2 # seconds
        
        for attempt in range(max_retries + 1):
            try:
                # Switch to requests library for better SSL/Error handling
                response = requests.post(DEEPSEEK_API_URL, json=data, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        return result['choices'][0]['message']['content'], result.get('usage', {})
                else:
                    console.print(f"[red]API Error Status: {response.status_code} - {response.text}[/red]")
                    if attempt < max_retries:
                        console.print(f"[yellow]Retrying API call (Attempt {attempt+2}/{max_retries+1})...[/yellow]")
                        time.sleep(retry_delay)
                
            except Exception as e:
                console.print(f"[red]API Connection Error: {e}[/red]")
                if attempt < max_retries:
                    console.print(f"[yellow]Retrying API call (Attempt {attempt+2}/{max_retries+1})...[/yellow]")
                    time.sleep(retry_delay)
                else:
                    return None, None
        
        return None, None

    def print_code_comparison(self, diff_text, base_ref=None, target_ref=None):
        lines = diff_text.splitlines()
        clean_lines = [line for line in lines if not (line.startswith("diff --git") or line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ ") or line.startswith("new file mode") or line.startswith("deleted file mode"))]
        syntax = Syntax("\n".join(clean_lines), "diff", theme="monokai", line_numbers=True, word_wrap=True)
        
        title = "Code Diff: 变更代码对比"
        if base_ref and target_ref:
            title += f" ({base_ref} -> {target_ref})"
        
        console.print(Panel(title, style="bold cyan", expand=False))
        console.print(syntax)
        console.print("-" * 80, style="dim")

    def extract_changed_methods(self, diff_text, file_path=None, project_root=None):
        """
        Parses the diff text AND the actual file content to precisely identify changed methods.
        Uses javalang for Java and MybatisAnalyzer for XML.
        """
        changed_methods = set()
        
        # --- XML Handling (MyBatis) ---
        if file_path and file_path.endswith(".xml") and project_root:
            try:
                analyzer = MybatisAnalyzer(project_root)
                # analyze_xml_change returns list of dicts: [{'class_name':..., 'method_name':...}]
                # We extract just the method_name (SQL ID) here for simple compatibility, 
                # but ideally we should return the class name too. 
                # For now, let's just return the method names (SQL IDs) and let the caller handle class name inference 
                # (Caller usually infers class name from filename, but for XML, filename is Mapper.xml, so it matches Mapper.java usually).
                
                # Wait, MybatisAnalyzer logic needs full path relative to repo
                rel_path = os.path.relpath(file_path, project_root)
                results = analyzer.analyze_xml_change(rel_path, diff_text)
                for res in results:
                    changed_methods.add(res['method_name'])
                
                # If we found methods via XML, we return them.
                if changed_methods:
                    return list(changed_methods)
            except Exception as e:
                console.print(f"[yellow]MyBatis analysis failed: {e}[/yellow]")

        # --- Java Handling ---
        
        # 1. Fallback / Quick Check: Regex on Hunk Header (Legacy)
        method_pattern = re.compile(r'(?:public|protected|private|static|\s) +[\w<>\[\]]+\s+(\w+)\s*\(')
        for line in diff_text.splitlines():
            if line.startswith('@@'):
                context_match = re.search(r'@@.*?@@(.*)', line)
                if context_match:
                    m = method_pattern.search(context_match.group(1).strip())
                    if m: changed_methods.add(m.group(1))
            elif line.startswith('+') and not line.startswith('+++'):
                content = line[1:].strip()
                if not content.startswith(('import ', '@', 'package ')):
                    m = method_pattern.search(content)
                    if m: changed_methods.add(m.group(1))

        # 2. Precise AST Mapping (if file exists locally)
        if file_path and os.path.exists(file_path) and file_path.endswith(".java"):
            try:
                import javalang
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                # Parse file to get method ranges
                tree = javalang.parse.parse(file_content)
                methods = []
                for _, node in tree.filter(javalang.tree.MethodDeclaration):
                    if node.name and node.position:
                        methods.append({'name': node.name, 'start': node.position.line})
                methods.sort(key=lambda x: x['start'])
                total_lines = len(file_content.splitlines())
                for i in range(len(methods)):
                    if i < len(methods) - 1:
                        methods[i]['end'] = methods[i+1]['start'] - 1
                    else:
                        methods[i]['end'] = total_lines

                # Parse diff to get changed line numbers (in new file)
                changed_lines = []
                current_line_num = 0
                for line in diff_text.splitlines():
                    if line.startswith('@@'):
                        match = re.search(r'\+(\d+)(?:,(\d+))?', line)
                        if match: current_line_num = int(match.group(1))
                    elif line.startswith('+') and not line.startswith('+++'):
                        changed_lines.append(current_line_num)
                        current_line_num += 1
                    elif not line.startswith('-'):
                        current_line_num += 1
                
                # Map lines to methods
                for line_num in changed_lines:
                    for m in methods:
                        if m['start'] <= line_num <= m['end']:
                            changed_methods.add(m['name'])
                            break
                            
            except Exception as e:
                console.print(f"[yellow]Precise method extraction failed: {e}[/yellow]")
        
        return list(changed_methods)

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

    def _extract_controller_params(self, affected_api_endpoints, root_dir):
        """提取 Controller 方法的参数信息，用于内部方法变更时的 Payload 生成"""
        params_info = []
        
        for item in affected_api_endpoints:
            if not isinstance(item, dict):
                continue
                
            caller_file = item.get('file', '')
            caller_method = item.get('caller_method', '')
            api_path = item.get('api', '')
            
            if not caller_file or not caller_method or not api_path:
                continue
            
            # 构建完整文件路径
            # caller_file 可能是绝对路径或相对路径
            if os.path.isabs(caller_file):
                full_path = caller_file
            else:
                full_path = os.path.join(root_dir, caller_file)
            
            # 如果文件不存在，尝试其他可能的路径
            if not os.path.exists(full_path):
                # 尝试相对路径（去掉开头的 /）
                if caller_file.startswith('/'):
                    full_path = os.path.join(root_dir, caller_file.lstrip('/'))
                # 如果还是不存在，尝试从 root_dir 开始查找
                if not os.path.exists(full_path):
                    # 提取文件名，在 root_dir 下递归查找
                    file_name = os.path.basename(caller_file)
                    for root, dirs, files in os.walk(root_dir):
                        if file_name in files:
                            full_path = os.path.join(root, file_name)
                            break
                    else:
                        continue
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 使用正则表达式提取方法签名和参数
                # 先找方法名，再在方法名附近查找参数定义
                method_name_pattern = rf'\b{re.escape(caller_method)}\s*\('
                method_name_match = re.search(method_name_pattern, content)
                
                method_def = None
                if method_name_match:
                    # 向前查找方法定义和注解（最多向前500字符）
                    start_pos = max(0, method_name_match.start() - 500)
                    # 向后查找方法参数结束（最多向后200字符）
                    end_pos = min(len(content), method_name_match.end() + 200)
                    snippet = content[start_pos:end_pos]
                    
                    # 在 snippet 中查找方法参数部分（包括注解）
                    # 匹配从 @RequestParam/@PathVariable/@RequestBody 开始到参数结束
                    param_with_annotation_pattern = r'(@(?:RequestParam|PathVariable|RequestBody)(?:\([^)]*\))?\s+\w+\s+\w+)'
                    param_matches = list(re.finditer(param_with_annotation_pattern, snippet))
                    
                    if param_matches:
                        # 找到了带注解的参数，使用这些参数
                        method_def = snippet
                    else:
                        # 如果找不到带注解的参数，尝试匹配完整的方法定义
                        method_pattern = rf'@(?:Request|Get|Post|Put|Delete|Patch)Mapping[^)]*\)\s*(?:public\s+)?[\w<>,\s]+\s+{re.escape(caller_method)}\s*\([^)]*\)'
                        method_match = re.search(method_pattern, snippet, re.MULTILINE | re.DOTALL)
                        if method_match:
                            method_def = method_match.group(0)
                
                if method_def:
                    # 提取参数：@RequestParam, @PathVariable, @RequestBody
                    params = []
                    
                    # 提取 @RequestParam 参数
                    request_param_pattern = r'@RequestParam\s+(?:\([^)]*\)\s*)?(\w+)\s+(\w+)'
                    for param_match in re.finditer(request_param_pattern, method_def):
                        param_type = param_match.group(1)
                        param_name = param_match.group(2)
                        params.append(f"@RequestParam {param_type} {param_name}")
                    
                    # 提取 @PathVariable 参数
                    path_var_pattern = r'@PathVariable\s+(?:\([^)]*\)\s*)?(\w+)\s+(\w+)'
                    for param_match in re.finditer(path_var_pattern, method_def):
                        param_type = param_match.group(1)
                        param_name = param_match.group(2)
                        params.append(f"@PathVariable {param_type} {param_name}")
                    
                    # 提取 @RequestBody 参数
                    request_body_pattern = r'@RequestBody\s+(\w+(?:<[^>]+>)?(?:\s*\[\])?)\s+(\w+)'
                    for param_match in re.finditer(request_body_pattern, method_def):
                        param_type = param_match.group(1)
                        param_name = param_match.group(2)
                        params.append(f"@RequestBody {param_type} {param_name}")
                    
                    if params:
                        # 格式化参数信息，使其更清晰
                        param_details = []
                        for param in params:
                            # 提取参数名和类型
                            if '@RequestParam' in param:
                                param_match = re.search(r'@RequestParam\s+\w+\s+(\w+)', param)
                                if param_match:
                                    param_name = param_match.group(1)
                                    param_details.append(f"`{param_name}` (Query String)")
                            elif '@PathVariable' in param:
                                param_match = re.search(r'@PathVariable\s+\w+\s+(\w+)', param)
                                if param_match:
                                    param_name = param_match.group(1)
                                    param_details.append(f"`{param_name}` (URL Path)")
                            elif '@RequestBody' in param:
                                param_match = re.search(r'@RequestBody\s+\w+\s+(\w+)', param)
                                if param_match:
                                    param_name = param_match.group(1)
                                    param_details.append(f"`{param_name}` (JSON Body)")
                        
                        if param_details:
                            params_info.append(f"**{api_path}** (Controller: {item.get('caller_class')}.{caller_method}):\n  - 参数定义: {', '.join(params)}\n  - 参数名: {', '.join(param_details)}\n  - **必须直接使用这些参数生成 Payload，不要写\"需查看\"等提示**")
                    else:
                        # 如果没有找到注解参数，尝试提取普通参数
                        param_list_pattern = r'\(([^)]+)\)'
                        param_list_match = re.search(param_list_pattern, method_def)
                        if param_list_match:
                            param_list = param_list_match.group(1).strip()
                            if param_list and param_list != '':
                                params_info.append(f"**{api_path}** (Controller: {item.get('caller_class')}.{caller_method}):\n  - 参数: {param_list} (未找到注解，需手动确认)")
                        
            except Exception as e:
                logger.warning(f"Failed to extract params from {caller_file}: {e}")
                continue
        
        if params_info:
            return "\n\n**Controller 参数信息（用于 Payload 生成 - 必须直接使用，不要写\"需查看\"提示）**:\n" + "\n".join(params_info) + "\n\n**重要**：如果上面提供了参数信息，Payload 示例必须直接使用这些参数，格式如下：\n- GET/DELETE + @RequestParam → `?参数名=值`\n- POST/PUT + @RequestParam → `?参数名=值`\n- POST/PUT + @RequestBody → `{{\"参数名\": \"值\"}}`\n严禁写\"需查看\"、\"需确认\"等提示性文字。"
        return ""

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
