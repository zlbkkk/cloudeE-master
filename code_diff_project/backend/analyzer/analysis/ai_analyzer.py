import os
import json
import re
import time
import requests
from django.conf import settings
from rich.console import Console
from rich.panel import Panel
from .static_parser import LightStaticAnalyzer
from .api_tracer import ApiUsageTracer
from loguru import logger

console = Console()

# --- DeepSeek API 配置 (从 Django settings 读取) ---
DEEPSEEK_API_KEY = getattr(settings, 'DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = getattr(settings, 'DEEPSEEK_API_URL', 'https://api.chataiapi.com/v1/chat/completions')
DEEPSEEK_MODEL = getattr(settings, 'DEEPSEEK_MODEL', 'gemini-2.5-flash')


def merge_downstream_line_numbers(report_json, cross_project_impacts):
    """
    合并 downstream_dependency 中同一文件的多个行号，并去除重复记录
    同时合并所有代码片段，包含上下文代码
    
    参数:
        report_json: AI 返回的报告 JSON
        cross_project_impacts: 跨项目影响原始数据列表
    
    返回:
        更新后的 report_json
    """
    if not report_json or 'downstream_dependency' not in report_json:
        return report_json
    
    if not cross_project_impacts:
        return report_json
    
    # 按文件路径分组 cross_project_impacts
    impacts_by_file = {}
    for impact in cross_project_impacts:
        file_path = impact.get('file', '')
        if file_path:
            if file_path not in impacts_by_file:
                impacts_by_file[file_path] = []
            impacts_by_file[file_path].append(impact)
    
    # 按文件路径分组 downstream_dependency，并合并同一文件的记录
    dependencies = report_json.get('downstream_dependency', [])
    merged_dependencies = {}
    
    for dep in dependencies:
        file_path = dep.get('file_path', '')
        
        # 如果这个文件已经处理过，跳过（去重）
        if file_path in merged_dependencies:
            continue
        
        # 尝试匹配文件路径（可能是部分路径）
        matched_impacts = []
        matched_full_path = None
        for full_path, impacts in impacts_by_file.items():
            if file_path in full_path or full_path.endswith(file_path):
                matched_impacts = impacts
                matched_full_path = full_path
                break
        
        if matched_impacts:
            # 收集所有行号和代码片段（包含上下文）
            line_numbers = []
            snippets = []
            
            # 读取文件内容以获取上下文
            file_content_lines = None
            if matched_full_path:
                # 尝试从多个可能的位置读取文件
                from pathlib import Path
                possible_paths = [
                    Path(matched_full_path),
                    Path('code_diff_project/workspace') / matched_full_path,
                    Path('workspace') / matched_full_path
                ]
                
                for path in possible_paths:
                    if path.exists():
                        try:
                            with open(path, 'r', encoding='utf-8') as f:
                                file_content_lines = f.readlines()
                            logger.info(f"成功读取文件: {path}")
                            break
                        except Exception as e:
                            logger.warning(f"读取文件失败 {path}: {e}")
                            continue
            
            for impact in matched_impacts:
                line_num = impact.get('line', 0)
                if line_num and line_num not in line_numbers:
                    line_numbers.append(line_num)
                    
                    # 如果能读取文件，构建结构化的上下文数据
                    if file_content_lines:
                        context_data = {
                            'target_line': line_num,
                            'target_code': file_content_lines[line_num - 1].rstrip() if line_num <= len(file_content_lines) else '',
                            'context_before': [],
                            'context_after': []
                        }
                        
                        # 上2行
                        start_line = max(0, line_num - 3)
                        for i in range(start_line, line_num - 1):
                            if i < len(file_content_lines):
                                context_data['context_before'].append({
                                    'line': i + 1,
                                    'code': file_content_lines[i].rstrip()
                                })
                        
                        # 下2行
                        end_line = min(len(file_content_lines), line_num + 2)
                        for i in range(line_num, end_line):
                            if i < len(file_content_lines):
                                context_data['context_after'].append({
                                    'line': i + 1,
                                    'code': file_content_lines[i].rstrip()
                                })
                        
                        logger.info(f"生成上下文数据 - 行号: {line_num}, 上文: {len(context_data['context_before'])} 行, 下文: {len(context_data['context_after'])} 行")
                        snippets.append(context_data)
                    else:
                        # 如果无法读取文件，使用原始片段（兼容旧格式）
                        snippet = impact.get('snippet', '')
                        if snippet:
                            logger.info(f"使用原始片段 - 行号: {line_num}")
                            snippets.append({
                                'target_line': line_num,
                                'target_code': snippet,
                                'context_before': [],
                                'context_after': []
                            })
            
            # 按行号排序
            line_numbers.sort()
            
            # 更新行号字段，格式：20 25（用空格分隔，不加 "Line:" 前缀）
            if line_numbers:
                dep['line_number'] = ' '.join([str(ln) for ln in line_numbers])
                logger.info(f"合并行号: {file_path} -> {dep['line_number']}")
            
            # 更新代码片段字段，存储结构化数据
            if snippets:
                # 将结构化数据存储（不需要转换为 JSON 字符串，直接存储列表）
                dep['call_snippet_data'] = snippets
                logger.info(f"合并代码片段（结构化）: {file_path} -> {len(snippets)} 个片段")
                logger.debug(f"片段数据: {snippets}")
        
        # 保存到合并后的字典中（去重）
        merged_dependencies[file_path] = dep
    
    # 将合并后的依赖列表替换原来的列表
    report_json['downstream_dependency'] = list(merged_dependencies.values())
    logger.info(f"去重后的依赖数量: {len(merged_dependencies)} (原始: {len(dependencies)})")
    
    return report_json


def format_cross_project_impacts(impacts):
    """
    格式化跨项目影响信息为人类可读的文本
    
    参数:
        impacts: 影响字典列表，每个字典包含:
            - project: str (项目名称)
            - type: str ('class_reference', 'api_call', 或 'method_call')
            - file: str (文件路径)
            - line: int (行号)
            - snippet: str (代码片段)
            - detail: str (详细描述)
            - api: str (可选，仅用于 api_call 类型)
            - caller_class: str (可选，仅用于 method_call 类型)
            - caller_method: str (可选，仅用于 method_call 类型)
    
    返回:
        格式化的字符串
    """
    if not impacts:
        return "未检测到跨项目影响。"
    
    # 按项目和文件分组影响
    impacts_by_project = {}
    for impact in impacts:
        project = impact.get('project', 'Unknown')
        if project not in impacts_by_project:
            impacts_by_project[project] = {
                'class_references': {},  # 改为字典，按文件分组
                'api_calls': {},          # 改为字典，按文件分组
                'method_calls': {}        # 新增：方法调用影响
            }
        
        impact_type = impact.get('type', 'unknown')
        file_path = impact.get('file', 'Unknown')
        
        if impact_type == 'class_reference':
            if file_path not in impacts_by_project[project]['class_references']:
                impacts_by_project[project]['class_references'][file_path] = []
            impacts_by_project[project]['class_references'][file_path].append(impact)
        elif impact_type == 'api_call':
            if file_path not in impacts_by_project[project]['api_calls']:
                impacts_by_project[project]['api_calls'][file_path] = []
            impacts_by_project[project]['api_calls'][file_path].append(impact)
        elif impact_type == 'method_call':
            if file_path not in impacts_by_project[project]['method_calls']:
                impacts_by_project[project]['method_calls'][file_path] = []
            impacts_by_project[project]['method_calls'][file_path].append(impact)
    
    # 计算总影响数（按文件去重后）
    total_files = 0
    for project_impacts in impacts_by_project.values():
        total_files += len(project_impacts['class_references'])
        total_files += len(project_impacts['api_calls'])
        total_files += len(project_impacts['method_calls'])
    
    # 格式化为人类可读的文本
    lines = []
    lines.append("=" * 80)
    lines.append("跨项目影响分析结果")
    lines.append("=" * 80)
    lines.append(f"总计发现 {total_files} 个受影响文件，涉及 {len(impacts_by_project)} 个项目")
    lines.append("")
    
    for project_name, project_impacts in impacts_by_project.items():
        class_refs_by_file = project_impacts['class_references']
        api_calls_by_file = project_impacts['api_calls']
        method_calls_by_file = project_impacts['method_calls']
        
        lines.append(f"【项目】{project_name}")
        lines.append(f"  类引用: {len(class_refs_by_file)} 个文件 | API 调用: {len(api_calls_by_file)} 个文件 | 方法调用: {len(method_calls_by_file)} 个文件")
        lines.append("")
        
        # 格式化类引用（按文件分组）
        if class_refs_by_file:
            lines.append("  ▶ 类引用:")
            for file_idx, (file_path, refs) in enumerate(class_refs_by_file.items(), 1):
                lines.append(f"    {file_idx}. 文件: {file_path}")
                
                # 收集所有行号和代码片段
                usage_details = []
                for ref in refs:
                    line_num = ref.get('line', 'N/A')
                    snippet = ref.get('snippet', 'N/A')
                    usage_details.append(f"L{line_num}: {snippet}")
                
                # 显示所有使用位置
                lines.append(f"       使用位置: {len(refs)} 处")
                for detail in usage_details:
                    lines.append(f"         • {detail}")
                
                # 使用第一个引用的说明
                lines.append(f"       说明: {refs[0].get('detail', 'N/A')}")
                lines.append("")
        
        # 格式化 API 调用（按文件分组）
        if api_calls_by_file:
            lines.append("  ▶ API 调用:")
            for file_idx, (file_path, calls) in enumerate(api_calls_by_file.items(), 1):
                lines.append(f"    {file_idx}. 文件: {file_path}")
                
                # 收集所有 API 和调用位置
                api_details = []
                for call in calls:
                    api = call.get('api', 'Unknown')
                    line_num = call.get('line', 'N/A')
                    snippet = call.get('snippet', 'N/A')
                    method_signature = call.get('method_signature', '')  # 新增：获取方法签名
                    
                    # 如果有方法签名，添加到详情中
                    if method_signature:
                        api_details.append(f"{api} (方法签名: {method_signature}) @ L{line_num}: {snippet}")
                    else:
                        api_details.append(f"{api} @ L{line_num}: {snippet}")
                
                # 显示所有 API 调用
                lines.append(f"       调用位置: {len(calls)} 处")
                for detail in api_details:
                    lines.append(f"         • {detail}")
                
                # 使用第一个调用的说明
                lines.append(f"       说明: {calls[0].get('detail', 'N/A')}")
                lines.append("")
        
        # 格式化方法调用影响（按文件分组）
        if method_calls_by_file:
            lines.append("  ▶ 方法调用影响（受影响的中间层方法）:")
            for file_idx, (file_path, calls) in enumerate(method_calls_by_file.items(), 1):
                lines.append(f"    {file_idx}. 文件: {file_path}")
                
                # 收集所有方法调用
                method_details = []
                for call in calls:
                    caller_class = call.get('caller_class', 'Unknown')
                    caller_method = call.get('caller_method', 'Unknown')
                    method_signature = call.get('method_signature', '')  # 新增：获取方法签名
                    line_num = call.get('line', 'N/A')
                    snippet = call.get('snippet', 'N/A')
                    
                    # 如果有方法签名，使用方法签名；否则使用方法名
                    if method_signature:
                        method_details.append(f"{caller_class}.{method_signature} @ L{line_num}: {snippet}")
                    else:
                        method_details.append(f"{caller_class}.{caller_method} @ L{line_num}: {snippet}")
                
                # 显示所有方法调用
                lines.append(f"       受影响方法: {len(calls)} 个")
                for detail in method_details:
                    lines.append(f"         • {detail}")
                
                # 使用第一个调用的说明
                lines.append(f"       说明: {calls[0].get('detail', 'N/A')}")
                lines.append("")
        
        lines.append("-" * 80)
        lines.append("")
    
    return "\n".join(lines)


def call_deepseek_api(messages):
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


def analyze_with_llm(filename, diff_content, root_dir, task_id=None, base_ref=None, target_ref=None, tracer=None, scan_roots=None, update_task_log=None, print_code_comparison=None, get_project_structure=None, extract_api_info=None, search_api_usages=None, extract_changed_methods=None, extract_controller_params=None, refine_report_with_static_analysis=None):
    # 导入必要的函数（如果没有传入）
    if print_code_comparison is None:
        from .report_generator import print_code_comparison
    if update_task_log is None:
        from .utils import update_task_log
    if get_project_structure is None:
        from .code_analyzer import get_project_structure
    if extract_api_info is None:
        from .code_analyzer import extract_api_info
    if search_api_usages is None:
        from .code_analyzer import search_api_usages
    if extract_changed_methods is None:
        from .code_analyzer import extract_changed_methods
    if extract_controller_params is None:
        from .code_analyzer import extract_controller_params
    if refine_report_with_static_analysis is None:
        from .report_generator import refine_report_with_static_analysis
    
    print_code_comparison(diff_content, base_ref, target_ref)
    project_structure = get_project_structure(root_dir)
    api_info_list = extract_api_info(diff_content)
    downstream_callers = []
    
    if api_info_list:
        for api_info in api_info_list:
            callers = search_api_usages(root_dir, api_info, filename)
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
    update_task_log(task_id, f"[Link Analysis] 发现 {len(downstream_callers)} 个潜在下游调用点。\n{downstream_info}")
    
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
                update_task_log(task_id, f"[Static Analysis] 静态分析上下文获取成功。\n{static_context.strip()}")
            
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
        update_task_log(task_id, f"[Warning] Static analysis skipped: {e}")

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
        update_task_log(task_id, f"[Link Analysis] 检测到 {count} 个同服务内部调用。")
    
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
    update_task_log(task_id, f"[Link Analysis] 发现 {len(downstream_callers)} 个潜在跨服务调用点。\n{downstream_info}")

    # --- 任务 8.1: 提取变更的类和方法 ---
    full_class_name = None
    simple_class_name = None
    changed_methods = []
    
    if filename.endswith(".java"):
        try:
            console.print(f"[Info] 正在提取变更的类和方法...", style="bold blue")
            update_task_log(task_id, f"[Class/Method Extraction] 开始提取变更的类和方法...")
            full_path = os.path.join(root_dir, filename)
            
            # 1. 使用 LightStaticAnalyzer 解析 Java 文件，提取完全限定类名
            if os.path.exists(full_path):
                logger.info(f"正在解析 Java 文件: {filename}")
                analyzer = LightStaticAnalyzer(root_dir)
                full_class_name, simple_class_name, _ = analyzer.parse_java_file(full_path)
                
                if full_class_name:
                    console.print(f"[Info] 提取到完全限定类名: {full_class_name}", style="green")
                    update_task_log(task_id, f"[Class Extraction] 提取到类名: {full_class_name}")
                    logger.info(f"成功提取类名: {full_class_name}")
                else:
                    # 如果解析失败，使用文件名作为简单类名
                    simple_class_name = os.path.basename(filename).replace(".java", "")
                    console.print(f"[Warning] 无法解析类名，使用文件名: {simple_class_name}", style="yellow")
                    logger.warning(f"无法解析类名，使用文件名: {simple_class_name}")
                    update_task_log(task_id, f"[Class Extraction] 警告：无法解析类名，使用文件名: {simple_class_name}")
            else:
                simple_class_name = os.path.basename(filename).replace(".java", "")
                logger.warning(f"文件不存在: {full_path}")
            
            # 2. 提取变更的方法列表（使用现有的 extract_changed_methods 方法）
            logger.info(f"正在提取变更的方法...")
            changed_methods = extract_changed_methods(diff_content, full_path, project_root=root_dir)
            console.print(f"[Info] 识别到的变更方法: {changed_methods}", style="green")
            update_task_log(task_id, f"[Method Extraction] 识别到 {len(changed_methods)} 个变更方法: {', '.join(changed_methods)}")
            logger.info(f"成功提取 {len(changed_methods)} 个变更方法: {changed_methods}")
            
        except Exception as e:
            console.print(f"[yellow]提取类和方法失败: {e}[/yellow]")
            logger.error(f"提取类和方法失败: {e}", exc_info=True)
            update_task_log(task_id, f"[Warning] 提取类和方法失败: {e}")
            # 使用文件名作为后备
            simple_class_name = os.path.basename(filename).replace(".java", "")
    elif filename.endswith(".xml"):
        # XML 文件（MyBatis Mapper）
        try:
            logger.info(f"正在处理 XML 文件: {filename}")
            update_task_log(task_id, f"[Method Extraction] 开始提取 XML 文件的变更方法...")
            full_path = os.path.join(root_dir, filename)
            changed_methods = extract_changed_methods(diff_content, full_path, project_root=root_dir)
            simple_class_name = os.path.basename(filename).replace(".xml", "")
            console.print(f"[Info] XML 文件识别到的变更方法 (SQL ID): {changed_methods}", style="green")
            update_task_log(task_id, f"[Method Extraction] XML 文件识别到 {len(changed_methods)} 个变更方法: {', '.join(changed_methods)}")
            logger.info(f"XML 文件成功提取 {len(changed_methods)} 个变更方法: {changed_methods}")
        except Exception as e:
            console.print(f"[yellow]提取 XML 方法失败: {e}[/yellow]")
            logger.error(f"提取 XML 方法失败: {e}", exc_info=True)
            update_task_log(task_id, f"[Warning] 提取 XML 方法失败: {e}")
            simple_class_name = os.path.basename(filename).replace(".xml", "")

    # --- 任务 8.2: 调用跨项目影响查找 ---
    cross_project_impacts = []
    cross_project_impacts_formatted = ""
    
    # 检查是否为多项目模式（tracer 是否为 MultiProjectTracer 实例）
    from .multi_project_tracer import MultiProjectTracer
    if isinstance(tracer, MultiProjectTracer) and full_class_name and changed_methods:
        try:
            console.print(f"[Info] 正在执行跨项目影响分析...", style="bold magenta")
            logger.info(f"开始跨项目影响分析 - 类: {full_class_name}, 方法: {changed_methods}")
            update_task_log(task_id, f"[Cross-Project Analysis] 开始跨项目影响分析...")
            update_task_log(task_id, f"  - 目标类: {full_class_name}")
            update_task_log(task_id, f"  - 变更方法: {', '.join(changed_methods)}")
            
            # 获取关联项目数量
            related_projects = tracer.get_related_project_roots()
            logger.info(f"将扫描 {len(related_projects)} 个关联项目")
            update_task_log(task_id, f"  - 关联项目数量: {len(related_projects)}")
            
            # 调用 tracer.find_cross_project_impacts
            cross_project_impacts = tracer.find_cross_project_impacts(
                full_class_name,
                changed_methods
            )
            
            if cross_project_impacts:
                console.print(f"[Success] 发现 {len(cross_project_impacts)} 个跨项目影响", style="bold green")
                logger.info(f"跨项目影响分析完成 - 发现 {len(cross_project_impacts)} 个影响")
                update_task_log(task_id, f"[Cross-Project Analysis] 发现 {len(cross_project_impacts)} 个跨项目影响")
                
                # 统计影响类型
                class_refs = sum(1 for i in cross_project_impacts if i.get('type') == 'class_reference')
                api_calls = sum(1 for i in cross_project_impacts if i.get('type') == 'api_call')
                method_calls = sum(1 for i in cross_project_impacts if i.get('type') == 'method_call')
                logger.info(f"  - 类引用: {class_refs} 个")
                logger.info(f"  - API 调用: {api_calls} 个")
                logger.info(f"  - 方法调用: {method_calls} 个")
                update_task_log(task_id, f"  - 类引用: {class_refs} 个, API 调用: {api_calls} 个, 方法调用: {method_calls} 个")
                
                # --- 任务 8.3: 格式化跨项目影响信息 ---
                logger.info("正在格式化跨项目影响信息...")
                cross_project_impacts_formatted = format_cross_project_impacts(cross_project_impacts)
                logger.info("跨项目影响信息格式化完成")
                
                # 显示格式化后的跨项目影响
                console.print(Panel(
                    cross_project_impacts_formatted,
                    title="Cross-Project Impact Analysis",
                    border_style="magenta",
                    expand=False
                ))
                
                # 记录到任务日志
                update_task_log(task_id, f"[Cross-Project Analysis]\n{cross_project_impacts_formatted}")
            else:
                console.print(f"[Info] 未发现跨项目影响", style="dim")
                logger.info("跨项目影响分析完成 - 未发现影响")
                update_task_log(task_id, f"[Cross-Project Analysis] 未发现跨项目影响")
                cross_project_impacts_formatted = "未检测到跨项目影响。"
                
        except Exception as e:
            console.print(f"[red]跨项目影响分析失败: {e}[/red]")
            logger.error(f"跨项目影响分析失败: {e}", exc_info=True)
            update_task_log(task_id, f"[Error] 跨项目影响分析失败: {e}")
            update_task_log(task_id, f"  - 错误详情: {str(e)}")
            cross_project_impacts_formatted = f"跨项目影响分析失败: {e}"
            # 继续执行，不中断分析流程
    elif isinstance(tracer, MultiProjectTracer):
        console.print(f"[Info] 跳过跨项目分析：未提取到类名或方法", style="dim")
        logger.warning(f"跳过跨项目分析 - 类名: {full_class_name}, 方法: {changed_methods}")
        update_task_log(task_id, f"[Cross-Project Analysis] 跳过：未提取到类名或方法")
        cross_project_impacts_formatted = "未检测到跨项目影响（未提取到类名或方法）。"

    # --- ApiUsageTracer Integration (New) ---
    affected_api_endpoints = []
    if filename.endswith(".java") or filename.endswith(".xml"):
        try:
            console.print(f"[Info] 正在执行深度 API 链路追踪 (ApiUsageTracer)...", style="bold blue")
            # Use passed tracer or create new one
            # 如果是 MultiProjectTracer，使用主项目的 tracer
            if isinstance(tracer, MultiProjectTracer):
                main_project_root = tracer.get_main_project_root()
                if main_project_root and main_project_root in tracer.tracers:
                    current_tracer = tracer.tracers[main_project_root]
                else:
                    current_tracer = ApiUsageTracer(root_dir)
            else:
                current_tracer = tracer if tracer else ApiUsageTracer(root_dir)
            
            # Use the extracted class name and methods
            if not simple_class_name:
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
                api = item.get('api')
                caller_class = item.get('caller_class')
                caller_method = item.get('caller_method')
                method_signature = item.get('method_signature', caller_method)  # 使用完整方法签名
                
                # 格式化输出，包含方法签名
                lines.append(f"- {api}")
                lines.append(f"  Controller: {caller_class}.{method_signature}")
                lines.append(f"  调用链: Controller → Service/Manager")
            else:
                lines.append(f"- {item}")
        affected_apis_str = "\n".join(lines)
        
        # Extract Controller parameters if this is an internal method change
        # Check if current file is a Service/Manager/Mapper (not a Controller)
        is_internal_method = filename.endswith(".java") and not any(
            keyword in filename.lower() for keyword in ["controller", "provider", "rest"]
        )
        
        if is_internal_method and affected_api_endpoints:
            controller_params_info = extract_controller_params(affected_api_endpoints, root_dir)
        
        console.print(Panel(f"[bold green]深度追踪发现受影响 API:[/bold green]\n{affected_apis_str}", title="Deep API Trace", border_style="green"))
        update_task_log(task_id, f"[Deep API Trace] 深度追踪发现受影响 API:\n{affected_apis_str}")
        
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

    # --- 任务 8.4: 集成到 downstream_info ---
    # 将格式化的跨项目影响添加到 downstream_info 字符串
    if cross_project_impacts_formatted and cross_project_impacts_formatted != "未检测到跨项目影响。":
        logger.info("正在将跨项目影响信息集成到 AI 分析上下文...")
        
        # 如果已有 downstream_info，添加分隔符
        if downstream_info and downstream_info not in ["未检测到明显的跨服务调用引用。", "未检测到明显的调用引用。"]:
            downstream_info += "\n\n" + "=" * 80 + "\n"
            logger.info("已有 downstream_info，添加分隔符")
        else:
            downstream_info = ""
            logger.info("初始化 downstream_info")
        
        # 添加跨项目影响信息
        downstream_info += "\n【跨项目影响分析】\n"
        downstream_info += cross_project_impacts_formatted
        
        console.print(f"[Info] 跨项目影响信息已集成到 AI 分析上下文", style="green")
        logger.info("跨项目影响信息已成功集成到 AI 分析上下文")
        update_task_log(task_id, f"[Cross-Project Analysis] 跨项目影响信息已集成到 AI 分析上下文")
        update_task_log(task_id, f"  - 跨项目影响信息长度: {len(cross_project_impacts_formatted)} 字符")
    else:
        logger.info("无跨项目影响信息需要集成")

    console.print(f"\n[AI Analysis] 正在使用 DeepSeek ({DEEPSEEK_MODEL}) 分析 {filename} ...", style="bold magenta")
    update_task_log(task_id, f"[AI Analysis] 正在请求 AI 分析...")
    
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
    
    ## 参数提取规则（严格遵守，按优先级执行）
    
    ### 优先级 1：从 Git Diff 中提取（如果 Controller 代码在本次变更中）
    1. 定位到 Controller 方法（带有 @GetMapping/@PostMapping/@PutMapping/@DeleteMapping 注解）
    2. 提取方法参数及其注解：
       - `@PathVariable`：参数在 URL 路径中（如 `/{{orderId}}`）
       - `@RequestParam`：参数通过 Query String 或 Form Data 传递
       - `@RequestBody`：参数通过 JSON Body 传递
    3. **严禁**从 Service 层或其他非 Controller 方法推断参数
    
    ### 优先级 2：使用系统提供的参数信息（如果 Controller 代码不在 Diff 中）
    1. 检查上述 "Controller 参数信息" 部分是否存在
    2. 如果有，**必须直接使用**其中的参数名和类型，**严禁**修改或推测
    3. 如果没有，执行优先级 3
    
    ### 优先级 3：从 [Deep API Trace] 推断（如果系统未提供参数信息）
    1. 查看 [Deep API Trace] 中提到的 Controller 文件路径
    2. 从调用链信息推断 Controller 类和方法
    3. 如果确实无法确定参数，Payload 标注为："参数待确认（建议查看 Controller 代码）"
    
    ### 关键约束
    1. **严禁**从 Service/Manager/Mapper 层方法推断 Controller 参数
    2. **严禁**编造不存在的参数
    3. **严禁**混淆 @PathVariable 和 @RequestParam
    4. 如果方法没有 @RequestParam 或 @RequestBody 参数，Payload 留空或标注"无参数"
    
    ### 示例
    - ✅ 正确：`@GetMapping("/{{orderId}}")` + `@PathVariable Long orderId` → Payload: 无（orderId 已在 URL 中）
    - ❌ 错误：从 `createOrder(Long userId, String productName, BigDecimal amount)` 推断 `getOrder` 的参数
    
    ## 参数格式规范（严格遵守）
    
    ### 规则 1：@PathVariable（路径参数）
    - **定义**：参数在 URL 路径中（如 `/{{orderId}}`）
    - **Payload**：无（参数已在 URL 中，不需要在 Payload 中重复）
    - **示例**：
      - 代码：`@GetMapping("/{{orderId}}")` + `@PathVariable Long orderId`
      - URL：`GET /api/orders/123`
      - Payload：无
    
    ### 规则 2：@RequestParam（查询参数）
    - **定义**：参数通过 Query String 或 Form Data 传递
    - **适用于**：所有 HTTP 方法（GET/POST/PUT/DELETE）
    - **Payload 格式**：`?key1=value1&key2=value2`
    - **示例**：
      - 代码：`@GetMapping("/status")` + `@RequestParam String orderId`
      - URL：`GET /api/orders/status?orderId=12345`
      - Payload：`?orderId=12345`
      
      - 代码：`@PostMapping("/order")` + `@RequestParam Long userId, @RequestParam String orderNumber`
      - URL：`POST /api/notifications/order?userId=789&orderNumber=ORD-12345`
      - Payload：`?userId=789&orderNumber=ORD-12345`
    
    ### 规则 3：@RequestBody（请求体参数）
    - **定义**：参数通过 JSON Body 传递
    - **适用于**：POST/PUT 方法
    - **Payload 格式**：`{{"key1": "value1", "key2": "value2"}}`
    - **示例**：
      - 代码：`@PostMapping("/create")` + `@RequestBody OrderDTO dto`
      - URL：`POST /api/orders/create`
      - Payload：`{{"userId": 123, "productName": "Product A", "amount": 100.00}}`
    
    ### 规则 4：混合参数
    - **定义**：同时使用 @PathVariable、@RequestParam、@RequestBody
    - **示例**：
      - 代码：`@PutMapping("/{{orderId}}/status")` + `@PathVariable Long orderId, @RequestParam Integer status`
      - URL：`PUT /api/orders/123/status?status=1`
      - Payload：`?status=1`（orderId 已在 URL 中）
    
    ### 关键约束
    1. **@PathVariable 不需要在 Payload 中重复**
    2. **@RequestParam 始终使用 Query String 格式**（无论 GET/POST/PUT/DELETE）
    3. **@RequestBody 始终使用 JSON Body 格式**（仅 POST/PUT）
    4. **严禁**将 @RequestParam 误写为 JSON Body 格式
    5. **严禁**将 @RequestBody 误写为 Query String 格式

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
    
    禁止使用"可能"、"如果"等模棱两可的词汇，必须使用"确定"、"必挂"等强语气词汇来警示开发人员。

    ## 代码逻辑分析要求（严格遵守）
    
    ### 规则 1：追踪方法调用链
    1. 对于状态变更类方法（如 updateStatus、cancelOrder、activate），**必须**追踪到最终的状态值
    2. 示例：
       - 代码：`cancelOrder(orderId)` → 调用 `updateOrderStatus(orderId, 2)`
       - 结论：取消状态码是 **2**，不是 0
    3. 验证点必须基于实际代码逻辑，**严禁**推测
    
    ### 规则 2：识别硬编码值
    1. 如果方法内部硬编码了某些值（如状态码、常量），**必须**提取这些值
    2. 示例：
       - 代码：`order.setStatus(1); // 1 = 已支付`
       - 结论：订单状态码 1 表示"已支付"
    3. 测试用例的验证点必须使用这些硬编码值
    
    ### 规则 3：分析方法参数与内部逻辑的关系
    1. 如果方法没有某个参数，**严禁**在 Payload 中添加该参数
    2. 示例：
       - 代码：`cancelOrder(Long orderId)` → 内部调用 `updateOrderStatus(orderId, 2)`
       - 结论：`cancelOrder` 方法不需要 `status` 参数，状态码由方法内部决定
    3. Payload 只包含方法签名中的参数
    
    ### 规则 4：识别业务规则变更
    1. 对比 Git Diff 中的 `+` 和 `-` 行，识别业务规则的变更
    2. 示例：
       - 变更前：`order.setStatus(0);`
       - 变更后：`order.setStatus(1);`
       - 结论：订单默认状态从"待支付"改为"已支付"
    3. 测试用例必须覆盖这些业务规则变更
    
    ### 关键约束
    1. **严禁**仅根据方法名推测逻辑（如看到 `cancelOrder` 就认为状态码是 0）
    2. **必须**追踪方法调用链，找到最终的状态值
    3. **必须**提取硬编码值，用于测试验证点
    
    ## 方法重载识别规则（严格遵守）
    
    ### 规则 1：识别重载方法
    1. 如果同一个类中存在多个同名方法（参数不同），这些方法是**重载方法**
    2. 示例：
       ```java
       // 方法 1
       public String sendOrderNotification(Long userId, String orderNumber) {{
           // 只调用 getUserById
       }}
       
       // 方法 2（重载）
       public String sendOrderNotification(Long orderId) {{
           // 调用 getOrderById ✓
       }}
       ```
    3. **必须**识别每个重载方法的实现逻辑，选择正确的方法进行测试
    
    ### 规则 2：选择正确的重载方法
    1. 根据测试目标，选择能触发目标逻辑的重载方法
    2. 示例：
       - 测试目标：验证 `getOrderById` 方法的兼容性
       - 正确选择：`sendOrderNotification(Long orderId)`（会调用 `getOrderById`）
       - 错误选择：`sendOrderNotification(Long userId, String orderNumber)`（不会调用 `getOrderById`）
    
    ### 规则 3：匹配 HTTP 接口与重载方法
    1. 如果重载方法有对应的 HTTP 接口，使用 HTTP 接口测试
    2. 如果重载方法没有对应的 HTTP 接口，使用单元测试
    3. **关键**：使用 [Deep API Trace] 中提供的方法签名信息来精确匹配
    4. 示例：
       - `sendOrderNotification(Long userId, String orderNumber)` → 有接口：`POST /api/notifications/order`
       - `sendOrderNotification(Long orderId)` → 无接口 → 使用单元测试
    
    ### 规则 3.1：使用 Deep API Trace 或 Cross-Project Impact Analysis 的方法签名验证（重要）
    1. [Deep API Trace] 和 [Cross-Project Impact Analysis] 会提供完整的方法签名，格式如：
       ```
       - POST /api/notifications/order (方法签名: sendOrderNotification(Long, String))
         Controller: NotificationController.sendOrderNotification(Long, String)
         调用链: Controller → Service/Manager
       ```
    2. **必须**根据方法签名中的参数类型来判断调用的是哪个重载方法
    3. **方法签名格式说明**：
       - `sendOrderNotification(Long, String)` 表示两个参数：第一个是 Long 类型，第二个是 String 类型
       - `sendOrderNotification(Long)` 表示一个参数：Long 类型
       - 参数类型的顺序和数量必须完全匹配
    4. 示例分析：
       - 方法签名：`sendOrderNotification(Long, String)` 
       - 参数类型：`Long userId, String orderNumber`
       - 结论：调用的是 `sendOrderNotification(Long userId, String orderNumber)` 方法
       - 验证：检查这个方法的实现，确认是否会调用目标方法（如 `getOrderStatusText`）
       - 如果该方法**不会**调用目标方法，则该 API 接口**不适合**用于测试目标方法
    5. **严禁**假设会调用其他重载方法，必须基于实际的方法签名判断
    6. **关键判断流程**：
       a. 查看 [Deep API Trace] 或 [Cross-Project Impact Analysis] 中的方法签名
       b. 根据方法签名确定调用的是哪个重载方法
       c. 检查该重载方法的实现，确认是否会调用目标方法
       d. 如果不会调用目标方法，说明该 API 接口不适合用于测试，需要使用其他方式
    
    ### 规则 4：明确说明测试方式
    1. 如果使用 HTTP 接口测试，提供完整的 URL、HTTP 方法、Payload
    2. 如果使用单元测试，提供 Java 方法调用示例
    3. 示例：
       - HTTP 接口测试：`POST /api/notifications/order?userId=789&orderNumber=ORD-12345`
       - 单元测试：`notificationService.sendOrderNotification(123L)`
    
    ### 关键约束
    1. **严禁**混淆不同的重载方法
    2. **必须**根据测试目标选择正确的重载方法
    3. **必须**明确说明测试方式（HTTP 接口 vs 单元测试）
    
    ## 跨服务测试路径生成规则（严格遵守）
    
    ### 规则 1：验证 HTTP 接口与目标方法的匹配关系
    1. **关键原则**：只有当 HTTP 接口调用的方法**会触发目标逻辑**时，才能使用该接口进行测试
    2. **验证步骤**：
       a. 查看 [Cross-Project Impact Analysis] 中的 API 调用信息
       b. 检查该 API 的**方法签名**
       c. 根据方法签名判断调用的是哪个重载方法
       d. 检查该重载方法的实现，确认是否会调用目标方法
       e. **如果不会调用目标方法，则该 API 不适合用于测试**
    
    3. **示例场景**：
       - 测试目标：验证 `service-b` 调用 `service-a` 的 `getOrderStatusText` 方法
       - [Cross-Project Impact Analysis] 显示：
         * API: `POST /api/notifications/order` (方法签名: `sendOrderNotification(Long, String)`)
         * 方法调用: `NotificationService.sendOrderNotification(Long)` @ L118 调用了 `getOrderStatusText`
       - **分析**：
         * `POST /api/notifications/order` 调用的是 `sendOrderNotification(Long, String)` 方法
         * 但真正调用 `getOrderStatusText` 的是 `sendOrderNotification(Long)` 方法
         * 这两个是**不同的重载方法**
       - **结论**：`POST /api/notifications/order` **不适合**用于测试 `getOrderStatusText` 的跨服务调用
       - **正确做法**：生成说明性测试用例，指出需要单元测试或新增接口
    
    ### 规则 2：生成说明性测试用例（当 HTTP 接口不适用时）
    1. **适用场景**：
       - 目标方法没有对应的 HTTP 接口
       - 或者 HTTP 接口调用的是错误的重载方法
    
    2. **测试用例格式**：
       - title: "跨服务调用测试 - [目标方法] (需要单元测试或新增接口)"
       - priority: "P0"
       - steps: "说明：[目标方法] 会调用 [跨服务方法]，但该方法没有对应的 HTTP 接口。建议：1. 使用单元测试直接调用 [目标方法]；2. 或在 Controller 中新增接口暴露该方法。"
       - payload: "单元测试示例：notificationService.sendOrderNotification(123L)"
       - validation: "验证 [跨服务方法] 被正确调用，且返回预期结果。"
    
    3. **具体示例**：
       - title: "跨服务调用测试 - NotificationService.sendOrderNotification(Long) (需要单元测试或新增接口)"
       - priority: "P0"
       - steps: "说明：NotificationService.sendOrderNotification(Long orderId) 方法会调用 service-a 的 getOrderStatusText 接口，但该方法没有对应的 HTTP 接口（现有的 POST /api/notifications/order 接口调用的是另一个重载方法 sendOrderNotification(Long, String)，不会触发跨服务调用）。建议：1. 使用单元测试直接调用 notificationService.sendOrderNotification(123L)；2. 或在 NotificationController 中新增接口，如 POST /api/notifications/order-by-id?orderId=123。"
       - payload: "单元测试示例：notificationService.sendOrderNotification(123L)"
       - validation: "验证 service-a 的 GET /api/orders/{{orderId}}/status-text 接口被正确调用，且返回的状态描述（如 '待支付'）被正确使用。"
    
    ### 规则 3：严禁生成错误的 HTTP 接口测试用例
    1. **严禁**使用不会触发目标逻辑的 HTTP 接口进行测试
    2. **严禁**假设 HTTP 接口会调用其他重载方法
    3. **必须**基于实际的方法签名判断
    
    ### 规则 4：处理没有 HTTP 接口的内部方法
    1. 如果目标方法没有对应的 HTTP 接口（如 Service/Manager 层方法），使用以下测试方式：
       - **方式 1（推荐）**：单元测试（直接调用 Java 方法）
       - **方式 2**：建议新增 HTTP 接口
    2. 示例：
       - 目标方法：`NotificationService.sendOrderNotification(Long orderId)`（无 HTTP 接口）
       - 方式 1：单元测试 `notificationService.sendOrderNotification(123L)`
       - 方式 2：建议新增接口 `POST /api/notifications/order-by-id?orderId=123`
       - 正确选择：`sendOrderNotification(Long orderId)`（会调用 `userClient.getOrderById`）
       - 错误选择：`sendOrderNotification(Long userId, String orderNumber)`（不会调用 `getOrderById`）
    
    ### 规则 4：明确测试步骤
    1. 对于单元测试，提供 Java 方法调用示例
    2. 对于集成测试，提供完整的 HTTP 接口调用步骤
    3. 对于跨服务测试，说明调用链路（如 service-b → service-a）
    
    ### 关键约束
    1. **严禁**编造不存在的 HTTP 接口
    2. **必须**验证接口是否存在
    3. **必须**根据方法是否有 HTTP 接口选择测试方式（HTTP 接口 vs 单元测试）
    4. **必须**明确说明测试步骤和调用链路
    
    ## 核心规则（必须严格遵守）
    1. 分析"跨服务影响"时，**仅基于** `Cross-Service Impact` 列表中的服务，禁止扩展至列表外的服务；
    2. 严禁混淆「上游依赖」和「下游受影响方」：
    - 示例1：本服务调用 `PointClient`（本服务→Point服务）→ Point服务是上游依赖，本服务变更不会影响Point服务（除非修改了调用Point服务的接口入参）；
    - 示例2：`Cross-Service Impact` 列表包含「Order服务」→ Order服务调用本服务，本服务变更会影响Order服务（下游受影响方）；
    3. 分析"下游依赖/影响功能"时，仅使用【项目包含的真实服务模块列表】中的服务名称，禁止编造；
    4. 若 `Cross-Service Impact` 无跨服务调用（仅内部调用/无），`cross_service_impact` 字段填"无"；
    5. 禁止直接复制模板值，所有内容需基于实际代码变更填充；
    6. 风险等级判定规则：
    - 严重：导致核心业务中断（如转账资金不一致）、数据丢失、大面积服务不可用；
    - 高：影响核心功能正确性（如积分计算错误），需紧急修复；
    - 中：影响非核心功能（如日志打印异常），不影响主流程；
    - 低：仅格式/注释变更，无功能影响；
    7. 字段无数据时的兜底规则：
    - line_number/call_snippet 无数据 → 填"无"；
    - affected_apis 无受影响API → 数组留空（[]）；
    - downstream_dependency 无依赖 → 数组留空（[]）。

    ## 字段约束（必须严格遵守）
    ### 1. functional_impact 字段
    必须是结构化JSON对象（非字符串），每个子字段需满足：
    - business_scenario：具体到"触发条件+业务动作+结果"，禁止笼统描述（如禁止"转账业务"，需写"用户发起账户间转账且金额≥1000元时，系统新增风控预校验流程，校验不通过则拒绝转账"）；
    - data_flow：按步骤详细描述数据流转过程，必须使用序号（1. 2. 3.）分步说明，禁止使用箭头（→）简单连接。每一步需包含：涉及的方法/组件、关键逻辑判断、数据变更（如字段状态变化）。示例："1. 用户调用 /api/transfer 接口，传入 amount=100... 2. TransferController 接收请求，调用 UserManager.initiateTransfer()... 3. 校验余额充足后，扣减 A 账户余额..."）；
    - api_impact：详细分析API及方法层面的影响。需包含：1. 具体变更的方法及其内部逻辑变化（如"UserManager.initiateTransfer方法内部逻辑变更，新增了对PointClient.addPoint的调用"）；2. 该变更带来的额外业务影响/连带变更（禁止使用"副作用"一词，需直白描述，如"在转账成功的同时，系统将额外自动执行积分增加操作"）；3. 接口契约（URL、参数、返回值）是否发生物理变更；4. 若涉及跨服务调用，明确说明作为调用方的影响（如"不影响下游服务接口契约，但引入了新的依赖"）。禁止简单一句话描述。
    - risks：必须返回一个详细的字符串数组，每项代表一个具体的风险点。格式要求：使用 "**风险类别**: 详细描述" 的形式。**建议考虑（但不限于）以下维度，请根据实际变更灵活调整**：**数据一致性**（如分布式事务）、**幂等性**、**性能影响**（RT增加）、**可用性**（依赖风险）、**错误处理**（回滚/补偿）、**安全风险**、**兼容性**。示例："**数据一致性**: 若 pointClient 调用超时，本地事务已提交，导致数据不一致..."。禁止简单的单行描述。
    - entry_points：列出代码/接口层面的具体入口（如"API Endpoint: POST /api/v1/user/transfer"、"Java方法: com.user.service.TransferService.initiateTransfer(String fromUserId, String toUserId, BigDecimal amount)"）。

    ### 2. 其他字段约束
    - business_rules：**这是测试人员验收的核心依据**。请识别代码逻辑变化，并**以对比表格形式**呈现。
      - 目标：清晰展示"变更前 vs 变更后"的业务规则差异，消除测试人员的脑补成本。
      - 格式：对象数组，每个对象包含：
        - `scenario`: 业务场景（如"普通用户积分上限"、"VIP奖金策略"）。
        - `old_rule`: 变更前的规则（如"2000分"、"无限制"、"N/A (新增)"）。
        - `new_rule`: 变更后的规则（如"3000分"、">10000 拒绝"）。
        - `impact`: 变更带来的具体影响（如"⬆️ 额度提升"、"🛡️ 新增风控"、"⚠️ 需人工审核"）。
        - `related_file`: 关联文件名。
      - **关键要求**：
        1. **必须包含数值对比**：如果涉及阈值变化，必须写出具体数字（如 2000 -> 3000）。
        2. **针对新增规则**：`old_rule` 填 "无 (新增逻辑)"，`new_rule` 填具体规则。
        3. **针对删除规则**：`old_rule` 填具体规则，`new_rule` 填 "已移除"。
        4. **禁止笼统描述**：不要写"修改了逻辑"，要写"从同步执行改为异步执行"。

    - code_review_warning：从"代码规范、性能、安全、兼容性、事务一致性"维度分析（如"转账方法未加幂等校验，可能导致重复扣减余额"）；
    - change_intent：变更详情。请返回一个对象数组，每个对象包含 "summary"（核心变更点）和 "details"（详细说明列表）。
      - **details 要求**：必须深入到**代码实现层面**。不要只说"优化了性能"，要说"将同步锁 `synchronized` 替换为 `ReentrantLock` 以提升高并发下的吞吐量"。不要只说"增加了日志"，要说"在 `catch` 块中增加了 `log.error` 打印堆栈信息"。
    - affected_apis：仅列出本次变更直接影响的API，包含method/url/description，无则留空数组；
    - downstream_dependency：仅列出`Cross-Service Impact`中的服务，字段需精准（如caller_method需包含参数类型，如"transfer(String, BigDecimal)"）；
    - test_strategy：payload示例需贴合代码变更的真实参数，标注必填/选填，验证点需可量化。
      - **关键要求（测试步骤）**：
        1. **必须黑盒化**：测试人员无法直接"创建DTO"或"调用Java方法"。必须将内部代码逻辑映射为**外部可调用的 HTTP API**。
        2. **如果变更是内部类/DTO**：你必须结合 [Link Analysis] 和 [Deep API Trace] 找到触发该逻辑的上游 API（例如 `POST /ucenter/recharge`）。
        3. **格式要求**：步骤必须写成"调用接口 A -> 传入参数 B -> 验证结果 C"。
        4. **禁止**："模拟业务场景"、"创建实例"、"调用set方法"等开发术语。
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
        
        2. **参数格式必须与 HTTP 方法和注解匹配**：
           - **@PathVariable**：
             * 参数在 URL 路径中（如 `/api/orders/{{orderId}}`）
             * Payload：无（参数已在 URL 中）
             * 测试步骤：`调用 GET /api/orders/123`
             * ❌ 错误：`?orderId=123`（不应使用 Query String）
             * ✅ 正确：URL 中直接包含 `123`
           
           - **@RequestParam + GET/DELETE 请求**：
             * 参数通过 **URL Query String** 传递
             * Payload 格式：`?orderId=12345` 或 `?userId=100&status=active`
             * 测试步骤：`调用 GET /api/path?orderId=12345`
             * ❌ 错误：`{{"orderId": "12345"}}`（JSON Body 格式）
             * ✅ 正确：`?orderId=12345`（Query String 格式）
         
           - **@RequestParam + POST/PUT 请求**：
             * 参数通过 **URL Query String** 或 **Form Data** 传递（不是 JSON Body）
             * Payload 格式：`?key=value` 或 Form Data
             * 测试步骤：`调用 POST /api/path?orderId=12345`
             * ❌ 错误：`{{"orderId": "12345"}}`（JSON Body 格式）
             * ✅ 正确：`?orderId=12345`（Query String 格式）
           
           - **@RequestBody + POST/PUT 请求**：
             * 参数通过 **JSON Body** 传递
             * Payload 格式：`{{"key": "value"}}`（JSON 对象）
             * 测试步骤：`调用 POST /api/path，Body 为 {{"orderId": "12345"}}`
             * ❌ 错误：`?orderId=12345`（Query String 格式）
             * ✅ 正确：`{{"orderId": "12345"}}`（JSON Body 格式）
        
        3. **Payload 示例格式规范**：
           - @PathVariable → 无 Payload（参数在 URL 路径中）
           - GET/DELETE + @RequestParam → `?paramName=value`（Query String）
           - POST/PUT + @RequestParam → `?paramName=value`（Query String，不是 JSON Body）
           - POST/PUT + @RequestBody → `{{"fieldName": "value"}}`（JSON 对象）
           - 必须标注必填/选填：`{{"orderId": "12345" (必填, 示例值)}}`
           - 如果参数在 URL 路径中（@PathVariable），在 steps 中说明，payload 中不重复
        
        4. **验证示例**：
           - 代码：`@GetMapping("/{{orderId}}")` + `@PathVariable Long orderId`
           - ✅ 正确 URL：`GET /api/orders/123`
           - ✅ 正确 Payload：无
           - ❌ 错误 Payload：`?orderId=123`（@PathVariable 不需要 Query String）
           
           - 代码：`@GetMapping("/status")` + `@RequestParam String orderId`
           - ✅ 正确 Payload：`?orderId=12345`（Query String）
           - ❌ 错误 Payload：`{{"orderId": "12345"}}`（GET 请求不应使用 JSON Body）
           
           - 代码：`@PostMapping("/order")` + `@RequestParam Long userId, @RequestParam String orderNumber`
           - ✅ 正确 Payload：`?userId=789&orderNumber=ORD-12345`（Query String）
           - ❌ 错误 Payload：`{{"userId": 789, "orderNumber": "ORD-12345"}}`（@RequestParam 不使用 JSON Body）
           
           - 代码：`@PostMapping("/create")` + `@RequestBody OrderDTO dto`
           - ✅ 正确 Payload：`{{"userId": 123, "amount": 100.00}}`（JSON Body）
           - ❌ 错误 Payload：`?userId=123&amount=100.00`（@RequestBody 不使用 Query String）

    ## 禁止示例（以下回答无效）
    1. functional_impact 字段为字符串："functional_impact": "修改了转账逻辑，可能影响用户系统"；
    2. business_scenario 笼统描述："业务场景：影响转账业务"；
    3. risks 泛泛而谈："风险：可能影响数据一致性"；
    4. business_rules 笼统描述："修改了积分规则"（必须写出具体规则，如"积分获取上限从 1000 调整为 5000"）；
    5. 编造不存在的服务名称："service_name": "PaymentService"（不在项目服务列表中）；
    6. **参数提取错误**：
       - 从 Service 层推断 Controller 参数：
         * 代码：`@GetMapping("/{{orderId}}")` + `@PathVariable Long orderId`
         * ❌ 错误：从 `createOrder(Long userId, String productName, BigDecimal amount)` 推断出 `?userId=456&productName=SampleProduct&amount=100.00`
         * ✅ 正确：无 Payload（orderId 已在 URL 中）
    
    7. **参数格式错误**：
       - @PathVariable 误用 Query String：
         * 代码：`@GetMapping("/{{orderId}}")` + `@PathVariable Long orderId`
         * ❌ 错误 Payload：`?orderId=123`
         * ✅ 正确：无 Payload（参数在 URL 中：`/api/orders/123`）
       
       - @RequestParam 误用 JSON Body：
         * 代码：`@PostMapping("/order")` + `@RequestParam Long userId, @RequestParam String orderNumber`
         * ❌ 错误 Payload：`{{"userId": 789, "orderNumber": "ORD-12345"}}`
         * ✅ 正确 Payload：`?userId=789&orderNumber=ORD-12345`
       
       - @RequestBody 误用 Query String：
         * 代码：`@PostMapping("/create")` + `@RequestBody OrderDTO dto`
         * ❌ 错误 Payload：`?userId=123&amount=100.00`
         * ✅ 正确 Payload：`{{"userId": 123, "amount": 100.00}}`
    
    8. **参数名错误**：
       - 代码：`@RequestParam String orderId` → ❌ 错误 Payload：`{{"rechargeId": "12345"}}`（参数名错误）
       - 代码：`@GetMapping("/status")` + `@RequestParam String orderId` → ❌ 错误 Payload：`{{"orderId": "12345"}}`（GET 请求不应使用 JSON Body，应使用 Query String：`?orderId=12345`）
       - ✅ 正确：从代码中提取准确参数名 `orderId`，GET 请求使用 `?orderId=12345` 格式。
    
    9. **内部方法变更时使用错误的参数**：
       - 变更：`UserService.getUserById(Long id)`（内部方法，无 HTTP 接口）
       - [Deep API Trace] 发现：`GET /api/user/info` 调用了此方法
       - Controller：`@GetMapping("/api/user/info") public Result getUserInfo(@RequestParam String userId)`
       - ❌ 错误 Payload：`{{"id": 123}}`（使用了内部方法的参数 `id`，而不是 Controller 的参数 `userId`）
       - ✅ 正确 Payload：`?userId=456`（使用 Controller 接口的参数 `userId`）
    
    10. **代码逻辑分析错误**：
        - 代码：`cancelOrder(orderId)` → 调用 `updateOrderStatus(orderId, 2)`
        - ❌ 错误验证点：`验证订单状态已更新为 0 (取消)`
        - ✅ 正确验证点：`验证订单状态已更新为 2 (已取消)`
    
    11. **方法重载识别错误**：
        - 场景：存在两个重载方法，需要选择正确的方法进行测试
        - 方法 1：`sendOrderNotification(Long userId, String orderNumber)` → 不会调用 `getOrderStatusText`
        - 方法 2：`sendOrderNotification(Long orderId)` → 会调用 `getOrderStatusText` ✓
        
        **错误示例 A：混淆重载方法**
        - 测试目标：验证 `getOrderStatusText` 方法的跨服务调用
        - ❌ 错误：使用 `POST /api/notifications/order?userId=789&orderNumber=ORD-301` 测试
        - 原因：该接口调用的是方法 1，不会触发 `getOrderStatusText`
        - ✅ 正确：
          * 方式 1：新增接口 `POST /api/notifications/order-by-id?orderId=301` 调用方法 2
          * 方式 2：使用单元测试 `notificationService.sendOrderNotification(301L)`
        
        **错误示例 B：忽略 Deep API Trace 或 Cross-Project Impact Analysis 的方法签名**
        - [Deep API Trace] 或 [Cross-Project Impact Analysis] 显示：
          ```
          - POST /api/notifications/order (方法签名: sendOrderNotification(Long, String))
            Controller: NotificationController.sendOrderNotification(Long, String)
          ```
        - ❌ 错误：假设该接口会调用 `sendOrderNotification(Long orderId)` 方法
        - 原因：方法签名是 `(Long, String)`，明确指出调用的是两参数的重载方法
        - ✅ 正确：根据方法签名 `(Long, String)` 判断调用的是 `sendOrderNotification(Long userId, String orderNumber)`
        - ✅ 正确：检查该方法的实现，发现它不会调用 `getOrderStatusText`，因此该接口不适合用于测试
    
    12. **跨服务测试路径错误**：
        - ❌ 错误：编造不存在的接口 `POST /api/notifications/order-detail`
        - ✅ 正确：验证接口是否存在，如果不存在则使用单元测试
        
        **错误示例：验证点与实际调用不符**
        - 接口：`POST /api/notifications/order?userId=789&orderNumber=ORD-301`
        - 实际调用：`sendOrderNotification(Long userId, String orderNumber)` → 不调用 `getOrderStatusText`
        - ❌ 错误验证点：验证响应包含 "已支付" 状态描述
        - 原因：该方法不会调用 `getOrderStatusText`，响应消息是固定格式，不包含状态描述
        - ✅ 正确：根据实际方法实现生成验证点

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
            "data_flow": "1. 步骤一描述...\\n2. 步骤二描述...",
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
                "payload": "<Payload示例：**如果系统提供了 Controller 参数信息，必须直接使用其中的参数名生成 Payload**。GET/DELETE请求使用Query String格式（如 ?orderId=12345），POST/PUT请求根据@RequestParam或@RequestBody使用对应格式。参数名必须与代码中的变量名完全一致，严禁编造。**严禁写\\"需查看\\"、\\"需确认\\"等提示性文字，必须直接生成实际的 Payload**。标注必填/选填>",
                "validation": "<可量化的验证点>"
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
        console.print(f"[dim]DeepSeek Token Usage: Total {total}[/dim]")
        update_task_log(task_id, f"DeepSeek Token Usage: Total {total}")
        
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
        report_json = refine_report_with_static_analysis(report_json, root_dir)
        
        # Merge multiple line numbers for the same file in downstream_dependency
        report_json = merge_downstream_line_numbers(report_json, cross_project_impacts)
        
        # Inject Usage Info for DB storage
        if usage:
            report_json['_usage'] = usage

        return report_json
    except json.JSONDecodeError as e:
        from analyzer.log_config import log_and_print
        
        # 同时输出到控制台和日志文件
        log_and_print(f"[red]解析 AI 响应失败[/red]", level="ERROR", style="red")
        log_and_print(f"JSON 解析错误: {str(e)}", level="ERROR")
        log_and_print(f"错误位置: 第 {e.lineno} 行, 第 {e.colno} 列", level="ERROR")
        
        # 输出 AI 原始响应内容（分段显示）
        if response_content:
            log_and_print("=" * 80, level="ERROR")
            log_and_print("AI 原始响应内容（前 2000 字符）:", level="ERROR")
            log_and_print(response_content[:2000], level="ERROR")
            
            if len(response_content) > 2000:
                log_and_print("=" * 80, level="ERROR")
                log_and_print("AI 原始响应内容（后 2000 字符）:", level="ERROR")
                log_and_print(response_content[-2000:], level="ERROR")
            
            log_and_print("=" * 80, level="ERROR")
        else:
            log_and_print("AI 响应为空", level="ERROR")
        
        # 更新任务日志
        update_task_log(task_id, f"[Error] JSON 解析失败: {str(e)}")
        update_task_log(task_id, f"[Error] 错误位置: 第 {e.lineno} 行, 第 {e.colno} 列")
        update_task_log(task_id, f"[Error] AI 响应前 500 字符: {response_content[:500] if response_content else '空'}")
        
        return None
