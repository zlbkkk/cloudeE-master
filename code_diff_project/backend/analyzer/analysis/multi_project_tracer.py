"""
MultiProjectTracer - 协调多个项目仓库的分析

本模块提供一个协调器类，管理多个 ApiUsageTracer 和 LightStaticAnalyzer 实例，
每个项目一个实例，以支持微服务架构中的跨项目影响分析。
"""

import os
import logging
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
        
        logger.info(f"开始对类 {full_class_name} 进行跨项目影响分析")
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
                
                # 2. 为每个变更的方法查找 API 影响
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
                            "detail": f"{project_name} 中的 API {api_impact.get('api', 'unknown')} 调用了 {simple_class_name}.{method_name}"
                        }
                        all_impacts.append(impact)
                        logger.info(f"    ✓ 找到 API 影响: {api_impact.get('api', 'unknown')}")
                
            except Exception as e:
                logger.error(f"扫描项目 {project_name} 时出错: {str(e)}")
                logger.error(f"堆栈跟踪:", exc_info=True)
                # 继续处理其他项目
                continue
        
        # 按项目分组影响以生成摘要
        impacts_by_project = {}
        for impact in all_impacts:
            project = impact['project']
            if project not in impacts_by_project:
                impacts_by_project[project] = []
            impacts_by_project[project].append(impact)
        
        # 记录摘要
        logger.info(f"跨项目影响分析完成:")
        logger.info(f"  找到的总影响数: {len(all_impacts)}")
        for project, impacts in impacts_by_project.items():
            class_refs = sum(1 for i in impacts if i['type'] == 'class_reference')
            api_calls = sum(1 for i in impacts if i['type'] == 'api_call')
            logger.info(f"  {project}: {class_refs} 个类引用, {api_calls} 个 API 调用")
        
        return all_impacts
