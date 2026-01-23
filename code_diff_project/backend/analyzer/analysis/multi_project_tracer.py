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
from .rabbitmq_analyzer import RabbitMQAnalyzer
from .resttemplate_analyzer import RestTemplateAnalyzer

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
        self.mybatis_analyzers: Dict[str, 'MybatisAnalyzer'] = {}  # 添加：MyBatis 分析器（如果需要）
        self.rabbitmq_analyzers: Dict[str, RabbitMQAnalyzer] = {}  # 新增：RabbitMQ 分析器
        self.resttemplate_analyzers: Dict[str, RestTemplateAnalyzer] = {}  # 新增：RestTemplate 分析器
        
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
                
                # 创建 RabbitMQAnalyzer 实例
                self.rabbitmq_analyzers[project_root] = RabbitMQAnalyzer(project_root)
                logger.info(f"✓ RabbitMQAnalyzer 已为 {project_name} 初始化")
                
                # 创建 RestTemplateAnalyzer 实例
                self.resttemplate_analyzers[project_root] = RestTemplateAnalyzer(project_root)
                logger.info(f"✓ RestTemplateAnalyzer 已为 {project_name} 初始化")
                
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
        target_method: str,
        target_method_signature: str = None
    ) -> List[Dict]:
        """
        在指定项目中查找 API 影响
        
        该方法使用 ApiUsageTracer 搜索受指定类和方法变更影响的 API 端点。
        
        参数:
            project_root: 项目根目录的绝对路径
            target_class: 简单类名或完全限定类名（例如 "UserManager"）
            target_method: 方法名（例如 "updateUser"）
            target_method_signature: 方法签名（可选），用于区分重载方法
                                    格式：methodName(Type1, Type2) 或 methodName()
            
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
                "updateUser",
                "updateUser(Long, UserDTO)"
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
            
            if target_method_signature:
                logger.info(f"正在项目 {project_name} 中搜索 '{target_class}.{target_method_signature}' 的 API 影响")
            else:
                logger.info(f"正在项目 {project_name} 中搜索 '{target_class}.{target_method}' 的 API 影响")
            
            # 使用 ApiUsageTracer 的现有 find_affected_apis 方法（传递方法签名）
            impacts = tracer.find_affected_apis(target_class, target_method, target_method_signature)
            
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
        4. **Dubbo RPC 调用**：如果变更的类实现了接口，查找对接口的 @DubboReference 引用
        
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
        
        logger.info(f"开始对类 {full_class_name} 进行跨项目影响分析（递归模式）")
        logger.info(f"变更的方法: {', '.join(changed_methods)}")
        logger.info(f"扫描 {len(related_projects)} 个关联项目")
        
        if not related_projects:
            logger.info("没有关联项目需要扫描跨项目影响")
            return []
        
        # 提取简单类名用于日志记录
        simple_class_name = full_class_name.split('.')[-1] if '.' in full_class_name else full_class_name
        
        # 【新增】查找变更类实现的接口（用于 Dubbo RPC 识别）
        implemented_interfaces = self._find_implemented_interfaces(main_project_root, full_class_name)
        if implemented_interfaces:
            logger.info(f"  → 类 {simple_class_name} 实现了接口: {', '.join(implemented_interfaces)}")
        else:
            logger.info(f"  → 类 {simple_class_name} 未实现任何接口")
        
        # 遍历所有关联项目（跳过主项目）
        for project_root in related_projects:
            project_name = os.path.basename(project_root)
            logger.info(f"正在扫描项目: {project_name}")
            
            try:
                # 1. 查找类引用（实现类）
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
                
                # 1.5 【新增】查找对接口的 Dubbo RPC 引用
                if implemented_interfaces:
                    logger.info(f"  → 正在搜索对接口的 Dubbo RPC 引用...")
                    dubbo_impacts = self._find_dubbo_rpc_references(
                        project_root,
                        project_name,
                        implemented_interfaces,
                        changed_methods
                    )
                    if dubbo_impacts:
                        logger.info(f"    ✓ 找到 {len(dubbo_impacts)} 个 Dubbo RPC 引用")
                        all_impacts.extend(dubbo_impacts)
                    else:
                        logger.info(f"    - 未找到 Dubbo RPC 引用")
                
                # 2. 为每个变更的方法查找 API 影响（直接影响）
                # 首先提取方法签名（用于区分重载方法）
                method_signatures = {}
                try:
                    # 在主项目中查找变更的类文件，提取方法签名
                    main_project_root = self.get_main_project_root()
                    if main_project_root:
                        # 查找类文件
                        class_file = None
                        for root, dirs, files in os.walk(main_project_root):
                            # 忽略常见的非源码目录
                            for ignore in ["target", "node_modules", ".git", "venv", "__pycache__"]:
                                if ignore in dirs:
                                    dirs.remove(ignore)
                            
                            for file in files:
                                if file == f"{simple_class_name}.java":
                                    class_file = os.path.join(root, file)
                                    break
                            
                            if class_file:
                                break
                        
                        if class_file and os.path.exists(class_file):
                            import javalang
                            with open(class_file, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            tree = javalang.parse.parse(file_content)
                            
                            # 遍历所有方法，提取方法签名
                            for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
                                method_name = method_node.name
                                # 提取参数类型
                                params = []
                                if method_node.parameters:
                                    for param in method_node.parameters:
                                        if param.type:
                                            if hasattr(param.type, 'name'):
                                                params.append(param.type.name)
                                            elif hasattr(param.type, 'type') and hasattr(param.type.type, 'name'):
                                                params.append(param.type.type.name)
                                
                                # 构建方法签名
                                if params:
                                    signature = f"{method_name}({', '.join(params)})"
                                else:
                                    signature = f"{method_name}()"
                                
                                # 存储方法签名（如果有重载，存储为列表）
                                if method_name not in method_signatures:
                                    method_signatures[method_name] = []
                                method_signatures[method_name].append(signature)
                            
                            logger.info(f"  → 成功提取 {len(method_signatures)} 个方法的签名")
                except Exception as e:
                    logger.warning(f"  → 提取方法签名失败: {e}")
                for method_name in changed_methods:
                    # 获取该方法的签名（如果有多个重载，使用第一个，或者追踪所有重载）
                    method_signature = None
                    if method_name in method_signatures:
                        signatures = method_signatures[method_name]
                        if len(signatures) == 1:
                            # 只有一个签名，直接使用
                            method_signature = signatures[0]
                            logger.info(f"  → 正在搜索 {simple_class_name}.{method_signature} 的 API 影响...")
                        else:
                            # 有多个重载，需要追踪所有重载
                            logger.info(f"  → 方法 {method_name} 有 {len(signatures)} 个重载: {signatures}")
                            # 暂时使用第一个签名，后续可以改进为追踪所有重载
                            method_signature = signatures[0]
                            logger.warning(f"  → 方法 {method_name} 有多个重载，当前只追踪第一个: {method_signature}")
                    else:
                        logger.info(f"  → 正在搜索 {simple_class_name}.{method_name} 的 API 影响...")
                    
                    api_impacts = self.find_api_impacts_in_project(
                        project_root,
                        simple_class_name,
                        method_name,
                        method_signature  # 传递方法签名
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
                    # 获取该方法的签名
                    method_signature = None
                    if method_name in method_signatures:
                        signatures = method_signatures[method_name]
                        method_signature = signatures[0] if signatures else None
                    
                    intermediate_impacts = self._find_intermediate_method_impacts(
                        project_root,
                        project_name,
                        simple_class_name,
                        method_name,
                        method_signature  # 传递方法签名
                    )
                    
                    if intermediate_impacts:
                        logger.info(f"    ✓ 找到 {len(intermediate_impacts)} 个受影响的中间层方法")
                        all_impacts.extend(intermediate_impacts)
                    else:
                        logger.info(f"    - 未找到受影响的中间层方法")
                
                # 2.6 查找 RabbitMQ 消息队列影响
                logger.info(f"  → 正在搜索 RabbitMQ 消息队列影响...")
                rabbitmq_impacts = self._find_rabbitmq_impacts(
                    project_root,
                    project_name,
                    simple_class_name,
                    changed_methods
                )
                
                if rabbitmq_impacts:
                    logger.info(f"    ✓ 找到 {len(rabbitmq_impacts)} 个 RabbitMQ 消息队列影响")
                    all_impacts.extend(rabbitmq_impacts)
                else:
                    logger.info(f"    - 未找到 RabbitMQ 消息队列影响")
                
                # 2.7 查找 RestTemplate HTTP 调用影响
                logger.info(f"  → 正在搜索 RestTemplate HTTP 调用影响...")
                
                resttemplate_impacts = self._find_resttemplate_impacts(
                    project_root,
                    project_name,
                    simple_class_name,
                    changed_methods
                )
                
                if resttemplate_impacts:
                    logger.info(f"    ✓ 找到 {len(resttemplate_impacts)} 个 RestTemplate HTTP 调用影响")
                    all_impacts.extend(resttemplate_impacts)
                else:
                    logger.info(f"    - 未找到 RestTemplate HTTP 调用影响")
                
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
                impact.get('caller_method', ''),  # 方法调用需要包含 caller_method 字段
                impact.get('exchange', ''),  # RabbitMQ 生产者需要包含 exchange 字段
                impact.get('queue', ''),  # RabbitMQ 消费者需要包含 queue 字段
                impact.get('url', ''),  # RestTemplate 调用需要包含 url 字段
                impact.get('called_method', '')  # Dubbo RPC 调用需要包含 called_method 字段
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
            rabbitmq_calls = sum(1 for i in impacts if i['type'] in ['rabbitmq_producer', 'rabbitmq_consumer'])
            resttemplate_calls = sum(1 for i in impacts if i['type'] == 'resttemplate_call')
            dubbo_calls = sum(1 for i in impacts if i['type'] in ['dubbo_rpc_call', 'dubbo_rpc_reference'])
            logger.info(f"  {project}: {class_refs} 个类引用, {api_calls} 个 API 调用, {method_calls} 个方法调用, {rabbitmq_calls} 个 RabbitMQ 消息, {resttemplate_calls} 个 RestTemplate 调用, {dubbo_calls} 个 Dubbo RPC 调用")
        
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
        target_method: str,
        target_method_signature: str = None
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
            
            # 使用 ApiUsageTracer 的内部方法查找调用者（传递方法签名）
            callers = tracer._find_callers_of_method(simple_class_name, target_method, target_method_signature)
            
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

    def _find_rabbitmq_impacts(
        self,
        project_root: str,
        project_name: str,
        target_class: str,
        changed_methods: List[str]
    ) -> List[Dict]:
        """
        查找 RabbitMQ 消息队列影响
        
        工作流程：
        1. 在主项目中查找变更方法是否发送 RabbitMQ 消息（生产者）
        2. 如果发送消息，在所有关联项目中查找对应的消息消费者
        3. 返回消息流影响信息
        
        参数:
            project_root: 当前扫描的项目根目录
            project_name: 项目名称
            target_class: 目标类名
            changed_methods: 变更的方法列表
            
        返回:
            RabbitMQ 影响字典列表
        """
        impacts = []
        
        try:
            # 获取主项目的 RabbitMQ 分析器
            main_project_root = self.get_main_project_root()
            if not main_project_root or main_project_root not in self.rabbitmq_analyzers:
                logger.debug(f"    主项目没有 RabbitMQ 分析器")
                return []
            
            main_rabbitmq_analyzer = self.rabbitmq_analyzers[main_project_root]
            
            # 1. 在主项目中查找变更方法是否发送 RabbitMQ 消息
            producers = []
            for method_name in changed_methods:
                method_producers = main_rabbitmq_analyzer.find_message_producers(
                    target_class_name=target_class,
                    target_method_name=method_name
                )
                producers.extend(method_producers)
            
            if not producers:
                logger.debug(f"    变更方法未发送 RabbitMQ 消息")
                return []
            
            logger.info(f"    发现 {len(producers)} 个 RabbitMQ 消息生产者")
            
            # 2. 在当前项目中查找消息消费者
            if project_root not in self.rabbitmq_analyzers:
                logger.debug(f"    项目 {project_name} 没有 RabbitMQ 分析器")
                return []
            
            current_rabbitmq_analyzer = self.rabbitmq_analyzers[project_root]
            
            # 查找所有消费者
            all_consumers = current_rabbitmq_analyzer.find_message_consumers()
            
            if not all_consumers:
                logger.debug(f"    项目 {project_name} 中未找到 RabbitMQ 消息消费者")
                return []
            
            logger.info(f"    项目 {project_name} 中发现 {len(all_consumers)} 个 RabbitMQ 消息消费者")
            
            # 3. 匹配生产者和消费者
            # 注意：这里的匹配逻辑比较简单，实际应该根据 exchange、routingKey 和 queue 的绑定关系来匹配
            # 但由于绑定关系通常在配置文件中定义，这里暂时报告所有可能的消费者
            
            for producer in producers:
                exchange = producer.get('exchange', 'Unknown')
                routing_key = producer.get('routing_key', 'Unknown')
                producer_method = producer.get('method', 'Unknown')
                
                # 为每个生产者创建一个影响记录
                producer_impact = {
                    "project": os.path.basename(main_project_root),
                    "type": "rabbitmq_producer",
                    "file": os.path.relpath(producer.get('file', ''), main_project_root) if os.path.isabs(producer.get('file', '')) else producer.get('file', ''),
                    "line": producer.get('line', 0),
                    "snippet": producer.get('snippet', ''),
                    "exchange": exchange,
                    "routing_key": routing_key,
                    "message_type": producer.get('message_type', 'Unknown'),
                    "detail": f"方法 {target_class}.{producer_method} 发送 RabbitMQ 消息到 exchange={exchange}, routingKey={routing_key}"
                }
                impacts.append(producer_impact)
                
                # 为每个消费者创建一个影响记录
                for consumer in all_consumers:
                    queue = consumer.get('queue', 'Unknown')
                    consumer_method = consumer.get('method', 'Unknown')
                    consumer_class = consumer.get('class', 'Unknown')
                    
                    consumer_impact = {
                        "project": project_name,
                        "type": "rabbitmq_consumer",
                        "file": os.path.relpath(consumer.get('file', ''), project_root) if os.path.isabs(consumer.get('file', '')) else consumer.get('file', ''),
                        "line": consumer.get('line', 0),
                        "snippet": consumer.get('snippet', ''),
                        "queue": queue,
                        "consumer_class": consumer_class,
                        "consumer_method": consumer_method,
                        "detail": f"{project_name} 中的方法 {consumer_class}.{consumer_method} 可能消费来自 exchange={exchange}, routingKey={routing_key} 的消息 (queue={queue})"
                    }
                    impacts.append(consumer_impact)
                    
                    logger.info(f"      ✓ 匹配到消费者: {consumer_class}.{consumer_method} (queue={queue})")
        
        except Exception as e:
            logger.error(f"查找 RabbitMQ 影响时出错: {str(e)}")
            logger.error(f"堆栈跟踪:", exc_info=True)
        
        return impacts

    def _find_resttemplate_impacts(
        self,
        project_root: str,
        project_name: str,
        target_class: str,
        changed_methods: List[str]
    ) -> List[Dict]:
        """
        查找 RestTemplate HTTP 调用影响
        
        工作流程：
        1. 在主项目中提取变更方法对应的 API 端点
        2. 在当前关联项目中查找是否有 RestTemplate 调用这些 API 端点
        3. 返回 HTTP 调用影响信息
        
        参数:
            project_root: 当前扫描的项目根目录（关联项目）
            project_name: 项目名称
            target_class: 目标类名
            changed_methods: 变更的方法列表
            
        返回:
            RestTemplate 影响字典列表
        """
        impacts = []
        
        try:
            # 获取主项目根目录
            main_project_root = self.get_main_project_root()
            if not main_project_root:
                logger.debug(f"    无法获取主项目根目录")
                return []
            
            # 1. 在主项目中提取变更方法对应的 API 端点
            # 查找主项目中变更的类文件
            simple_class_name = target_class.split('.')[-1] if '.' in target_class else target_class
            class_file = None
            for root, dirs, files in os.walk(main_project_root):
                # 忽略常见的非源码目录
                for ignore in ["target", "node_modules", ".git", "venv", "__pycache__"]:
                    if ignore in dirs:
                        dirs.remove(ignore)
                
                for file in files:
                    if file == f"{simple_class_name}.java":
                        class_file = os.path.join(root, file)
                        break
                
                if class_file:
                    break
            
            if not class_file or not os.path.exists(class_file):
                logger.debug(f"    未找到类文件: {simple_class_name}.java")
                return []
            
            # 解析类文件，提取 API 端点
            api_endpoints = self._extract_api_endpoints(class_file, changed_methods)
            
            if not api_endpoints:
                logger.debug(f"    未找到变更方法对应的 API 端点")
                return []
            
            logger.info(f"    提取到 {len(api_endpoints)} 个 API 端点")
            
            # 2. 在当前关联项目中查找 RestTemplate 调用
            if project_root not in self.resttemplate_analyzers:
                logger.debug(f"    项目 {project_name} 没有 RestTemplate 分析器")
                return []
            
            current_resttemplate_analyzer = self.resttemplate_analyzers[project_root]
            
            # 查找所有 RestTemplate 调用
            all_http_calls = current_resttemplate_analyzer.find_http_calls()
            
            if not all_http_calls:
                logger.debug(f"    项目 {project_name} 中未找到 RestTemplate HTTP 调用")
                return []
            
            logger.info(f"    项目 {project_name} 中发现 {len(all_http_calls)} 个 RestTemplate HTTP 调用")
            
            # 3. 匹配 API 端点和 RestTemplate 调用
            for api_endpoint in api_endpoints:
                api_method = api_endpoint['method']
                api_path = api_endpoint['path']
                
                for http_call in all_http_calls:
                    # 匹配 HTTP 方法和 URL 路径
                    if self._match_api_call(api_method, api_path, http_call):
                        http_method = http_call.get('http_method', 'Unknown')
                        url = http_call.get('url', 'Unknown')
                        response_type = http_call.get('response_type', 'Unknown')
                        call_class = http_call.get('class', 'Unknown')
                        call_method = http_call.get('method', 'Unknown')
                        
                        # 创建影响记录
                        impact = {
                            "project": project_name,
                            "type": "resttemplate_call",
                            "file": os.path.relpath(http_call.get('file', ''), project_root) if os.path.isabs(http_call.get('file', '')) else http_call.get('file', ''),
                            "line": http_call.get('line', 0),
                            "snippet": http_call.get('snippet', ''),
                            "http_method": http_method,
                            "url": url,
                            "response_type": response_type,
                            "caller_class": call_class,
                            "caller_method": call_method,
                            "detail": f"{project_name} 中的方法 {call_class}.{call_method} 使用 RestTemplate 调用了变更的 API: {api_method} {api_path}"
                        }
                        impacts.append(impact)
                        
                        logger.info(f"      ✓ 匹配到 RestTemplate 调用: {call_class}.{call_method} -> {http_method} {url}")
        
        except Exception as e:
            logger.error(f"查找 RestTemplate 影响时出错: {str(e)}")
            logger.error(f"堆栈跟踪:", exc_info=True)
        
        return impacts
    
    def _extract_api_endpoints(self, class_file: str, changed_methods: List[str]) -> List[Dict]:
        """
        从 Controller 类文件中提取 API 端点
        
        参数:
            class_file: Controller 类文件路径
            changed_methods: 变更的方法列表
            
        返回:
            API 端点列表，每个元素包含 method 和 path
        """
        api_endpoints = []
        
        try:
            with open(class_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否为 Controller
            if "@RestController" not in content and "@Controller" not in content:
                return []
            
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
                    # 只处理变更的方法
                    if method_node.name not in changed_methods:
                        continue
                    
                    if method_node.annotations:
                        for ann in method_node.annotations:
                            if ann.name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'RequestMapping']:
                                method_path = self._extract_annotation_value(ann)
                                http_method = self._resolve_http_method(ann.name)
                                
                                # 组合路径
                                full_path = self._combine_paths(base_path, method_path)
                                
                                api_endpoints.append({
                                    'method': http_method,
                                    'path': full_path,
                                    'java_method': method_node.name
                                })
                                
                                logger.debug(f"      提取 API 端点: {http_method} {full_path} (方法: {method_node.name})")
        
        except Exception as e:
            logger.debug(f"提取 API 端点失败: {str(e)}")
        
        return api_endpoints
    
    def _match_api_call(self, api_method: str, api_path: str, http_call: Dict) -> bool:
        """
        匹配 API 端点和 RestTemplate 调用
        
        参数:
            api_method: API 的 HTTP 方法（GET、POST 等）
            api_path: API 路径（如 /api/orders/{orderId}/status-text）
            http_call: RestTemplate 调用信息
            
        返回:
            True 如果匹配，否则 False
        """
        call_method = http_call.get('http_method', '')
        call_url = http_call.get('url', '')
        
        # 1. HTTP 方法必须匹配
        if api_method != call_method and api_method != 'ALL':
            return False
        
        # 2. URL 路径匹配（支持路径参数）
        # API 路径: /api/orders/{orderId}/status-text
        # 调用 URL: SERVICE_A_ORDER_URL + "/" + orderId + "/status-text"
        #          或 /api/orders/123/status-text
        
        # 简化匹配：检查 URL 中是否包含 API 路径的关键部分
        # 将路径参数 {xxx} 替换为通配符
        api_path_pattern = re.sub(r'\{[^}]+\}', r'[^/]+', api_path)
        api_path_pattern = api_path_pattern.replace('/', r'\/')
        
        # 检查 URL 是否匹配模式
        if re.search(api_path_pattern, call_url):
            return True
        
        # 如果 URL 是变量拼接（如 "Variable: xxx"），尝试模糊匹配
        if "Variable:" in call_url or "String concatenation" in call_url:
            # 提取 API 路径的关键部分（去除路径参数）
            api_parts = [part for part in api_path.split('/') if part and not part.startswith('{')]
            # 检查是否所有关键部分都在 snippet 中
            snippet = http_call.get('snippet', '')
            if all(part in snippet for part in api_parts):
                return True
        
        return False

    def _find_implemented_interfaces(self, project_root: str, full_class_name: str) -> List[str]:
        """
        查找类实现的接口
        
        参数:
            project_root: 项目根目录
            full_class_name: 完全限定类名
            
        返回:
            接口完全限定名列表
        """
        interfaces = []
        
        try:
            # 提取简单类名
            simple_class_name = full_class_name.split('.')[-1] if '.' in full_class_name else full_class_name
            
            # 查找类文件
            class_file = None
            for root, dirs, files in os.walk(project_root):
                # 忽略常见的非源码目录
                for ignore in ["target", "node_modules", ".git", "venv", "__pycache__"]:
                    if ignore in dirs:
                        dirs.remove(ignore)
                
                for file in files:
                    if file == f"{simple_class_name}.java":
                        class_file = os.path.join(root, file)
                        break
                
                if class_file:
                    break
            
            if not class_file or not os.path.exists(class_file):
                logger.debug(f"未找到类文件: {simple_class_name}.java")
                return []
            
            # 解析类文件
            with open(class_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = javalang.parse.parse(content)
            
            # 获取包名
            package_name = tree.package.name if tree.package else ""
            
            # 获取导入的类
            imports = {}
            for imp in tree.imports:
                if imp.path:
                    # 提取简单类名作为 key
                    simple_name = imp.path.split('.')[-1]
                    imports[simple_name] = imp.path
            
            # 查找类声明
            for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
                if class_node.name == simple_class_name:
                    # 获取实现的接口
                    if class_node.implements:
                        for interface in class_node.implements:
                            interface_simple_name = interface.name
                            
                            # 尝试解析接口的完全限定名
                            if interface_simple_name in imports:
                                # 接口已导入，使用导入的完全限定名
                                interface_fqn = imports[interface_simple_name]
                            else:
                                # 接口未导入，假设在同一个包中
                                interface_fqn = f"{package_name}.{interface_simple_name}" if package_name else interface_simple_name
                            
                            interfaces.append(interface_fqn)
                            logger.debug(f"  找到接口: {interface_fqn}")
                    
                    break
        
        except Exception as e:
            logger.debug(f"查找实现的接口失败: {str(e)}")
        
        return interfaces
    
    def _find_dubbo_rpc_references(
        self,
        project_root: str,
        project_name: str,
        interface_names: List[str],
        changed_methods: List[str]
    ) -> List[Dict]:
        """
        查找对接口的 Dubbo RPC 引用（@DubboReference）
        
        参数:
            project_root: 项目根目录
            project_name: 项目名称
            interface_names: 接口完全限定名列表
            changed_methods: 变更的方法列表
            
        返回:
            Dubbo RPC 引用列表
        """
        dubbo_impacts = []
        
        try:
            # 遍历所有 Java 文件
            for root, dirs, files in os.walk(project_root):
                # 忽略常见的非源码目录
                for ignore in ["target", "node_modules", ".git", "venv", "__pycache__", "test"]:
                    if ignore in dirs:
                        dirs.remove(ignore)
                
                for file in files:
                    if not file.endswith(".java"):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 快速检查：文件中是否包含 @DubboReference
                        if "@DubboReference" not in content:
                            continue
                        
                        # 解析文件
                        tree = javalang.parse.parse(content)
                        
                        # 获取导入的类
                        imports = {}
                        for imp in tree.imports:
                            if imp.path:
                                simple_name = imp.path.split('.')[-1]
                                imports[simple_name] = imp.path
                        
                        # 获取包名
                        package_name = tree.package.name if tree.package else ""
                        
                        # 查找类声明
                        for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
                            current_class_name = class_node.name
                            
                            # 遍历类的字段
                            for field in class_node.fields:
                                # 检查字段是否有 @DubboReference 注解
                                has_dubbo_reference = False
                                if field.annotations:
                                    for ann in field.annotations:
                                        if ann.name == "DubboReference" or ann.name.endswith(".DubboReference"):
                                            has_dubbo_reference = True
                                            break
                                
                                if not has_dubbo_reference:
                                    continue
                                
                                # 获取字段类型（接口名）
                                field_type = None
                                if field.type and hasattr(field.type, 'name'):
                                    field_type = field.type.name
                                
                                if not field_type:
                                    continue
                                
                                # 解析字段类型的完全限定名
                                field_type_fqn = None
                                if field_type in imports:
                                    field_type_fqn = imports[field_type]
                                else:
                                    # 假设在同一个包中
                                    field_type_fqn = f"{package_name}.{field_type}" if package_name else field_type
                                
                                # 检查字段类型是否匹配我们要查找的接口
                                if field_type_fqn not in interface_names:
                                    continue
                                
                                logger.info(f"    ✓ 发现 Dubbo RPC 引用: {current_class_name} 通过 @DubboReference 注入了 {field_type}")
                                
                                # 获取字段声明的行号
                                field_line = 0
                                if hasattr(field, 'position') and field.position:
                                    field_line = field.position.line
                                
                                # 获取字段声明的代码片段
                                lines = content.splitlines()
                                field_snippet = ""
                                if field_line > 0 and field_line <= len(lines):
                                    # 获取前后几行作为上下文
                                    start_line = max(0, field_line - 2)
                                    end_line = min(len(lines), field_line + 1)
                                    field_snippet = "\n".join(lines[start_line:end_line])
                                
                                # 获取字段名
                                field_name = field.declarators[0].name if field.declarators else "unknown"
                                
                                # 查找该字段的所有方法调用
                                method_calls = self._find_field_method_calls(
                                    content,
                                    tree,
                                    field_name,
                                    changed_methods
                                )
                                
                                if method_calls:
                                    logger.info(f"      ✓ 找到 {len(method_calls)} 个对变更方法的调用")
                                    
                                    for call in method_calls:
                                        # 创建影响记录
                                        rel_path = os.path.relpath(file_path, project_root)
                                        
                                        impact = {
                                            "project": project_name,
                                            "type": "dubbo_rpc_call",
                                            "file": rel_path,
                                            "line": call['line'],
                                            "snippet": call['snippet'],
                                            "caller_class": current_class_name,
                                            "caller_method": call['caller_method'],
                                            "interface": field_type,
                                            "interface_fqn": field_type_fqn,
                                            "called_method": call['called_method'],
                                            "detail": f"{project_name} 中的 {current_class_name}.{call['caller_method']} 通过 Dubbo RPC 调用了 {field_type}.{call['called_method']}"
                                        }
                                        dubbo_impacts.append(impact)
                                        
                                        logger.info(f"        → {current_class_name}.{call['caller_method']} 调用了 {field_type}.{call['called_method']}")
                                else:
                                    # 即使没有找到对变更方法的调用，也报告 Dubbo 引用
                                    rel_path = os.path.relpath(file_path, project_root)
                                    
                                    impact = {
                                        "project": project_name,
                                        "type": "dubbo_rpc_reference",
                                        "file": rel_path,
                                        "line": field_line,
                                        "snippet": field_snippet,
                                        "caller_class": current_class_name,
                                        "interface": field_type,
                                        "interface_fqn": field_type_fqn,
                                        "detail": f"{project_name} 中的 {current_class_name} 通过 @DubboReference 注入了 {field_type} 接口"
                                    }
                                    dubbo_impacts.append(impact)
                                    
                                    logger.info(f"      - 未找到对变更方法的直接调用，但报告 Dubbo 引用")
                    
                    except Exception as e:
                        # 解析单个文件失败不影响其他文件
                        logger.debug(f"解析文件 {file_path} 失败: {str(e)}")
                        continue
        
        except Exception as e:
            logger.error(f"查找 Dubbo RPC 引用失败: {str(e)}")
            logger.error(f"堆栈跟踪:", exc_info=True)
        
        return dubbo_impacts
    
    def _find_field_method_calls(
        self,
        content: str,
        tree,
        field_name: str,
        target_methods: List[str]
    ) -> List[Dict]:
        """
        查找对字段的方法调用
        
        参数:
            content: 文件内容
            tree: javalang 解析树
            field_name: 字段名（如 orderService）
            target_methods: 目标方法列表（如 ['getOrderStatusText']）
            
        返回:
            方法调用列表
        """
        method_calls = []
        
        try:
            lines = content.splitlines()
            
            # 遍历所有方法
            for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
                caller_method_name = method_node.name
                
                # 查找方法调用
                for _, invoke_node in method_node.filter(javalang.tree.MethodInvocation):
                    # 检查是否是对目标字段的调用
                    # 例如：orderService.getOrderStatusText(orderId)
                    # invoke_node.qualifier 是 orderService
                    # invoke_node.member 是 getOrderStatusText
                    
                    if invoke_node.qualifier == field_name and invoke_node.member in target_methods:
                        # 找到匹配的调用
                        call_line = invoke_node.position.line if invoke_node.position else 0
                        call_snippet = lines[call_line - 1].strip() if call_line > 0 and call_line <= len(lines) else ""
                        
                        method_calls.append({
                            'caller_method': caller_method_name,
                            'called_method': invoke_node.member,
                            'line': call_line,
                            'snippet': call_snippet
                        })
        
        except Exception as e:
            logger.debug(f"查找字段方法调用失败: {str(e)}")
        
        return method_calls
