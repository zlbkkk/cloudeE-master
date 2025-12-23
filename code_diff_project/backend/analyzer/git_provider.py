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
        返回: 项目列表，每个项目包含 name, path, git_url, description 等字段
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
            max_pages = 50  # 最多获取 50 页，避免无限循环
            
            logger.info(f"开始从 GitLab 组织 '{organization}' 获取项目列表...")
            
            while page <= max_pages:
                try:
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
                        timeout=60  # 增加超时时间到 60 秒
                    )
                    
                    if response.status_code == 404:
                        logger.error(f"GitLab 组织 '{organization}' 不存在或无权访问")
                        return []
                    elif response.status_code != 200:
                        logger.error(f"GitLab API 错误: HTTP {response.status_code}, {response.text}")
                        break
                    
                    page_projects = response.json()
                    
                    if not page_projects:
                        break
                    
                    logger.info(f"第 {page} 页: 获取到 {len(page_projects)} 个项目")
                    
                    # 解析项目信息
                    for proj in page_projects:
                        # 确保 default_branch 不为 None
                        default_branch = proj.get('default_branch') or 'master'
                        
                        projects.append({
                            'name': proj.get('name', ''),
                            'path': proj.get('path_with_namespace', ''),
                            'git_url': proj.get('http_url_to_repo', ''),
                            'ssh_url': proj.get('ssh_url_to_repo', ''),
                            'description': proj.get('description', ''),
                            'default_branch': default_branch,
                            'last_activity': proj.get('last_activity_at', ''),
                        })
                    
                    # 检查是否还有下一页
                    if len(page_projects) < per_page:
                        break
                        
                    page += 1
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"第 {page} 页请求超时，已获取 {len(projects)} 个项目")
                    break
                except requests.exceptions.RequestException as e:
                    logger.error(f"第 {page} 页请求失败: {str(e)}")
                    break
            
            logger.info(f"从 GitLab 组织 '{organization}' 共发现 {len(projects)} 个项目")
            return projects
            
        except Exception as e:
            logger.error(f"列出项目时发生错误: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    

class GitHubProvider(GitProviderInterface):
    """GitHub API 实现"""
    
    def __init__(self, server_url: str, access_token: str):
        """
        初始化 GitHub Provider
        
        Args:
            server_url: GitHub 服务器地址，如 https://api.github.com 或 https://github.company.com/api/v3
            access_token: Personal Access Token 或 Fine-grained token
        """
        self.server_url = server_url.rstrip('/')
        # 如果是 github.com，使用标准 API 地址
        if 'github.com' in self.server_url and 'api.github.com' not in self.server_url:
            self.api_base = 'https://api.github.com'
        else:
            self.api_base = self.server_url
        
        self.access_token = access_token
        self.headers = {
            'Authorization': f'token {access_token}',
            'Accept': 'application/vnd.github.v3+json',
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
                username = user_data.get('login', 'Unknown')
                return True, f"连接成功！当前用户: {username}"
            elif response.status_code == 401:
                return False, "认证失败：Token 无效或已过期"
            elif response.status_code == 403:
                return False, "认证失败：Token 权限不足或 API 速率限制"
            else:
                return False, f"连接失败：HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "连接超时：无法访问 GitHub 服务器"
        except requests.exceptions.ConnectionError:
            return False, "连接错误：无法访问 GitHub 服务器，请检查服务器地址"
        except Exception as e:
            return False, f"未知错误：{str(e)}"
    
    def list_projects(self, organization: str) -> List[Dict]:
        """列出组织或用户下的所有项目"""
        try:
            projects = []
            page = 1
            per_page = 100
            max_pages = 50  # 最多获取 50 页，避免无限循环
            
            logger.info(f"开始从 GitHub 组织/用户 '{organization}' 获取项目列表...")
            
            # 先尝试作为组织获取
            is_org = self._check_if_organization(organization)
            
            while page <= max_pages:
                try:
                    # GitHub API: 获取组织或用户的仓库
                    if is_org:
                        url = f"{self.api_base}/orgs/{organization}/repos"
                    else:
                        url = f"{self.api_base}/users/{organization}/repos"
                    
                    response = requests.get(
                        url,
                        headers=self.headers,
                        params={
                            'page': page,
                            'per_page': per_page,
                            'type': 'all',  # all, public, private, forks, sources, member
                            'sort': 'updated',  # created, updated, pushed, full_name
                            'direction': 'desc'
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 404:
                        logger.error(f"GitHub 组织/用户 '{organization}' 不存在或无权访问")
                        return []
                    elif response.status_code == 403:
                        logger.error(f"GitHub API 速率限制或权限不足")
                        # 检查速率限制
                        remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
                        reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                        logger.error(f"剩余请求次数: {remaining}, 重置时间: {reset_time}")
                        break
                    elif response.status_code != 200:
                        logger.error(f"GitHub API 错误: HTTP {response.status_code}, {response.text}")
                        break
                    
                    page_projects = response.json()
                    
                    if not page_projects:
                        break
                    
                    logger.info(f"第 {page} 页: 获取到 {len(page_projects)} 个项目")
                    
                    # 解析项目信息
                    for repo in page_projects:
                        # 跳过 fork 的仓库（可选）
                        # if repo.get('fork', False):
                        #     continue
                        
                        projects.append({
                            'name': repo.get('name', ''),
                            'path': repo.get('full_name', ''),
                            'git_url': repo.get('clone_url', ''),
                            'ssh_url': repo.get('ssh_url', ''),
                            'description': repo.get('description', '') or '',
                            'default_branch': repo.get('default_branch', 'main'),
                            'last_activity': repo.get('updated_at', ''),
                            'is_private': repo.get('private', False),
                            'is_fork': repo.get('fork', False),
                            'stars': repo.get('stargazers_count', 0),
                            'forks': repo.get('forks_count', 0),
                        })
                    
                    # 检查是否还有下一页
                    # GitHub 使用 Link header 来指示分页
                    link_header = response.headers.get('Link', '')
                    if 'rel="next"' not in link_header:
                        break
                        
                    page += 1
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"第 {page} 页请求超时，已获取 {len(projects)} 个项目")
                    break
                except requests.exceptions.RequestException as e:
                    logger.error(f"第 {page} 页请求失败: {str(e)}")
                    break
            
            logger.info(f"从 GitHub 组织/用户 '{organization}' 共发现 {len(projects)} 个项目")
            return projects
            
        except Exception as e:
            logger.error(f"列出项目时发生错误: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _check_if_organization(self, name: str) -> bool:
        """检查是组织还是用户"""
        try:
            response = requests.get(
                f"{self.api_base}/orgs/{name}",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


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
