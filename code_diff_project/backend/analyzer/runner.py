import os
import json
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from analyzer.models import AnalysisTask
from loguru import logger

# 导入新模块
from analyzer.analysis import (
    update_task_log,
    format_field,
    get_git_diff,
    parse_diff,
    clone_or_update_project,
    save_to_db,
    analyze_with_llm,
    ApiUsageTracer,
    MultiProjectTracer
)

# 初始化 Rich Console
console = Console()

# --- DeepSeek API 配置 ---
USE_DEEPSEEK_API = True


def run_analysis(project_root=None, base_ref='HEAD^', target_ref='HEAD', task_id=None, 
                 enable_cross_project=False, related_projects=None):
    """
    运行精准测试分析并保存报告
    
    Args:
        project_root: 项目根目录路径
        base_ref: 基准版本 (e.g. master, HEAD^)
        target_ref: 目标版本 (e.g. feature, HEAD)
        task_id: 关联的任务ID
        enable_cross_project: 启用跨项目分析
        related_projects: 关联项目配置列表
    """
    # 1. 确定项目根目录
    if not project_root:
        project_root = os.path.abspath(os.path.join(settings.BASE_DIR, '..', '..'))
    
    # 2. 解析跨项目分析参数
    if related_projects is None:
        related_projects = []
    
    # 如果 related_projects 是字符串，尝试解析为 JSON
    if isinstance(related_projects, str):
        try:
            related_projects = json.loads(related_projects)
            if not isinstance(related_projects, list):
                logger.warning(f"related_projects should be a list, got {type(related_projects)}")
                related_projects = []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse related_projects JSON: {e}")
            update_task_log(task_id, f"[Error] 解析关联项目配置失败: {e}")
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
    update_task_log(task_id, f"[Info] 项目根目录: {project_root}")
    update_task_log(task_id, f"[Info] 比对版本: {base_ref} ... {target_ref}")
    update_task_log(task_id, f"[Info] 跨项目分析: {'启用' if enable_cross_project else '禁用'}")
    
    if enable_cross_project:
        if related_projects:
            update_task_log(task_id, f"[Info] 关联项目数量: {len(related_projects)}")
            for idx, proj in enumerate(related_projects, 1):
                proj_name = proj.get('related_project_name', 'Unknown')
                proj_git_url = proj.get('related_project_git_url', 'Unknown')
                proj_branch = proj.get('related_project_branch', 'master')
                update_task_log(task_id, f"[Info]   {idx}. {proj_name}")
                update_task_log(task_id, f"[Info]      Git URL: {proj_git_url}")
                update_task_log(task_id, f"[Info]      分支: {proj_branch}")
        else:
            update_task_log(task_id, f"[Warning] 跨项目分析已启用，但未配置关联项目")
            logger.warning("Cross-project analysis enabled but no related projects configured")
    
    # 3. 克隆/更新关联项目（如果启用跨项目分析）
    scan_roots = [project_root]  # 默认只包含主项目
    
    if enable_cross_project and related_projects:
        console.print("\n[bold blue]开始克隆/更新关联项目...[/bold blue]")
        update_task_log(task_id, "\n[Info] 开始克隆/更新关联项目...")
        
        # 创建 workspace 目录
        workspace_dir = os.path.join(os.path.dirname(project_root), 'workspace')
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)
            console.print(f"[Info] 创建 workspace 目录: {workspace_dir}", style="dim")
            update_task_log(task_id, f"[Info] 创建 workspace 目录: {workspace_dir}")
        
        # 克隆/更新关联项目（并行执行）
        successful_projects = []
        failed_projects = []
        
        # 使用 ThreadPoolExecutor 并行执行克隆/更新操作
        # 限制并发数为 4，避免资源耗尽
        max_workers = min(4, len(related_projects))
        
        console.print(f"[Info] 使用 {max_workers} 个并发线程处理 {len(related_projects)} 个项目", style="dim")
        update_task_log(task_id, f"[Info] 使用 {max_workers} 个并发线程处理 {len(related_projects)} 个项目")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_proj = {}
            for idx, proj in enumerate(related_projects, 1):
                future = executor.submit(
                    clone_or_update_project,
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
                        update_task_log(task_id, f"[Success] 项目 {result['name']} 准备完成")
                    else:
                        failed_projects.append({
                            'name': result['name'],
                            'error': result['error']
                        })
                        console.print(f"[Error] 项目 {result['name']} 处理失败: {result['error']}", style="red")
                        update_task_log(task_id, f"[Error] 项目 {result['name']} 处理失败: {result['error']}")
                
                except Exception as e:
                    proj_name = proj.get('related_project_name', 'Unknown')
                    error_msg = f"Future execution failed: {str(e)}"
                    failed_projects.append({
                        'name': proj_name,
                        'error': error_msg
                    })
                    console.print(f"[Error] 项目 {proj_name} 执行异常: {error_msg}", style="red")
                    update_task_log(task_id, f"[Error] 项目 {proj_name} 执行异常: {error_msg}")
        
        # 输出汇总信息
        console.print(f"\n[bold]关联项目处理完成:[/bold]", style="cyan")
        console.print(f"  成功: {len(successful_projects)}", style="green")
        console.print(f"  失败: {len(failed_projects)}", style="red" if failed_projects else "dim")
        
        update_task_log(task_id, f"\n[Info] 关联项目处理完成:")
        update_task_log(task_id, f"[Info]   成功: {len(successful_projects)}")
        update_task_log(task_id, f"[Info]   失败: {len(failed_projects)}")
        
        if failed_projects:
            console.print("\n[bold red]失败的项目:[/bold red]")
            update_task_log(task_id, "\n[Warning] 失败的项目:")
            for failed in failed_projects:
                msg = f"  - {failed['name']}: {failed['error']}"
                console.print(msg, style="red")
                update_task_log(task_id, f"[Warning] {msg}")
        
        if successful_projects:
            console.print("\n[bold green]成功的项目将被包含在分析中[/bold green]")
            update_task_log(task_id, "\n[Info] 成功的项目将被包含在分析中")
    
    # 切换工作目录以便 git 命令生效
    os.chdir(project_root)

    console.rule("[bold blue]精准测试分析助手 (DeepSeek版)[/bold blue]")
    
    # 2. 获取 Diff
    try:
        diff_text = get_git_diff(base_ref, target_ref)
        if not diff_text:
            msg = f"[yellow]未检测到 Java/XML/SQL/Config 文件的变更 ({base_ref} vs {target_ref})。[/yellow]"
            console.print(msg)
            update_task_log(task_id, msg)
            return

        # 3. 解析 Diff
        files_map = parse_diff(diff_text)
        msg = f"[green]检测到 {len(files_map)} 个核心文件 (Java/XML/SQL/Config) 发生变更。[/green]"
        console.print(msg + "\n")
        update_task_log(task_id, msg)

        # 4. 初始化追踪器（单项目或多项目模式）
        tracer = None
        try:
            if len(scan_roots) > 1:
                # 多项目模式：使用 MultiProjectTracer
                console.print(f"[Info] 初始化多项目追踪器，扫描 {len(scan_roots)} 个项目...", style="dim")
                update_task_log(task_id, f"[Info] 初始化多项目追踪器，扫描 {len(scan_roots)} 个项目")
                
                for idx, root in enumerate(scan_roots, 1):
                    proj_name = os.path.basename(root)
                    console.print(f"[Info]   {idx}. {proj_name}: {root}", style="dim")
                    update_task_log(task_id, f"[Info]   {idx}. {proj_name}: {root}")
                
                tracer = MultiProjectTracer(scan_roots)
                console.print(f"[Success] 多项目追踪器初始化完成", style="green")
                update_task_log(task_id, f"[Success] 多项目追踪器初始化完成")
            else:
                # 单项目模式：使用 ApiUsageTracer
                console.print("[Info] 初始化单项目索引 (Project Index)...", style="dim")
                update_task_log(task_id, "[Info] 初始化单项目索引")
                tracer = ApiUsageTracer(project_root)
                console.print(f"[Success] 单项目索引初始化完成", style="green")
                update_task_log(task_id, f"[Success] 单项目索引初始化完成")
        
        except Exception as e:
            error_msg = f"[Warning] 追踪器初始化失败: {e}"
            console.print(error_msg, style="yellow")
            update_task_log(task_id, error_msg)
            logger.error(f"Tracer initialization failed: {e}\n{traceback.format_exc()}")

        # 5. 逐个分析变更文件
        for filename, content in files_map.items():
            update_task_log(task_id, f"正在分析文件: {filename} ...")
            if USE_DEEPSEEK_API:
                report = analyze_with_llm(
                    filename, 
                    content, 
                    project_root, 
                    task_id, 
                    base_ref, 
                    target_ref, 
                    tracer=tracer, 
                    scan_roots=scan_roots
                )
                
                if report is None: 
                    update_task_log(task_id, f"文件 {filename} 分析失败，生成基础占位报告。")
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
                        prio = format_field(s.get('priority', '-'))
                        title = format_field(s.get('title', '-'))
                        payload = format_field(s.get('payload', '-')).replace('\n', '')
                        if len(payload) > 40:
                            payload = payload[:37] + "..."
                        
                        val = s.get('validation', '-')
                        if isinstance(val, str):
                            val = re.sub(r'(?<!^)(\d+\.)', r'\n\1', val)
                        else:
                            val = format_field(val)
                        
                        table.add_row(prio, title, payload, val)
                    
                    console.print(table)
                
                # --- Generate Log for Task Details ---
                log_msg = f"\n╭──────────────── 【精准测试作战手册】 ────────────────╮\n"
                log_msg += f"│ 文件: {filename}\n"
                log_msg += f"╰──────────────────────────────────────────────────────╯\n"
                
                if warning:
                    log_msg += f"\n[CODE REVIEW 警示]\n{warning}\n"
                
                log_msg += "\n[Change Analysis] 变更分析\n"
                log_msg += f"• 意图推测:\n  {format_field(report.get('change_intent', 'N/A')).replace(chr(10), chr(10)+'  ')}\n"
                log_msg += f"• 风险等级: {format_field(report.get('risk_level', 'N/A'))}\n"
                log_msg += f"• 跨服务影响:\n  {format_field(report.get('cross_service_impact', 'N/A')).replace(chr(10), chr(10)+'  ')}\n"
                log_msg += f"• 影响功能:\n  {format_field(report.get('functional_impact', 'N/A')).replace(chr(10), chr(10)+'  ')}\n"
                
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

                update_task_log(task_id, log_msg)

                # --- 保存至数据库 ---
                project_name = os.path.basename(project_root)
                save_to_db(filename, report, content, project_name=project_name, task_id=task_id)
                update_task_log(task_id, f"文件 {filename} 分析完成并保存。")

    except Exception as e:
        error_msg = f"Unexpected error in run_analysis: {str(e)}\n{traceback.format_exc()}"
        console.print(f"[red]{error_msg}[/red]")
        update_task_log(task_id, error_msg)
        # Re-raise so views.py can also catch it if needed, or just let it be failed.
        if task_id:
            try:
                task = AnalysisTask.objects.get(id=task_id)
                task.status = 'FAILED'
                task.save()
            except: pass
        raise e
