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

    def find_affected_apis(self, target_class_name, target_method_name):
        """
        Finds public APIs (Controller endpoints) that eventually call the target method.
        
        Args:
            target_class_name (str): Simple class name (e.g. "UserManager") or FQN
            target_method_name (str): Method name (e.g. "initiateTransfer")
            
        Returns:
            list[str]: List of API strings, e.g., ["POST /api/user/transfer"]
        """
        # Clean inputs
        if '.' in target_class_name:
            simple_class_name = target_class_name.split('.')[-1]
        else:
            simple_class_name = target_class_name
            
        targets_to_trace = [(simple_class_name, target_method_name)]
        
        # 1. If target is an Implementation, trace its Interface(s) too
        # (Because callers usually reference the Interface)
        if simple_class_name in self.project_index.impl_interface_map:
            interfaces = self.project_index.impl_interface_map[simple_class_name]
            for interface in interfaces:
                logger.info(f"Adding interface {interface} to trace list for implementation {simple_class_name}")
                targets_to_trace.append((interface, target_method_name))
                
        # 2. If target is an Interface, trace its Implementation(s) too
        # (Though usually we want to know who calls the interface, sometimes we need to know who calls specific impl logic if we are tracing downstream)
        # But for 'find_affected_apis' (upstream trace), knowing the interface is usually enough.
        
        found_apis = []
        visited = set()
        
        for target in targets_to_trace:
            logger.info(f"Starting API trace for: {target[0]}.{target[1]}")
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
        target_class, target_method = target
        visit_key = f"{target_class}.{target_method}"
        
        if depth > self.max_depth:
            return
        if visit_key in visited:
            return
        visited.add(visit_key)
        
        # logger.debug(f"Tracing: {visit_key} (Depth: {depth})")
        
        # 1. Find all callers of this method
        callers = self._find_callers_of_method(target_class, target_method)
        
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
                logger.info(f"Found API endpoint: {api_info} (via {caller_class}.{caller_method})")
                
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
                    self._trace_recursive((caller_class, caller_method), depth + 1, visited, found_apis)

    def _find_callers_of_method(self, target_class, target_method):
        """
        Scans the codebase for calls to target_class.target_method()
        Returns list of dict: {'file': path, 'class': className, 'method': methodName}
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

                # Parse to verify
                found_in_file = self._parse_file_for_calls(file_path, content, target_class, target_method)
                callers.extend(found_in_file)
                
        return callers

    def _parse_file_for_calls(self, file_path, content, target_class, target_method):
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
