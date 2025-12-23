import logging
import threading
import os
import subprocess
import traceback
from urllib.parse import urlparse
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
import datetime
from django.db import models
from .models import AnalysisReport, AnalysisTask, ProjectRelation
from .serializers import AnalysisReportSerializer, AnalysisTaskSerializer, ProjectRelationSerializer
from .runner import run_analysis

logger = logging.getLogger(__name__)


def add_token_to_git_url(git_url):
    """
    为 Git URL 添加内置的访问 Token（如果配置了的话）
    
    Args:
        git_url: 原始的 Git URL
        
    Returns:
        添加了 Token 的 Git URL（如果适用），否则返回原 URL
    """
    try:
        # 解析 URL
        parsed = urlparse(git_url)
        
        # 只处理 https 协议
        if parsed.scheme != 'https':
            return git_url
        
        # 检查是否有配置的 Token
        git_tokens = getattr(settings, 'GIT_TOKENS', {})
        hostname = parsed.hostname
        
        if hostname in git_tokens:
            token = git_tokens[hostname]
            # 构造带 Token 的 URL: https://oauth2:TOKEN@hostname/path
            new_url = f"https://oauth2:{token}@{hostname}{parsed.path}"
            logger.info(f"[Info] 为 {hostname} 添加了内置 Token")
            return new_url
        
        return git_url
    except Exception as e:
        logger.warning(f"[Warning] 添加 Token 失败: {e}")
        return git_url

class AnalysisTaskViewSet(viewsets.ModelViewSet):
    queryset = AnalysisTask.objects.all()
    serializer_class = AnalysisTaskSerializer

    def list(self, request, *args, **kwargs):
        # Auto-fail tasks that are stuck in PROCESSING/PENDING for more than 10 minutes
        try:
            timeout_threshold = timezone.now() - datetime.timedelta(minutes=10)
            stuck_tasks = AnalysisTask.objects.filter(
                status__in=['PENDING', 'PROCESSING'],
                created_at__lt=timeout_threshold
            )
            if stuck_tasks.exists():
                count = stuck_tasks.count()
                stuck_tasks.update(
                    status='FAILED', 
                    log_details=models.functions.Concat(
                        models.F('log_details'), 
                        models.Value('\n[System] Task timed out after 10 minutes (Auto-terminated).')
                    )
                )
                logger.warning(f"Marked {count} stuck tasks as FAILED due to timeout.")
        except Exception as e:
            logger.error(f"Error checking task timeouts: {e}")
            
        return super().list(request, *args, **kwargs)

class AnalysisReportViewSet(viewsets.ModelViewSet):
    queryset = AnalysisReport.objects.all()
    serializer_class = AnalysisReportSerializer

    @action(detail=False, methods=['post'], url_path='trigger')
    def trigger_analysis(self, request):
        """
        触发后端分析任务
        """
        mode = request.data.get('mode', 'local')
        project_path = request.data.get('projectPath')
        git_url = request.data.get('gitUrl')
        # Commit-based comparison parameters
        target_branch = request.data.get('targetBranch', 'HEAD')
        base_commit = request.data.get('baseCommit', 'HEAD^')
        target_commit = request.data.get('targetCommit', 'HEAD')
        
        # 跨项目分析参数
        enable_cross_project = request.data.get('enableCrossProject', False)
        cross_project_list = request.data.get('crossProjectList', [])  # 直接接收项目列表
        
        # 使用前端传递的项目列表
        related_projects = cross_project_list if enable_cross_project else []
        
        logger.info(f"[Info] 跨项目分析: {'已启用' if enable_cross_project else '未启用'}")
        if enable_cross_project and related_projects:
            logger.info(f"[Info] 关联项目数量: {len(related_projects)}")

        # 1. 创建分析任务记录
        log_details = '任务已创建，等待执行...\n'
        if enable_cross_project:
            log_details += f'跨项目分析: 已启用\n'
            log_details += f'关联项目数量: {len(related_projects)}\n'
            if related_projects:
                log_details += '关联项目列表:\n'
                for proj in related_projects:
                    proj_name = proj.get('related_project_name', 'Unknown')
                    proj_url = proj.get('related_project_git_url', 'Unknown')
                    proj_branch = proj.get('related_project_branch', 'master')
                    log_details += f"  - {proj_name} ({proj_url}, 分支: {proj_branch})\n"
        else:
            log_details += '跨项目分析: 未启用\n'
        
        task = AnalysisTask.objects.create(
            project_name=git_url.split('/')[-1].replace('.git', '') if git_url else 'Local Project',
            mode=mode,
            source_branch=target_branch,
            target_branch=f"{base_commit} -> {target_commit}", # Store comparison range here
            status='PENDING',
            log_details=log_details
        )

        def run_cmd(task_id, enable_cross_project, related_projects):
            try:
                # 更新状态为进行中
                task = AnalysisTask.objects.get(id=task_id)
                task.status = 'PROCESSING'
                task.log_details = '任务开始执行...\n'
                task.save()

                target_root = project_path
                
                if mode == 'git':
                    if not git_url:
                        logger.error("[Error] Git URL required for git mode")
                        task.status = 'FAILED'
                        task.log_details += "[Error] Git URL required for git mode\n"
                        task.save()
                        return
                    
                    # 为 URL 添加内置 Token（如果配置了）
                    git_url_with_token = add_token_to_git_url(git_url)
                    
                    # Define workspace
                    workspace_root = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'workspace'))
                    if not os.path.exists(workspace_root):
                        os.makedirs(workspace_root)
                    
                    # Extract repo name
                    repo_name = git_url.split('/')[-1].replace('.git', '')
                    repo_path = os.path.join(workspace_root, repo_name)
                    target_root = repo_path
                    
                    task.log_details += f"工作目录: {repo_path}\n"
                    task.save()

                    if not os.path.exists(repo_path):
                        logger.info(f"[Info] Cloning {git_url} to {repo_path}...")
                        task.log_details += f"正在克隆代码仓库...\n"
                        task.save()
                        # 使用带 Token 的 URL 进行 clone
                        subprocess.check_call(["git", "clone", git_url_with_token, repo_path])
                    else:
                        logger.info(f"[Info] Fetching updates in {repo_path}...")
                        task.log_details += f"正在更新代码仓库...\n"
                        task.save()
                        subprocess.check_call(["git", "fetch", "--all"], cwd=repo_path)
                    
                    # Checkout working branch to ensure workspace has the correct context
                    # 优先使用 target_commit，确保工作区代码与分析目标一致
                    if target_commit and target_commit != 'HEAD':
                        logger.info(f"[Info] Checking out specific target commit: {target_commit}")
                        task.log_details += f"切换工作区到目标提交: {target_commit}\n"
                        task.save()
                        subprocess.check_call(["git", "reset", "--hard", "HEAD"], cwd=repo_path)
                        subprocess.check_call(["git", "checkout", target_commit], cwd=repo_path)
                    elif target_branch and target_branch != 'HEAD':
                        logger.info(f"[Info] Checking out working branch: {target_branch}")
                        task.log_details += f"切换分支到: {target_branch}\n"
                        task.save()
                        subprocess.check_call(["git", "reset", "--hard", "HEAD"], cwd=repo_path)
                        subprocess.check_call(["git", "checkout", target_branch], cwd=repo_path)
                        logger.info(f"[Info] Resetting to origin/{target_branch}...")
                        subprocess.check_call(["git", "reset", "--hard", f"origin/{target_branch}"], cwd=repo_path)
                
                # Run analysis comparing Base Commit vs Target Commit
                task.log_details += f"开始执行分析: {base_commit} ... {target_commit}\n"
                task.save()
                
                # 传递跨项目分析参数
                run_analysis(
                    project_root=target_root, 
                    base_ref=base_commit, 
                    target_ref=target_commit, 
                    task_id=task_id,
                    enable_cross_project=enable_cross_project,
                    related_projects=related_projects
                )
                
                # 更新任务完成 (注意：run_analysis内部可能会更新更详细的日志，这里做个兜底)
                task.refresh_from_db()
                if task.status != 'FAILED':
                    task.status = 'COMPLETED'
                    task.log_details += "分析任务执行完毕。\n"
                    task.save()

            except Exception as e:
                error_msg = f"Analysis failed: {str(e)}\n{traceback.format_exc()}"
                logger.error(f"[Error] {error_msg}")
                task = AnalysisTask.objects.get(id=task_id)
                task.status = 'FAILED'
                task.log_details += error_msg
                task.save()
        
        # 异步执行，避免阻塞 HTTP 请求
        thread = threading.Thread(target=run_cmd, args=(task.id, enable_cross_project, related_projects))
        thread.start()
        
        response_data = {
            "status": "Analysis started", 
            "task_id": task.id,
            "message": "分析任务已在后台启动。"
        }
        
        if enable_cross_project:
            response_data["enable_cross_project"] = True
            response_data["related_projects_count"] = len(related_projects)
        
        return Response(response_data)

    @action(detail=False, methods=['post'], url_path='git-branches')
    def fetch_git_branches(self, request):
        repo_url = request.data.get('git_url')
        logger.info(f"[Info] Fetching branches for: {repo_url}")
        if not repo_url:
            return Response({"error": "Git URL is required"}, status=400)
        
        # 为 URL 添加内置 Token（如果配置了）
        repo_url_with_token = add_token_to_git_url(repo_url)
        
        try:
            # 1. Try to find local repo first (Prioritize local branches)
            workspace_root = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'workspace'))
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            repo_path = os.path.join(workspace_root, repo_name)
            
            branches = set()
            
            if os.path.exists(repo_path):
                logger.info(f"[Info] Reading branches from local repo: {repo_path}")
                # Fetch latest branches from remote
                try:
                    subprocess.check_call(["git", "fetch", "--all"], cwd=repo_path)
                except Exception as fetch_err:
                    logger.warning(f"[Warning] Git fetch failed: {fetch_err}")

                cmd = ["git", "branch", "-a"]
                result = subprocess.check_output(cmd, cwd=repo_path, text=True, stderr=subprocess.STDOUT, encoding='utf-8')
                
                for line in result.splitlines():
                    line = line.strip().replace('* ', '')
                    if '->' in line: continue
                    
                    if line.startswith('remotes/origin/'):
                        name = line.replace('remotes/origin/', '')
                    else:
                        name = line
                    
                    if name:
                        branches.add(name)

            # 2. If no branches found locally, query remote (使用带 Token 的 URL)
            if not branches:
                cmd = ["git", "ls-remote", "--heads", repo_url_with_token]
                result = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, encoding='utf-8')
                for line in result.splitlines():
                    parts = line.split('\t')
                    if len(parts) > 1:
                        name = parts[1].replace('refs/heads/', '')
                        branches.add(name)

            sorted_branches = sorted(list(branches))
            logger.info(f"[Info] Found {len(sorted_branches)} branches.")
            return Response({"branches": sorted_branches})
        except subprocess.CalledProcessError as e:
            error_msg = f"Git command failed: {e.output}"
            logger.error(f"[Error] {error_msg}")
            return Response({"error": error_msg}, status=500)
        except Exception as e:
            logger.error(f"[Error] Unexpected error: {str(e)}")
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='git-commits')
    def fetch_git_commits(self, request):
        repo_url = request.data.get('git_url')
        branch = request.data.get('branch', 'HEAD')
        
        if not repo_url:
            return Response({"error": "Git URL is required"}, status=400)
        
        # 为 URL 添加内置 Token（如果配置了）
        repo_url_with_token = add_token_to_git_url(repo_url)
            
        try:
            # 不拉取代码，直接使用 git ls-remote 查询远程提交记录
            # 这样可以避免下载整个仓库，加快查询速度
            logger.info(f"[Info] Fetching commits for {branch} from remote: {repo_url}")
            
            # 使用 git log 命令查询远程分支的提交记录（不需要 clone）
            # 格式：Hash|Message|Date|Author
            cmd = [
                "git", "log", 
                f"origin/{branch}", 
                "--pretty=format:%h|%s|%ad|%an", 
                "--date=format:%Y-%m-%d %H:%M:%S",
                "--remotes",
                f"--remote={repo_url_with_token}"
            ]
            
            # 由于 git log 不支持直接查询远程，我们需要使用临时的浅克隆
            # 创建临时目录
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_repo_path = os.path.join(temp_dir, 'temp_repo')
                
                # 浅克隆（只克隆最近的提交历史，不下载完整代码）
                # --depth=100 只获取最近100次提交
                # --single-branch 只克隆指定分支
                # --no-checkout 不检出工作区文件（不下载代码文件）
                logger.info(f"[Info] Performing shallow clone for commit history...")
                subprocess.check_call([
                    "git", "clone",
                    "--depth=100",  # 只获取最近100次提交
                    "--single-branch",
                    "--branch", branch,
                    "--no-checkout",  # 不检出文件，只获取提交历史
                    repo_url_with_token,
                    temp_repo_path
                ], stderr=subprocess.DEVNULL)
                
                # 获取提交记录
                cmd = [
                    "git", "log",
                    "--pretty=format:%h|%s|%ad|%an",
                    "--date=format:%Y-%m-%d %H:%M:%S"
                ]
                result = subprocess.check_output(
                    cmd, 
                    cwd=temp_repo_path, 
                    text=True, 
                    stderr=subprocess.STDOUT, 
                    encoding='utf-8'
                )
                
                commits = []
                for line in result.splitlines():
                    parts = line.split('|')
                    if len(parts) >= 4:
                        commits.append({
                            "hash": parts[0],
                            "message": parts[1],
                            "date": parts[2],
                            "author": parts[3]
                        })
                
                logger.info(f"[Info] Found {len(commits)} commits")
                return Response({"commits": commits})
                
        except subprocess.CalledProcessError as e:
            error_output = e.output if hasattr(e, 'output') else str(e)
            logger.error(f"[Error] Git command failed: {error_output}")
            return Response({"error": f"Failed to fetch commits: {error_output}"}, status=500)
        except Exception as e:
            logger.error(f"[Error] {e}")
            return Response({"error": str(e)}, status=500)


class ProjectRelationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project relations.
    Provides CRUD operations and custom actions for querying related projects.
    """
    queryset = ProjectRelation.objects.all()
    serializer_class = ProjectRelationSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new project relation with error handling.
        """
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[Error] Failed to create project relation: {str(e)}")
            return Response(
                {"error": f"Failed to create project relation: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        """
        Update a project relation with error handling.
        """
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[Error] Failed to update project relation: {str(e)}")
            return Response(
                {"error": f"Failed to update project relation: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        """
        Delete a project relation with error handling.
        """
        try:
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[Error] Failed to delete project relation: {str(e)}")
            return Response(
                {"error": f"Failed to delete project relation: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='by-main-project')
    def get_by_main_project(self, request):
        """
        Get all active project relations for a given main project Git URL.
        
        Query Parameters:
            main_git_url: The Git URL of the main project
            
        Returns:
            List of active project relations for the specified main project
        """
        try:
            main_git_url = request.query_params.get('main_git_url')
            
            if not main_git_url:
                return Response(
                    {"error": "main_git_url query parameter is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Query active relations for the main project
            relations = ProjectRelation.objects.filter(
                main_project_git_url=main_git_url,
                is_active=True
            )
            
            serializer = self.get_serializer(relations, many=True)
            
            logger.info(f"[Info] Found {relations.count()} active relations for {main_git_url}")
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"[Error] Failed to query project relations: {str(e)}")
            return Response(
                {"error": f"Failed to query project relations: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GitOrganizationViewSet(viewsets.ModelViewSet):
    """
    Git 组织配置管理 ViewSet
    提供 CRUD 操作和自动发现功能
    """
    from .models import GitOrganization, DiscoveredProject
    from .serializers import GitOrganizationSerializer
    from .git_provider import create_git_provider
    
    queryset = GitOrganization.objects.all()
    serializer_class = GitOrganizationSerializer

    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        """
        测试 Git 组织连接是否正常
        """
        try:
            org = self.get_object()
            
            # 创建 Git Provider
            from .git_provider import create_git_provider
            provider = create_git_provider(
                org.git_server_type,
                org.git_server_url,
                org.access_token
            )
            
            # 测试连接
            success, message = provider.test_connection()
            
            if success:
                return Response({
                    "success": True,
                    "message": message
                })
            else:
                return Response({
                    "success": False,
                    "message": message
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"[Error] 测试连接失败: {str(e)}")
            return Response({
                "success": False,
                "message": f"测试连接失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='discover-projects')
    def discover_projects(self, request, pk=None):
        """
        自动发现组织下的所有项目（异步执行）
        """
        try:
            org = self.get_object()
            
            logger.info(f"[Info] 收到项目发现请求，组织: '{org.name}'")
            
            # 异步执行发现任务
            def discover_task():
                try:
                    from .models import DiscoveredProject
                    from .git_provider import create_git_provider
                    
                    logger.info(f"[Info] 开始发现组织 '{org.name}' 下的项目...")
                    
                    # 创建 Git Provider
                    provider = create_git_provider(
                        org.git_server_type,
                        org.git_server_url,
                        org.access_token
                    )
                    
                    # 获取项目列表
                    projects = provider.list_projects(org.name)
                    
                    if not projects:
                        logger.warning(f"[Warning] 未发现任何项目，组织: '{org.name}'")
                        # 即使未发现项目，也更新时间戳，让前端知道任务已完成
                        org.last_discovery_at = timezone.now()
                        org.discovered_project_count = 0
                        org.save()
                        return
                    
                    # 保存或更新项目信息
                    created_count = 0
                    updated_count = 0
                    
                    for proj_data in projects:
                        project, created = DiscoveredProject.objects.update_or_create(
                            organization=org,
                            project_path=proj_data['path'],
                            defaults={
                                'project_name': proj_data['name'],
                                'git_url': proj_data['git_url'],
                                'default_branch': proj_data.get('default_branch', 'master'),
                                'description': proj_data.get('description', ''),
                                'language': proj_data.get('language', ''),
                            }
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    
                    # 更新组织的发现信息
                    org.last_discovery_at = timezone.now()
                    org.discovered_project_count = len(projects)
                    org.save()
                    
                    logger.info(f"[Info] 项目发现完成: 新增 {created_count} 个, 更新 {updated_count} 个")
                    
                except Exception as e:
                    error_msg = f"项目发现失败: {str(e)}\n{traceback.format_exc()}"
                    logger.error(f"[Error] {error_msg}")
                    # 即使发生异常，也更新时间戳，让前端知道任务已完成（失败）
                    try:
                        org.last_discovery_at = timezone.now()
                        org.save()
                    except Exception as save_error:
                        logger.error(f"[Error] 无法更新组织时间戳: {str(save_error)}")
            
            # 启动异步线程
            thread = threading.Thread(target=discover_task)
            thread.daemon = True
            thread.start()
            
            return Response({
                "success": True,
                "message": "项目发现任务已在后台启动，请稍后刷新查看结果"
            })
            
        except Exception as e:
            error_msg = f"启动项目发现任务失败: {str(e)}"
            logger.error(f"[Error] {error_msg}")
            return Response({
                "success": False,
                "message": error_msg
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DiscoveredProjectViewSet(viewsets.ModelViewSet):
    """
    发现的项目管理 ViewSet
    """
    from .models import DiscoveredProject
    from .serializers import DiscoveredProjectSerializer
    
    queryset = DiscoveredProject.objects.all()
    serializer_class = DiscoveredProjectSerializer
    
    def get_queryset(self):
        """支持按组织过滤"""
        queryset = super().get_queryset()
        org_id = self.request.query_params.get('organization_id')
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset


class DashboardViewSet(viewsets.ViewSet):
    """
    首页数据统计接口
    """
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        获取首页统计数据
        """
        try:
            from .models import DiscoveredProject, GitOrganization
            from django.db.models import Count, Avg, Q
            from django.db.models.functions import TruncDate
            
            # 1. 核心指标
            total_analyses = AnalysisReport.objects.count()
            total_projects = DiscoveredProject.objects.filter(is_active=True).count()
            
            # 本周分析次数（最近7天）
            week_ago = timezone.now() - datetime.timedelta(days=7)
            weekly_analyses = AnalysisReport.objects.filter(created_at__gte=week_ago).count()
            
            # 平均分析时长（基于任务表）
            avg_duration_seconds = AnalysisTask.objects.filter(
                status='COMPLETED'
            ).annotate(
                duration=models.F('updated_at') - models.F('created_at')
            ).aggregate(
                avg_duration=Avg('duration')
            )['avg_duration']
            
            if avg_duration_seconds:
                avg_duration_minutes = avg_duration_seconds.total_seconds() / 60
                avg_duration = f"{avg_duration_minutes:.1f}分钟"
            else:
                avg_duration = "暂无数据"
            
            # 2. 分析趋势数据（最近30天）
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            trend_data = AnalysisReport.objects.filter(
                created_at__gte=thirty_days_ago
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
            
            # 转换为前端需要的格式
            trend_list = [
                {
                    'date': item['date'].strftime('%Y-%m-%d'),
                    'count': item['count']
                }
                for item in trend_data
            ]
            
            # 3. 任务成功率趋势（最近30天）
            task_trend = AnalysisTask.objects.filter(
                created_at__gte=thirty_days_ago
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='COMPLETED')),
                failed=Count('id', filter=Q(status='FAILED'))
            ).order_by('date')
            
            task_trend_list = [
                {
                    'date': item['date'].strftime('%Y-%m-%d'),
                    'total': item['total'],
                    'completed': item['completed'],
                    'failed': item['failed'],
                    'success_rate': round(item['completed'] / item['total'] * 100, 1) if item['total'] > 0 else 0
                }
                for item in task_trend
            ]
            
            # 4. 最活跃项目 TOP 10
            top_projects = AnalysisReport.objects.values('project_name').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            top_projects_list = [
                {
                    'project_name': item['project_name'],
                    'count': item['count']
                }
                for item in top_projects
            ]
            
            # 5. 风险等级分布
            risk_distribution = AnalysisReport.objects.values('risk_level').annotate(
                count=Count('id')
            ).order_by('risk_level')
            
            # 风险等级映射（英文转中文，兼容旧数据）
            risk_level_map = {
                'CRITICAL': '高',
                'HIGH': '高',
                'MEDIUM': '中',
                'LOW': '低',
                'UNKNOWN': '未知',
                '严重': '高',  # 兼容旧数据
                '高': '高',
                '中': '中',
                '低': '低',
                '未知': '未知'
            }
            
            # 转换为中文并合并相同等级
            risk_dist_dict = {}
            for item in risk_distribution:
                original_level = item['risk_level']
                chinese_level = risk_level_map.get(original_level, original_level)
                if chinese_level in risk_dist_dict:
                    risk_dist_dict[chinese_level] += item['count']
                else:
                    risk_dist_dict[chinese_level] = item['count']
            
            # 6. 最近分析记录（最近10条）
            recent_analyses = AnalysisReport.objects.select_related('task').order_by('-created_at')[:10]
            
            # 风险等级映射（英文转中文，兼容旧数据）
            risk_level_map_recent = {
                'CRITICAL': '高',
                'HIGH': '高',
                'MEDIUM': '中',
                'LOW': '低',
                'UNKNOWN': '未知',
                '严重': '高',  # 兼容旧数据
                '高': '高',
                '中': '中',
                '低': '低',
                '未知': '未知'
            }
            
            recent_list = [
                {
                    'id': report.id,
                    'project_name': report.project_name,
                    'file_name': report.file_name,
                    'risk_level': risk_level_map_recent.get(report.risk_level, report.risk_level),  # 转换为中文
                    'created_at': report.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'task_id': report.task.id if report.task else None,
                    'task_status': report.task.status if report.task else None
                }
                for report in recent_analyses
            ]
            
            # 7. 系统健康状态
            running_tasks = AnalysisTask.objects.filter(
                status__in=['PENDING', 'PROCESSING']
            ).count()
            
            # 返回统计数据
            return Response({
                'core_metrics': {
                    'total_analyses': total_analyses,
                    'total_projects': total_projects,
                    'weekly_analyses': weekly_analyses,
                    'avg_duration': avg_duration
                },
                'trend_data': trend_list,
                'task_trend': task_trend_list,
                'top_projects': top_projects_list,
                'risk_distribution': risk_dist_dict,
                'recent_analyses': recent_list,
                'system_health': {
                    'running_tasks': running_tasks
                }
            })
            
        except Exception as e:
            logger.error(f"获取统计数据失败: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': f'获取统计数据失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
