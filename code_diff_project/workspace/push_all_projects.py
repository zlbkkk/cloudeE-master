#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动提交和推送三个项目到 Git 远程仓库
"""

import subprocess
import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 项目配置
PROJECTS = [
    {
        'name': 'common-api',
        'path': 'common-api',
        'commit_message': 'feat: 新增 RabbitMQ 消息队列支持 - 添加 OrderEventDTO 和 QueueConstant'
    },
    {
        'name': 'service-a',
        'path': 'service-a',
        'commit_message': 'feat: 新增融资交易管理接口 - 添加 OfTransactionController 实现 /ofTransaction/page 分页查询接口，支持融资审核界面数据查询'
    },
    {
        'name': 'service-b',
        'path': 'service-b',
        'commit_message': 'feat: 新增 RabbitMQ 消息消费者 - OrderEventConsumer 处理订单事件'
    }
]

def run_command(cmd, cwd):
    """执行命令并返回结果"""
    try:
        # 创建一个新的环境变量副本，确保不使用固定的 git 日期
        env = os.environ.copy()
        # 移除可能导致固定时间的环境变量
        env.pop('GIT_AUTHOR_DATE', None)
        env.pop('GIT_COMMITTER_DATE', None)
        
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            env=env  # 使用清理后的环境变量
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, '', str(e)

def get_current_branch(project_path):
    """获取当前分支名"""
    code, stdout, stderr = run_command('git branch --show-current', project_path)
    if code == 0:
        return stdout.strip()
    return 'main'  # 默认返回 main

def commit_and_push_project(project):
    """提交并推送单个项目"""
    project_path = Path(__file__).parent / project['path']
    project_name = project['name']
    commit_message = project['commit_message']
    
    print(f"\n{'='*60}")
    print(f"处理项目: {project_name}")
    print(f"路径: {project_path}")
    print(f"{'='*60}")
    
    if not project_path.exists():
        print(f"❌ 错误: 项目路径不存在: {project_path}")
        return False
    
    # 0. 检查并切换到 main 分支
    print("\n[0/7] 检查当前分支...")
    current_branch = get_current_branch(project_path)
    if not current_branch or current_branch == '':
        print("⚠ 检测到 detached HEAD 状态")
        
        # 检查是否有未提交的修改
        code, status_output, stderr = run_command('git status --short', project_path)
        has_changes = bool(status_output.strip())
        
        if has_changes:
            print("⚠ 检测到未提交的修改，先在 detached HEAD 状态下提交")
            
            # 在 detached HEAD 状态下添加并提交修改
            print("添加所有修改...")
            run_command('git add .', project_path)
            
            print(f"提交修改: {commit_message}")
            code, stdout, stderr = run_command(f'git commit -m "{commit_message}"', project_path)
            if code == 0:
                print("✓ 在 detached HEAD 状态下提交成功")
            else:
                print(f"⚠ 提交时出现问题: {stderr}")
        
        # 获取当前 HEAD 的 commit hash
        code, commit_hash, stderr = run_command('git rev-parse HEAD', project_path)
        if code == 0:
            commit_hash = commit_hash.strip()
            print(f"当前 HEAD commit: {commit_hash[:8]}")
        
        # 切换到 main 分支
        print("切换到 main 分支...")
        code, stdout, stderr = run_command('git checkout main', project_path)
        if code == 0:
            print("✓ 已切换到 main 分支")
            
            # 如果 detached HEAD 有新提交，需要合并
            if commit_hash:
                print(f"检查是否需要合并 detached HEAD 的提交...")
                # 使用 cherry-pick 将 detached HEAD 的提交应用到 main
                code, stdout, stderr = run_command(f'git cherry-pick {commit_hash}', project_path)
                if code == 0:
                    print(f"✓ 已合并 detached HEAD 的提交: {commit_hash[:8]}")
                elif 'nothing to commit' in stdout or 'nothing to commit' in stderr:
                    print("ℹ detached HEAD 的提交已存在于 main 分支")
                else:
                    print(f"⚠ 合并提交时出现问题: {stderr}")
            
            current_branch = 'main'
        else:
            print(f"❌ 切换分支失败: {stderr}")
            # 尝试创建并切换到 main 分支
            print("尝试创建 main 分支...")
            code, stdout, stderr = run_command('git checkout -b main', project_path)
            if code == 0:
                print("✓ 已创建并切换到 main 分支")
                current_branch = 'main'
            else:
                print(f"❌ 创建分支失败: {stderr}")
                return False
    else:
        print(f"✓ 当前分支: {current_branch}")
    
    # 1. 检查状态
    print("\n[1/7] 检查 Git 状态...")
    code, stdout, stderr = run_command('git status --short', project_path)
    if stdout.strip():
        print(f"发现未提交的更改:\n{stdout}")
    else:
        print("工作区干净，检查是否有未推送的提交...")
    
    # 2. 添加所有更改
    print("\n[2/7] 添加所有更改...")
    code, stdout, stderr = run_command('git add .', project_path)
    if code == 0:
        print("✓ 添加成功")
    else:
        print(f"⚠ 添加时出现警告: {stderr}")
    
    # 3. 提交更改
    print("\n[3/7] 提交更改...")
    code, stdout, stderr = run_command(f'git commit -m "{commit_message}"', project_path)
    if code == 0:
        print(f"✓ 提交成功: {commit_message}")
        print(stdout)
    elif 'nothing to commit' in stdout or 'nothing to commit' in stderr:
        print("ℹ 没有需要提交的更改")
    else:
        print(f"⚠ 提交时出现问题: {stderr}")
    
    # 4. 再次确认当前分支
    current_branch = get_current_branch(project_path)
    print(f"\n[4/7] 确认当前分支: {current_branch}")
    
    if not current_branch or current_branch == '':
        print("❌ 错误: 仍然无法获取分支信息")
        return False
    
    # 5. 设置上游分支（如果需要）
    print(f"\n[5/7] 检查上游分支...")
    code, stdout, stderr = run_command(f'git branch --set-upstream-to=origin/{current_branch} {current_branch}', project_path)
    if code == 0:
        print(f"✓ 已设置上游分支: origin/{current_branch}")
    else:
        print(f"ℹ 上游分支可能已设置或不需要设置")
    
    # 6. 拉取远程最新代码（避免冲突）
    print(f"\n[6/7] 拉取远程最新代码...")
    code, stdout, stderr = run_command(f'git pull origin {current_branch} --rebase', project_path)
    if code == 0:
        if 'Already up to date' in stdout or 'Already up to date' in stderr:
            print("✓ 本地已是最新")
        else:
            print("✓ 已拉取并合并远程代码")
    else:
        print(f"⚠ 拉取时出现问题: {stderr}")
    
    # 7. 推送到远程
    print(f"\n[7/7] 推送到远程仓库 (origin/{current_branch})...")
    code, stdout, stderr = run_command(f'git push origin {current_branch}', project_path)
    
    if code == 0:
        if 'Everything up-to-date' in stderr or 'Everything up-to-date' in stdout:
            print("✓ 远程仓库已是最新")
        else:
            print("✓ 推送成功")
            print(stderr if stderr else stdout)
        return True
    else:
        print(f"❌ 推送失败: {stderr}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("自动提交和推送 Git 项目")
    print("=" * 60)
    
    success_count = 0
    failed_projects = []
    
    for project in PROJECTS:
        try:
            if commit_and_push_project(project):
                success_count += 1
            else:
                failed_projects.append(project['name'])
        except Exception as e:
            print(f"\n❌ 处理项目 {project['name']} 时发生错误: {e}")
            failed_projects.append(project['name'])
    
    # 总结
    print("\n" + "=" * 60)
    print("执行总结")
    print("=" * 60)
    print(f"✓ 成功: {success_count}/{len(PROJECTS)} 个项目")
    
    if failed_projects:
        print(f"❌ 失败: {', '.join(failed_projects)}")
    else:
        print("🎉 所有项目都已成功推送到远程仓库！")
    
    print("=" * 60)

if __name__ == '__main__':
    main()
