import os
import re
from rich.console import Console
from .mybatis_analyzer import MybatisAnalyzer
from loguru import logger

console = Console()


def extract_changed_methods(diff_text, file_path=None, project_root=None):
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


def extract_api_info(diff_text):
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


def extract_controller_params(affected_api_endpoints, root_dir):
    """
    提取 Controller 方法的参数信息，用于内部方法变更时的 Payload 生成
    
    参数:
        affected_api_endpoints: API 端点列表
        root_dir: 项目根目录
    
    返回:
        str: 格式化的参数信息字符串
    """
    from .api_tracer import ApiUsageTracer
    
    params_info_list = []
    
    for item in affected_api_endpoints:
        if not isinstance(item, dict):
            continue
            
        caller_file = item.get('file', '')
        caller_method = item.get('caller_method', '')
        api_path = item.get('api', '')
        caller_class = item.get('caller_class', '')
        project_root = item.get('project_root', root_dir)
        
        if not caller_file or not caller_method or not api_path:
            continue
        
        # 构建完整文件路径
        if os.path.isabs(caller_file):
            full_path = caller_file
        else:
            full_path = os.path.join(project_root, caller_file)
        
        # 如果文件不存在，尝试其他可能的路径
        if not os.path.exists(full_path):
            if caller_file.startswith('/'):
                full_path = os.path.join(project_root, caller_file.lstrip('/'))
            if not os.path.exists(full_path):
                file_name = os.path.basename(caller_file)
                for root, dirs, files in os.walk(project_root):
                    if file_name in files:
                        full_path = os.path.join(root, file_name)
                        break
                else:
                    continue
        
        # 使用 ApiUsageTracer 的新方法提取参数
        try:
            tracer = ApiUsageTracer(project_root)
            param_info = tracer.extract_controller_params(full_path, caller_method)
            
            if param_info and param_info.get('params'):
                # 格式化参数信息
                http_method = param_info.get('http_method', 'UNKNOWN')
                path = param_info.get('path', '')
                params = param_info.get('params', [])
                
                # 构建参数详情
                param_details = []
                payload_example_parts = []
                
                for param in params:
                    param_name = param.get('name')
                    param_type = param.get('type')
                    annotation = param.get('annotation')
                    required = param.get('required', True)
                    
                    if annotation == 'RequestParam':
                        param_details.append(f"`{param_name}` ({param_type}, Query String, {'必填' if required else '可选'})")
                        # 生成示例值
                        example_value = _generate_example_value(param_type)
                        payload_example_parts.append(f"{param_name}={example_value}")
                    
                    elif annotation == 'PathVariable':
                        param_details.append(f"`{param_name}` ({param_type}, URL Path, 必填)")
                        # PathVariable 在 URL 中，不在 Query String 中
                    
                    elif annotation == 'RequestBody':
                        param_details.append(f"`{param_name}` ({param_type}, JSON Body, 必填)")
                        # RequestBody 需要 JSON 格式
                        payload_example_parts.append(f"Body: {{{param_name}: <{param_type} object>}}")
                
                # 构建 Payload 示例
                payload_example = ""
                if payload_example_parts:
                    if any('Body:' in part for part in payload_example_parts):
                        # 有 RequestBody
                        payload_example = "\n  - ".join(payload_example_parts)
                    else:
                        # 只有 Query String
                        payload_example = "?" + "&".join(payload_example_parts)
                
                # 添加到结果列表
                info_text = f"**{http_method} {path}** (Controller: {caller_class}.{caller_method}):\n"
                info_text += f"  - 参数: {', '.join(param_details)}\n"
                if payload_example:
                    info_text += f"  - Payload 示例: `{payload_example}`\n"
                info_text += f"  - **必须直接使用这些参数生成测试 Payload，不要写\"参数待确认\"等提示**"
                
                params_info_list.append(info_text)
            
        except Exception as e:
            logger.debug(f"提取 Controller 参数时出错 {full_path}: {e}")
            continue
    
    if params_info_list:
        return "\n\n## Controller 参数信息（系统自动提取）\n\n" + "\n\n".join(params_info_list)
    else:
        return ""


def _generate_example_value(param_type):
    """根据参数类型生成示例值"""
    type_examples = {
        'Long': '1001',
        'Integer': '100',
        'String': 'example',
        'BigDecimal': '99.99',
        'Double': '99.99',
        'Float': '99.99',
        'Boolean': 'true',
        'Date': '2024-01-01',
        'LocalDateTime': '2024-01-01T12:00:00',
    }
    return type_examples.get(param_type, 'value')


def search_api_usages(root_dir, api_info, exclude_file):
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
                            # 提取服务名
                            rel_path = os.path.relpath(full_path, root_dir)
                            service_name = rel_path.split(os.sep)[0] if os.sep in rel_path else rel_path.split('/')[0]
                            
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


def get_project_structure(root_dir):
    services = []
    try:
        for item in os.listdir(root_dir):
            if os.path.isdir(os.path.join(root_dir, item)) and not item.startswith('.') and item != "code_diff_project":
                services.append(item)
    except: pass
    return ", ".join(services)
