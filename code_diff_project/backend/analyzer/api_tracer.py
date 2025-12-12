import os
import re
import javalang
from loguru import logger

class ApiUsageTracer:
    def __init__(self, project_root):
        self.project_root = project_root
        self.max_depth = 8  # Increased depth for complex chains

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
            target_class_name = target_class_name.split('.')[-1]
            
        initial_target = (target_class_name, target_method_name)
        found_apis = []
        visited = set()
        
        logger.info(f"Starting API trace for: {target_class_name}.{target_method_name}")
        self._trace_recursive(initial_target, 0, visited, found_apis)
        
        # Deduplicate results
        return sorted(list(set(found_apis)))

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
            
            # 2. Check if caller is a Controller
            api_info = self._get_controller_api(caller_file, caller_method)
            if api_info:
                # Found an API entry point!
                logger.info(f"Found API endpoint: {api_info} (via {caller_class}.{caller_method})")
                found_apis.append(api_info)
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
            
            # Check body for method invocations
            # We look for MethodInvocation nodes where .member == target_method
            for _, invoke_node in method_node.filter(javalang.tree.MethodInvocation):
                if invoke_node.member == target_method:
                    found.append({
                        'file': file_path,
                        'class': current_class_name,
                        'method': caller_method_name
                    })
                    break # Count once per caller method
        return found

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
                            base_path = self._extract_value_from_annotation(ann)
                
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
