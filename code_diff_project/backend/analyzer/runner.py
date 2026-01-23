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
from analyzer.analysis.frontend_discovery import FrontendProjectDiscovery
from analyzer.analysis.frontend_api_scanner import FrontendApiScanner
from analyzer.analysis.frontend_backend_mapper import FrontendBackendMapper, BackendApi
from analyzer.analysis.test_case_generator import TestCaseGenerator

# 初始化 Rich Console（禁用Unicode字符，避免Windows终端乱码）
console = Console(legacy_windows=True, force_terminal=True)

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
    
    # ===== 前端项目扫描（使用workspace中已存在的代码）=====
    # 注意：前端项目的拉取由 views.py 中的 trigger_analysis 处理
    # 这里只负责扫描 workspace 中已存在的前端项目
    frontend_projects = []
    frontend_api_calls = []
    
    try:
        logger.info("开始扫描workspace中的前端项目...")
        console.print("[Info] 扫描workspace中的前端项目", style="dim")
        update_task_log(task_id, "[Info] 扫描workspace中的前端项目")
        
        # 确定 workspace 路径
        # 如果 project_root 已经在 workspace 目录下（例如：workspace/service-a），使用父目录
        # 否则，使用 project_root/workspace
        if os.path.basename(os.path.dirname(project_root)) == 'workspace':
            workspace_path = os.path.dirname(project_root)
            logger.info(f"检测到 project_root 在 workspace 下，使用父目录: {workspace_path}")
        else:
            workspace_path = os.path.join(project_root, 'workspace')
            logger.info(f"使用 project_root/workspace: {workspace_path}")
        
        discovery = FrontendProjectDiscovery(workspace_path=workspace_path)
        frontend_projects = discovery.discover_projects()
        
        if frontend_projects:
            console.print(f"[bold green]OK[/bold green] 发现 {len(frontend_projects)} 个前端项目", style="green")
            update_task_log(task_id, f"[Info] 发现 {len(frontend_projects)} 个前端项目")
            
            for project in frontend_projects:
                console.print(f"  - {project.name} ({project.framework})", style="dim")
                update_task_log(task_id, f"[Info]   - {project.name} ({project.framework})")
                if project.api_base_url:
                    console.print(f"    API: {project.api_base_url}", style="dim")
            
            # 1.6 扫描前端 API 调用
            logger.info("开始扫描前端 API 调用...")
            console.print("\n[bold blue]扫描前端 API 调用...[/bold blue]")
            update_task_log(task_id, "[Info] 开始扫描前端 API 调用...")
            
            for project in frontend_projects:
                try:
                    scanner = FrontendApiScanner(project.path)
                    calls = scanner.scan_project()
                    frontend_api_calls.extend(calls)
                    
                    console.print(f"  - {project.name}: 发现 {len(calls)} 个 API 调用", style="dim")
                    update_task_log(task_id, f"[Info]   - {project.name}: 发现 {len(calls)} 个 API 调用")
                except Exception as e:
                    logger.warning(f"扫描前端项目 {project.name} 失败: {e}")
                    console.print(f"  - {project.name}: 扫描失败 - {e}", style="yellow")
                    update_task_log(task_id, f"[Warning]   - {project.name}: 扫描失败 - {e}")
            
            if frontend_api_calls:
                console.print(f"[bold green]OK[/bold green] 总共发现 {len(frontend_api_calls)} 个前端 API 调用", style="green")
                update_task_log(task_id, f"[Info] 总共发现 {len(frontend_api_calls)} 个前端 API 调用")
            else:
                console.print("[yellow]未发现前端 API 调用[/yellow]", style="dim")
                update_task_log(task_id, "[Info] 未发现前端 API 调用")
        else:
            console.print("[yellow]未发现前端项目[/yellow]", style="dim")
            update_task_log(task_id, "[Info] 未发现前端项目")
    
    except Exception as e:
        logger.warning(f"前端项目扫描失败: {e}")
        console.print(f"[yellow]前端项目扫描失败: {e}[/yellow]", style="dim")
        update_task_log(task_id, f"[Warning] 前端项目扫描失败: {e}")
    # ===== 前端项目扫描结束 =====
    
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
        # 修复：如果 project_root 已经在 workspace 目录下，直接使用其父目录
        # 否则，在 project_root 的父目录下创建 workspace
        if os.path.basename(os.path.dirname(project_root)) == 'workspace':
            # project_root 已经在 workspace 下，例如：code_diff_project/workspace/service-a
            workspace_dir = os.path.dirname(project_root)
        else:
            # project_root 不在 workspace 下，创建 workspace 目录
            workspace_dir = os.path.join(os.path.dirname(project_root), 'workspace')
        
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)
            console.print(f"[Info] 创建 workspace 目录: {workspace_dir}", style="dim")
            update_task_log(task_id, f"[Info] 创建 workspace 目录: {workspace_dir}")
        else:
            console.print(f"[Info] 使用已存在的 workspace 目录: {workspace_dir}", style="dim")
            update_task_log(task_id, f"[Info] 使用已存在的 workspace 目录: {workspace_dir}")
        
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

        # ===== 前端扫描和映射（使用已存在的前端代码） =====
        frontend_calls_map = {}  # 存储每个API对应的前端调用信息
        
        try:
            console.print("\n[Frontend Analysis] 开始分析前端API调用...", style="bold cyan")
            update_task_log(task_id, "[Frontend Analysis] 开始分析前端API调用...")
            
            # 使用已经扫描的前端项目和API调用
            if frontend_projects:
                console.print(f"[Info] 使用已发现的 {len(frontend_projects)} 个前端项目", style="green")
                console.print(f"[Info] 使用已扫描的 {len(frontend_api_calls)} 个前端API调用", style="green")
                update_task_log(task_id, f"[Frontend API Scanner] 使用 {len(frontend_api_calls)} 个API调用")
                
                # 3. 建立前后端映射（从变更的文件中提取后端API）
                backend_apis = []
                for file_path in files_map.keys():
                    if file_path.endswith('.java') and 'Controller' in file_path:
                        # 解析Controller文件，提取API端点
                        full_path = os.path.join(project_root, file_path)
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # 提取类级别的 @RequestMapping
                            class_base_path = ''
                            class_mapping_match = re.search(r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']', content)
                            if class_mapping_match:
                                class_base_path = class_mapping_match.group(1)
                            
                            # 提取类级别的菜单路径注释
                            # 匹配：菜单路径：资产管理 > 订单管理
                            # 或：对应前端菜单：资产管理 > 订单管理
                            class_menu_path = None
                            menu_patterns = [
                                r'菜单路径[：:]\s*([^\n\r\(]+)',
                                r'对应前端菜单[：:]\s*([^\n\r\(]+)',
                                r'@menu\s+([^\n\r]+)',
                            ]
                            for menu_pattern in menu_patterns:
                                menu_match = re.search(menu_pattern, content)
                                if menu_match:
                                    class_menu_path = menu_match.group(1).strip()
                                    logger.info(f"从Controller注释中提取到菜单路径: {class_menu_path}")
                                    break
                            
                            # 提取方法级别的映射注解
                            # 匹配 @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, @RequestMapping
                            method_patterns = [
                                (r'@GetMapping\s*\(\s*["\']([^"\']+)["\']', 'GET'),
                                (r'@PostMapping\s*\(\s*["\']([^"\']+)["\']', 'POST'),
                                (r'@PutMapping\s*\(\s*["\']([^"\']+)["\']', 'PUT'),
                                (r'@DeleteMapping\s*\(\s*["\']([^"\']+)["\']', 'DELETE'),
                            ]
                            
                            for pattern, method in method_patterns:
                                matches = re.finditer(pattern, content)
                                for match in matches:
                                    method_path = match.group(1)
                                    # 拼接完整路径
                                    full_api_path = class_base_path + method_path
                                    backend_api = BackendApi(
                                        path=full_api_path,
                                        method=method,
                                        menu_path=class_menu_path  # 传入菜单路径
                                    )
                                    backend_apis.append(backend_api)
                                    logger.info(f"提取到后端API: {method} {full_api_path}, 菜单路径: {class_menu_path}")
                        
                        except Exception as e:
                            logger.error(f"解析Controller文件失败 {file_path}: {e}")
                
                logger.info(f"共提取到 {len(backend_apis)} 个后端API端点")
                console.print(f"[Info] 提取到 {len(backend_apis)} 个后端API端点", style="green")
                
                if backend_apis:
                    mapper = FrontendBackendMapper()
                    mappings = mapper.map_apis(backend_apis, frontend_api_calls)
                    
                    logger.info(f"建立了 {len(mappings)} 个前后端映射关系")
                    console.print(f"[Info] 建立了 {len(mappings)} 个前后端映射关系", style="green")
                    
                    # 初始化测试用例生成器（用于端识别）
                    # 使用第一个前端项目的路径来初始化（如果有多个项目，使用第一个）
                    test_case_generator = None
                    if frontend_projects:
                        first_project_path = frontend_projects[0].path
                        logger.info(f"[端识别] 准备初始化测试用例生成器")
                        logger.info(f"[端识别] 前端项目数量: {len(frontend_projects)}")
                        logger.info(f"[端识别] 使用第一个项目路径: {first_project_path}")
                        logger.info(f"[端识别] 项目对象: {frontend_projects[0]}")
                        try:
                            test_case_generator = TestCaseGenerator(project_path=first_project_path)
                            logger.info(f"[端识别] ✅ 测试用例生成器初始化成功")
                            logger.info(f"[端识别] 路由映射数量: {len(test_case_generator._route_to_company_types)}")
                            logger.info(f"[端识别] 精确映射数量: {len(test_case_generator._route_menu_to_company_type)}")
                        except Exception as e:
                            logger.error(f"[端识别] ❌ 测试用例生成器初始化失败: {e}")
                            import traceback
                            logger.error(f"[端识别] 异常详情: {traceback.format_exc()}")
                    else:
                        logger.warning(f"[端识别] ⚠️ 未发现前端项目，无法初始化测试用例生成器")
                    
                    # 构建映射字典：API -> 前端调用列表
                    for mapping in mappings:
                        api_key = f"{mapping.backend_api.method} {mapping.backend_api.path}"
                        frontend_calls_map[api_key] = []
                        
                        # 获取后端API的菜单路径（从Controller注释中提取的）
                        backend_menu_path = getattr(mapping.backend_api, 'menu_path', None)
                        
                        for call in mapping.frontend_calls:
                            # 优先使用前端调用的菜单路径，如果没有则使用后端的菜单路径
                            frontend_menu_path = getattr(call, 'menu_path', None)
                            final_menu_path = frontend_menu_path if frontend_menu_path else backend_menu_path
                            
                            # 【关键日志】记录 /balanceManageHome 相关API的菜单路径合并过程
                            page_route = getattr(call, 'page_route', '')
                            if '/balanceManageHome' in str(page_route) or '/balanceManageHome' in str(mapping.backend_api.path):
                                logger.info(f"[菜单合并-关键] 🔍 API: {api_key}")
                                logger.info(f"[菜单合并-关键] 🔍 前端菜单路径: {frontend_menu_path}")
                                logger.info(f"[菜单合并-关键] 🔍 后端菜单路径: {backend_menu_path}")
                                logger.info(f"[菜单合并-关键] 🔍 最终菜单路径: {final_menu_path}")
                                logger.info(f"[菜单合并-关键] 🔍 页面路由: {page_route}")
                                logger.info(f"[菜单合并-关键] 🔍 来源: {'前端' if frontend_menu_path else '后端注释'}")
                                # 检查最终结果
                                if final_menu_path and '企业信息' in final_menu_path:
                                    logger.error(f"[菜单合并-关键] ❌❌❌ 错误！最终菜单路径包含'企业信息': '{final_menu_path}' (应该是'准入授信')")
                                elif final_menu_path and '准入授信' in final_menu_path:
                                    logger.info(f"[菜单合并-关键] ✅ 正确！最终菜单路径包含'准入授信': '{final_menu_path}'")
                            
                            # 识别端类型
                            company_type = None
                            company_type_name = None
                            try:
                                if test_case_generator and page_route:
                                    logger.debug(f"[端识别] 开始识别: 路由={page_route}, 菜单={final_menu_path}")
                                    company_types = test_case_generator._identify_company_type(page_route, final_menu_path)
                                    if company_types:
                                        company_type = company_types[0]  # 如果有多个端，使用第一个
                                        company_type_name = test_case_generator._get_company_type_name(company_type)
                                        logger.info(f"[端识别] ✅ 成功识别: API {api_key}: 路由={page_route}, 菜单={final_menu_path} -> {company_type} ({company_type_name})")
                                    else:
                                        logger.debug(f"[端识别] ⚠️ 无法识别端类型: 路由={page_route}, 菜单={final_menu_path}")
                                elif not test_case_generator:
                                    logger.debug(f"[端识别] ⚠️ 测试用例生成器未初始化")
                                elif not page_route:
                                    logger.debug(f"[端识别] ⚠️ 页面路由为空，无法识别端类型")
                            except Exception as e:
                                logger.warning(f"[端识别] ❌ 端识别失败: {e}, API={api_key}, 路由={page_route}, 菜单={final_menu_path}")
                                import traceback
                                logger.debug(f"[端识别] 异常详情: {traceback.format_exc()}")
                            
                            call_info = {
                                'api_method': mapping.backend_api.method,
                                'api_path': mapping.backend_api.path,
                                'component_name': call.component_name,
                                'file_path': call.file_path,
                                'line_number': call.line_number,
                                'call_type': call.call_type,
                                'menu_path': final_menu_path or '',  # 使用合并后的菜单路径
                                'page_route': getattr(call, 'page_route', ''),
                                'trigger_element': getattr(call, 'trigger_element', ''),
                                'trigger_text': getattr(call, 'trigger_text', ''),
                                'company_type': company_type,  # 新增：端类型
                                'company_type_name': company_type_name  # 新增：端名称
                            }
                            frontend_calls_map[api_key].append(call_info)
                            
                            if final_menu_path:
                                logger.info(f"API {api_key} 的菜单路径: {final_menu_path} (来源: {'前端' if frontend_menu_path else '后端注释'})")
                    
                    console.print(f"[Info] 建立了 {len(mappings)} 个前后端映射关系", style="green")
                    update_task_log(task_id, f"[Frontend-Backend Mapping] 建立了 {len(mappings)} 个映射关系")
            else:
                console.print("[Info] 未发现前端项目，跳过前端分析", style="yellow")
                update_task_log(task_id, "[Frontend Analysis] 未发现前端项目")
                
        except Exception as e:
            console.print(f"[Warning] 前端扫描失败: {e}", style="yellow")
            logger.warning(f"前端扫描失败: {e}")
            update_task_log(task_id, f"[Frontend Analysis] 扫描失败: {e}")
            # 失败不影响主流程，继续执行
        # ===== 前端扫描和映射结束 =====

        # 5. 逐个分析变更文件
        for filename, content in files_map.items():
            update_task_log(task_id, f"正在分析文件: {filename} ...")
            
            # ===== 为当前文件准备前端调用信息 =====
            current_file_frontend_calls = []
            if frontend_calls_map and 'Controller' in filename:
                # 如果当前文件是Controller，传递所有的前端调用信息
                # AI会根据API路径自动匹配相关的前端调用
                for api_key, calls in frontend_calls_map.items():
                    current_file_frontend_calls.extend(calls)
                    logger.info(f"为Controller文件 {filename} 添加前端调用: {api_key}, {len(calls)} 个调用")
            
            if current_file_frontend_calls:
                console.print(f"[Info] 文件 {filename} 关联 {len(current_file_frontend_calls)} 个前端调用", style="cyan")
                logger.info(f"文件 {filename} 关联 {len(current_file_frontend_calls)} 个前端调用")
            else:
                logger.info(f"文件 {filename} 没有关联的前端调用")
            # ===== 前端调用信息准备结束 =====
            
            if USE_DEEPSEEK_API:
                report = analyze_with_llm(
                    filename, 
                    content, 
                    project_root, 
                    task_id, 
                    base_ref, 
                    target_ref, 
                    tracer=tracer, 
                    scan_roots=scan_roots,
                    frontend_calls_info=current_file_frontend_calls  # 新增参数
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
                    table = Table(title="[Test Strategy] 测试策略矩阵", show_header=True, header_style="bold magenta", box=box.ASCII, expand=True)
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

                # --- 添加前端调用信息到报告 ---
                if frontend_api_calls and report.get('affected_apis'):
                    try:
                        # 从报告中提取后端 API 信息
                        backend_apis = []
                        for api in report.get('affected_apis', []):
                            backend_apis.append(BackendApi(
                                path=api.get('url', ''),
                                method=api.get('method', 'GET'),
                                controller=None,
                                function=api.get('description', '')
                            ))
                        
                        if backend_apis:
                            # 建立前后端映射
                            mapper = FrontendBackendMapper()
                            mappings = mapper.map_apis(backend_apis, frontend_api_calls)
                            
                            # 将映射信息添加到报告中
                            frontend_calls_info = []
                            for mapping in mappings:
                                for call in mapping.frontend_calls:
                                    frontend_calls_info.append({
                                        'backend_api': f"{mapping.backend_api.method} {mapping.backend_api.path}",
                                        'component': call.component_name,
                                        'file_path': call.file_path,
                                        'line_number': call.line_number,
                                        'call_type': call.call_type
                                    })
                            
                            if frontend_calls_info:
                                report['frontend_calls'] = frontend_calls_info
                                console.print(f"\n[bold green]OK[/bold green] 发现 {len(frontend_calls_info)} 个前端调用关联", style="green")
                                update_task_log(task_id, f"[Info] 发现 {len(frontend_calls_info)} 个前端调用关联")
                    except Exception as e:
                        logger.warning(f"添加前端调用信息失败: {e}")
                        console.print(f"[yellow]添加前端调用信息失败: {e}[/yellow]", style="dim")

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
