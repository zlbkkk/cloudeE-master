"""
MultiProjectTracer - 协调多个项目仓库的分析

本模块提供一个协调器类，管理多个 ApiUsageTracer 和 LightStaticAnalyzer 实例，
每个项目一个实例，以支持微服务架构中的跨项目影响分析。
"""

import os
import re
import logging
import javalang
from typing import List, Dict, Optional
from .api_tracer import ApiUsageTracer
from .static_parser import LightStaticAnalyzer

logger = logging.getLogger(__name__)


class MultiProjectTracer:
    """
    协调多个项目的 API 和依赖追踪
    
    该类为每个项目维护独立的追踪器实例，并提供方法在所有项目中搜索类使用情况和 API 影响。
    """
    
    def __init__(self, project_roots: List[str]):
        """
        为所有项目初始化追踪器
        
        参数:
            project_roots: 项目根目录的绝对路径列表
                          第一个项目被视为主项目
                          
        示例:
            project_roots = [
                '/path/to/main-project',
                '/path/to/related-project-1',
                '/path/to/related-project-2'
            ]
        """
        self.project_roots = project_roots
        self.tracers: Dict[str, ApiUsageTracer] = {}
        self.analyzers: Dict[str, LightStaticAnalyzer] = {}
        
        logger.info(f"正在初始化 MultiProjectTracer，共 {len(project_roots)} 个项目")
        
        # 为每个项目初始化追踪器和分析器
        for project_root in project_roots:
            try:
                if not os.path.exists(project_root):
                    logger.warning(f"项目根目录不存在: {project_root}")
                    continue
                
                project_name = os.path.basename(project_root)
                logger.info(f"正在为项目初始化追踪器: {project_name} ({project_root})")
                
                # 创建 ApiUsageTracer 实例
                self.tracers[project_root] = ApiUsageTracer(project_root)
                logger.info(f"✓ ApiUsageTracer 已为 {project_name} 初始化")
                
                # 创建 LightStaticAnalyzer 实例
                self.analyzers[project_root] = LightStaticAnalyzer(project_root)
                logger.info(f"✓ LightStaticAnalyzer 已为 {project_name} 初始化")
                
            except Exception as e:
                logger.error(f"为 {project_root} 初始化追踪器失败: {str(e)}")
                logger.error(f"堆栈跟踪:", exc_info=True)
                # 即使一个项目失败也继续处理其他项目
                continue
        
        logger.info(f"MultiProjectTracer 初始化完成。"
                   f"成功初始化 {len(self.tracers)} 个项目。")
    
    def get_main_project_root(self) -> Optional[str]:
        """
        获取主项目根目录（列表中的第一个）
        
        返回:
            主项目根目录路径，如果没有初始化项目则返回 None
        """
        return self.project_roots[0] if self.project_roots else None
    
    def get_related_project_roots(self) -> List[str]:
        """
        获取所有关联项目根目录（不包括主项目）
        
        返回:
            关联项目根目录路径列表
        """
        return self.project_roots[1:] if len(self.project_roots) > 1 else []

    def find_class_usages_in_project(
        self, 
        project_root: str, 
        full_class_name: str
    ) -> List[Dict]:
        """
        在指定项目中查找类的使用情况
        
        该方法使用 LightStaticAnalyzer 在单个项目中搜索指定类的导入和引用。
        
        参数:
            project_root: 项目根目录的绝对路径
            full_class_name: 完全限定类名（例如 "com.example.UserManager"）
            
        返回:
            使用情况字典列表，包含以下键:
                - path: str (相对文件路径)
                - line: int (行号)
                - snippet: str (代码片段)
                - service: str (服务名称)
                - type: str (使用类型: "explicit import", "FQN" 等)
                
        示例:
            usages = tracer.find_class_usages_in_project(
                "/path/to/project",
                "com.example.service.UserManager"
            )
            # 返回: [
            #     {
            #         "path": "src/main/java/com/example/controller/UserController.java",
            #         "line": 15,
            #         "snippet": "private UserManager userManager;",
            #         "service": "user-service",
            #         "type": "explicit import"
            #     }
            # ]
        """
        try:
            # 检查项目是否存在于分析器中
            if project_root not in self.analyzers:
                logger.warning(f"在分析器中未找到项目: {project_root}")
                return []
            
            analyzer = self.analyzers[project_root]
            project_name = os.path.basename(project_root)
            
            logger.info(f"正在项目 {project_name} 中搜索类 '{full_class_name}' 的使用情况")
            
            # 使用 LightStaticAnalyzer 的现有 find_usages 方法
            usages = analyzer.find_usages(full_class_name)
            
            logger.info(f"在 {project_name} 中找到 {len(usages)} 处 '{full_class_name}' 的使用")
            
            return usages
            
        except Exception as e:
            logger.error(f"在 {project_root} 中查找类使用情况时出错: {str(e)}")
            logger.error(f"堆栈跟踪:", exc_info=True)
            return []

    def find_api_impacts_in_project(
        self,
        project_root: str,
        target_class: str,
        target_method: str
    ) -> List[Dict]:
        """
        在指定项目中查找 API 影响
        
        该方法使用 ApiUsageTracer 搜索受指定类和方法变更影响的 API 端点。
        
        参数:
            project_root: 项目根目录的绝对路径
            target_class: 简单类名或完全限定类名（例如 "UserManager"）
            target_method: 方法名（例如 "updateUser"）
            
        返回:
            影响字典列表，包含以下键:
                - api: str (API 端点，例如 "POST /api/users")
                - file: str (文件路径)
                - line: int (行号)
                - snippet: str (代码片段)
                - caller_class: str (调用该方法的类)
                - caller_method: str (调用目标方法的方法)
                
        示例:
            impacts = tracer.find_api_impacts_in_project(
                "/path/to/project",
                "UserManager",
                "updateUser"
            )
            # 返回: [
            #     {
            #         "api": "POST /api/users/update",
            #         "file": "/path/to/UserController.java",
            #         "line": 45,
            #         "snippet": "userManager.updateUser(userId, data);",
            #         "caller_class": "UserController",
            #         "caller_method": "handleUpdate"
            #     }
            # ]
        """
        try:
            # 检查项目是否存在于追踪器中
            if project_root not in self.tracers:
                logger.warning(f"在追踪器中未找到项目: {project_root}")
                return []
            
            tracer = self.tracers[project_root]
            project_name = os.path.basename(project_root)
            
            logger.info(f"正在项目 {project_name} 中搜索 '{target_class}.{target_method}' 的 API 影响")
            
            # 使用 ApiUsageTracer 的现有 find_affected_apis 方法
            impacts = tracer.find_affected_apis(target_class, target_method)
            
            logger.info(f"在 {project_name} 中找到 {len(impacts)} 个 '{target_class}.{target_method}' 的 API 影响")
            
            return impacts
            
        except Exception as e:
            logger.error(f"在 {project_root} 中查找 API 影响时出错: {str(e)}")
            logger.error(f"堆栈跟踪:", exc_info=True)
            return []

    def find_cross_project_impacts(
        self,
        full_class_name: str,
        changed_methods: List[str]
    ) -> List[Dict]:
        """
        在所有关联项目中查找影响（不包括主项目）
        
        这是跨项目分析的主要方法。它在所有关联项目中搜索:
        1. 类引用（导入和使用）
        2. 受变更方法影响的 API 调用
        3. **递归追踪**：继续追踪使用这些类的其他类，直到找到 Controller 层的 API 接口
        
        参数:
            full_class_name: 完全限定类名（例如 "com.example.UserManager"）
            changed_methods: 已修改的方法名列表
            
        返回:
            影响字典列表，包含以下键:
                - project: str (项目名称)
                - type: str ('class_reference' 或 'api_call')
                - file: str (文件路径)
                - line: int (行号)
                - snippet: str (代码片段)
                - detail: str (人类可读的描述)
                - api: str (可选，仅用于 api_call 类型)
                
        示例:
            impacts = tracer.find_cross_project_impacts(
                "com.example.service.UserManager",
                ["updateUser", "deleteUser"]
            )
            # 返回: [
            #     {
            #         "project": "frontend-service",
            #         "type": "class_reference",
            #         "file": "src/UserService.java",
            #         "line": 10,
            #         "snippet": "import com.example.service.UserManager;",
            #         "detail": "类 UserManager 在 frontend-service 中被引用"
            #     },
            #     {
            #         "project": "api-gateway",
            #         "type": "api_call",
            #         "file": "src/GatewayController.java",
            #         "line": 45,
            #         "snippet": "userManager.updateUser(id, data);",
            #         "detail": "API POST /api/users/update 调用了 UserManager.updateUser",
            #         "api": "POST /api/users/update"
            #     }
            # ]
        """
        all_impacts = []
        
        # 获取主项目根目录以跳过它
        main_project_root = self.get_main_project_root()
        related_projects = self.get_related_project_roots()
        
        if not related_projects:
            logger.info("没有关联项目需要扫描跨项目影响")
            return []
        
        logger.info(f"开始对类 {full_class_name} 进行跨项目影响分析（递归模式）")
        logger.info(f"变更的方法: {', '.join(changed_methods)}")
        logger.info(f"扫描 {len(related_projects)} 个关联项目")
        
        # 提取简单类名用于日志记录
        simple_class_name = full_class_name.split('.')[-1] if '.' in full_class_name else full_class_name
        
        # 遍历所有关联项目（跳过主项目）
        for project_root in related_projects:
            project_name = os.path.basename(project_root)
            logger.info(f"正在扫描项目: {project_name}")
            
            try:
                # 1. 查找类引用
                logger.info(f"  → 正在搜索对 {simple_class_name} 的类引用...")
                class_usages = self.find_class_usages_in_project(project_root, full_class_name)
                
                for usage in class_usages:
                    impact = {
                        "project": project_name,
                        "type": "class_reference",
                        "file": usage.get('path', ''),
                        "line": usage.get('line', 0),
                        "snippet": usage.get('snippet', ''),
                        "detail": f"类 {simple_class_name} 在 {project_name} 中被引用 ({usage.get('type', 'unknown')})"
                    }
                    all_impacts.append(impact)
                    logger.info(f"    ✓ 在 {usage.get('path', 'unknown')} 中找到类引用")
                
                # 2. 为每个变更的方法查找 API 影响（直接影响）
                for method_name in changed_methods:
                    logger.info(f"  → 正在搜索 {simple_class_name}.{method_name} 的 API 影响...")
                    api_impacts = self.find_api_impacts_in_project(
                        project_root,
                        simple_class_name,
                        method_name
                    )
                    
                    for api_impact in api_impacts:
                        impact = {
                            "project": project_name,
                            "type": "api_call",
                            "file": api_impact.get('file', ''),
                            "line": api_impact.get('line', 0),
                            "snippet": api_impact.get('snippet', ''),
                            "api": api_impact.get('api', ''),
                            "method_signature": api_impact.get('method_signature', ''),  # 新增：方法签名
                            "caller_class": api_impact.get('caller_class', ''),  # 新增：调用类
                            "caller_method": api_impact.get('caller_method', ''),  # 新增：调用方法
                            "detail": f"{project_name} 中的 API {api_impact.get('api', 'unknown')} 调用了 {simple_class_name}.{method_name}"
                        }
                        all_impacts.append(impact)
                        
                        # 添加日志：显示方法签名
                        method_sig = api_impact.get('method_signature', '')
                        if method_sig:
                            logger.info(f"    ✓ 找到 API 影响: {api_impact.get('api', 'unknown')} (方法签名: {method_sig})")
                        else:
                            logger.info(f"    ✓ 找到 API 影响: {api_impact.get('api', 'unknown')} (方法签名: 未提取)")
                            logger.warning(f"    ⚠ 警告：未提取到方法签名，可能导致重载方法识别错误")
                
                # 2.5 查找受影响的中间层方法（Service/Client 方法），即使没有 Controller 调用
                logger.info(f"  → 正在搜索受影响的中间层方法...")
                for method_name in changed_methods:
                    intermediate_impacts = self._find_intermediate_method_impacts(
                        project_root,
                        project_name,
                        simple_class_name,
                        method_name
                    )
                    
                    if intermediate_impacts:
                        logger.info(f"    ✓ 找到 {len(intermediate_impacts)} 个受影响的中间层方法")
                        all_impacts.extend(intermediate_impacts)
                    else:
                        logger.info(f"    - 未找到受影响的中间层方法")
                
                # 3. **新增：递归追踪影响链**
                logger.info(f"  → 开始递归追踪影响链...")
                recursive_impacts = self._find_recursive_impacts(
                    project_root,
                    project_name,
                    full_class_name,
                    changed_methods,
                    depth=0,
                    max_depth=5
                )
                
                if recursive_impacts:
                    logger.info(f"    ✓ 递归追踪发现 {len(recursive_impacts)} 个额外影响")
                    all_impacts.extend(recursive_impacts)
                else:
                    logger.info(f"    - 递归追踪未发现额外影响")
                
            except Exception as e:
                logger.error(f"扫描项目 {project_name} 时出错: {str(e)}")
                logger.error(f"堆栈跟踪:", exc_info=True)
                # 继续处理其他项目
                continue
        
        # 去重：基于 project + file + line + type 组合
        unique_impacts = []
        seen_keys = set()
        for impact in all_impacts:
            key = (
                impact.get('project', ''),
                impact.get('file', ''),
                impact.get('line', 0),
                impact.get('type', ''),
                impact.get('api', ''),  # API 调用需要包含 api 字段
                impact.get('caller_method', '')  # 方法调用需要包含 caller_method 字段
            )
            if key not in seen_keys:
                seen_keys.add(key)
                unique_impacts.append(impact)
        
        # 按项目分组影响以生成摘要
        impacts_by_project = {}
        for impact in unique_impacts:
            project = impact['project']
            if project not in impacts_by_project:
                impacts_by_project[project] = []
            impacts_by_project[project].append(impact)
        
        # 记录摘要
        logger.info(f"跨项目影响分析完成（递归模式）:")
        logger.info(f"  找到的总影响数: {len(unique_impacts)} (去重后)")
        for project, impacts in impacts_by_project.items():
            class_refs = sum(1 for i in impacts if i['type'] == 'class_reference')
            api_calls = sum(1 for i in impacts if i['type'] == 'api_call')
            method_calls = sum(1 for i in impacts if i['type'] == 'method_call')
            logger.info(f"  {project}: {class_refs} 个类引用, {api_calls} 个 API 调用, {method_calls} 个方法调用")
        
        return unique_impacts
    
    def _find_recursive_impacts(
        self,
        project_root: str,
        project_name: str,
        target_class: str,
        changed_methods: List[str],
        depth: int,
        max_depth: int,
        visited: Optional[set] = None
    ) -> List[Dict]:
        """
        递归追踪影响链，直到找到 Controller 层的 API 接口
        
        工作流程：
        1. 找到使用 target_class 的所有类（调用者）
        2. 对每个调用者：
           a. 检查是否为 Controller（如果是，提取 API 接口）
           b. 如果不是 Controller，递归追踪这个调用者
        3. 重复直到达到最大深度或找到所有 Controller
        
        参数:
            project_root: 项目根目录
            project_name: 项目名称
            target_class: 目标类名（完全限定名或简单名）
            changed_methods: 变更的方法列表
            depth: 当前递归深度
            max_depth: 最大递归深度
            visited: 已访问的类集合（避免循环依赖）
            
        返回:
            影响字典列表
        """
        if visited is None:
            visited = set()
        
        if depth >= max_depth:
            logger.debug(f"    [Depth {depth}] 达到最大递归深度，停止追踪")
            return []
        
        # 提取简单类名
        simple_class_name = target_class.split('.')[-1] if '.' in target_class else target_class
        
        # 避免重复访问
        if simple_class_name in visited:
            logger.debug(f"    [Depth {depth}] 类 {simple_class_name} 已访问，跳过")
            return []
        
        visited.add(simple_class_name)
        
        logger.debug(f"    [Depth {depth}] 递归追踪: {simple_class_name}")
        
        impacts = []
        
        try:
            # 获取该项目的分析器
            if project_root not in self.analyzers:
                logger.warning(f"    [Depth {depth}] 项目 {project_name} 没有分析器")
                return []
            
            analyzer = self.analyzers[project_root]
            
            # 查找使用 target_class 的所有类
            usages = analyzer.find_usages(target_class)
            
            if not usages:
                logger.debug(f"    [Depth {depth}] 未找到 {simple_class_name} 的使用者")
                return []
            
            logger.debug(f"    [Depth {depth}] 找到 {len(usages)} 个使用 {simple_class_name} 的位置")
            
            # 提取使用者的类名（去重）
            caller_classes = set()
            for usage in usages:
                usage_path = usage.get('path', '')
                if usage_path:
                    # 从文件路径提取类名
                    # 例如: src/main/java/com/example/service/NotificationService.java -> NotificationService
                    caller_class = os.path.basename(usage_path).replace('.java', '')
                    caller_classes.add(caller_class)
            
            logger.debug(f"    [Depth {depth}] 使用者类: {', '.join(caller_classes)}")
            
            # 对每个调用者类进行处理
            for caller_class in caller_classes:
                # 检查是否为 Controller
                is_controller = 'Controller' in caller_class or 'controller' in caller_class.lower()
                
                if is_controller:
                    logger.info(f"    [Depth {depth}] ✓ 发现 Controller: {caller_class}")
                    
                    # 为每个变更的方法查找 API 影响
                    for method_name in changed_methods:
                        api_impacts = self.find_api_impacts_in_project(
                            project_root,
                            caller_class,
                            method_name
                        )
                        
                        for api_impact in api_impacts:
                            impact = {
                                "project": project_name,
                                "type": "api_call",
                                "file": api_impact.get('file', ''),
                                "line": api_impact.get('line', 0),
                                "snippet": api_impact.get('snippet', ''),
                                "api": api_impact.get('api', ''),
                                "detail": f"{project_name} 中的 API {api_impact.get('api', 'unknown')} 通过调用链受到影响 (深度: {depth+1})"
                            }
                            impacts.append(impact)
                            logger.info(f"    [Depth {depth}] ✓✓ 找到递归 API 影响: {api_impact.get('api', 'unknown')}")
                    
                    # 即使是 Controller，也尝试查找它的所有方法对应的 API
                    # 因为 Controller 的任何方法都可能暴露 API
                    tracer = self.tracers.get(project_root)
                    if tracer:
                        # 获取 Controller 的所有公共方法
                        controller_apis = self._find_controller_apis(project_root, caller_class)
                        for api_info in controller_apis:
                            impact = {
                                "project": project_name,
                                "type": "api_call",
                                "file": api_info.get('file', ''),
                                "line": api_info.get('line', 0),
                                "snippet": api_info.get('snippet', ''),
                                "api": api_info.get('api', ''),
                                "detail": f"{project_name} 中的 API {api_info.get('api', 'unknown')} 可能受到影响 (通过 {caller_class})"
                            }
                            impacts.append(impact)
                            logger.info(f"    [Depth {depth}] ✓✓ 找到 Controller API: {api_info.get('api', 'unknown')}")
                else:
                    # 不是 Controller，继续递归追踪
                    logger.debug(f"    [Depth {depth}] → 继续追踪: {caller_class}")
                    recursive_impacts = self._find_recursive_impacts(
                        project_root,
                        project_name,
                        caller_class,
                        changed_methods,
                        depth + 1,
                        max_depth,
                        visited
                    )
                    impacts.extend(recursive_impacts)
        
        except Exception as e:
            logger.error(f"    [Depth {depth}] 递归追踪出错: {str(e)}")
            logger.error(f"    堆栈跟踪:", exc_info=True)
        
        return impacts
    
    def _find_controller_apis(self, project_root: str, controller_class: str) -> List[Dict]:
        """
        查找 Controller 类中的所有 API 接口
        
        参数:
            project_root: 项目根目录
            controller_class: Controller 类名
            
        返回:
            API 信息字典列表
        """
        apis = []
        
        try:
            # 查找 Controller 文件
            controller_file = None
            for root, dirs, files in os.walk(project_root):
                # 忽略常见的非源码目录
                for ignore in ["target", "node_modules", ".git", "venv", "__pycache__"]:
                    if ignore in dirs:
                        dirs.remove(ignore)
                
                for file in files:
                    if file == f"{controller_class}.java":
                        controller_file = os.path.join(root, file)
                        break
                
                if controller_file:
                    break
            
            if not controller_file:
                logger.debug(f"未找到 Controller 文件: {controller_class}.java")
                return []
            
            # 读取文件内容
            with open(controller_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否为 Controller
            if "@RestController" not in content and "@Controller" not in content:
                return []
            
            # 使用 javalang 解析
            import javalang
            tree = javalang.parse.parse(content)
            
            # 获取类级别的 @RequestMapping
            base_path = ""
            for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
                if class_node.annotations:
                    for ann in class_node.annotations:
                        if ann.name == 'RequestMapping':
                            base_path = self._extract_annotation_value(ann)
                
                # 遍历所有方法
                for method_node in class_node.methods:
                    if method_node.annotations:
                        for ann in method_node.annotations:
                            if ann.name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'RequestMapping']:
                                method_path = self._extract_annotation_value(ann)
                                http_method = self._resolve_http_method(ann.name)
                                
                                # 组合路径
                                full_path = self._combine_paths(base_path, method_path)
                                
                                # 获取行号
                                line_num = method_node.position.line if method_node.position else 0
                                
                                apis.append({
                                    "api": f"{http_method} {full_path}",
                                    "file": controller_file,
                                    "line": line_num,
                                    "snippet": f"@{ann.name} {method_node.name}(...)"
                                })
        
        except Exception as e:
            logger.debug(f"解析 Controller {controller_class} 失败: {str(e)}")
        
        return apis
    
    def _extract_annotation_value(self, ann) -> str:
        """从注解中提取 value 或 path 属性"""
        try:
            if not ann.element:
                return ""
            
            if isinstance(ann.element, list):
                for elem in ann.element:
                    if elem.name in ['value', 'path']:
                        if hasattr(elem.value, 'value'):
                            return elem.value.value.strip('"')
            elif hasattr(ann.element, 'value'):
                return ann.element.value.strip('"')
            elif isinstance(ann.element, javalang.tree.Literal):
                return ann.element.value.strip('"')
        except:
            pass
        
        return ""
    
    def _resolve_http_method(self, ann_name: str) -> str:
        """解析 HTTP 方法"""
        mapping = {
            'GetMapping': 'GET',
            'PostMapping': 'POST',
            'PutMapping': 'PUT',
            'DeleteMapping': 'DELETE',
            'RequestMapping': 'ALL'
        }
        return mapping.get(ann_name, 'ALL')
    
    def _combine_paths(self, base: str, sub: str) -> str:
        """组合基础路径和子路径"""
        import re
        
        if not base:
            base = ""
        if not sub:
            sub = ""
        
        combined = f"{base}/{sub}"
        # 规范化斜杠
        combined = re.sub(r'/+', '/', combined)
        if combined.endswith('/') and len(combined) > 1:
            combined = combined[:-1]
        if not combined.startswith('/'):
            combined = '/' + combined
        
        return combined
    
    def _find_intermediate_method_impacts(
        self,
        project_root: str,
        project_name: str,
        target_class: str,
        target_method: str
    ) -> List[Dict]:
        """
        查找受影响的中间层方法（Service/Client 方法），即使没有 Controller 调用
        
        这个方法用于实现"选项 B"：报告所有受影响的 Service 方法，即使没有 Controller 调用
        
        参数:
            project_root: 项目根目录
            project_name: 项目名称
            target_class: 目标类名（简单名或完全限定名）
            target_method: 目标方法名
            
        返回:
            影响字典列表，包含受影响的中间层方法信息
        """
        impacts = []
        
        try:
            # 提取简单类名
            simple_class_name = target_class.split('.')[-1] if '.' in target_class else target_class
            
            # 在项目中查找调用目标方法的所有方法
            tracer = self.tracers.get(project_root)
            if not tracer:
                return []
            
            # 使用 ApiUsageTracer 的内部方法查找调用者
            callers = tracer._find_callers_of_method(simple_class_name, target_method)
            
            for caller in callers:
                caller_file = caller.get('file', '')
                caller_class = caller.get('class', '')
                caller_method = caller.get('method', '')
                caller_method_signature = caller.get('method_signature', '')  # 新增：获取方法签名
                caller_line = caller.get('line', 0)
                caller_snippet = caller.get('snippet', '')
                
                # 判断是否为中间层（Service/Client/Manager 等，不是 Controller）
                is_intermediate = any(
                    keyword in caller_class
                    for keyword in ['Service', 'Client', 'Manager', 'Helper', 'Util']
                )
                
                is_controller = 'Controller' in caller_class or 'controller' in caller_class.lower()
                
                # 只报告中间层方法，不报告 Controller（Controller 已经在 API 影响中报告了）
                if is_intermediate and not is_controller:
                    # 获取相对路径
                    rel_path = os.path.relpath(caller_file, project_root) if os.path.isabs(caller_file) else caller_file
                    
                    impact = {
                        "project": project_name,
                        "type": "method_call",  # 新类型：方法调用影响
                        "file": rel_path,
                        "line": caller_line,
                        "snippet": caller_snippet,
                        "caller_class": caller_class,
                        "caller_method": caller_method,
                        "method_signature": caller_method_signature,  # 新增：方法签名
                        "detail": f"{project_name} 中的方法 {caller_class}.{caller_method} 调用了 {simple_class_name}.{target_method}"
                    }
                    impacts.append(impact)
                    
                    # 添加日志：显示方法签名
                    if caller_method_signature:
                        logger.debug(f"      ✓ 找到中间层方法影响: {caller_class}.{caller_method_signature}")
                    else:
                        logger.debug(f"      ✓ 找到中间层方法影响: {caller_class}.{caller_method} (方法签名: 未提取)")
                        logger.warning(f"      ⚠ 警告：未提取到方法签名，可能导致重载方法识别错误")
        
        except Exception as e:
            logger.error(f"查找中间层方法影响时出错: {str(e)}")
            logger.error(f"堆栈跟踪:", exc_info=True)
        
        return impacts
