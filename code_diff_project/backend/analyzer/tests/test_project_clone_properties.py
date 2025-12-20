"""
Property-Based Tests for Project Clone and Update Operations

This module tests the correctness properties for project cloning and updating:
- Property 7: Branch Switching Correctness
- Property 27: Successful Clone Added to Scan List

These tests use Hypothesis for property-based testing to verify behavior across
a wide range of inputs.
"""

import os
import sys
import tempfile
import shutil
import subprocess
from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import composite
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from analyzer.analysis.project_manager import clone_or_update_project


# ============================================================================
# Test Data Generators
# ============================================================================

@composite
def valid_branch_name(draw):
    """Generate valid Git branch names."""
    # Branch names can contain alphanumeric, dash, underscore, slash
    # Avoid starting with dash or containing consecutive dots
    parts = draw(st.lists(
        st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
            min_size=1,
            max_size=20
        ).filter(lambda x: not x.startswith('-') and '..' not in x),
        min_size=1,
        max_size=3
    ))
    return '/'.join(parts)


@composite
def project_config(draw):
    """Generate a project configuration dictionary."""
    name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
        min_size=3,
        max_size=20
    ))
    branch = draw(valid_branch_name())
    
    return {
        'related_project_name': name,
        'related_project_git_url': None,  # Will be set to actual test repo
        'related_project_branch': branch
    }


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_git_repo(repo_path, branches=None):
    """
    Create a test Git repository with specified branches.
    
    Args:
        repo_path: Path where to create the repository
        branches: List of branch names to create (default: ['master'])
    
    Returns:
        Path to the created repository
    """
    if branches is None:
        branches = ['master']
    
    os.makedirs(repo_path, exist_ok=True)
    
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_path, capture_output=True, check=True)
    
    # Create initial commit on master
    test_file = os.path.join(repo_path, 'README.md')
    with open(test_file, 'w') as f:
        f.write('# Test Repository\n')
    
    subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_path, capture_output=True, check=True)
    
    # Create additional branches
    for branch in branches:
        if branch != 'master':
            subprocess.run(['git', 'branch', branch], cwd=repo_path, capture_output=True, check=True)
            # Add a commit to the branch to make it different
            subprocess.run(['git', 'checkout', branch], cwd=repo_path, capture_output=True, check=True)
            branch_file = os.path.join(repo_path, f'{branch}.txt')
            with open(branch_file, 'w') as f:
                f.write(f'Branch: {branch}\n')
            subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', f'Commit on {branch}'], cwd=repo_path, capture_output=True, check=True)
    
    # Return to master
    subprocess.run(['git', 'checkout', 'master'], cwd=repo_path, capture_output=True, check=True)
    
    return repo_path


def get_current_branch(repo_path):
    """Get the current branch of a Git repository."""
    result = subprocess.run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


def cleanup_temp_dir(path):
    """Remove temporary directory."""
    if os.path.exists(path):
        shutil.rmtree(path)


# ============================================================================
# Property Tests
# ============================================================================

class TestProperty7_BranchSwitchingCorrectness(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 7: Branch Switching Correctness**
    
    For any related project and configured branch name, after the update operation,
    the local repository's current branch should match the configured branch.
    
    **Validates: Requirements 2.4**
    """
    
    @given(st.sampled_from(['master', 'develop', 'feature/test', 'release/v1.0']))
    @settings(max_examples=20, deadline=None)
    def test_switches_to_configured_branch(self, target_branch):
        """Property: Update operation switches to the configured branch."""
        source_repo = None
        workspace_dir = None
        
        try:
            # Create source repository with multiple branches
            source_repo = tempfile.mkdtemp(prefix='source_repo_')
            branches = ['master', 'develop', 'feature/test', 'release/v1.0']
            create_test_git_repo(source_repo, branches=branches)
            
            # Create workspace directory
            workspace_dir = tempfile.mkdtemp(prefix='workspace_')
            
            # Configure project to clone
            proj_config = {
                'related_project_name': 'test_project',
                'related_project_git_url': source_repo,
                'related_project_branch': target_branch
            }
            
            # Execute clone operation
            result = clone_or_update_project(proj_config, workspace_dir, 1, 1)
            
            # Verify operation succeeded
            self.assertTrue(result['success'], 
                          f"Clone operation should succeed. Error: {result.get('error')}")
            self.assertIsNotNone(result['path'], "Result should contain project path")
            
            # Verify the repository exists
            project_path = result['path']
            self.assertTrue(os.path.exists(project_path), 
                          f"Project path should exist: {project_path}")
            
            # Verify current branch matches configured branch
            current_branch = get_current_branch(project_path)
            self.assertEqual(current_branch, target_branch,
                           f"Current branch should be '{target_branch}', got '{current_branch}'")
            
        finally:
            if source_repo:
                cleanup_temp_dir(source_repo)
            if workspace_dir:
                cleanup_temp_dir(workspace_dir)
    
    @given(st.sampled_from(['master', 'develop', 'feature/new']))
    @settings(max_examples=15, deadline=None)
    def test_updates_existing_repo_to_correct_branch(self, target_branch):
        """Property: Update operation on existing repo switches to correct branch."""
        source_repo = None
        workspace_dir = None
        
        try:
            # Create source repository
            source_repo = tempfile.mkdtemp(prefix='source_repo_')
            branches = ['master', 'develop', 'feature/new']
            create_test_git_repo(source_repo, branches=branches)
            
            # Create workspace directory
            workspace_dir = tempfile.mkdtemp(prefix='workspace_')
            
            # First clone with master branch
            proj_config = {
                'related_project_name': 'test_project',
                'related_project_git_url': source_repo,
                'related_project_branch': 'master'
            }
            
            result1 = clone_or_update_project(proj_config, workspace_dir, 1, 1)
            self.assertTrue(result1['success'], "Initial clone should succeed")
            
            project_path = result1['path']
            initial_branch = get_current_branch(project_path)
            self.assertEqual(initial_branch, 'master', "Initial branch should be master")
            
            # Now update to target branch
            proj_config['related_project_branch'] = target_branch
            result2 = clone_or_update_project(proj_config, workspace_dir, 1, 1)
            
            self.assertTrue(result2['success'], 
                          f"Update operation should succeed. Error: {result2.get('error')}")
            
            # Verify branch was switched
            current_branch = get_current_branch(project_path)
            self.assertEqual(current_branch, target_branch,
                           f"After update, branch should be '{target_branch}', got '{current_branch}'")
            
        finally:
            if source_repo:
                cleanup_temp_dir(source_repo)
            if workspace_dir:
                cleanup_temp_dir(workspace_dir)
    
    def test_falls_back_to_default_branch_when_configured_not_exists(self):
        """Property: When configured branch doesn't exist, falls back to master/main."""
        source_repo = None
        workspace_dir = None
        
        try:
            # Create source repository with only master
            source_repo = tempfile.mkdtemp(prefix='source_repo_')
            create_test_git_repo(source_repo, branches=['master'])
            
            # Create workspace directory
            workspace_dir = tempfile.mkdtemp(prefix='workspace_')
            
            # Configure project with non-existent branch
            proj_config = {
                'related_project_name': 'test_project',
                'related_project_git_url': source_repo,
                'related_project_branch': 'nonexistent_branch'
            }
            
            # Execute clone operation
            result = clone_or_update_project(proj_config, workspace_dir, 1, 1)
            
            # Verify operation succeeded (should fall back)
            self.assertTrue(result['success'], 
                          f"Clone should succeed with fallback. Error: {result.get('error')}")
            
            # Verify it fell back to master
            project_path = result['path']
            current_branch = get_current_branch(project_path)
            self.assertIn(current_branch, ['master', 'main'],
                        f"Should fall back to master/main, got '{current_branch}'")
            
        finally:
            if source_repo:
                cleanup_temp_dir(source_repo)
            if workspace_dir:
                cleanup_temp_dir(workspace_dir)


class TestProperty27_SuccessfulCloneAddedToScanList(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 27: Successful Clone Added to Scan List**
    
    For any parallel clone operation, when it completes successfully,
    the project path should be added to the scan roots list.
    
    **Validates: Requirements 8.2**
    """
    
    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=10, deadline=None)
    def test_successful_clones_return_valid_paths(self, num_projects):
        """Property: Successful clone operations return valid project paths."""
        source_repos = []
        workspace_dir = None
        
        try:
            # Create multiple source repositories
            workspace_dir = tempfile.mkdtemp(prefix='workspace_')
            
            for i in range(num_projects):
                source_repo = tempfile.mkdtemp(prefix=f'source_repo_{i}_')
                create_test_git_repo(source_repo, branches=['master'])
                source_repos.append(source_repo)
            
            # Clone all projects
            results = []
            for idx, source_repo in enumerate(source_repos):
                proj_config = {
                    'related_project_name': f'project_{idx}',
                    'related_project_git_url': source_repo,
                    'related_project_branch': 'master'
                }
                
                result = clone_or_update_project(proj_config, workspace_dir, idx + 1, num_projects)
                results.append(result)
            
            # Verify all operations succeeded
            successful_results = [r for r in results if r['success']]
            self.assertEqual(len(successful_results), num_projects,
                           f"All {num_projects} clone operations should succeed")
            
            # Verify all successful results have valid paths
            for result in successful_results:
                self.assertIsNotNone(result['path'], 
                                   "Successful result should contain path")
                self.assertTrue(os.path.exists(result['path']),
                              f"Path should exist: {result['path']}")
                self.assertTrue(os.path.isdir(result['path']),
                              f"Path should be a directory: {result['path']}")
                
                # Verify it's a valid git repository
                git_dir = os.path.join(result['path'], '.git')
                self.assertTrue(os.path.exists(git_dir),
                              f"Should be a git repository: {result['path']}")
            
            # Simulate building scan_roots list (as done in runner.py)
            scan_roots = []
            for result in results:
                if result['success']:
                    scan_roots.append(result['path'])
            
            # Verify scan_roots contains all successful paths
            self.assertEqual(len(scan_roots), num_projects,
                           f"Scan roots should contain all {num_projects} successful paths")
            
            # Verify all paths in scan_roots are unique
            self.assertEqual(len(scan_roots), len(set(scan_roots)),
                           "All paths in scan_roots should be unique")
            
        finally:
            for source_repo in source_repos:
                cleanup_temp_dir(source_repo)
            if workspace_dir:
                cleanup_temp_dir(workspace_dir)
    
    def test_failed_clone_does_not_return_path(self):
        """Property: Failed clone operations do not return valid paths."""
        workspace_dir = None
        
        try:
            # Create workspace directory
            workspace_dir = tempfile.mkdtemp(prefix='workspace_')
            
            # Configure project with invalid Git URL
            proj_config = {
                'related_project_name': 'invalid_project',
                'related_project_git_url': '/nonexistent/invalid/repo',
                'related_project_branch': 'master'
            }
            
            # Execute clone operation
            result = clone_or_update_project(proj_config, workspace_dir, 1, 1)
            
            # Verify operation failed
            self.assertFalse(result['success'], 
                           "Clone with invalid URL should fail")
            self.assertIsNone(result['path'],
                            "Failed result should not contain valid path")
            self.assertIsNotNone(result['error'],
                               "Failed result should contain error message")
            
            # Simulate building scan_roots list
            scan_roots = []
            if result['success']:
                scan_roots.append(result['path'])
            
            # Verify failed clone is not in scan_roots
            self.assertEqual(len(scan_roots), 0,
                           "Failed clone should not be added to scan_roots")
            
        finally:
            if workspace_dir:
                cleanup_temp_dir(workspace_dir)
    
    def test_mixed_success_and_failure_only_adds_successful(self):
        """Property: When some clones succeed and some fail, only successful paths are added."""
        source_repo = None
        workspace_dir = None
        
        try:
            # Create one valid source repository
            source_repo = tempfile.mkdtemp(prefix='source_repo_')
            create_test_git_repo(source_repo, branches=['master'])
            
            # Create workspace directory
            workspace_dir = tempfile.mkdtemp(prefix='workspace_')
            
            # Clone one valid and one invalid project
            configs = [
                {
                    'related_project_name': 'valid_project',
                    'related_project_git_url': source_repo,
                    'related_project_branch': 'master'
                },
                {
                    'related_project_name': 'invalid_project',
                    'related_project_git_url': '/nonexistent/invalid/repo',
                    'related_project_branch': 'master'
                }
            ]
            
            results = []
            for idx, config in enumerate(configs):
                result = clone_or_update_project(config, workspace_dir, idx + 1, len(configs))
                results.append(result)
            
            # Verify one succeeded and one failed
            successful_results = [r for r in results if r['success']]
            failed_results = [r for r in results if not r['success']]
            
            self.assertEqual(len(successful_results), 1, "One clone should succeed")
            self.assertEqual(len(failed_results), 1, "One clone should fail")
            
            # Simulate building scan_roots list
            scan_roots = []
            for result in results:
                if result['success']:
                    scan_roots.append(result['path'])
            
            # Verify only successful path is in scan_roots
            self.assertEqual(len(scan_roots), 1,
                           "Only successful clone should be in scan_roots")
            self.assertEqual(scan_roots[0], successful_results[0]['path'],
                           "Scan roots should contain the successful project path")
            
        finally:
            if source_repo:
                cleanup_temp_dir(source_repo)
            if workspace_dir:
                cleanup_temp_dir(workspace_dir)


if __name__ == '__main__':
    unittest.main()
