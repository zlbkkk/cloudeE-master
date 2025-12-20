"""
Git Provider 接口和实现
支持 GitLab、GitHub、Gitea 等 Git 服务器的 API 调用
"""
import requests
import logging
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class GitProviderInterface(ABC):
    """Git 服务器提供商接口"""
    
    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """
        测试连接是否正常
        返回: (是否成功, 消息)
        """
        pass
    
    @abstractmethod
    def list_projects(self, organization: str) -> List[Dict]:
        """
        列出组织下的所有项目
        返回: 项目列表，每个项目包含 name, path, git_url, description, language 等字段
        """
        pass


class GitLabProvider(GitProviderInterface):
    """GitLab API 实现"""
    
    def __init__(self, server_url: str, access_token: str):
        """
        初始化 GitLab Provider
        
        Args:
            server_url: GitLab 服务器地址，如 https://git.hrlyit.com
            access_token: Personal Access Token
        """
        self.server_url = server_url.rstrip('/')
        self.access_token = access_token
        self.api_base = f"{self.server_url}/api/v4"
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def test_connection(self) -> tuple[bool, str]:
        """测试连接"""
        try:
            # 测试 API 是否可访问
            response = requests.get(
                f"{self.api_base}/user",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('username', 'Unknown')
                return True, f"连接成功！当前用户: {username}"
            elif response.status_code == 401:
                return False, "认证失败：Token 无效或已过期"
            else:
                return False, f"连接失败：HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "连接超时：无法访问 Git 服务器"
        except requests.exceptions.ConnectionError:
            return False, "连接错误：无法访问 Git 服务器，请检查服务器地址"
        except Exception as e:
            return False, f"未知错误：{str(e)}"
    
    def list_projects(self, organization: str) -> List[Dict]:
        """列出组织下的所有项目"""
        try:
            projects = []
            page = 1
            per_page = 100
            
            while True:
                # GitLab API: 获取群组下的项目
                response = requests.get(
                    f"{self.api_base}/groups/{organization}/projects",
                    headers=self.headers,
                    params={
                        'page': page,
                        'per_page': per_page,
                        'include_subgroups': True,  # 包含子群组
                        'archived': False  # 排除已归档项目
                    },
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.error(f"GitLab API 错误: HTTP {response.status_code}, {response.text}")
                    break
                
                page_projects = response.json()
                
                if not page_projects:
                    break
                
                # 解析项目信息
                for proj in page_projects:
                    projects.append({
                        'name': proj.get('name', ''),
                        'path': proj.get('path_with_namespace', ''),
                        'git_url': proj.get('http_url_to_repo', ''),
                        'ssh_url': proj.get('ssh_url_to_repo', ''),
                        'description': proj.get('description', ''),
                        'default_branch': proj.get('default_branch', 'master'),
                        'language': self._detect_language(proj),
                        'last_activity': proj.get('last_activity_at', ''),
                    })
                
                # 检查是否还有下一页
                if len(page_projects) < per_page:
                    break
                    
                page += 1
            
            logger.info(f"从 GitLab 组织 '{organization}' 发现 {len(projects)} 个项目")
            return projects
            
        except requests.exceptions.Timeout:
            logger.error("GitLab API 请求超时")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"GitLab API 请求失败: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"列出项目时发生错误: {str(e)}")
            return []
    
    def _detect_language(self, project_data: Dict) -> Optional[str]:
        """检测项目主要编程语言"""
        # GitLab API 可能不直接返回语言信息
        # 可以通过项目名称或其他字段推断
        name = project_data.get('name', '').lower()
        
        if 'frontend' in name or 'h5' in name or 'web' in name:
            return 'JavaScript'
        elif 'service' in name or 'api' in name or 'server' in name:
            return 'Java'
        else:
            return None


class GitHubProvider(GitProviderInterface):
    """GitHub API 实现（预留）"""
    
    def __init__(self, server_url: str, access_token: str):
        self.server_url = server_url
        self.access_token = access_token
        # TODO: 实现 GitHub API
    
    def test_connection(self) -> tuple[bool, str]:
        return False, "GitHub 支持尚未实现"
    
    def list_projects(self, organization: str) -> List[Dict]:
        return []


class GiteaProvider(GitProviderInterface):
    """Gitea API 实现（预留）"""
    
    def __init__(self, server_url: str, access_token: str):
        self.server_url = server_url
        self.access_token = access_token
        # TODO: 实现 Gitea API
    
    def test_connection(self) -> tuple[bool, str]:
        return False, "Gitea 支持尚未实现"
    
    def list_projects(self, organization: str) -> List[Dict]:
        return []


def create_git_provider(server_type: str, server_url: str, access_token: str) -> GitProviderInterface:
    """
    工厂方法：根据服务器类型创建对应的 Provider
    
    Args:
        server_type: 服务器类型 (gitlab, github, gitea)
        server_url: 服务器地址
        access_token: 访问 Token
        
    Returns:
        GitProviderInterface 实例
    """
    providers = {
        'gitlab': GitLabProvider,
        'github': GitHubProvider,
        'gitea': GiteaProvider,
    }
    
    provider_class = providers.get(server_type.lower())
    if not provider_class:
        raise ValueError(f"不支持的 Git 服务器类型: {server_type}")
    
    return provider_class(server_url, access_token)
