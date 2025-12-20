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
