import logging
import threading
import os
import subprocess
import traceback
from django.conf import settings
from django.core.management import call_command
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
import datetime
from django.db import models
from .models import AnalysisReport, AnalysisTask
from .serializers import AnalysisReportSerializer, AnalysisTaskSerializer

logger = logging.getLogger(__name__)

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

        # 1. 创建分析任务记录
        task = AnalysisTask.objects.create(
            project_name=git_url.split('/')[-1].replace('.git', '') if git_url else 'Local Project',
            mode=mode,
            source_branch=target_branch,
            target_branch=f"{base_commit} -> {target_commit}", # Store comparison range here
            status='PENDING',
            log_details='任务已创建，等待执行...'
        )

        def run_cmd(task_id):
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
                        subprocess.check_call(["git", "clone", git_url, repo_path])
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
                
                call_command('run_analysis', project_root=target_root, base_ref=base_commit, target_ref=target_commit, task_id=task_id)
                
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
        thread = threading.Thread(target=run_cmd, args=(task.id,))
        thread.start()
        
        return Response({
            "status": "Analysis started", 
            "task_id": task.id,
            "message": "分析任务已在后台启动。"
        })

    @action(detail=False, methods=['post'], url_path='git-branches')
    def fetch_git_branches(self, request):
        repo_url = request.data.get('git_url')
        logger.info(f"[Info] Fetching branches for: {repo_url}")
        if not repo_url:
            return Response({"error": "Git URL is required"}, status=400)
        
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

            # 2. If no branches found locally, query remote
            if not branches:
                cmd = ["git", "ls-remote", "--heads", repo_url]
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
            
        try:
            workspace_root = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'workspace'))
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            repo_path = os.path.join(workspace_root, repo_name)
            
            if not os.path.exists(repo_path):
                # Try to clone lightly if not exists (or error)
                # But assuming flow is: fetch branches -> select branch -> fetch commits
                # branches endpoint usually clones if needed.
                return Response({"error": "Repository not found locally. Please fetch branches first."}, status=400)
            
            logger.info(f"[Info] Fetching commits for {branch} in {repo_path}")
            
            # Ensure we have latest info
            subprocess.check_call(["git", "fetch", "--all"], cwd=repo_path)
            
            # Get logs: Hash|Message|Date|Author
            # Use custom date format for full precision
            # Return ALL commits (no limit) as requested
            cmd = ["git", "log", f"origin/{branch}", "--pretty=format:%h|%s|%ad|%an", "--date=format:%Y-%m-%d %H:%M:%S"]
            result = subprocess.check_output(cmd, cwd=repo_path, text=True, stderr=subprocess.STDOUT, encoding='utf-8')
            
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
            
            return Response({"commits": commits})
        except subprocess.CalledProcessError as e:
            logger.error(f"[Error] Git log failed: {e.output}")
            return Response({"error": f"Failed to fetch commits: {e.output}"}, status=500)
        except Exception as e:
            logger.error(f"[Error] {e}")
            return Response({"error": str(e)}, status=500)
