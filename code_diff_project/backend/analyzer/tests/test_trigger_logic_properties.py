"""
Property-Based Tests for Analysis Trigger Logic

This module tests the correctness properties for analysis trigger logic,
focusing on:
- Property 6: Related Project Query Triggering
- Property 22: Metadata Recording

These tests verify behavior using Django's test framework with property-based
testing principles.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import json
import unittest
from unittest.mock import patch, MagicMock
from django.test import TransactionTestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request

from analyzer.models import ProjectRelation, AnalysisTask
from analyzer.views import AnalysisReportViewSet


# ============================================================================
# Property Tests
# ============================================================================

class TestProperty6_RelatedProjectQueryTriggering(TransactionTestCase):
    """
    **Feature: cross-project-analysis, Property 6: Related Project Query Triggering**
    
    For any analysis task with cross-project analysis enabled, the system should
    query and return all active related projects for the main project.
    
    **Validates: Requirements 2.1**
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.viewset = AnalysisReportViewSet()
        # Clean up any existing data
        ProjectRelation.objects.all().delete()
        AnalysisTask.objects.all().delete()
    
    def tearDown(self):
        """Clean up after tests."""
        ProjectRelation.objects.all().delete()
        AnalysisTask.objects.all().delete()
    
    def test_query_returns_only_active_relations_property(self):
        """
        Property: For any main project URL and set of relations (active and inactive),
        querying should return only active relations matching that URL.
        """
        # Test with various combinations
        test_cases = [
            {'main_url': 'git@github.com:org/main1.git', 'num_active': 1, 'num_inactive': 0},
            {'main_url': 'git@github.com:org/main2.git', 'num_active': 3, 'num_inactive': 2},
            {'main_url': 'git@github.com:org/main3.git', 'num_active': 5, 'num_inactive': 3},
            {'main_url': 'https://github.com/org/main4.git', 'num_active': 2, 'num_inactive': 1},
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # Clean up before each subtest
                ProjectRelation.objects.all().delete()
                
                main_git_url = case['main_url']
                num_active = case['num_active']
                num_inactive = case['num_inactive']
                
                # Create active relations
                for i in range(num_active):
                    ProjectRelation.objects.create(
                        main_project_name=f"main-project-{i}",
                        main_project_git_url=main_git_url,
                        related_project_name=f"related-active-{i}",
                        related_project_git_url=f"git@github.com:org/active-{i}.git",
                        related_project_branch='master',
                        is_active=True
                    )
                
                # Create inactive relations
                for i in range(num_inactive):
                    ProjectRelation.objects.create(
                        main_project_name=f"main-project-{i}",
                        main_project_git_url=main_git_url,
                        related_project_name=f"related-inactive-{i}",
                        related_project_git_url=f"git@github.com:org/inactive-{i}.git",
                        related_project_branch='master',
                        is_active=False
                    )
                
                # Query relations
                queried_relations = ProjectRelation.objects.filter(
                    main_project_git_url=main_git_url,
                    is_active=True
                )
                
                # Verify only active relations are returned
                self.assertEqual(queried_relations.count(), num_active,
                                f"Should return exactly {num_active} active relations")
                
                # Verify all returned relations are active
                for rel in queried_relations:
                    self.assertTrue(rel.is_active,
                                  "All returned relations should be active")
                    self.assertEqual(rel.main_project_git_url, main_git_url,
                                   "All returned relations should match main project URL")
    
    @patch('analyzer.views.threading.Thread')
    @patch('analyzer.views.run_analysis')
    def test_trigger_queries_relations_when_enabled_property(self, mock_run_analysis, mock_thread):
        """
        Property: For any main project with relations, when cross-project is enabled,
        trigger should query and pass all active relations to the analysis thread.
        """
        test_cases = [
            {'main_url': 'git@github.com:org/test1.git', 'num_relations': 1},
            {'main_url': 'git@github.com:org/test2.git', 'num_relations': 3},
            {'main_url': 'https://github.com/org/test3.git', 'num_relations': 5},
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # Clean up
                ProjectRelation.objects.all().delete()
                AnalysisTask.objects.all().delete()
                mock_thread.reset_mock()
                
                main_git_url = case['main_url']
                num_relations = case['num_relations']
                
                # Create relations
                for i in range(num_relations):
                    ProjectRelation.objects.create(
                        main_project_name=f"main-project-{i}",
                        main_project_git_url=main_git_url,
                        related_project_name=f"related-project-{i}",
                        related_project_git_url=f"git@github.com:org/related-{i}.git",
                        related_project_branch='master',
                        is_active=True
                    )
                
                # Create request with cross-project enabled
                request_data = {
                    'mode': 'git',
                    'projectPath': '/tmp/test',
                    'gitUrl': main_git_url,
                    'targetBranch': 'master',
                    'baseCommit': 'HEAD^',
                    'targetCommit': 'HEAD',
                    'enableCrossProject': True
                }
                
                request = self.factory.post('/api/reports/trigger/', request_data, format='json')
                drf_request = Request(request)
                
                # Trigger analysis
                response = self.viewset.trigger_analysis(drf_request)
                
                # Verify response
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data.get('enable_cross_project', False),
                               "Response should indicate cross-project is enabled")
                self.assertEqual(response.data.get('related_projects_count', 0), num_relations,
                                f"Response should indicate {num_relations} related projects")
                
                # Verify thread was called with correct arguments
                mock_thread.assert_called_once()
                call_args = mock_thread.call_args
                thread_args = call_args[1]['args']
                task_id, enable_cross_project, related_projects = thread_args
                
                self.assertTrue(enable_cross_project,
                               "Thread should be called with enable_cross_project=True")
                self.assertEqual(len(related_projects), num_relations,
                                f"Thread should receive {num_relations} related projects")
    
    @patch('analyzer.views.threading.Thread')
    @patch('analyzer.views.run_analysis')
    def test_trigger_skips_query_when_disabled_property(self, mock_run_analysis, mock_thread):
        """
        Property: For any main project, when cross-project is disabled,
        trigger should not query relations and should pass empty list.
        """
        test_urls = [
            'git@github.com:org/test1.git',
            'https://github.com/org/test2.git',
            'git@gitlab.com:org/test3.git',
        ]
        
        for main_git_url in test_urls:
            with self.subTest(url=main_git_url):
                # Clean up
                ProjectRelation.objects.all().delete()
                AnalysisTask.objects.all().delete()
                mock_thread.reset_mock()
                
                # Create some relations (should not be queried)
                ProjectRelation.objects.create(
                    main_project_name="main-project",
                    main_project_git_url=main_git_url,
                    related_project_name="related-project",
                    related_project_git_url="git@github.com:org/related.git",
                    related_project_branch='master',
                    is_active=True
                )
                
                # Create request with cross-project disabled
                request_data = {
                    'mode': 'git',
                    'projectPath': '/tmp/test',
                    'gitUrl': main_git_url,
                    'targetBranch': 'master',
                    'baseCommit': 'HEAD^',
                    'targetCommit': 'HEAD',
                    'enableCrossProject': False
                }
                
                request = self.factory.post('/api/reports/trigger/', request_data, format='json')
                drf_request = Request(request)
                
                # Trigger analysis
                response = self.viewset.trigger_analysis(drf_request)
                
                # Verify response
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('enable_cross_project', response.data,
                                "Response should not include cross-project flag when disabled")
                
                # Verify thread was called with empty related projects
                mock_thread.assert_called_once()
                call_args = mock_thread.call_args
                thread_args = call_args[1]['args']
                task_id, enable_cross_project, related_projects = thread_args
                
                self.assertFalse(enable_cross_project,
                                "Thread should be called with enable_cross_project=False")
                self.assertEqual(len(related_projects), 0,
                                "Thread should receive empty related projects list")


class TestProperty22_MetadataRecording(TransactionTestCase):
    """
    **Feature: cross-project-analysis, Property 22: Metadata Recording**
    
    For any analysis task, the enableCrossProject flag value should be recorded
    in the task metadata.
    
    **Validates: Requirements 6.5**
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.viewset = AnalysisReportViewSet()
        # Clean up any existing data
        ProjectRelation.objects.all().delete()
        AnalysisTask.objects.all().delete()
    
    def tearDown(self):
        """Clean up after tests."""
        ProjectRelation.objects.all().delete()
        AnalysisTask.objects.all().delete()
    
    @patch('analyzer.views.threading.Thread')
    @patch('analyzer.views.run_analysis')
    def test_task_records_cross_project_status_property(self, mock_run_analysis, mock_thread):
        """
        Property: For any analysis task, the task metadata should record
        whether cross-project analysis is enabled and the number of relations.
        """
        test_cases = [
            {'url': 'git@github.com:org/test1.git', 'enabled': True, 'num_relations': 0},
            {'url': 'git@github.com:org/test2.git', 'enabled': True, 'num_relations': 2},
            {'url': 'git@github.com:org/test3.git', 'enabled': False, 'num_relations': 0},
            {'url': 'https://github.com/org/test4.git', 'enabled': True, 'num_relations': 3},
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # Clean up
                ProjectRelation.objects.all().delete()
                AnalysisTask.objects.all().delete()
                
                main_git_url = case['url']
                enable_cross_project = case['enabled']
                num_relations = case['num_relations']
                
                # Create relations if needed
                if enable_cross_project and num_relations > 0:
                    for i in range(num_relations):
                        ProjectRelation.objects.create(
                            main_project_name=f"main-project-{i}",
                            main_project_git_url=main_git_url,
                            related_project_name=f"related-project-{i}",
                            related_project_git_url=f"git@github.com:org/related-{i}.git",
                            related_project_branch='master',
                            is_active=True
                        )
                
                # Create request
                request_data = {
                    'mode': 'git',
                    'projectPath': '/tmp/test',
                    'gitUrl': main_git_url,
                    'targetBranch': 'master',
                    'baseCommit': 'HEAD^',
                    'targetCommit': 'HEAD',
                    'enableCrossProject': enable_cross_project
                }
                
                request = self.factory.post('/api/reports/trigger/', request_data, format='json')
                drf_request = Request(request)
                
                # Trigger analysis
                response = self.viewset.trigger_analysis(drf_request)
                
                # Verify response
                self.assertEqual(response.status_code, 200)
                
                # Get the created task
                task = AnalysisTask.objects.latest('created_at')
                self.assertIsNotNone(task)
                
                # Verify metadata in log_details
                log_details = task.log_details
                self.assertIsNotNone(log_details, "Task should have log_details")
                
                if enable_cross_project:
                    # Should contain cross-project enabled message
                    self.assertIn('跨项目分析: 已启用', log_details,
                                 "Log should indicate cross-project analysis is enabled")
                    
                    # Should contain related projects count
                    self.assertIn(f'关联项目数量: {num_relations}', log_details,
                                 f"Log should indicate {num_relations} related projects")
                else:
                    # Should contain cross-project disabled message
                    self.assertIn('跨项目分析: 未启用', log_details,
                                 "Log should indicate cross-project analysis is not enabled")
    
    @patch('analyzer.views.threading.Thread')
    @patch('analyzer.views.run_analysis')
    def test_task_records_related_project_details_property(self, mock_run_analysis, mock_thread):
        """
        Property: For any analysis task with relations, the task metadata should
        record details of each related project (name, URL, branch).
        """
        test_cases = [
            {'url': 'git@github.com:org/test1.git', 'num_relations': 1},
            {'url': 'git@github.com:org/test2.git', 'num_relations': 2},
            {'url': 'https://github.com/org/test3.git', 'num_relations': 3},
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # Clean up
                ProjectRelation.objects.all().delete()
                AnalysisTask.objects.all().delete()
                
                main_git_url = case['url']
                num_relations = case['num_relations']
                
                # Create relations
                created_relations = []
                for i in range(num_relations):
                    rel = ProjectRelation.objects.create(
                        main_project_name=f"main-project-{i}",
                        main_project_git_url=main_git_url,
                        related_project_name=f"related-project-{i}",
                        related_project_git_url=f"git@github.com:org/related-{i}.git",
                        related_project_branch=f"branch-{i}",
                        is_active=True
                    )
                    created_relations.append(rel)
                
                # Create request with cross-project enabled
                request_data = {
                    'mode': 'git',
                    'projectPath': '/tmp/test',
                    'gitUrl': main_git_url,
                    'targetBranch': 'master',
                    'baseCommit': 'HEAD^',
                    'targetCommit': 'HEAD',
                    'enableCrossProject': True
                }
                
                request = self.factory.post('/api/reports/trigger/', request_data, format='json')
                drf_request = Request(request)
                
                # Trigger analysis
                response = self.viewset.trigger_analysis(drf_request)
                
                # Verify response
                self.assertEqual(response.status_code, 200)
                
                # Get the created task
                task = AnalysisTask.objects.latest('created_at')
                self.assertIsNotNone(task)
                
                # Verify each related project is recorded in log_details
                log_details = task.log_details
                
                for rel in created_relations:
                    # Check project name is recorded
                    self.assertIn(rel.related_project_name, log_details,
                                 f"Log should contain related project name '{rel.related_project_name}'")
                    
                    # Check git URL is recorded
                    self.assertIn(rel.related_project_git_url, log_details,
                                 f"Log should contain related project git URL '{rel.related_project_git_url}'")
                    
                    # Check branch is recorded
                    self.assertIn(f"分支: {rel.related_project_branch}", log_details,
                                 f"Log should contain related project branch '{rel.related_project_branch}'")
    
    @patch('analyzer.views.threading.Thread')
    @patch('analyzer.views.run_analysis')
    def test_task_metadata_persists_across_status_changes_property(self, mock_run_analysis, mock_thread):
        """
        Property: For any analysis task, metadata recorded at creation should
        persist when task status changes.
        """
        test_urls = [
            'git@github.com:org/test1.git',
            'https://github.com/org/test2.git',
        ]
        
        for main_git_url in test_urls:
            with self.subTest(url=main_git_url):
                # Clean up
                ProjectRelation.objects.all().delete()
                AnalysisTask.objects.all().delete()
                
                # Create a relation
                ProjectRelation.objects.create(
                    main_project_name="main-project",
                    main_project_git_url=main_git_url,
                    related_project_name="related-project",
                    related_project_git_url="git@github.com:org/related.git",
                    related_project_branch='master',
                    is_active=True
                )
                
                # Create request with cross-project enabled
                request_data = {
                    'mode': 'git',
                    'projectPath': '/tmp/test',
                    'gitUrl': main_git_url,
                    'targetBranch': 'master',
                    'baseCommit': 'HEAD^',
                    'targetCommit': 'HEAD',
                    'enableCrossProject': True
                }
                
                request = self.factory.post('/api/reports/trigger/', request_data, format='json')
                drf_request = Request(request)
                
                # Trigger analysis
                response = self.viewset.trigger_analysis(drf_request)
                
                # Get the created task
                task = AnalysisTask.objects.latest('created_at')
                initial_log = task.log_details
                
                # Verify initial metadata
                self.assertIn('跨项目分析: 已启用', initial_log)
                self.assertIn('关联项目数量: 1', initial_log)
                
                # Simulate status change
                task.status = 'PROCESSING'
                task.save()
                task.refresh_from_db()
                
                # Verify metadata is still present
                self.assertIn('跨项目分析: 已启用', task.log_details,
                             "Metadata should persist after status change")
                self.assertIn('关联项目数量: 1', task.log_details,
                             "Metadata should persist after status change")


if __name__ == '__main__':
    unittest.main()
