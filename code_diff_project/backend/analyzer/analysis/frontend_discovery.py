"""
前端项目自动发现模块

负责扫描 workspace 目录，识别前端项目，提取框架类型和 API 配置
"""
import os
import json
from dataclasses import dataclass
from typing import List, Optional, Dict
from loguru import logger


@dataclass
class FrontendProject:
    """前端项目信息"""
    name: str                    # 项目名称
    path: str                    # 项目路径
    framework: str               # 框架类型：'react', 'vue', 'angular', 'unknown'
    api_base_url: Optional[str]  # API 基础路径
    package_json: dict           # package.json 内容


class FrontendProjectDiscovery:
    """前端项目发现器"""
    
    def __init__(self, workspace_path: str = None):
        """
        初始化前端项目发现器
        
        Args:
            workspace_path: workspace 根目录路径，默认为 code_diff_project/workspace
        """
        self.workspace_path = workspace_path or os.path.join('code_diff_project', 'workspace')
        self.exclude_dirs = {'node_modules', 'dist', 'build', '.git', 'coverage', 'venv', '__pycache__', 'cloudeE-master'}
        
        # 排除的完整路径（用于排除特定的嵌套项目）
        self.exclude_paths = set()
        if self.workspace_path:
            # 排除 workspace/cloudeE-master 目录
            cloudee_path = os.path.join(self.workspace_path, 'cloudeE-master')
            self.exclude_paths.add(os.path.normpath(cloudee_path))
    
    def discover_projects(self) -> List[FrontendProject]:
        """
        扫描 workspace 目录，发现所有前端项目
        
        Returns:
            前端项目列表
        """
        projects = []
        
        if not os.path.exists(self.workspace_path):
            logger.warning(f"Workspace 路径不存在: {self.workspace_path}")
            return projects
        
        logger.info(f"开始扫描前端项目: {self.workspace_path}")
        
        # 遍历 workspace 下的所有子目录
        for root, dirs, files in os.walk(self.workspace_path):
            # 检查当前路径是否在排除列表中
            normalized_root = os.path.normpath(root)
            should_skip = False
            
            for exclude_path in self.exclude_paths:
                # 如果当前路径是排除路径或其子路径，跳过
                if normalized_root == exclude_path or normalized_root.startswith(exclude_path + os.sep):
                    should_skip = True
                    logger.debug(f"跳过排除目录: {root}")
                    break
            
            if should_skip:
                # 清空 dirs 列表，阻止 os.walk 继续遍历子目录
                dirs[:] = []
                continue
            
            # 排除不需要扫描的目录
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            # 检查是否包含 package.json
            if 'package.json' in files:
                package_json_path = os.path.join(root, 'package.json')
                try:
                    with open(package_json_path, 'r', encoding='utf-8') as f:
                        package_json = json.load(f)
                    
                    # 创建前端项目对象
                    project = self._create_project(root, package_json)
                    if project:
                        projects.append(project)
                        logger.info(f"发现前端项目: {project.name} ({project.framework})")
                
                except Exception as e:
                    logger.warning(f"解析 package.json 失败 {package_json_path}: {e}")
        
        logger.info(f"共发现 {len(projects)} 个前端项目")
        return projects
    
    def _create_project(self, project_path: str, package_json: dict) -> Optional[FrontendProject]:
        """
        创建前端项目对象
        
        Args:
            project_path: 项目路径
            package_json: package.json 内容
            
        Returns:
            前端项目对象，如果不是前端项目则返回 None
        """
        # 提取项目名称
        project_name = package_json.get('name', os.path.basename(project_path))
        
        # 识别框架类型
        framework = self.identify_framework(package_json)
        
        # 如果无法识别框架，可能不是前端项目
        if framework == 'unknown':
            logger.debug(f"无法识别框架类型: {project_name}")
            return None
        
        # 提取 API 基础路径
        api_base_url = self.extract_api_base_url(project_path)
        
        return FrontendProject(
            name=project_name,
            path=project_path,
            framework=framework,
            api_base_url=api_base_url,
            package_json=package_json
        )
    
    def identify_framework(self, package_json: dict) -> str:
        """
        识别前端框架类型
        
        Args:
            package_json: package.json 内容
            
        Returns:
            框架类型：'react', 'vue', 'angular', 'unknown'
        """
        dependencies = package_json.get('dependencies', {})
        dev_dependencies = package_json.get('devDependencies', {})
        all_deps = {**dependencies, **dev_dependencies}
        
        # 检测 React
        if 'react' in all_deps or 'react-dom' in all_deps:
            return 'react'
        
        # 检测 Vue
        if 'vue' in all_deps:
            return 'vue'
        
        # 检测 Angular
        if '@angular/core' in all_deps:
            return 'angular'
        
        return 'unknown'
    
    def extract_api_base_url(self, project_path: str) -> Optional[str]:
        """
        提取 API 基础路径配置
        
        Args:
            project_path: 项目路径
            
        Returns:
            API 基础路径，如 'http://localhost:8000/api'
        """
        # 常见的配置文件位置
        config_files = [
            'src/config.js',
            'src/config.ts',
            'src/constants.js',
            'src/constants.ts',
            'src/utils/config.js',
            'src/utils/constants.js',
            '.env',
            '.env.development'
        ]
        
        for config_file in config_files:
            config_path = os.path.join(project_path, config_file)
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 查找常见的 API 配置模式
                    api_url = self._extract_api_url_from_content(content)
                    if api_url:
                        logger.debug(f"找到 API 配置: {api_url} in {config_file}")
                        return api_url
                
                except Exception as e:
                    logger.debug(f"读取配置文件失败 {config_path}: {e}")
        
        return None
    
    def _extract_api_url_from_content(self, content: str) -> Optional[str]:
        """
        从配置文件内容中提取 API URL
        
        Args:
            content: 文件内容
            
        Returns:
            API URL
        """
        import re
        
        # 常见的 API URL 配置模式
        patterns = [
            r'baseURL\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            r'API_BASE_URL\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            r'REACT_APP_API_URL\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            r'VUE_APP_API_URL\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            r'apiUrl\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        return None
