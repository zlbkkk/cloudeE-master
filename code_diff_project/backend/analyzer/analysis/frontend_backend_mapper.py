"""
前后端映射器
建立后端 API 与前端调用的映射关系
"""
import re
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class BackendApi:
    """后端 API 信息"""
    path: str  # API 路径，如 /api/users/{id}
    method: str  # HTTP 方法
    controller: Optional[str] = None  # 控制器名称
    function: Optional[str] = None  # 函数名称
    menu_path: Optional[str] = None  # 菜单路径，如 "资产管理 > 订单管理"


@dataclass
class ApiMapping:
    """前后端 API 映射关系"""
    backend_api: BackendApi  # 后端 API
    frontend_calls: List  # 前端调用列表（ApiCall 对象）
    match_score: float = 1.0  # 匹配得分（0-1）


class FrontendBackendMapper:
    """前后端映射器"""
    
    def __init__(self):
        """初始化映射器"""
        pass
    
    def map_apis(self, backend_apis: List[BackendApi], frontend_calls: List) -> List[ApiMapping]:
        """
        建立前后端 API 映射关系
        
        Args:
            backend_apis: 后端 API 列表
            frontend_calls: 前端 API 调用列表
            
        Returns:
            映射关系列表
        """
        mappings = []
        
        # 打印所有前端调用的 URL（用于调试）
        logger.info(f"[映射] 开始映射，后端API数量: {len(backend_apis)}, 前端调用数量: {len(frontend_calls)}")
        if frontend_calls:
            logger.info(f"[映射] 前端调用示例（前10个）:")
            for i, call in enumerate(frontend_calls[:10]):
                logger.info(f"  [{i+1}] {call.method} {call.url} (文件: {call.file_path}:{call.line_number})")
        
        # 为每个后端 API 查找匹配的前端调用
        for backend_api in backend_apis:
            matched_calls = []
            
            logger.info(f"[映射] 查找后端API的匹配: {backend_api.method} {backend_api.path}")
            
            # 收集所有可能匹配的前端调用（用于调试）
            potential_matches = []
            
            for frontend_call in frontend_calls:
                # 检查 HTTP 方法是否匹配
                if backend_api.method.upper() != frontend_call.method.upper():
                    continue
                
                # 检查路径是否匹配
                if self.match_path(backend_api.path, frontend_call.url):
                    logger.info(f"[映射] ✓ 匹配成功: {backend_api.method} {backend_api.path} <-> {frontend_call.method} {frontend_call.url}")
                    matched_calls.append(frontend_call)
                else:
                    # 记录可能相关的调用（用于调试）
                    if any(keyword in frontend_call.url.lower() for keyword in backend_api.path.lower().split('/') if keyword):
                        potential_matches.append(frontend_call)
            
            # 如果有匹配的前端调用，创建映射关系
            if matched_calls:
                mappings.append(ApiMapping(
                    backend_api=backend_api,
                    frontend_calls=matched_calls,
                    match_score=1.0
                ))
            else:
                logger.warning(f"[映射] ✗ 未找到匹配的前端调用: {backend_api.method} {backend_api.path}")
                if potential_matches:
                    logger.info(f"[映射] 可能相关的前端调用（前5个）:")
                    for call in potential_matches[:5]:
                        logger.info(f"  - {call.method} {call.url} (文件: {call.file_path}:{call.line_number})")
        
        logger.info(f"建立了 {len(mappings)} 个前后端映射关系")
        return mappings

    
    def match_path(self, backend_path: str, frontend_path: str) -> bool:
        """
        判断后端路径和前端路径是否匹配
        支持路径参数匹配，如 /api/orders/{id} 匹配 /api/orders/123
        
        Args:
            backend_path: 后端 API 路径，如 /api/users/{id}
            frontend_path: 前端调用路径，如 /api/users/123 或 USERS_URL
            
        Returns:
            是否匹配
        """
        # 清理路径（去除首尾空格）
        backend_path = backend_path.strip()
        frontend_path = frontend_path.strip()
        
        # 如果前端路径是变量名（不以 / 开头），尝试部分匹配
        if not frontend_path.startswith('/') and not frontend_path.startswith('$'):
            # 提取后端路径的关键词
            backend_parts = re.findall(r'[a-zA-Z]+', backend_path.lower())
            backend_keywords = set(backend_parts)
            
            # 提取前端变量名的关键词
            frontend_parts = re.findall(r'[a-zA-Z]+', frontend_path.lower())
            frontend_keywords = set(frontend_parts)
            
            # 计算关键词重叠度
            if backend_keywords and frontend_keywords:
                overlap = backend_keywords & frontend_keywords
                # 如果有至少一个关键词匹配，认为可能相关
                if overlap:
                    return True
            return False
        
        # 精确匹配
        if backend_path == frontend_path:
            logger.debug(f"[路径匹配] 精确匹配: {backend_path} == {frontend_path}")
            return True
        
        # 规范化路径：去除末尾的斜杠（如果有）
        backend_path_normalized = backend_path.rstrip('/')
        frontend_path_normalized = frontend_path.rstrip('/')
        
        if backend_path_normalized == frontend_path_normalized:
            logger.debug(f"[路径匹配] 规范化后精确匹配: {backend_path_normalized} == {frontend_path_normalized}")
            return True
        
        # 将后端路径中的参数占位符转换为正则表达式
        # {id} -> [^/]+  (任意非斜杠字符)
        pattern = backend_path_normalized
        
        # 替换所有参数占位符
        pattern = re.sub(r'\{[^}]+\}', r'[^/]+', pattern)
        
        # 转义特殊字符
        pattern = pattern.replace('/', r'\/')
        pattern = pattern.replace('.', r'\.')
        
        # 添加开始和结束标记
        pattern = f'^{pattern}$'
        
        # 尝试匹配
        try:
            if re.match(pattern, frontend_path_normalized):
                logger.debug(f"[路径匹配] 正则匹配成功: {pattern} 匹配 {frontend_path_normalized}")
                return True
        except re.error:
            logger.warning(f"正则表达式匹配失败: {pattern}")
        
        logger.debug(f"[路径匹配] 不匹配: {backend_path} vs {frontend_path}")
        return False
    
    def get_unmapped_frontend_calls(self, frontend_calls: List, mappings: List[ApiMapping]) -> List:
        """
        获取未映射的前端调用
        
        Args:
            frontend_calls: 所有前端调用列表
            mappings: 已建立的映射关系列表
            
        Returns:
            未映射的前端调用列表
        """
        mapped_calls = set()
        for mapping in mappings:
            for call in mapping.frontend_calls:
                mapped_calls.add(id(call))
        
        unmapped = [call for call in frontend_calls if id(call) not in mapped_calls]
        return unmapped
