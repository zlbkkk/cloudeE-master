import subprocess
import os
from loguru import logger


def clone_or_update_project(proj_config, workspace_dir, idx, total):
    """
    克隆或更新单个项目的辅助函数，用于并行执行
    
    参数:
        proj_config: 项目配置字典
        workspace_dir: workspace 目录路径
        idx: 项目索引（用于日志）
        total: 总项目数（用于日志）
    
    返回:
        dict: {'success': bool, 'name': str, 'path': str, 'error': str}
    """
    proj_name = proj_config.get('related_project_name', f'project_{idx}')
    proj_git_url = proj_config.get('related_project_git_url', '')
    proj_branch = proj_config.get('related_project_branch', 'master')
    
    result = {
        'success': False,
        'name': proj_name,
        'path': None,
        'error': None
    }
    
    if not proj_git_url:
        result['error'] = 'Missing Git URL'
        return result
    
    project_local_path = os.path.join(workspace_dir, proj_name)
    
    try:
        if not os.path.exists(project_local_path):
            # 项目不存在，执行克隆
            logger.info(f"[{idx}/{total}] 克隆项目: {proj_name} from {proj_git_url}")
            
            clone_cmd = ['git', 'clone', proj_git_url, project_local_path]
            clone_result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if clone_result.returncode != 0:
                result['error'] = f"Clone failed: {clone_result.stderr}"
                return result
            
            logger.info(f"[{idx}/{total}] 克隆成功: {proj_name}")
        else:
            # 项目已存在，执行更新
            logger.info(f"[{idx}/{total}] 更新项目: {proj_name}")
            
            # 先强制清理本地更改，避免冲突
            logger.info(f"[{idx}/{total}] 清理本地更改: {proj_name}")
            
            # 重置所有本地更改
            reset_local_cmd = ['git', '-C', project_local_path, 'reset', '--hard']
            subprocess.run(reset_local_cmd, capture_output=True, text=True)
            
            # 清理未跟踪的文件
            clean_cmd = ['git', '-C', project_local_path, 'clean', '-fd']
            subprocess.run(clean_cmd, capture_output=True, text=True)
            
            # 执行 git fetch
            fetch_cmd = ['git', '-C', project_local_path, 'fetch', '--all', '--prune']
            fetch_result = subprocess.run(
                fetch_cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2分钟超时
            )
            
            if fetch_result.returncode != 0:
                logger.warning(f"[{idx}/{total}] Fetch 失败: {proj_name} - {fetch_result.stderr}")
            else:
                logger.info(f"[{idx}/{total}] Fetch 成功: {proj_name}")
        
        # 检查分支是否存在
        check_branch_cmd = ['git', '-C', project_local_path, 'rev-parse', '--verify', f'origin/{proj_branch}']
        check_result = subprocess.run(
            check_branch_cmd,
            capture_output=True,
            text=True
        )
        
        if check_result.returncode != 0:
            logger.warning(f"[{idx}/{total}] 分支 {proj_branch} 不存在，尝试默认分支")
            # 尝试使用 master 或 main
            for default_branch in ['master', 'main']:
                check_cmd = ['git', '-C', project_local_path, 'rev-parse', '--verify', f'origin/{default_branch}']
                check_result = subprocess.run(check_cmd, capture_output=True, text=True)
                if check_result.returncode == 0:
                    proj_branch = default_branch
                    logger.info(f"[{idx}/{total}] 使用默认分支: {default_branch}")
                    break
        
        # 切换分支
        checkout_cmd = ['git', '-C', project_local_path, 'checkout', proj_branch]
        checkout_result = subprocess.run(
            checkout_cmd,
            capture_output=True,
            text=True
        )
        
        if checkout_result.returncode != 0:
            logger.warning(f"[{idx}/{total}] 切换分支失败: {proj_name} - {checkout_result.stderr}")
        else:
            logger.info(f"[{idx}/{total}] 切换到分支: {proj_branch}")
        
        # Reset 到最新提交
        reset_cmd = ['git', '-C', project_local_path, 'reset', '--hard', f'origin/{proj_branch}']
        reset_result = subprocess.run(
            reset_cmd,
            capture_output=True,
            text=True
        )
        
        if reset_result.returncode != 0:
            logger.warning(f"[{idx}/{total}] Reset 失败: {proj_name} - {reset_result.stderr}")
        else:
            logger.info(f"[{idx}/{total}] Reset 到最新提交")
        
        # 成功
        result['success'] = True
        result['path'] = project_local_path
        logger.info(f"[{idx}/{total}] 项目准备完成: {proj_name}")
        
    except subprocess.TimeoutExpired:
        result['error'] = 'Operation timeout'
        logger.error(f"[{idx}/{total}] 操作超时: {proj_name}")
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"[{idx}/{total}] 处理失败: {proj_name} - {str(e)}")
    
    return result
