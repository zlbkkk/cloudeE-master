"""
RestTemplate HTTP 调用分析器

识别 RestTemplate 的 HTTP 调用，用于跨服务同步调用分析
"""

import os
import re
import javalang
from loguru import logger


class RestTemplateAnalyzer:
    """
    RestTemplate HTTP 调用分析器
    
    识别模式：
    1. restTemplate.getForObject(url, ResponseType.class)
    2. restTemplate.postForObject(url, request, ResponseType.class)
    3. restTemplate.exchange(url, method, entity, ResponseType.class)
    4. restTemplate.getForEntity(url, ResponseType.class)
    5. restTemplate.postForEntity(url, request, ResponseType.class)
    """
    
    # RestTemplate 的常见方法
    REST_TEMPLATE_METHODS = [
        'getForObject', 'getForEntity',
        'postForObject', 'postForEntity',
        'put', 'delete',
        'exchange', 'execute'
    ]
    
    def __init__(self, project_root):
        self.project_root = project_root
    
    def find_http_calls(self, target_class_name=None, target_method_name=None):
        """
        查找 RestTemplate HTTP 调用
        
        参数:
            target_class_name: 目标类名（可选），如果指定则只查找该类中的 HTTP 调用
            target_method_name: 目标方法名（可选），如果指定则只查找该方法中的 HTTP 调用
        
        返回:
            HTTP 调用列表，每个元素包含:
                - file: 文件路径
                - class: 类名
                - method: 方法名
                - line: 行号
                - snippet: 代码片段
                - http_method: HTTP 方法（GET, POST, PUT, DELETE 等）
                - url: 请求 URL（如果能提取）
                - response_type: 响应类型（如果能推断）
        """
        http_calls = []
        
        for root, dirs, files in os.walk(self.project_root):
            # 忽略常见的非源码目录
            for ignore in ["target", "node_modules", ".git", "venv", "__pycache__", "code_diff_project"]:
                if ignore in dirs:
                    dirs.remove(ignore)
            
            for file in files:
                if not file.endswith(".java"):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except:
                    continue
                
                # 快速检查：文件中是否包含 RestTemplate
                if 'RestTemplate' not in content and 'restTemplate' not in content:
                    continue
                
                # 解析文件
                found_in_file = self._parse_file_for_http_calls(
                    file_path, content, target_class_name, target_method_name
                )
                http_calls.extend(found_in_file)
        
        return http_calls
    
    def _parse_file_for_http_calls(self, file_path, content, target_class_name, target_method_name):
        """
        解析文件，查找 RestTemplate HTTP 调用
        """
        found = []
        
        try:
            tree = javalang.parse.parse(content)
        except:
            return []
        
        lines = content.splitlines()
        
        # 获取当前文件的类名
        current_class_name = None
        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            current_class_name = node.name
            break
        
        if not current_class_name:
            return []
        
        # 如果指定了目标类名，检查是否匹配
        if target_class_name and current_class_name != target_class_name:
            return []
        
        # 遍历所有方法
        for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
            method_name = method_node.name
            
            # 如果指定了目标方法名，检查是否匹配
            if target_method_name and method_name != target_method_name:
                continue
            
            # 在方法体中查找 restTemplate 调用
            for _, invoke_node in method_node.filter(javalang.tree.MethodInvocation):
                # 检查是否为 RestTemplate 方法
                if invoke_node.member not in self.REST_TEMPLATE_METHODS:
                    continue
                
                # 检查是否为 restTemplate 调用
                if not invoke_node.qualifier or 'restTemplate' not in invoke_node.qualifier.lower():
                    continue
                
                # 获取行号和代码片段
                line_num = invoke_node.position.line if invoke_node.position else 0
                snippet = lines[line_num - 1].strip() if line_num > 0 and line_num <= len(lines) else "Code snippet not available"
                
                # 推断 HTTP 方法
                http_method = self._infer_http_method(invoke_node.member)
                
                # 提取参数：url, responseType
                url = None
                response_type = None
                
                if invoke_node.arguments and len(invoke_node.arguments) >= 1:
                    # 第一个参数通常是 URL
                    url_arg = invoke_node.arguments[0]
                    url = self._extract_argument_value(url_arg, content)
                    
                    # 最后一个参数通常是响应类型（Class<T>）
                    if len(invoke_node.arguments) >= 2:
                        response_type_arg = invoke_node.arguments[-1]
                        response_type = self._extract_response_type(response_type_arg)
                
                found.append({
                    'file': file_path,
                    'class': current_class_name,
                    'method': method_name,
                    'line': line_num,
                    'snippet': snippet,
                    'http_method': http_method or 'Unknown',
                    'url': url or 'Unknown',
                    'response_type': response_type or 'Unknown',
                    'type': 'resttemplate_call'
                })
                
                logger.info(f"Found RestTemplate call: {current_class_name}.{method_name} -> {http_method} {url}")
        
        return found
    
    def _infer_http_method(self, method_name):
        """
        根据 RestTemplate 方法名推断 HTTP 方法
        """
        method_name_lower = method_name.lower()
        
        if 'get' in method_name_lower:
            return 'GET'
        elif 'post' in method_name_lower:
            return 'POST'
        elif 'put' in method_name_lower:
            return 'PUT'
        elif 'delete' in method_name_lower:
            return 'DELETE'
        elif method_name == 'exchange':
            # exchange 方法需要从参数中提取 HTTP 方法
            return 'EXCHANGE'  # 标记为需要进一步分析
        else:
            return 'UNKNOWN'
    
    def _extract_argument_value(self, arg_node, content):
        """
        提取参数值（字符串字面量或变量名）
        """
        if isinstance(arg_node, javalang.tree.Literal):
            # 字符串字面量
            if arg_node.value:
                return arg_node.value.strip('"').strip("'")
        elif isinstance(arg_node, javalang.tree.MemberReference):
            # 变量引用
            return f"Variable: {arg_node.member}"
        elif isinstance(arg_node, javalang.tree.BinaryOperation):
            # 字符串拼接（如 baseUrl + "/api/users"）
            return "String concatenation"
        elif hasattr(arg_node, 'member'):
            # 其他类型的成员引用
            return arg_node.member
        
        return None
    
    def _extract_response_type(self, response_type_arg):
        """
        提取响应类型（从 Class<T> 参数中）
        """
        # 如果是 MemberReference，可能是 ResponseType.class
        if isinstance(response_type_arg, javalang.tree.MemberReference):
            # 获取类型名称（去掉 .class 后缀）
            if hasattr(response_type_arg, 'qualifier'):
                return response_type_arg.qualifier
            elif hasattr(response_type_arg, 'member'):
                return response_type_arg.member
        
        # 如果是 ClassReference
        elif isinstance(response_type_arg, javalang.tree.ClassReference):
            if hasattr(response_type_arg, 'type') and hasattr(response_type_arg.type, 'name'):
                return response_type_arg.type.name
        
        return None
    
    def find_matching_endpoints(self, http_call, project_root):
        """
        查找匹配的 API 端点
        
        给定一个 RestTemplate HTTP 调用，在指定项目中查找可能匹配的 Controller 端点
        
        参数:
            http_call: HTTP 调用信息字典
            project_root: 要搜索的项目根目录
        
        返回:
            匹配的端点列表
        """
        # TODO: 实现端点匹配逻辑
        # 需要解析 URL 模式，并在目标项目中查找匹配的 @RequestMapping
        # 这是一个复杂的功能，需要：
        # 1. 解析 URL 模板（如 /api/users/{id}）
        # 2. 在目标项目中查找所有 Controller
        # 3. 匹配 HTTP 方法和 URL 路径
        
        return []
