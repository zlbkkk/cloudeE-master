"""
前端 API 调用扫描器
扫描前端代码，识别 axios 和 fetch API 调用
"""
import os
import re
from dataclasses import dataclass
from typing import List, Optional
from loguru import logger


@dataclass
class ApiCall:
    """API 调用信息"""
    file_path: str  # 文件路径（相对于项目根目录）
    line_number: int  # 行号
    method: str  # HTTP 方法（GET, POST, PUT, DELETE）
    url: str  # API 路径
    component_name: Optional[str] = None  # 组件名称
    call_type: str = 'unknown'  # 调用类型：axios, fetch
    # UI入口信息
    trigger_element: Optional[str] = None  # 触发元素类型：button, link, form等
    trigger_text: Optional[str] = None  # 触发元素文本：如"查询"、"提交订单"
    page_route: Optional[str] = None  # 页面路由：如 /orders/list
    menu_path: Optional[str] = None  # 菜单路径：如 "订单管理 > 订单列表"


class FrontendApiScanner:
    """前端 API 调用扫描器"""
    
    def __init__(self, project_path: str):
        """
        初始化扫描器
        
        Args:
            project_path: 前端项目根目录路径
        """
        self.project_path = os.path.abspath(project_path)  # 转换为绝对路径
        self.src_path = os.path.join(self.project_path, 'src')
        
        # 需要排除的目录
        self.exclude_dirs = {
            'node_modules', 'dist', 'build', '.git', 
            'coverage', 'public', 'assets'
        }
        
        # 支持的文件扩展名
        self.file_extensions = {'.js', '.jsx', '.ts', '.tsx', '.vue'}
        
        # 缓存菜单配置（避免重复读取）
        self._menu_config_cache = None
        self._menu_url_to_path_map = None
        
        # 缓存 baseURL 映射（文件路径 -> baseURL）
        self._base_url_cache = {}

    
    def scan_project(self) -> List[ApiCall]:
        """
        扫描整个前端项目，提取所有 API 调用
        
        Returns:
            API 调用列表
        """
        api_calls = []
        
        # 第一步：扫描并缓存所有API配置文件中的 baseURL
        logger.info("开始扫描 API 配置文件中的 baseURL...")
        self._scan_base_urls()
        
        # 第二步：扫描src目录提取API调用
        if os.path.exists(self.src_path):
            api_calls.extend(self._scan_directory(self.src_path))
        else:
            logger.warning(f"源代码目录不存在: {self.src_path}")
        
        logger.info(f"扫描完成，发现 {len(api_calls)} 个 API 调用")
        return api_calls
    
    def _scan_base_urls(self):
        """
        扫描项目中的 API 配置文件，提取 baseURL 配置
        将结果缓存到 self._base_url_cache 中
        
        缓存格式：{
            'serviceAApi.js': '/api',
            'beehiveApi.js': '/beehive',
            ...
        }
        """
        if not os.path.exists(self.src_path):
            return
        
        # 查找所有可能包含 API 配置的文件
        # 通常在 src/api/ 目录下
        api_dir = os.path.join(self.src_path, 'api')
        if not os.path.exists(api_dir):
            logger.warning(f"API 配置目录不存在: {api_dir}")
            return
        
        # 扫描 api 目录下的所有 JS/TS 文件
        for root, dirs, files in os.walk(api_dir):
            # 排除 node_modules 等目录
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                if file.endswith(('.js', '.ts')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 提取 baseURL
                        base_url = self._extract_base_url_from_content(content)
                        if base_url:
                            # 使用文件名作为key（不含路径）
                            self._base_url_cache[file] = base_url
                            logger.info(f"发现 baseURL 配置: {file} -> {base_url}")
                    except Exception as e:
                        logger.error(f"读取文件失败 {file_path}: {e}")
        
        logger.info(f"共发现 {len(self._base_url_cache)} 个 baseURL 配置")
    
    def _extract_base_url_from_content(self, content: str) -> Optional[str]:
        """
        从文件内容中提取 baseURL
        
        Args:
            content: 文件内容
            
        Returns:
            baseURL，如 '/api', '/beehive' 等
        """
        # 匹配 baseURL: '/api' 或 baseURL: "/api"
        # 支持多行匹配（因为 baseURL 可能在 Object.assign 等函数调用中）
        patterns = [
            r'baseURL\s*:\s*[\'"]([^\'"]+)[\'"]',  # 单行匹配
            r'baseUrl\s*:\s*[\'"]([^\'"]+)[\'"]',  # 驼峰命名
            r'API_BASE_URL\s*[:=]\s*[\'"]([^\'"]+)[\'"]',  # 常量定义
        ]
        
        for pattern in patterns:
            # 使用 re.MULTILINE | re.DOTALL 支持跨行匹配
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                base_url = match.group(1)
                logger.debug(f"从内容中提取到 baseURL: {base_url}")
                return base_url
        
        return None
    
    def _get_base_url_for_file(self, file_path: str) -> Optional[str]:
        """
        根据文件路径推断应该使用的 baseURL
        
        策略：
        1. 如果文件在 src/api/xxxApi/ 目录下，查找 xxxApi.js 的 baseURL
        2. 如果找不到，返回 None
        
        Args:
            file_path: 文件路径
            
        Returns:
            baseURL，如 '/api'
        """
        # 提取文件所在的 API 目录名
        # 例如：src/api/serviceAApi/controller/orderController.js -> serviceAApi
        rel_path = os.path.relpath(file_path, self.project_path)
        parts = rel_path.split(os.sep)
        
        # 查找 api 目录的位置
        try:
            api_index = parts.index('api')
            if api_index + 1 < len(parts):
                api_dir_name = parts[api_index + 1]  # serviceAApi, beehiveApi 等
                
                # 查找对应的配置文件
                # 尝试多种可能的文件名
                possible_files = [
                    f'{api_dir_name}.js',
                    f'{api_dir_name}.ts',
                ]
                
                for file_name in possible_files:
                    if file_name in self._base_url_cache:
                        return self._base_url_cache[file_name]
        except ValueError:
            pass
        
        return None
    
    def _is_api_definition_file(self, file_path: str) -> bool:
        """
        判断文件是否是 API 定义文件（而不是 API 调用文件）
        
        API 定义文件的特征：
        1. 包含多个函数定义，每个函数都返回 Promise
        2. 函数内部调用了 API 客户端（如 orderApi(), beehiveApi(), axios() 等）
        3. 函数定义了 url 字段
        4. 通常使用 export default { ... } 导出多个方法
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 表示是 API 定义文件，应该跳过扫描
        """
        # Vue 文件一定不是 API 定义文件
        if file_path.endswith('.vue'):
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 特征1: 检查是否有多个 Promise 返回的函数定义
            # 匹配：methodName(params) { return new Promise(...) }
            promise_pattern = r'\w+\s*\([^)]*\)\s*\{\s*return\s+new\s+Promise'
            promise_matches = re.findall(promise_pattern, content)
            
            # 特征2: 检查是否有 url 字段定义
            # 匹配：url: '/xxx' 或 url: `/xxx`
            url_pattern = r'url\s*:\s*[\'"`]/[^\'"`,]+'
            url_matches = re.findall(url_pattern, content)
            
            # 特征3: 检查是否使用 export default { ... } 导出
            export_default_pattern = r'export\s+default\s*\{'
            has_export_default = bool(re.search(export_default_pattern, content))
            
            # 判断逻辑：
            # 如果同时满足以下条件，则认为是 API 定义文件：
            # 1. 有 2 个以上的 Promise 函数定义
            # 2. 有 2 个以上的 url 字段定义
            # 3. 使用 export default 导出
            if len(promise_matches) >= 2 and len(url_matches) >= 2 and has_export_default:
                logger.debug(f"[API定义文件检测] {file_path} - Promise函数: {len(promise_matches)}, URL定义: {len(url_matches)}, export default: {has_export_default}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"[API定义文件检测] 读取文件失败 {file_path}: {e}")
            return False
    
    def _scan_directory(self, directory: str) -> List[ApiCall]:
        """
        递归扫描目录
        
        Args:
            directory: 要扫描的目录路径
            
        Returns:
            API 调用列表
        """
        api_calls = []
        
        # 递归扫描目录
        for root, dirs, files in os.walk(directory):
            # 排除不需要扫描的目录
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                # 只处理 JavaScript/TypeScript/Vue 文件
                if any(file.endswith(ext) for ext in self.file_extensions):
                    file_path = os.path.join(root, file)
                    
                    # 跳过 API 定义文件（通过文件内容特征判断）
                    if self._is_api_definition_file(file_path):
                        logger.info(f"[扫描跳过] 跳过 API 定义文件: {file_path}")
                        continue
                    
                    try:
                        calls = self.scan_file(file_path)
                        api_calls.extend(calls)
                    except Exception as e:
                        logger.error(f"扫描文件失败 {file_path}: {e}")
        
        return api_calls
    
    def scan_file(self, file_path: str) -> List[ApiCall]:
        """
        扫描单个文件，提取 API 调用
        
        Args:
            file_path: 文件路径
            
        Returns:
            该文件中的 API 调用列表
        """
        api_calls = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 提取组件名称
            component_name = self._extract_component_name(file_path, code)
            
            # 提取 axios 调用
            axios_calls = self.extract_axios_calls(code, file_path, component_name)
            api_calls.extend(axios_calls)
            
            # 提取 fetch 调用
            fetch_calls = self.extract_fetch_calls(code, file_path, component_name)
            api_calls.extend(fetch_calls)
            
            # 提取自定义 API 函数调用（如 beehiveApi, orderApi 等）
            custom_api_calls = self.extract_custom_api_calls(code, file_path, component_name)
            api_calls.extend(custom_api_calls)
            
            # 为每个API调用提取UI入口信息
            for api_call in api_calls:
                logger.info(f"[UI入口提取] 开始为 API 提取 UI 入口信息: {api_call.method} {api_call.url}")
                self._extract_ui_entry_info(api_call, code, file_path)
                logger.info(f"[UI入口提取] 完成，菜单路径: {api_call.menu_path}")
            
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
        
        return api_calls

    
    def extract_axios_calls(self, code: str, file_path: str, component_name: Optional[str]) -> List[ApiCall]:
        """
        从代码中提取 axios API 调用
        
        Args:
            code: 源代码内容
            file_path: 文件路径
            component_name: 组件名称
            
        Returns:
            axios 调用列表
        """
        api_calls = []
        lines = code.split('\n')
        
        # 匹配 axios 调用的正则表达式
        patterns = [
            # axios.get('/api/users') 或 axios.get(SOME_URL)
            (r'axios\.get\s*\(\s*([\'"`]?)([^\'"`,\)]+)\1', 'GET'),
            # axios.post('/api/users', data) 或 axios.post(SOME_URL, data)
            (r'axios\.post\s*\(\s*([\'"`]?)([^\'"`,\)]+)\1', 'POST'),
            # axios.put('/api/users/1', data)
            (r'axios\.put\s*\(\s*([\'"`]?)([^\'"`,\)]+)\1', 'PUT'),
            # axios.delete('/api/users/1')
            (r'axios\.delete\s*\(\s*([\'"`]?)([^\'"`,\)]+)\1', 'DELETE'),
            # axios({ method: 'GET', url: '/api/users' })
            (r'axios\s*\(\s*\{[^}]*url\s*:\s*([\'"`]?)([^\'"`,\)]+)\1', None),
        ]
        
        for line_num, line in enumerate(lines, 1):
            for pattern, default_method in patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    # match.group(2) 是 URL（可能是字符串或变量名）
                    url = match.group(2).strip()
                    
                    # 如果是通用 axios() 调用，尝试提取 method
                    method = default_method
                    if method is None:
                        method_match = re.search(r'method\s*:\s*[\'"`](\w+)[\'"`]', line)
                        method = method_match.group(1).upper() if method_match else 'GET'
                    
                    # 计算相对路径
                    rel_path = os.path.relpath(file_path, self.project_path)
                    
                    api_calls.append(ApiCall(
                        file_path=rel_path,
                        line_number=line_num,
                        method=method,
                        url=url,
                        component_name=component_name,
                        call_type='axios'
                    ))
        
        return api_calls

    
    def extract_fetch_calls(self, code: str, file_path: str, component_name: Optional[str]) -> List[ApiCall]:
        """
        从代码中提取 fetch API 调用
        
        Args:
            code: 源代码内容
            file_path: 文件路径
            component_name: 组件名称
            
        Returns:
            fetch 调用列表
        """
        api_calls = []
        lines = code.split('\n')
        
        # 匹配 fetch 调用的正则表达式
        # fetch('/api/users')
        # fetch('/api/users', { method: 'POST' })
        fetch_pattern = r'fetch\s*\(\s*[\'"`]([^\'"` ]+)[\'"`]'
        
        for line_num, line in enumerate(lines, 1):
            matches = re.finditer(fetch_pattern, line)
            for match in matches:
                url = match.group(1)
                
                # 尝试提取 method，默认为 GET
                method = 'GET'
                method_match = re.search(r'method\s*:\s*[\'"`](\w+)[\'"`]', line)
                if method_match:
                    method = method_match.group(1).upper()
                
                # 计算相对路径
                rel_path = os.path.relpath(file_path, self.project_path)
                
                api_calls.append(ApiCall(
                    file_path=rel_path,
                    line_number=line_num,
                    method=method,
                    url=url,
                    component_name=component_name,
                    call_type='fetch'
                ))
        
        return api_calls
    
    def extract_custom_api_calls(self, code: str, file_path: str, component_name: Optional[str]) -> List[ApiCall]:
        """
        从代码中提取自定义 API 函数调用
        支持两种模式：
        1. beehiveApi({ url: '/loginOut', method: 'POST' })
        2. beehiveApi.xxxController.xxxMethod() 或 orderApi.xxxController.xxxMethod()
        
        Args:
            code: 源代码内容
            file_path: 文件路径
            component_name: 组件名称
            
        Returns:
            自定义 API 调用列表
        """
        api_calls = []
        lines = code.split('\n')
        
        # 模式1：beehiveApi({ url: '/loginOut', method: 'POST' })
        # 常见的自定义 API 函数名模式
        # 匹配类似 beehiveApi, orderApi, wecApi, xxxApi 等
        api_function_pattern = r'(\w+Api(?:Order)?)\s*\('
        
        for line_num, line in enumerate(lines, 1):
            # 查找自定义 API 函数调用
            api_func_matches = re.finditer(api_function_pattern, line)
            
            for func_match in api_func_matches:
                api_func_name = func_match.group(1)
                
                # 尝试在当前行或后续几行中提取 url 和 method
                # 因为参数可能跨多行
                context_start = max(0, line_num - 1)
                context_end = min(len(lines), line_num + 10)  # 向后看10行
                context = '\n'.join(lines[context_start:context_end])
                
                # 提取 url
                url_match = re.search(r'url\s*:\s*[\'"`]([^\'"`,]+)[\'"`]', context)
                if not url_match:
                    continue
                
                url = url_match.group(1).strip()
                
                # 提取 method，默认为 GET
                method = 'GET'
                method_match = re.search(r'method\s*:\s*[\'"`](\w+)[\'"`]', context)
                if method_match:
                    method = method_match.group(1).upper()
                
                # 尝试拼接 baseURL
                base_url = self._get_base_url_for_file(file_path)
                if base_url and not url.startswith('http'):
                    # 确保拼接正确：去除重复的斜杠
                    if base_url.endswith('/') and url.startswith('/'):
                        url = base_url + url[1:]
                    elif not base_url.endswith('/') and not url.startswith('/'):
                        url = base_url + '/' + url
                    else:
                        url = base_url + url
                    logger.info(f"[API扫描] 拼接 baseURL: {base_url} + {url_match.group(1).strip()} = {url}")
                else:
                    if not base_url:
                        logger.warning(f"[API扫描] 未找到 baseURL，文件: {file_path}, URL: {url}")
                    else:
                        logger.debug(f"[API扫描] URL已包含协议，跳过baseURL拼接: {url}")
                
                # 计算相对路径
                rel_path = os.path.relpath(file_path, self.project_path)
                
                api_calls.append(ApiCall(
                    file_path=rel_path,
                    line_number=line_num,
                    method=method,
                    url=url,
                    component_name=component_name,
                    call_type=f'custom-{api_func_name}'
                ))
        
        # 模式2：beehiveApi.xxxController.xxxMethod() 或 orderApi.xxxController.xxxMethod()
        # 这是链式调用模式，需要特殊处理
        chain_api_calls = self._extract_chain_api_calls(code, file_path, component_name, lines)
        api_calls.extend(chain_api_calls)
        
        return api_calls
    
    def _extract_chain_api_calls(self, code: str, file_path: str, 
                                 component_name: Optional[str], 
                                 lines: List[str]) -> List[ApiCall]:
        """
        提取链式API调用
        支持两种模式：
        1. 三段式：beehiveApi.companyController.getCompanysOnCompanyType({...})
        2. 两段式：orderApi.getOrderDetailReport({...})（从 controller 文件导入的）
        
        Args:
            code: 源代码内容
            file_path: 文件路径
            component_name: 组件名称
            lines: 代码行列表
            
        Returns:
            API调用列表
        """
        api_calls = []
        
        # 模式1：三段式链式调用 xxxApi.xxxController.xxxMethod(
        # 例如：beehiveApi.companyController.getCompanysOnCompanyType(
        #      orderApi.ofOrderController.pageOrder(
        chain_pattern_3 = r'(\w+Api)\.(\w+Controller)\.(\w+)\s*\('
        
        for line_num, line in enumerate(lines, 1):
            matches = re.finditer(chain_pattern_3, line)
            
            for match in matches:
                api_name = match.group(1)  # beehiveApi, orderApi
                controller_name = match.group(2)  # companyController, ofOrderController
                method_name = match.group(3)  # getCompanysOnCompanyType, pageOrder
                
                # 推断HTTP方法（基于方法名）
                method = self._infer_http_method(method_name)
                
                # 尝试从 controller 文件中提取实际的 URL
                # 首先找到 controller 文件路径
                controller_file_path = self._get_controller_file_path_for_chain_call(
                    code, api_name, controller_name
                )
                
                actual_url = None
                if controller_file_path:
                    actual_url = self._extract_actual_url_from_controller(
                        controller_file_path, 
                        method_name
                    )
                
                if actual_url:
                    # 使用从 controller 文件中提取的实际 URL
                    url = actual_url
                    logger.info(f"[链式调用-Controller解析] 成功提取实际URL: {api_name}.{controller_name}.{method_name}() -> {url}")
                else:
                    # 构建API路径（基于controller和method名称，回退方案）
                    # 例如：companyController.getCompanysOnCompanyType -> /company/getCompanysOnCompanyType
                    url = self._construct_api_url(controller_name, method_name)
                    if controller_file_path:
                        logger.warning(f"[链式调用-Controller解析] 无法提取实际URL，使用构建的URL: {url}")
                    else:
                        logger.debug(f"[链式调用] 未找到controller文件，使用构建的URL: {url}")
                
                # 尝试拼接 baseURL
                # 优先使用 API 名称查找 baseURL（如 beehiveApi -> beehiveApi.js）
                base_url = self._get_base_url_by_api_name(api_name)
                if not base_url:
                    # 如果找不到，尝试从文件路径推断
                    base_url = self._get_base_url_for_file(file_path)
                
                if base_url and not url.startswith('http'):
                    # 确保拼接正确：去除重复的斜杠
                    if base_url.endswith('/') and url.startswith('/'):
                        url = base_url + url[1:]
                    elif not base_url.endswith('/') and not url.startswith('/'):
                        url = base_url + '/' + url
                    else:
                        url = base_url + url
                    logger.info(f"[链式调用] 拼接 baseURL: {base_url} + {actual_url if actual_url else self._construct_api_url(controller_name, method_name)} = {url}")
                else:
                    if not base_url:
                        logger.warning(f"[链式调用] 未找到 baseURL，API: {api_name}, 文件: {file_path}, URL: {url}")
                
                # 计算相对路径
                rel_path = os.path.relpath(file_path, self.project_path)
                
                api_calls.append(ApiCall(
                    file_path=rel_path,
                    line_number=line_num,
                    method=method,
                    url=url,
                    component_name=component_name,
                    call_type=f'chain-{api_name}.{controller_name}'
                ))
        
        # 模式2：两段式链式调用 xxxApi.xxxMethod(
        # 例如：orderApi.getOrderDetailReport(
        # 这种情况下，xxxApi 是从 controller 文件导入的，已经包含了 controller 信息
        chain_pattern_2 = r'(\w+Api)\.(\w+)\s*\('
        
        for line_num, line in enumerate(lines, 1):
            # 跳过已经被模式1匹配的（避免重复）
            if re.search(chain_pattern_3, line):
                continue
            
            matches = re.finditer(chain_pattern_2, line)
            
            for match in matches:
                api_name = match.group(1)  # orderApi
                method_name = match.group(2)  # getOrderDetailReport
                
                # 推断HTTP方法（基于方法名）
                method = self._infer_http_method(method_name)
                
                # 对于两段式调用，我们需要从 import 语句中推断 controller 名称
                # 例如：import orderApi from '@/api/serviceAApi/controller/orderController.js'
                controller_name = self._infer_controller_from_import(code, api_name)
                controller_file_path = self._get_controller_file_path(code, api_name)
                
                # 尝试从 controller 文件中提取实际的 HTTP 路径
                actual_url = None
                if controller_file_path:
                    actual_url = self._extract_actual_url_from_controller(
                        controller_file_path, 
                        method_name
                    )
                
                if actual_url:
                    # 使用从 controller 文件中提取的实际 URL
                    url = actual_url
                    logger.info(f"[Controller解析] 成功提取实际URL: {method_name} -> {url}")
                elif controller_name:
                    # 构建API路径（回退方案）
                    url = self._construct_api_url(controller_name, method_name)
                    logger.warning(f"[Controller解析] 无法提取实际URL，使用构建的URL: {url}")
                else:
                    # 如果无法推断 controller，使用 api_name 作为 controller
                    # 例如：orderApi -> order
                    controller_base = api_name.replace('Api', '')
                    url = f'/{self._camel_to_kebab(controller_base)}/{method_name}'
                    logger.warning(f"[Controller解析] 无法推断controller，使用默认URL: {url}")
                
                # 尝试拼接 baseURL
                base_url = self._get_base_url_for_file(file_path)
                if base_url and not url.startswith('http'):
                    # 确保拼接正确：去除重复的斜杠
                    if base_url.endswith('/') and url.startswith('/'):
                        url = base_url + url[1:]
                    elif not base_url.endswith('/') and not url.startswith('/'):
                        url = base_url + '/' + url
                    else:
                        url = base_url + url
                    logger.debug(f"拼接 baseURL (两段式链式调用): {base_url} + {url} = {url}")
                
                # 计算相对路径
                rel_path = os.path.relpath(file_path, self.project_path)
                
                api_calls.append(ApiCall(
                    file_path=rel_path,
                    line_number=line_num,
                    method=method,
                    url=url,
                    component_name=component_name,
                    call_type=f'chain-{api_name}'
                ))
        
        return api_calls
    
    def _infer_controller_from_import(self, code: str, api_name: str) -> Optional[str]:
        """
        从 import 语句中推断 controller 名称
        
        例如：
        import orderApi from '@/api/serviceAApi/controller/orderController.js'
        -> orderController
        
        Args:
            code: 源代码内容
            api_name: API 变量名，如 orderApi
            
        Returns:
            controller 名称，如 orderController
        """
        # 匹配 import 语句
        # import orderApi from '@/api/serviceAApi/controller/orderController.js'
        # import { orderApi } from '@/api/serviceAApi/controller/orderController.js'
        patterns = [
            rf'import\s+{api_name}\s+from\s+[\'"].*?/(\w+Controller)\.js[\'"]',
            rf'import\s+\{{\s*{api_name}\s*\}}\s+from\s+[\'"].*?/(\w+Controller)\.js[\'"]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                return match.group(1)
        
        return None
    
    def _get_controller_file_path(self, code: str, api_name: str) -> Optional[str]:
        """
        从 import 语句中获取 controller 文件的完整路径
        
        例如：
        import orderApi from '@/api/serviceAApi/controller/orderController.js'
        -> workspace/xxx/src/api/serviceAApi/controller/orderController.js
        
        Args:
            code: 源代码内容
            api_name: API 变量名，如 orderApi
            
        Returns:
            controller 文件的完整路径
        """
        # 匹配 import 语句，提取完整路径
        patterns = [
            rf'import\s+{api_name}\s+from\s+[\'"]([^\'"]+)[\'"]',
            rf'import\s+\{{\s*{api_name}\s*\}}\s+from\s+[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                import_path = match.group(1)
                
                # 处理 @ 别名（通常指向 src 目录）
                if import_path.startswith('@/'):
                    import_path = import_path.replace('@/', 'src/')
                elif import_path.startswith('~/'):
                    import_path = import_path.replace('~/', 'src/')
                
                # 移除 .js 扩展名（如果有）
                if import_path.endswith('.js'):
                    import_path = import_path[:-3]
                
                # 添加 .js 扩展名
                import_path += '.js'
                
                # 构建完整路径
                full_path = os.path.join(self.project_path, import_path)
                
                # 检查文件是否存在
                if os.path.exists(full_path):
                    logger.debug(f"[Controller路径] 找到controller文件: {full_path}")
                    return full_path
                else:
                    logger.warning(f"[Controller路径] controller文件不存在: {full_path}")
        
        return None
    
    def _get_controller_file_path_for_chain_call(self, code: str, api_name: str, controller_name: str) -> Optional[str]:
        """
        从三段式链式调用中找到 controller 文件路径
        
        例如：
        beehiveApi.bankController.distinctCodeList()
        -> controller 文件路径: src/api/beehiveApi/controller/bankController.js
        
        注意：beehiveApi 通常是通过 require.context 动态加载的，
        所以直接从标准路径查找：src/api/{api_name}/controller/{controller_name}.js
        
        Args:
            code: 源代码内容
            api_name: API 变量名，如 beehiveApi, orderApi
            controller_name: Controller 名称，如 bankController
            
        Returns:
            controller 文件的完整路径
        """
        # 直接尝试标准路径结构
        # 例如：src/api/beehiveApi/controller/bankController.js
        controller_file = f'src/api/{api_name}/controller/{controller_name}.js'
        full_path = os.path.join(self.project_path, controller_file)
        
        # 检查文件是否存在
        if os.path.exists(full_path):
            logger.debug(f"[链式调用-Controller路径] 找到controller文件: {full_path}")
            return full_path
        
        # 尝试另一种可能的路径结构（如果 api_name 有变化）
        # 例如：beehiveApi -> beehive-order-finance-api
        alt_paths = [
            os.path.join(self.project_path, 'src', 'api', api_name.replace('Api', ''), 'controller', f'{controller_name}.js'),
            os.path.join(self.project_path, 'src', 'api', api_name.lower(), 'controller', f'{controller_name}.js'),
        ]
        
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                logger.debug(f"[链式调用-Controller路径] 找到controller文件（备用路径）: {alt_path}")
                return alt_path
        
        logger.warning(f"[链式调用-Controller路径] controller文件不存在: {full_path}")
        return None
    
    def _get_base_url_by_api_name(self, api_name: str) -> Optional[str]:
        """
        根据 API 名称查找 baseURL
        
        Args:
            api_name: API 名称，如 beehiveApi, orderApi
            
        Returns:
            baseURL，如 '/scfpc-web'
        """
        # 尝试多种可能的文件名
        possible_files = [
            f'{api_name}.js',
            f'{api_name}.ts',
        ]
        
        for file_name in possible_files:
            if file_name in self._base_url_cache:
                logger.debug(f"[BaseURL查找] 通过API名称找到: {api_name} -> {file_name} -> {self._base_url_cache[file_name]}")
                return self._base_url_cache[file_name]
        
        logger.debug(f"[BaseURL查找] 未找到API名称对应的baseURL: {api_name}")
        return None
    
    def _extract_actual_url_from_controller(self, controller_file_path: str, method_name: str) -> Optional[str]:
        """
        从 controller 文件中提取指定方法的实际 HTTP 请求路径
        
        例如：
        getOrderDetailReport(orderId) {
            return new Promise((resolve, reject) => {
                serviceAApi({
                    url: `/orders/${orderId}/detail-report`,
                    method: 'GET'
                })
            })
        }
        -> /orders/${orderId}/detail-report
        
        Args:
            controller_file_path: controller 文件路径
            method_name: 方法名，如 getOrderDetailReport
            
        Returns:
            实际的 HTTP 请求路径
        """
        try:
            with open(controller_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找方法定义
            # 匹配：methodName(params) { ... }
            # 或：methodName: function(params) { ... }
            method_pattern = rf'{method_name}\s*[:\(]'
            method_match = re.search(method_pattern, content)
            
            if not method_match:
                logger.warning(f"[Controller解析] 未找到方法定义: {method_name}")
                return None
            
            # 从方法定义开始，提取方法体
            method_start = method_match.start()
            
            # 确保不是在注释中（简单检查：向前看是否有 //）
            line_start = content.rfind('\n', 0, method_start) + 1
            line_before_method = content[line_start:method_start]
            if '//' in line_before_method:
                # 在注释中，查找下一个匹配
                logger.info(f"[Controller解析] 跳过注释中的方法名: 位置={method_start}")
                # 从当前位置之后继续查找
                next_match = re.search(method_pattern, content[method_start + len(method_name):])
                if next_match:
                    method_start = method_start + len(method_name) + next_match.start()
                    logger.info(f"[Controller解析] 找到实际方法定义: 位置={method_start}")
                else:
                    logger.warning(f"[Controller解析] 未找到实际方法定义: {method_name}")
                    return None
            
            # 找到方法体的开始位置（第一个 { ）
            # 策略：找到方法名后，跳过参数括号，然后找第一个 {
            method_body_start = -1
            paren_count = 0
            found_params = False
            
            for i in range(method_start, len(content)):
                char = content[i]
                
                if char == '(':
                    paren_count += 1
                    found_params = True
                elif char == ')':
                    paren_count -= 1
                elif char == '{' and found_params and paren_count == 0:
                    # 找到参数括号后的第一个 {
                    method_body_start = i
                    logger.info(f"[Controller解析] 找到方法体开始: 位置={i}")
                    break
            
            if method_body_start == -1:
                logger.warning(f"[Controller解析] 无法找到方法体开始: {method_name}")
                return None
            
            logger.info(f"[Controller解析] 方法体开始位置: {method_body_start}, 字符: '{content[method_body_start:method_body_start+10]}'")
            
            # 找到方法体的结束位置（匹配大括号）
            # 需要跳过字符串和模板字符串中的大括号
            brace_count = 0
            method_body_end = -1
            in_string = False
            in_template = False
            string_char = None
            i = method_body_start
            
            while i < len(content):
                char = content[i]
                
                # 处理字符串
                if char in ('"', "'") and not in_template:
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char and (i == 0 or content[i-1] != '\\'):
                        in_string = False
                        string_char = None
                
                # 处理模板字符串
                elif char == '`':
                    if not in_string:
                        in_template = not in_template
                
                # 只在非字符串、非模板字符串中计数大括号
                elif not in_string and not in_template:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            method_body_end = i
                            break
                
                i += 1
            
            if method_body_start == -1 or method_body_end == -1:
                logger.warning(f"[Controller解析] 无法提取方法体: {method_name}, start={method_body_start}, end={method_body_end}")
                return None
            
            logger.info(f"[Controller解析] 方法体结束位置: {method_body_end}, 字符: '{content[method_body_end-10:method_body_end+1]}'")
            
            method_body = content[method_body_start:method_body_end + 1]
            
            logger.info(f"[Controller解析] 方法体长度: {len(method_body)}")
            logger.info(f"[Controller解析] 方法体前200字符: {method_body[:200]}")
            
            # 在方法体中查找 url 字段
            # 匹配：url: '/orders/${orderId}/detail-report'
            # 或：url: `/orders/${orderId}/detail-report`
            url_patterns = [
                r'url\s*:\s*`([^`]+)`',  # url: `...` (模板字符串)
                r'url\s*:\s*[\'"]([^\'"]+)[\'"]',  # url: '...' 或 url: "..."
            ]
            
            for url_pattern in url_patterns:
                url_match = re.search(url_pattern, method_body)
                if url_match:
                    url = url_match.group(1)
                    logger.info(f"[Controller解析] 成功提取URL: {method_name} -> {url}")
                    return url
                else:
                    logger.info(f"[Controller解析] 模式未匹配: {url_pattern}")
            
            logger.warning(f"[Controller解析] 未找到URL字段: {method_name}")
            return None
            
        except Exception as e:
            logger.error(f"[Controller解析] 解析失败: {controller_file_path}, 错误: {e}")
            return None
    
    def _infer_http_method(self, method_name: str) -> str:
        """
        根据方法名推断HTTP方法
        
        Args:
            method_name: 方法名，如 getCompanysOnCompanyType, pageOrder, delOrder
            
        Returns:
            HTTP方法：GET, POST, PUT, DELETE
        """
        method_lower = method_name.lower()
        
        # 常见的方法名前缀映射
        if method_lower.startswith('get') or method_lower.startswith('query') or \
           method_lower.startswith('list') or method_lower.startswith('page') or \
           method_lower.startswith('find') or method_lower.startswith('search'):
            return 'GET'
        elif method_lower.startswith('del') or method_lower.startswith('delete') or \
             method_lower.startswith('remove') or 'delete' in method_lower:
            return 'DELETE'
        elif method_lower.startswith('update') or method_lower.startswith('edit') or \
             method_lower.startswith('modify') or method_lower.startswith('put'):
            return 'PUT'
        elif method_lower.startswith('add') or method_lower.startswith('create') or \
             method_lower.startswith('insert') or method_lower.startswith('save') or \
             method_lower.startswith('post') or method_lower.startswith('submit') or \
             method_lower.startswith('export') or method_lower.startswith('import'):
            return 'POST'
        else:
            # 默认为POST（因为大多数业务操作是POST）
            return 'POST'
    
    def _construct_api_url(self, controller_name: str, method_name: str) -> str:
        """
        根据controller和method名称构建API URL
        
        Args:
            controller_name: controller名称，如 companyController, ofOrderController
            method_name: 方法名，如 getCompanysOnCompanyType, pageOrder
            
        Returns:
            API URL，如 /company/getCompanysOnCompanyType
        """
        # 移除Controller后缀
        controller_base = controller_name.replace('Controller', '')
        
        # 转换为短横线命名
        # ofOrderController -> of-order
        # companyController -> company
        controller_path = self._camel_to_kebab(controller_base)
        
        # 构建完整URL
        url = f'/{controller_path}/{method_name}'
        
        return url
    
    def _extract_component_name(self, file_path: str, code: str) -> Optional[str]:
        """
        从文件名或代码中提取组件名称
        
        Args:
            file_path: 文件路径
            code: 源代码内容
            
        Returns:
            组件名称
        """
        # 首先从文件名推断
        file_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(file_name)[0]
        
        # 如果文件名是有效的组件名（首字母大写），直接使用
        if name_without_ext and name_without_ext[0].isupper():
            return name_without_ext
        
        # 尝试从代码中提取
        # 匹配 class 组件: class MyComponent extends
        class_match = re.search(r'class\s+(\w+)\s+extends', code)
        if class_match:
            return class_match.group(1)
        
        # 匹配函数组件: function MyComponent() 或 const MyComponent = () =>
        func_match = re.search(r'(?:function|const)\s+(\w+)\s*[=\(]', code)
        if func_match:
            name = func_match.group(1)
            if name and name[0].isupper():
                return name
        
        # 匹配默认导出: export default MyComponent
        export_match = re.search(r'export\s+default\s+(\w+)', code)
        if export_match:
            name = export_match.group(1)
            if name and name[0].isupper():
                return name
        
        return name_without_ext

    
    def _extract_ui_entry_info(self, api_call: ApiCall, code: str, file_path: str):
        """
        提取API调用的UI入口信息（按钮文本、触发元素等）
        
        Args:
            api_call: API调用对象
            code: 源代码内容
            file_path: 文件路径
        """
        lines = code.split('\n')
        target_line_num = api_call.line_number
        
        # 向前查找触发元素（最多向前看30行）
        search_start = max(0, target_line_num - 30)
        search_end = min(len(lines), target_line_num + 5)
        context = '\n'.join(lines[search_start:search_end])
        
        # 1. 提取触发元素类型和文本
        trigger_info = self._find_trigger_element(context, lines, target_line_num)
        if trigger_info:
            api_call.trigger_element = trigger_info['element_type']
            api_call.trigger_text = trigger_info['text']
        
        # 2. 尝试从文件路径推断页面路由
        api_call.page_route = self._infer_page_route(file_path)
        
        # 3. 尝试提取菜单路径（从注释或文件结构）
        api_call.menu_path = self._extract_menu_path(code, file_path)
    
    def _find_trigger_element(self, context: str, lines: List[str], target_line: int) -> Optional[dict]:
        """
        查找触发API调用的UI元素
        
        对于Vue文件，需要特殊处理：
        1. 在template中查找按钮
        2. 在script中查找方法名
        3. 关联按钮的@click和方法名
        
        Returns:
            {'element_type': 'button/link/form', 'text': '按钮文本'}
        """
        # 首先尝试在整个文件中查找（对于Vue文件）
        full_file_context = '\n'.join(lines)
        
        # 提取当前API调用所在的方法名
        # 向前查找方法定义
        method_name = None
        for i in range(target_line - 1, max(0, target_line - 50), -1):
            line = lines[i]
            # 匹配方法定义：methodName() { 或 methodName: function() {
            method_match = re.search(r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{', line)
            if not method_match:
                method_match = re.search(r'(\w+)\s*:\s*(?:async\s+)?function\s*\(', line)
            
            if method_match:
                method_name = method_match.group(1)
                break
        
        # 如果找到了方法名，在template中查找调用这个方法的按钮
        if method_name:
            # 在template中查找 @click="methodName" 或 @click="methodName()"
            button_patterns = [
                # <lls-button ... @click="methodName">按钮文本</lls-button>
                (rf'<lls-button[^>]*@click\s*=\s*["\']({method_name}(?:\([^)]*\))?)["\'][^>]*>([^<]+)</lls-button>', 'button'),
                # <button ... @click="methodName">按钮文本</button>
                (rf'<button[^>]*@click\s*=\s*["\']({method_name}(?:\([^)]*\))?)["\'][^>]*>([^<]+)</button>', 'button'),
                # <lls-button ... @click="methodName" icon="xxx">按钮文本</lls-button>
                (rf'<lls-button[^>]*@click\s*=\s*["\']({method_name}(?:\([^)]*\))?)["\'][^>]*>([^<]+)</lls-button>', 'button'),
                # <a ... @click="methodName">链接文本</a>
                (rf'<a[^>]*@click\s*=\s*["\']({method_name}(?:\([^)]*\))?)["\'][^>]*>([^<]+)</a>', 'link'),
            ]
            
            for pattern, element_type in button_patterns:
                matches = re.finditer(pattern, full_file_context, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    text = match.group(2).strip()
                    # 清理文本（移除多余空格、换行和HTML标签）
                    text = re.sub(r'<[^>]+>', '', text)  # 移除HTML标签
                    text = re.sub(r'\s+', ' ', text)  # 合并空格
                    text = text.strip()
                    
                    if text and len(text) < 50:  # 文本不能太长
                        return {'element_type': element_type, 'text': text}
        
        # 如果上面的方法没找到，使用原来的通用模式
        # 常见的触发模式
        patterns = [
            # Button组件: <Button onClick={handleSubmit}>提交</Button>
            (r'<Button[^>]*onClick[^>]*>([^<]+)</Button>', 'button'),
            # button标签: <button onClick={...}>查询</button>
            (r'<button[^>]*onClick[^>]*>([^<]+)</button>', 'button'),
            # lls-button: <lls-button @click="...">搜索</lls-button>
            (r'<lls-button[^>]*@click[^>]*>([^<]+)</lls-button>', 'button'),
            # a标签: <a onClick={...}>删除</a>
            (r'<a[^>]*onClick[^>]*>([^<]+)</a>', 'link'),
            # Form提交: <Form onSubmit={...}>
            (r'<Form[^>]*onSubmit', 'form'),
            # form标签: <form onSubmit={...}>
            (r'<form[^>]*onSubmit', 'form'),
            # 中文按钮文本模式（更宽松）
            (r'onClick.*?[>"]([^<>"]+?按钮|查询|搜索|提交|保存|删除|编辑|新增|确定|取消)', 'button'),
        ]
        
        for pattern, element_type in patterns:
            match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
            if match:
                # 提取文本内容
                if match.lastindex and match.lastindex >= 1:
                    text = match.group(1).strip()
                    # 清理文本（移除多余空格和换行）
                    text = re.sub(r'\s+', ' ', text)
                    if text and len(text) < 50:  # 文本不能太长
                        return {'element_type': element_type, 'text': text}
                else:
                    return {'element_type': element_type, 'text': None}
        
        # 不再从函数名推断操作类型（避免写死映射）
        # 如果没有找到明确的触发元素，返回None
        return None
    
    def _infer_page_route(self, file_path: str) -> Optional[str]:
        """
        从文件路径推断页面路由
        
        例如:
        - src/pages/OrderList.jsx -> /orders/list
        - src/views/user/UserManage.jsx -> /user/manage
        """
        # 提取pages或views后的路径
        path_parts = file_path.replace('\\', '/').split('/')
        
        try:
            # 查找pages或views的索引
            if 'pages' in path_parts:
                start_idx = path_parts.index('pages') + 1
            elif 'views' in path_parts:
                start_idx = path_parts.index('views') + 1
            else:
                return None
            
            # 提取路径部分
            route_parts = path_parts[start_idx:]
            
            # 移除文件扩展名
            if route_parts:
                route_parts[-1] = os.path.splitext(route_parts[-1])[0]
            
            # 转换为小写并用连字符连接
            # OrderList -> order-list
            route_parts = [self._camel_to_kebab(part) for part in route_parts]
            
            # 构建路由
            route = '/' + '/'.join(route_parts)
            return route
            
        except (ValueError, IndexError):
            return None
    
    def _camel_to_kebab(self, name: str) -> str:
        """将驼峰命名转换为短横线命名"""
        # OrderList -> order-list
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()
    
    def _extract_menu_path(self, code: str, file_path: str) -> Optional[str]:
        """
        提取菜单路径
        
        尝试从以下位置提取：
        1. 文件顶部的注释（如 // 菜单：订单管理 > 订单列表）
        2. 从菜单配置文件中查找（主要方法）
        """
        logger.info(f"[菜单路径提取] 开始提取菜单路径: {file_path}")
        
        # 【关键日志】检查是否是目标文件
        is_target_file = '/balanceManageHome' in file_path or 'balanceManageHome' in file_path
        if is_target_file:
            logger.info(f"[菜单路径提取-关键] 🔍 检测到目标文件: {file_path}")
        
        # 1. 查找注释中的菜单路径
        menu_patterns = [
            r'//\s*菜单[：:]\s*(.+)',
            r'/\*\s*菜单[：:]\s*(.+?)\*/',
            r'//\s*@menu\s+(.+)',
        ]
        
        for pattern in menu_patterns:
            match = re.search(pattern, code)
            if match:
                menu_path = match.group(1).strip()
                logger.info(f"[菜单路径提取] 从注释中找到菜单路径: {menu_path}")
                # 【关键日志】检查注释中的菜单路径是否正确
                if is_target_file:
                    logger.info(f"[菜单路径提取-关键] 🔍 从注释中找到菜单路径: '{menu_path}'")
                    if '企业信息' in menu_path:
                        logger.error(f"[菜单路径提取-关键] ❌❌❌ 错误！注释中的菜单路径包含'企业信息': '{menu_path}'")
                return menu_path
        
        # 2. 从菜单配置文件中查找（主要方法，不使用写死的映射）
        menu_path_from_config = self._find_menu_from_config(file_path)
        if menu_path_from_config:
            logger.info(f"[菜单路径提取] 从配置文件中找到菜单路径: {menu_path_from_config}")
            # 【关键日志】检查配置文件中的菜单路径是否正确
            if is_target_file:
                logger.info(f"[菜单路径提取-关键] 🔍 从配置文件中找到菜单路径: '{menu_path_from_config}'")
                if '企业信息' in menu_path_from_config:
                    logger.error(f"[菜单路径提取-关键] ❌❌❌ 错误！配置文件中的菜单路径包含'企业信息': '{menu_path_from_config}' (应该是'准入授信')")
                elif '准入授信' in menu_path_from_config:
                    logger.info(f"[菜单路径提取-关键] ✅ 正确！配置文件中的菜单路径包含'准入授信': '{menu_path_from_config}'")
            return menu_path_from_config
        
        # 如果都没找到，返回None（不再使用写死的映射）
        logger.warning(f"[菜单路径提取] 未找到菜单路径: {file_path}")
        return None
    
    def _load_menu_config(self) -> Optional[str]:
        """
        加载菜单配置文件内容（包括侧边栏菜单和顶部菜单）
        
        Returns:
            菜单配置文件内容，如果文件不存在则返回None
        """
        if self._menu_config_cache is not None:
            logger.info(f"[菜单配置] 使用缓存的菜单配置")
            return self._menu_config_cache
        
        # 查找菜单配置文件（支持多种可能的路径）
        # 包括侧边栏菜单（menu.js）和顶部菜单（topMenu.vue）
        possible_paths = [
            os.path.join(self.project_path, 'src', 'views', 'container', 'components', 'menu.js'),
            os.path.join(self.project_path, 'src', 'router', 'menu.js'),
            os.path.join(self.project_path, 'src', 'config', 'menu.js'),
            os.path.join(self.project_path, 'src', 'menu.js'),
        ]
        
        # 添加顶部菜单文件路径
        top_menu_paths = [
            os.path.join(self.project_path, 'src', 'views', 'container', 'components', 'topMenu.vue'),
            os.path.join(self.project_path, 'src', 'components', 'topMenu.vue'),
        ]
        
        # 规范化所有路径（统一使用操作系统的路径分隔符）
        possible_paths = [os.path.normpath(p) for p in possible_paths]
        top_menu_paths = [os.path.normpath(p) for p in top_menu_paths]
        
        logger.info(f"[菜单配置] 开始查找菜单配置文件，项目路径: {self.project_path}")
        logger.info(f"[菜单配置] 尝试的路径: {possible_paths + top_menu_paths}")
        
        combined_content = ""
        
        # 加载侧边栏菜单
        for menu_path in possible_paths:
            logger.info(f"[菜单配置] 检查路径: {menu_path}, 存在: {os.path.exists(menu_path)}")
            if os.path.exists(menu_path):
                try:
                    with open(menu_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        combined_content += content + "\n"
                        logger.info(f"[菜单配置] OK 成功加载侧边栏菜单配置: {menu_path}, 内容长度: {len(content)}")
                except Exception as e:
                    logger.warning(f"[菜单配置] ✗ 读取菜单配置文件失败 {menu_path}: {e}")
        
        # 加载顶部菜单
        for top_menu_path in top_menu_paths:
            logger.info(f"[菜单配置] 检查顶部菜单路径: {top_menu_path}, 存在: {os.path.exists(top_menu_path)}")
            if os.path.exists(top_menu_path):
                try:
                    with open(top_menu_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        combined_content += content + "\n"
                        logger.info(f"[菜单配置] OK 成功加载顶部菜单配置: {top_menu_path}, 内容长度: {len(content)}")
                except Exception as e:
                    logger.warning(f"[菜单配置] ✗ 读取顶部菜单配置文件失败 {top_menu_path}: {e}")
        
        if combined_content:
            self._menu_config_cache = combined_content
            logger.info(f"[菜单配置] OK 成功加载菜单配置，总内容长度: {len(combined_content)}")
            return self._menu_config_cache
        
        logger.warning(f"[菜单配置] ✗ 未找到任何菜单配置文件")
        self._menu_config_cache = ""  # 缓存空字符串，避免重复查找
        return None
    
    def _extract_port_from_comment(self, menu_content: str, menu_position: int) -> str:
        """
        从菜单配置文件的注释中提取端口信息
        
        Args:
            menu_content: 菜单配置文件内容
            menu_position: 当前菜单项在内容中的位置
            
        Returns:
            端口前缀，如 "[核企端] "、"[供应商端] "、"[资方端] " 等
            如果无法识别，返回空字符串
        """
        # 向前查找最近的注释（最多向前看2000个字符）
        search_start = max(0, menu_position - 2000)
        before_text = menu_content[search_start:menu_position]
        
        # 查找所有注释行
        # 匹配：// xxx菜单 或 // xxx
        comment_pattern = r'//\s*([^\n]+)'
        comment_matches = list(re.finditer(comment_pattern, before_text))
        
        if not comment_matches:
            return ""
        
        # 获取最近的注释（最后一个匹配）
        last_comment = comment_matches[-1].group(1).strip()
        
        logger.debug(f"[端口识别] 找到注释: '{last_comment}' (位置: {search_start + comment_matches[-1].start()})")
        
        # 根据注释内容判断端口类型
        # 注意：需要处理多种可能的表述方式
        port_mapping = {
            '供应商': '[供应商端] ',
            '核心企业': '[核企端] ',
            '核企': '[核企端] ',
            '资金方': '[资方端] ',
            '资方': '[资方端] ',
            '农行': '[农行端] ',
        }
        
        for keyword, prefix in port_mapping.items():
            if keyword in last_comment:
                logger.info(f"[端口识别] 识别到端口: '{last_comment}' -> {prefix}")
                return prefix
        
        # 如果无法识别，返回空字符串
        logger.debug(f"[端口识别] 无法识别端口类型: '{last_comment}'")
        return ""
    
    def _build_menu_url_map(self) -> dict:
        """
        构建URL到菜单路径的映射
        
        Returns:
            {'/orderManage': '[核企端] 资产管理 > 订单管理', ...}
        """
        if self._menu_url_to_path_map is not None:
            return self._menu_url_to_path_map
        
        self._menu_url_to_path_map = {}
        
        menu_content = self._load_menu_config()
        if not menu_content:
            return self._menu_url_to_path_map
        
        # 解析菜单配置，构建URL到菜单路径的映射
        
        # 模式1: 侧边栏菜单格式 - menuName: "xxx", url: "/xxx"
        # 支持跨行匹配（menuName 和 url 可能在不同行）
        # 使用非贪婪匹配，限制在遇到 } 或下一个 menuName 之前
        pattern1 = r'menuName:\s*["\']([^"\']+)["\'][\s\S]*?url:\s*["\']([^"\']+)["\']'
        
        matches = re.finditer(pattern1, menu_content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            menu_name = match.group(1)
            url = match.group(2)
            
            # 【新增】提取端口信息（从注释中识别）
            port_prefix = self._extract_port_from_comment(menu_content, match.start())
            
            # 【新增】提取端口信息（从注释中识别）
            port_prefix = self._extract_port_from_comment(menu_content, match.start())
            
            # 【关键日志】记录 /balanceManageHome 的映射过程
            if url == '/balanceManageHome':
                logger.info(f"[菜单映射-关键] 🔍 找到目标URL: {url}, 菜单名称: {menu_name}, 端口: {port_prefix}, 匹配位置: {match.start()}-{match.end()}")
                logger.info(f"[菜单映射-关键] 🔍 匹配文本片段: {menu_content[max(0, match.start()-200):match.end()+200]}")
                logger.info(f"[菜单映射-关键] 🔍 菜单名称应该是'准入授信'，实际是: '{menu_name}'")
            
            # 查找父菜单
            # 【关键日志】如果是目标URL，强制启用详细日志
            if url == '/balanceManageHome':
                parent_menu = self._find_parent_menu(menu_content, match.start(), menu_name)
            else:
                parent_menu = self._find_parent_menu(menu_content, match.start(), "")
            
            # 构建完整菜单路径（包含端口前缀）
            if parent_menu:
                full_path = f"{port_prefix}{parent_menu} > {menu_name}"
            else:
                full_path = f"{port_prefix}{menu_name}"
            
            # 【关键日志】记录 /balanceManageHome 的最终映射结果
            if url == '/balanceManageHome':
                logger.info(f"[菜单映射-关键] ✅ URL {url} 的最终菜单路径: '{full_path}' (端口: {port_prefix}, 父菜单: {parent_menu if parent_menu else '无'})")
                if parent_menu:
                    logger.error(f"[菜单映射-关键] ❌❌❌ 错误！'/balanceManageHome' 不应该有父菜单，但找到了父菜单: '{parent_menu}'")
                    logger.error(f"[菜单映射-关键] ❌❌❌ 这会导致菜单路径变成 '{full_path}'，应该是 '{port_prefix}{menu_name}'")
                else:
                    logger.info(f"[菜单映射-关键] ✅ 正确！'/balanceManageHome' 没有父菜单，菜单路径是: '{full_path}'")
            
            # 【重要修改】处理 URL 重复的情况
            # 由于现在有端口前缀，同一个 URL 可能对应多个不同端口的菜单
            # 策略：保留所有端口的菜单路径，用 " | " 分隔
            if url in self._menu_url_to_path_map:
                old_path = self._menu_url_to_path_map[url]
                
                # 检查是否是相同端口的重复（通过端口前缀判断）
                # 提取旧路径的端口前缀
                old_port_prefix = ""
                if old_path.startswith('['):
                    end_bracket = old_path.find(']')
                    if end_bracket != -1:
                        old_port_prefix = old_path[:end_bracket + 2]  # 包括 "] "
                
                if old_port_prefix == port_prefix:
                    # 相同端口的重复，需要判断使用哪个路径
                    # 优先使用没有父菜单的版本（顶级菜单）
                    old_has_parent = " > " in old_path
                    new_has_parent = " > " in full_path
                    
                    if old_has_parent and not new_has_parent:
                        # 旧路径有父菜单，新路径没有父菜单，使用新路径（顶级菜单）
                        logger.info(f"[菜单映射] ✅ URL重复(相同端口): {url}, 旧路径: {old_path} (有父菜单), 新路径: {full_path} (顶级菜单), 使用新路径")
                        self._menu_url_to_path_map[url] = full_path
                    elif not old_has_parent and new_has_parent:
                        # 旧路径没有父菜单，新路径有父菜单，保留旧路径（顶级菜单）
                        logger.info(f"[菜单映射] ✅ URL重复(相同端口): {url}, 旧路径: {old_path} (顶级菜单), 新路径: {full_path} (有父菜单), 保留旧路径")
                    else:
                        # 两者都有父菜单或都没有父菜单，使用新路径（后匹配的）
                        logger.warning(f"[菜单映射] ⚠️ URL重复(相同端口): {url}, 旧路径: {old_path}, 新路径: {full_path}, 将使用新路径")
                        self._menu_url_to_path_map[url] = full_path
                else:
                    # 不同端口的重复，保留所有端口的菜单路径
                    # 使用 " | " 分隔多个端口的菜单路径
                    combined_path = f"{old_path} | {full_path}"
                    logger.info(f"[菜单映射] ✅ URL重复(不同端口): {url}, 合并路径: {combined_path}")
                    self._menu_url_to_path_map[url] = combined_path
                    
                    # 【关键日志】如果是目标URL，特别记录
                    if url == '/balanceManageHome':
                        logger.info(f"[菜单映射-关键] ✅✅✅ 目标URL {url} 出现不同端口的重复映射！合并路径: '{combined_path}'")

            else:
                # URL不存在，直接添加
                self._menu_url_to_path_map[url] = full_path
                logger.info(f"[菜单映射] {url} -> {full_path}")
        
        # 模式2: 顶部菜单格式 - menuName: '融资查询', menuPath: '/cashFinanceHome'
        # 支持跨行匹配
        pattern2 = r'menuName:\s*["\']([^"\']+)["\'][\s\S]*?menuPath:\s*["\']([^"\']+)["\']'
        
        matches2 = re.finditer(pattern2, menu_content, re.MULTILINE | re.DOTALL)
        
        for match in matches2:
            menu_name = match.group(1)
            menu_path = match.group(2)
            
            # 顶部菜单通常没有父菜单，直接使用菜单名称
            # 如果URL已经存在，不覆盖（优先使用侧边栏菜单的路径）
            if menu_path not in self._menu_url_to_path_map:
                self._menu_url_to_path_map[menu_path] = menu_name
                logger.info(f"[菜单映射-顶部] {menu_path} -> {menu_name}")
        
        logger.info(f"[菜单映射] 共构建 {len(self._menu_url_to_path_map)} 个URL到菜单路径的映射")
        return self._menu_url_to_path_map
    
    def _find_parent_menu(self, menu_content: str, child_position: int, child_name: str = "") -> Optional[str]:
        """
        查找子菜单的父菜单名称
        
        Args:
            menu_content: 菜单配置内容
            child_position: 子菜单在内容中的位置
            child_name: 子菜单名称（用于调试日志）
            
        Returns:
            父菜单名称，如果没有父菜单则返回None
        """
        # 向前查找最近的父级menuName
        before_text = menu_content[:child_position]
        
        # 查找所有可能的父菜单
        # 改进正则表达式：支持跨行匹配，icon字段可能包含复杂表达式（如require(...)）
        # 使用非贪婪匹配，匹配 menuName 到 children: [ 之间的内容
        parent_pattern = r'menuName:\s*["\']([^"\']+)["\'][\s\S]*?children\s*:\s*\['
        parent_matches = list(re.finditer(parent_pattern, before_text, re.MULTILINE | re.DOTALL))
        
        if not parent_matches:
            if child_name:
                logger.debug(f"[父菜单查找] 子菜单 '{child_name}' (位置: {child_position})：未找到任何父菜单")
            return None
        
        if child_name:
            logger.info(f"[父菜单查找] 子菜单 '{child_name}' (位置: {child_position})：找到 {len(parent_matches)} 个可能的父菜单")
            # 列出所有找到的父菜单
            for idx, pm in enumerate(parent_matches):
                logger.info(f"[父菜单查找]   父菜单 {idx+1}: '{pm.group(1)}' (位置: {pm.start()}-{pm.end()})")
        
        # 找到最后一个父菜单（最近的）
        # 需要确保子菜单在children块内
        # 改进逻辑：使用括号匹配来判断子菜单是否在某个父菜单的children块内
        for pm in reversed(parent_matches):
            parent_name = pm.group(1)
            children_start = pm.end()  # children: [ 之后的位置
            
            # 重要：如果 children_start > child_position，说明这个父菜单在子菜单之后，应该跳过
            if children_start > child_position:
                if child_name:
                    logger.info(f"[父菜单查找] 跳过父菜单 '{parent_name}'：children_start ({children_start}) > child_position ({child_position})，父菜单在子菜单之后")
                continue
            
            between_text = menu_content[children_start:child_position]
            
            if child_name:
                logger.info(f"[父菜单查找] 检查父菜单 '{parent_name}': children_start={children_start}, child_position={child_position}, between_text长度={len(between_text)}")
            
            # 使用栈来准确匹配括号，判断children块是否已经闭合
            bracket_stack = 1  # children: [ 已经打开了一个括号
            found_closing_bracket = False
            i = 0
            while i < len(between_text):
                if between_text[i] == '[':
                    bracket_stack += 1
                elif between_text[i] == ']':
                    bracket_stack -= 1
                    # 如果栈回到0，说明children块已经闭合
                    if bracket_stack == 0:
                        found_closing_bracket = True
                        if child_name:
                            logger.info(f"[父菜单查找] 子菜单 '{child_name}'：跳过父菜单 '{parent_name}'：children块已闭合（在位置 {children_start + i} 检测到匹配的]）")
                        break
                i += 1
            
            # 如果栈 > 0，说明children块还没有闭合，子菜单在这个父菜单的children块内
            if bracket_stack > 0 and not found_closing_bracket:
                if child_name:
                    logger.info(f"[父菜单查找] ✅ 子菜单 '{child_name}'：找到父菜单 '{parent_name}' (位置: {pm.start()}-{pm.end()}, 括号栈: {bracket_stack})")
                    # 【关键日志】如果是"准入授信"，检查父菜单是否正确
                    if child_name == "准入授信" or (child_name and "准入授信" in child_name):
                        logger.error(f"[父菜单查找-关键] ❌❌❌ 错误！'准入授信'被识别为'{parent_name}'的子菜单！")
                        logger.error(f"[父菜单查找-关键] ❌❌❌ '准入授信'应该是顶级菜单，不应该有父菜单！")
                        logger.error(f"[父菜单查找-关键] ❌❌❌ 这会导致菜单路径变成 '{parent_name} > {child_name}'，应该是 '{child_name}'")
                return parent_name
        
        if child_name:
            logger.debug(f"[父菜单查找] 子菜单 '{child_name}'：未找到有效的父菜单")
        return None
    
    def _find_menu_from_config(self, file_path: str, is_component_search: bool = False) -> Optional[str]:
        """
        从菜单配置文件中查找中文菜单名称（动态查找，不使用写死的映射）
        
        Args:
            file_path: Vue文件路径
            is_component_search: 是否是从组件查找中调用的（避免递归）
            
        Returns:
            中文菜单路径，如 "资产管理 > 订单管理"
        """
        # 从文件路径提取路由
        # 例如: src/views/orderFinancing/orderManage.vue -> /orderManage
        path_parts = file_path.replace('\\', '/').split('/')
        
        logger.info(f"[菜单查找] 开始为文件查找菜单: {file_path}")
        
        # 查找views或pages后的路径
        try:
            if 'views' in path_parts:
                views_idx = path_parts.index('views')
            elif 'pages' in path_parts:
                views_idx = path_parts.index('pages')
            else:
                # 文件不在 views 或 pages 目录下（如 src/components/xxx.vue）
                # 尝试查找使用该组件的页面文件（仅在非递归调用时）
                if not is_component_search:
                    logger.info(f"[菜单查找] 文件路径中没有views或pages目录，尝试查找使用该组件的页面: {file_path}")
                    menu_path = self._find_menu_from_component_usage(file_path)
                    if menu_path:
                        return menu_path
                return None
            
            # 检查是否在 components 目录下
            # 如果是组件文件，应该使用父目录的菜单路径
            if 'components' in path_parts:
                components_idx = path_parts.index('components')
                # 获取 components 的父目录名（即页面目录）
                if components_idx > views_idx + 1:
                    parent_dir = path_parts[components_idx - 1]
                    logger.info(f"[菜单查找] 检测到组件文件，使用父目录: {parent_dir}")
                    # 使用父目录名作为路由
                    route = f"/{parent_dir}"
                else:
                    # 如果 components 直接在 views 下，使用文件名
                    file_name = os.path.splitext(path_parts[-1])[0]
                    route = f"/{file_name}"
            else:
                # 普通页面文件，使用文件名
                file_name = os.path.splitext(path_parts[-1])[0]
                route = f"/{file_name}"
            
            logger.info(f"[菜单查找] 提取的路由: {route}")
            
            # 构建URL到菜单路径的映射
            url_map = self._build_menu_url_map()
            
            logger.info(f"[菜单查找] URL映射表包含 {len(url_map)} 个条目")
            if len(url_map) > 0:
                # 只打印前10个映射，避免日志过长
                sample_map = dict(list(url_map.items())[:10])
                logger.info(f"[菜单查找] URL映射表示例: {sample_map}")
            
            # 查找匹配的菜单路径
            if route in url_map:
                menu_path = url_map[route]
                logger.info(f"[菜单查找] OK 找到匹配: {route} -> {menu_path}")
                # 【关键日志】记录 /balanceManageHome 的查找结果
                if route == '/balanceManageHome':
                    logger.info(f"[菜单查找-关键] ✅✅✅ 目标路由 {route} 找到菜单路径: '{menu_path}'")
                    # 检查是否正确
                    if '企业信息' in menu_path:
                        logger.error(f"[菜单查找-关键] ❌❌❌ 错误！目标路由 {route} 被映射到错误的菜单路径: '{menu_path}' (应该是'准入授信')")
                    elif '准入授信' in menu_path:
                        logger.info(f"[菜单查找-关键] ✅ 正确！目标路由 {route} 映射到正确的菜单路径: '{menu_path}'")
                return menu_path
            
            # 如果直接匹配失败，尝试其他可能的路由格式
            # 例如：orderManage 可能对应 /orderManage 或 /order-manage
            route_base = route.lstrip('/')
            alternative_routes = [
                route,
                f"/{self._camel_to_kebab(route_base)}",
            ]
            
            logger.info(f"[菜单查找] 尝试备选路由: {alternative_routes}")
            
            for alt_route in alternative_routes:
                if alt_route in url_map:
                    menu_path = url_map[alt_route]
                    logger.info(f"[菜单查找] OK 通过备选路由找到匹配: {alt_route} -> {menu_path}")
                    # 【关键日志】记录 /balanceManageHome 通过备选路由的查找结果
                    if route == '/balanceManageHome' or alt_route == '/balanceManageHome':
                        logger.info(f"[菜单查找-关键] ✅✅✅ 目标路由通过备选路由找到: {alt_route} -> '{menu_path}'")
                        if '企业信息' in menu_path:
                            logger.error(f"[菜单查找-关键] ❌❌❌ 错误！备选路由 {alt_route} 被映射到错误的菜单路径: '{menu_path}'")
                        elif '准入授信' in menu_path:
                            logger.info(f"[菜单查找-关键] ✅ 正确！备选路由 {alt_route} 映射到正确的菜单路径: '{menu_path}'")
                    return url_map[alt_route]
            
            logger.warning(f"[菜单查找] ✗ 未找到匹配的菜单路径，路由: {route}, 可用路由: {list(url_map.keys())[:20]}")
            
        except (ValueError, IndexError) as e:
            logger.info(f"[菜单查找] 从文件路径提取路由失败: {e}")
        
        return None
    
    def _find_menu_from_component_usage(self, component_file_path: str) -> Optional[str]:
        """
        对于不在 views 目录下的组件文件，查找使用该组件的页面文件，使用页面的菜单路径
        
        Args:
            component_file_path: 组件文件路径（如 src/components/accountForm/accountForm.vue）
            
        Returns:
            菜单路径，如果找到使用该组件的页面文件
        """
        try:
            # 提取组件名称（文件名，不含扩展名）
            component_name = os.path.splitext(os.path.basename(component_file_path))[0]
            # 也尝试提取目录名（如 accountForm/accountForm.vue -> accountForm）
            path_parts = component_file_path.replace('\\', '/').split('/')
            if len(path_parts) >= 2:
                component_dir_name = path_parts[-2]  # 父目录名
            else:
                component_dir_name = component_name
            
            logger.info(f"[组件菜单查找] 查找使用组件 '{component_name}' 或 '{component_dir_name}' 的页面文件")
            
            # 在项目路径下查找 views 目录
            views_dir = os.path.join(self.project_path, 'src', 'views')
            if not os.path.exists(views_dir):
                logger.info(f"[组件菜单查找] views 目录不存在: {views_dir}")
                return None
            
            # 搜索 views 目录下的所有 .vue 文件，查找引用该组件的文件
            import glob
            vue_files = glob.glob(os.path.join(views_dir, '**', '*.vue'), recursive=True)
            
            logger.info(f"[组件菜单查找] 在 {len(vue_files)} 个页面文件中搜索组件引用")
            
            for vue_file in vue_files:
                try:
                    with open(vue_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # 检查是否引用了该组件
                        # 匹配模式：import xxx from "@/components/accountForm/accountForm"
                        # 或：import AccountForm from "@/components/accountForm/accountForm"
                        # 或：import accountDialog from "@/components/accountDialog/accountDialog"
                        import_patterns = [
                            rf'from\s+["\']@/components/{component_dir_name}/{component_name}["\']',
                            rf'from\s+["\']@/components/{component_dir_name}["\']',
                            rf'from\s+["\']\.\.?/.*{component_name}["\']',
                            rf'import\s+\w+\s+from\s+["\'].*{component_dir_name}["\']',
                        ]
                        
                        for pattern in import_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                logger.info(f"[组件菜单查找] 找到使用组件的页面文件: {vue_file}")
                                # 使用该页面文件的菜单路径（传入 is_component_search=True 避免递归）
                                menu_path = self._find_menu_from_config(vue_file, is_component_search=True)
                                if menu_path:
                                    logger.info(f"[组件菜单查找] OK 通过页面文件找到菜单路径: {menu_path}")
                                    return menu_path
                                break
                except Exception as e:
                    logger.debug(f"[组件菜单查找] 读取文件失败 {vue_file}: {e}")
                    continue
            
            logger.info(f"[组件菜单查找] ✗ 未找到使用组件 '{component_name}' 的页面文件")
            return None
            
        except Exception as e:
            logger.warning(f"[组件菜单查找] 查找组件使用页面失败: {e}")
            return None
