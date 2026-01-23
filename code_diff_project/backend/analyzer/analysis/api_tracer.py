import os
import re
import javalang
from loguru import logger

class ProjectStructureBuilder:
    """
    Scans the project to build a map of Interfaces to their Implementations.
    This helps in tracing calls that go through interfaces (e.g. Service -> ServiceImpl).
    """
    def __init__(self, project_root):
        self.project_root = project_root
        self.interface_impl_map = {} # {'UserService': ['com.pkg.impl.UserServiceImpl']}
        self.impl_interface_map = {} # {'com.pkg.impl.UserServiceImpl': ['UserService']}
        
    def build_index(self):
        logger.info("Building project structure index (Interface -> Implementation)...")
        for root, dirs, files in os.walk(self.project_root):
            # Ignore non-source dirs
            for ignore in ["target", "node_modules", ".git", "venv", "__pycache__", "code_diff_project", "test"]:
                if ignore in dirs: dirs.remove(ignore)
                
            for file in files:
                if file.endswith(".java"):
                    self._index_file(os.path.join(root, file))
        logger.info(f"Project index built. Found implementations for {len(self.interface_impl_map)} interfaces.")

    def _index_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple heuristic optimization: check if 'implements' keyword exists
            if 'implements' not in content:
                return

            tree = javalang.parse.parse(content)
            
            package_name = ""
            if tree.package:
                package_name = tree.package.name

            for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
                if class_node.implements:
                    full_class_name = f"{package_name}.{class_node.name}" if package_name else class_node.name
                    simple_class_name = class_node.name
                    
                    for interface in class_node.implements:
                        # interface.name is usually the simple name (e.g. "UserService")
                        interface_simple_name = interface.name
                        
                        # Store Interface -> Impl
                        if interface_simple_name not in self.interface_impl_map:
                            self.interface_impl_map[interface_simple_name] = []
                        self.interface_impl_map[interface_simple_name].append(full_class_name)
                        
                        # Store Impl -> Interface (Reverse lookup)
                        if full_class_name not in self.impl_interface_map:
                            self.impl_interface_map[full_class_name] = []
                        self.impl_interface_map[full_class_name].append(interface_simple_name)
                        
                        # Also store by simple name for Impl
                        if simple_class_name not in self.impl_interface_map:
                            self.impl_interface_map[simple_class_name] = []
                        self.impl_interface_map[simple_class_name].append(interface_simple_name)

        except Exception:
            # Skip files that fail to parse
            pass

class ApiUsageTracer:
    def __init__(self, project_root):
        self.project_root = project_root
        self.max_depth = 8  # Increased depth for complex chains
        self.project_index = ProjectStructureBuilder(project_root)
        self.project_index.build_index()

    def find_affected_apis(self, target_class_name, target_method_name, target_method_signature=None):
        """
        Finds public APIs (Controller endpoints) that eventually call the target method.
        
        Args:
            target_class_name (str): Simple class name (e.g. "UserManager") or FQN
            target_method_name (str): Method name (e.g. "initiateTransfer")
            target_method_signature (str, optional): 方法签名，用于区分重载方法
                                                     格式：methodName(Type1, Type2) 或 methodName()
            
        Returns:
            list[str]: List of API strings, e.g., ["POST /api/user/transfer"]
        """
        # Clean inputs
        if '.' in target_class_name:
            simple_class_name = target_class_name.split('.')[-1]
        else:
            simple_class_name = target_class_name
            
        targets_to_trace = [(simple_class_name, target_method_name, target_method_signature)]
        
        # 1. If target is an Implementation, trace its Interface(s) too
        # (Because callers usually reference the Interface)
        if simple_class_name in self.project_index.impl_interface_map:
            interfaces = self.project_index.impl_interface_map[simple_class_name]
            for interface in interfaces:
                logger.info(f"Adding interface {interface} to trace list for implementation {simple_class_name}")
                targets_to_trace.append((interface, target_method_name, target_method_signature))
                
        # 2. If target is an Interface, trace its Implementation(s) too
        # (Though usually we want to know who calls the interface, sometimes we need to know who calls specific impl logic if we are tracing downstream)
        # But for 'find_affected_apis' (upstream trace), knowing the interface is usually enough.
        
        found_apis = []
        visited = set()
        
        for target in targets_to_trace:
            target_class, target_method, target_signature = target
            # logger.info(f"Starting API trace for: {target_class}.{target_method}" + 
            #            (f" with signature: {target_signature}" if target_signature else ""))
            self._trace_recursive(target, 0, visited, found_apis)
        
        # Deduplicate results based on API string
        unique_results = {}
        for item in found_apis:
            if isinstance(item, dict):
                key = item['api']
                if key not in unique_results:
                    unique_results[key] = item
            else:
                # Fallback for string results if any
                if item not in unique_results:
                    unique_results[item] = item
                    
        return list(unique_results.values())

    def _trace_recursive(self, target, depth, visited, found_apis):
        """
        递归追踪方法调用链
        
        Args:
            target: 元组 (target_class, target_method, target_signature)
            depth: 当前递归深度
            visited: 已访问的方法集合
            found_apis: 找到的 API 列表
        """
        target_class, target_method, target_signature = target
        visit_key = f"{target_class}.{target_method}"
        if target_signature:
            visit_key += f"#{target_signature}"  # 使用签名作为唯一标识
        
        if depth > self.max_depth:
            return
        if visit_key in visited:
            return
        visited.add(visit_key)
        
        # 1. Find all callers of this method (考虑方法签名)
        callers = self._find_callers_of_method(target_class, target_method, target_signature)
        
        if not callers and depth == 0:
            logger.debug(f"No callers found for {visit_key}")

        for caller in callers:
            caller_file = caller['file']
            caller_class = caller['class']
            caller_method = caller['method']
            caller_method_signature = caller.get('method_signature', caller_method)  # 新增：获取方法签名
            caller_line = caller.get('line')
            caller_snippet = caller.get('snippet')
            
            # 2. Check if caller is a Controller
            api_info = self._get_controller_api(caller_file, caller_method)
            if api_info:
                # Found an API entry point!
                # logger.info(f"Found API endpoint: {api_info} (via {caller_class}.{caller_method})")
                
                # Store structured info
                found_apis.append({
                    "api": api_info,
                    "caller_class": caller_class,
                    "caller_method": caller_method,
                    "method_signature": caller_method_signature,  # 新增：完整方法签名
                    "file": caller_file,
                    "line": caller_line,
                    "snippet": caller_snippet
                })
            else:
                # 3. Not a controller, continue tracing upstream
                if caller_class and caller_method:
                    # 继续追踪时，传递调用者的方法签名
                    self._trace_recursive((caller_class, caller_method, caller_method_signature), 
                                        depth + 1, visited, found_apis)

    def _find_callers_of_method(self, target_class, target_method, target_signature=None):
        """
        Scans the codebase for calls to target_class.target_method()
        
        Args:
            target_class: 目标类名
            target_method: 目标方法名
            target_signature: 目标方法签名（可选），用于过滤重载方法
            
        Returns list of dict: {'file': path, 'class': className, 'method': methodName, 
                               'method_signature': signature, 'line': line_num, 'snippet': code}
        """
        callers = []
        
        # Optimization: We only scan .java files
        # We also skip test files to focus on production APIs
        
        for root, dirs, files in os.walk(self.project_root):
            # Ignore common non-source dirs
            for ignore in ["target", "node_modules", ".git", "venv", "__pycache__", "code_diff_project"]:
                if ignore in dirs: dirs.remove(ignore)
            
            for file in files:
                if not file.endswith(".java") or "Test" in file: 
                    continue
                
                file_path = os.path.join(root, file)
                
                # Fast string check before parsing
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except:
                    continue
                
                # Heuristic: file must contain method name
                if target_method not in content:
                    continue
                
                # Heuristic: file should probably contain class name (as type or variable)
                if target_class not in content:
                    pass 

                # Parse to verify (传递目标签名)
                found_in_file = self._parse_file_for_calls(file_path, content, target_class, 
                                                           target_method, target_signature)
                callers.extend(found_in_file)
                
        return callers

    def _parse_file_for_calls(self, file_path, content, target_class, target_method, target_signature=None):
        """
        解析文件，查找对目标方法的调用
        
        参数:
            file_path: 文件路径
            content: 文件内容
            target_class: 目标类名
            target_method: 目标方法名
            target_signature: 目标方法签名（可选），用于过滤重载方法
                            格式：methodName(Type1, Type2) 或 methodName()
        
        返回:
            调用信息列表
        """
        found = []
        try:
            tree = javalang.parse.parse(content)
        except:
            return []

        lines = content.splitlines()

        # Find the class name of the current file
        current_class_name = None
        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            current_class_name = node.name
            break
        
        if not current_class_name: 
            return []

        # Iterate over all methods in this file
        for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
            caller_method_name = method_node.name
            
            # 提取方法签名（包含参数类型）
            method_signature = self._extract_method_signature(method_node)
            
            # Check body for method invocations
            # We look for MethodInvocation nodes where .member == target_method
            for _, invoke_node in method_node.filter(javalang.tree.MethodInvocation):
                if invoke_node.member == target_method:
                    # 如果指定了目标签名，需要验证被调用方法的签名是否匹配
                    if target_signature:
                        # 提取被调用方法的参数类型
                        invoked_signature = self._extract_invocation_signature(invoke_node, target_method)
                        
                        # 比较签名是否匹配
                        if not self._signatures_match(invoked_signature, target_signature):
                            # 签名不匹配，跳过这个调用
                            logger.debug(f"签名不匹配: 调用签名 {invoked_signature} != 目标签名 {target_signature}")
                            continue
                        else:
                            logger.debug(f"签名匹配: 调用签名 {invoked_signature} == 目标签名 {target_signature}")
                    
                    # Get line number and snippet
                    line_num = invoke_node.position.line if invoke_node.position else 0
                    snippet = lines[line_num - 1].strip() if line_num > 0 and line_num <= len(lines) else "Code snippet not available"

                    found.append({
                        'file': file_path,
                        'class': current_class_name,
                        'method': caller_method_name,
                        'method_signature': method_signature,  # 新增：完整方法签名
                        'line': line_num,
                        'snippet': snippet
                    })
                    # Count once per caller method to avoid duplicates? 
                    # No, keep all calls if we want precise snippets. But for now trace path, one is enough.
                    break 
        return found
    
    def _extract_invocation_signature(self, invoke_node, method_name):
        """
        从方法调用节点中提取被调用方法的签名
        
        参数:
            invoke_node: MethodInvocation 节点
            method_name: 方法名
        
        返回:
            方法签名字符串，格式：methodName(Type1, Type2) 或 methodName()
        """
        params = []
        
        if invoke_node.arguments:
            for arg in invoke_node.arguments:
                # 尝试推断参数类型
                param_type = self._infer_argument_type(arg)
                if param_type:
                    params.append(param_type)
        
        if params:
            return f"{method_name}({', '.join(params)})"
        else:
            return f"{method_name}()"
    
    def _infer_argument_type(self, arg_node):
        """
        推断参数的类型
        
        这是一个简化的实现，只能推断一些基本类型
        对于复杂类型，可能需要更复杂的类型推断逻辑
        
        参数:
            arg_node: 参数节点
        
        返回:
            类型名称字符串，如果无法推断则返回 None
        """
        # Literal 类型（字符串、数字等）
        if isinstance(arg_node, javalang.tree.Literal):
            if arg_node.value:
                # 字符串字面量
                if arg_node.value.startswith('"') or arg_node.value.startswith("'"):
                    return "String"
                # 数字字面量
                elif arg_node.value.isdigit():
                    return "Integer"  # 简化处理，实际可能是 Long、Integer 等
                elif 'L' in arg_node.value or 'l' in arg_node.value:
                    return "Long"
                elif '.' in arg_node.value:
                    return "Double"  # 简化处理，实际可能是 Float、Double 等
                elif arg_node.value in ['true', 'false']:
                    return "Boolean"
        
        # MemberReference 类型（变量引用）
        elif isinstance(arg_node, javalang.tree.MemberReference):
            # 无法直接推断变量类型，需要更复杂的类型推断
            # 暂时返回 None，表示无法推断
            return None
        
        # MethodInvocation 类型（方法调用结果）
        elif isinstance(arg_node, javalang.tree.MethodInvocation):
            # 无法直接推断方法返回类型，需要更复杂的类型推断
            # 暂时返回 None
            return None
        
        # Cast 类型（类型转换）
        elif isinstance(arg_node, javalang.tree.Cast):
            if arg_node.type and hasattr(arg_node.type, 'name'):
                return arg_node.type.name
        
        # 其他类型暂时无法推断
        return None
    
    def _signatures_match(self, invoked_signature, target_signature):
        """
        比较两个方法签名是否匹配
        
        由于参数类型推断可能不完整，这里采用宽松的匹配策略：
        1. 如果参数数量不同，则不匹配
        2. 如果参数数量相同，且能推断出的类型都匹配，则匹配
        3. 如果有参数类型无法推断（None），则认为可能匹配（宽松策略）
        
        参数:
            invoked_signature: 调用签名，格式：methodName(Type1, Type2) 或 methodName()
            target_signature: 目标签名，格式：methodName(Type1, Type2) 或 methodName()
        
        返回:
            True 如果签名匹配，否则 False
        """
        # 提取方法名和参数列表
        invoked_match = re.match(r'(\w+)\((.*)\)', invoked_signature)
        target_match = re.match(r'(\w+)\((.*)\)', target_signature)
        
        if not invoked_match or not target_match:
            # 无法解析签名，采用宽松策略，认为匹配
            return True
        
        invoked_method = invoked_match.group(1)
        target_method = target_match.group(1)
        
        # 方法名必须相同
        if invoked_method != target_method:
            return False
        
        # 提取参数类型列表
        invoked_params = [p.strip() for p in invoked_match.group(2).split(',') if p.strip()]
        target_params = [p.strip() for p in target_match.group(2).split(',') if p.strip()]
        
        # 参数数量必须相同
        if len(invoked_params) != len(target_params):
            logger.debug(f"参数数量不匹配: {len(invoked_params)} != {len(target_params)}")
            return False
        
        # 如果没有参数，直接匹配
        if len(invoked_params) == 0:
            return True
        
        # 比较每个参数类型
        for i, (invoked_type, target_type) in enumerate(zip(invoked_params, target_params)):
            # 如果调用签名中的参数类型无法推断（空字符串或 None），采用宽松策略
            if not invoked_type or invoked_type == 'None':
                logger.debug(f"参数 {i+1} 类型无法推断，采用宽松策略")
                continue
            
            # 如果类型不匹配，返回 False
            if invoked_type != target_type:
                logger.debug(f"参数 {i+1} 类型不匹配: {invoked_type} != {target_type}")
                return False
        
        # 所有参数类型都匹配（或无法推断）
        return True
    
    def _extract_method_signature(self, method_node):
        """
        提取方法的完整签名，包含参数类型
        例如：sendOrderNotification(Long, String)
        """
        method_name = method_node.name
        params = []
        
        if method_node.parameters:
            for param in method_node.parameters:
                # 获取参数类型
                if param.type:
                    param_type = self._get_type_name(param.type)
                    params.append(param_type)
        
        if params:
            return f"{method_name}({', '.join(params)})"
        else:
            return f"{method_name}()"
    
    def _get_type_name(self, type_node):
        """
        从类型节点中提取类型名称
        """
        if hasattr(type_node, 'name'):
            return type_node.name
        elif hasattr(type_node, 'type') and hasattr(type_node.type, 'name'):
            # 处理泛型类型，如 List<String>
            return type_node.type.name
        else:
            return "Unknown"

    def _get_controller_api(self, file_path, method_name):
        """
        If file is a Controller and method is mapped, returns "METHOD /path".
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Quick check
            if "@RestController" not in content and "@Controller" not in content:
                return None
                
            tree = javalang.parse.parse(content)
            
            base_path = ""
            # 1. Class Level @RequestMapping
            for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
                # Check if class is controller
                is_controller = False
                if class_node.annotations:
                    for ann in class_node.annotations:
                        if ann.name in ['RestController', 'Controller']:
                            is_controller = True
                        if ann.name == 'RequestMapping':
                            # Extract base path from Class-level @RequestMapping
                            extracted = self._extract_value_from_annotation(ann)
                            if extracted:
                                base_path = extracted
                
                if not is_controller:
                    continue

                # 2. Find the specific method
                for method_node in class_node.methods:
                    if method_node.name == method_name:
                        method_path = ""
                        http_method = "ALL"
                        
                        if method_node.annotations:
                            for ann in method_node.annotations:
                                if ann.name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'RequestMapping']:
                                    method_path = self._extract_value_from_annotation(ann)
                                    http_method = self._resolve_http_method(ann.name)
                                    
                                    # If http_method is ALL (from RequestMapping), try to extract method from annotation
                                    if http_method == "ALL" and ann.name == 'RequestMapping':
                                         extracted_method = self._extract_method_from_request_mapping(ann)
                                         if extracted_method: http_method = extracted_method

                                    # Combine paths
                                    full_path = self._combine_paths(base_path, method_path)
                                    return f"{http_method} {full_path}"
        except Exception as e:
            # logger.error(f"Error parsing controller {file_path}: {e}")
            pass
        return None

    def _extract_method_from_request_mapping(self, ann):
        # Look for method = RequestMethod.POST
        if isinstance(ann.element, list):
            for elem in ann.element:
                if elem.name == 'method':
                    # Value is typically a MemberReference: RequestMethod.POST
                    if hasattr(elem.value, 'member'):
                        return elem.value.member
        return None

    def _extract_value_from_annotation(self, ann):
        if not ann.element:
            return ""
        
        # Case 1: Single string value @GetMapping("/path") -> element is Literal
        if isinstance(ann.element, list):
             for elem in ann.element:
                if elem.name == 'value' or elem.name == 'path':
                    if hasattr(elem.value, 'value'):
                        return elem.value.value.strip('"')
        # Case 2: Key-value pair (handled above if list) or single value
        elif hasattr(ann.element, 'value'):
             # Handle Literal directly
            return ann.element.value.strip('"')
        
        # Case 3: Single value but it's a Literal object directly (not in a pair)
        # javalang parser structure varies. Sometimes ann.element IS the Literal.
        elif isinstance(ann.element, javalang.tree.Literal):
             return ann.element.value.strip('"')
            
        return ""

    def _resolve_http_method(self, ann_name):
        if ann_name == 'GetMapping': return "GET"
        if ann_name == 'PostMapping': return "POST"
        if ann_name == 'PutMapping': return "PUT"
        if ann_name == 'DeleteMapping': return "DELETE"
        return "ALL" # RequestMapping without method

    def _combine_paths(self, base, sub):
        if not base: base = ""
        if not sub: sub = ""
        
        combined = f"{base}/{sub}"
        # Normalize slashes
        combined = re.sub(r'/+', '/', combined)
        if combined.endswith('/') and len(combined) > 1:
            combined = combined[:-1]
        if not combined.startswith('/'):
            combined = '/' + combined
        return combined
    
    def extract_controller_params(self, file_path, method_name):
        """
        提取 Controller 方法的 HTTP 参数信息
        
        参数:
            file_path: Controller 文件路径
            method_name: 方法名
        
        返回:
            dict: {
                'http_method': 'POST',
                'path': '/api/orders',
                'params': [
                    {'name': 'userId', 'type': 'Long', 'annotation': 'RequestParam', 'required': True},
                    {'name': 'productName', 'type': 'String', 'annotation': 'RequestParam', 'required': True},
                    ...
                ]
            }
            如果无法提取则返回 None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 快速检查是否是 Controller
            if "@RestController" not in content and "@Controller" not in content:
                return None
            
            tree = javalang.parse.parse(content)
            
            base_path = ""
            # 1. 获取类级别的 @RequestMapping
            for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
                # 检查是否是 Controller
                is_controller = False
                if class_node.annotations:
                    for ann in class_node.annotations:
                        if ann.name in ['RestController', 'Controller']:
                            is_controller = True
                        if ann.name == 'RequestMapping':
                            extracted = self._extract_value_from_annotation(ann)
                            if extracted:
                                base_path = extracted
                
                if not is_controller:
                    continue
                
                # 2. 查找指定的方法
                for method_node in class_node.methods:
                    if method_node.name == method_name:
                        method_path = ""
                        http_method = "ALL"
                        
                        # 提取方法级别的映射注解
                        if method_node.annotations:
                            for ann in method_node.annotations:
                                if ann.name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'RequestMapping']:
                                    method_path = self._extract_value_from_annotation(ann)
                                    http_method = self._resolve_http_method(ann.name)
                                    
                                    if http_method == "ALL" and ann.name == 'RequestMapping':
                                        extracted_method = self._extract_method_from_request_mapping(ann)
                                        if extracted_method:
                                            http_method = extracted_method
                        
                        # 组合完整路径
                        full_path = self._combine_paths(base_path, method_path)
                        
                        # 3. 提取方法参数
                        params = []
                        if method_node.parameters:
                            for param in method_node.parameters:
                                param_info = self._extract_param_info(param)
                                if param_info:
                                    params.append(param_info)
                        
                        return {
                            'http_method': http_method,
                            'path': full_path,
                            'params': params
                        }
        
        except Exception as e:
            logger.debug(f"提取 Controller 参数时出错 {file_path}: {e}")
        
        return None
    
    def _extract_param_info(self, param):
        """
        提取单个参数的信息
        
        参数:
            param: MethodParameter 节点
        
        返回:
            dict: {'name': 'userId', 'type': 'Long', 'annotation': 'RequestParam', 'required': True}
            如果参数没有 HTTP 相关注解则返回 None
        """
        param_name = param.name
        param_type = self._get_type_name(param.type)
        
        # 检查参数注解
        if not param.annotations:
            return None
        
        for ann in param.annotations:
            # @RequestParam
            if ann.name == 'RequestParam':
                required = True  # 默认必填
                # 尝试提取 required 属性
                if isinstance(ann.element, list):
                    for elem in ann.element:
                        if elem.name == 'required':
                            if hasattr(elem.value, 'value'):
                                required = elem.value.value == 'true'
                
                return {
                    'name': param_name,
                    'type': param_type,
                    'annotation': 'RequestParam',
                    'required': required
                }
            
            # @PathVariable
            elif ann.name == 'PathVariable':
                return {
                    'name': param_name,
                    'type': param_type,
                    'annotation': 'PathVariable',
                    'required': True  # PathVariable 总是必填
                }
            
            # @RequestBody
            elif ann.name == 'RequestBody':
                return {
                    'name': param_name,
                    'type': param_type,
                    'annotation': 'RequestBody',
                    'required': True
                }
        
        return None
