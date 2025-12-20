"""
Property-Based Tests for Cross-Project Impact Formatting

This module tests the correctness properties for cross-project impact formatting
and report generation, focusing on:
- Property 11: Project Grouping Correctness
- Property 16: API Call Grouping
- Property 17: Report Contains Cross-Project Section
- Property 18: Impact Display Grouping
- Property 19: Impact Entry Completeness
- Property 20: Main Project vs Cross-Project Distinction

These tests use Hypothesis for property-based testing to verify behavior across
a wide range of inputs.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import json
import tempfile
import shutil
from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import composite
import unittest

from analyzer.analysis.ai_analyzer import format_cross_project_impacts


# ============================================================================
# Test Data Generators
# ============================================================================

@composite
def valid_project_name(draw):
    """Generate valid project names."""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=45, max_codepoint=122),
        min_size=3,
        max_size=20
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))


@composite
def valid_file_path(draw):
    """Generate valid file paths."""
    parts = draw(st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=45, max_codepoint=122),
            min_size=1,
            max_size=15
        ),
        min_size=2,
        max_size=5
    ))
    return '/'.join(parts) + '.java'


@composite
def valid_code_snippet(draw):
    """Generate valid code snippets."""
    snippets = [
        'import com.example.UserService;',
        'private UserService userService;',
        '@Autowired private OrderService orderService;',
        '@DubboReference private PaymentService paymentService;',
        'public void processOrder(Order order) {',
        'userService.getUserById(userId);',
        'return orderService.createOrder(request);'
    ]
    return draw(st.sampled_from(snippets))


@composite
def class_reference_impact(draw, project_name=None):
    """Generate a class reference impact record."""
    if project_name is None:
        project_name = draw(valid_project_name())
    
    return {
        'project': project_name,
        'type': 'class_reference',
        'file': draw(valid_file_path()),
        'line': draw(st.integers(min_value=1, max_value=1000)),
        'snippet': draw(valid_code_snippet()),
        'detail': draw(st.text(min_size=10, max_size=100))
    }


@composite
def api_call_impact(draw, project_name=None):
    """Generate an API call impact record."""
    if project_name is None:
        project_name = draw(valid_project_name())
    
    api_methods = ['GET', 'POST', 'PUT', 'DELETE']
    api_paths = ['/api/user/info', '/api/order/create', '/api/payment/process', '/api/product/list']
    
    return {
        'project': project_name,
        'type': 'api_call',
        'file': draw(valid_file_path()),
        'line': draw(st.integers(min_value=1, max_value=1000)),
        'snippet': draw(valid_code_snippet()),
        'detail': draw(st.text(min_size=10, max_size=100)),
        'api': f"{draw(st.sampled_from(api_methods))} {draw(st.sampled_from(api_paths))}"
    }


@composite
def mixed_impact_list(draw):
    """Generate a list of mixed class reference and API call impacts."""
    num_projects = draw(st.integers(min_value=1, max_value=5))
    project_names = [draw(valid_project_name()) for _ in range(num_projects)]
    
    impacts = []
    for project_name in project_names:
        # Each project has 1-5 impacts
        num_impacts = draw(st.integers(min_value=1, max_value=5))
        for _ in range(num_impacts):
            impact_type = draw(st.sampled_from(['class_reference', 'api_call']))
            if impact_type == 'class_reference':
                impacts.append(draw(class_reference_impact(project_name=project_name)))
            else:
                impacts.append(draw(api_call_impact(project_name=project_name)))
    
    return impacts


# ============================================================================
# Property Tests
# ============================================================================

class TestProperty11_ProjectGroupingCorrectness(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 11: Project Grouping Correctness**
    
    For any cross-project impact list, impacts from the same project should be grouped together.
    
    **Validates: Requirements 3.4**
    """
    
    @given(mixed_impact_list())
    @settings(max_examples=100, deadline=None)
    def test_impacts_grouped_by_project(self, impacts):
        """Property: Impacts from same project are grouped together."""
        if not impacts:
            return
        
        # Format the impacts
        formatted = format_cross_project_impacts(impacts)
        
        # Extract project names from impacts
        project_names = list(set(impact['project'] for impact in impacts))
        
        # Verify each project appears in the formatted output
        for project_name in project_names:
            self.assertIn(project_name, formatted,
                         f"Formatted output should contain project name '{project_name}'")
        
        # Verify grouping by checking that all impacts from same project
        # appear in the same section
        for project_name in project_names:
            project_impacts = [i for i in impacts if i['project'] == project_name]
            
            # Find the section for this project in formatted output
            lines = formatted.split('\n')
            project_section_start = None
            project_section_end = None
            
            for i, line in enumerate(lines):
                if f"【项目】{project_name}" in line:
                    project_section_start = i
                elif project_section_start is not None and "【项目】" in line:
                    project_section_end = i
                    break
            
            if project_section_start is not None:
                if project_section_end is None:
                    project_section_end = len(lines)
                
                project_section = '\n'.join(lines[project_section_start:project_section_end])
                
                # Verify all impacts from this project are in this section
                for impact in project_impacts:
                    # Check if file path appears in the section
                    self.assertIn(impact['file'], project_section,
                                f"Impact file '{impact['file']}' should appear in project section for '{project_name}'")


class TestProperty16_APICallGrouping(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 16: API Call Grouping**
    
    For any API endpoint with multiple callers, results should be grouped by project name.
    
    **Validates: Requirements 4.4**
    """
    
    @given(st.lists(api_call_impact(), min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_api_calls_grouped_by_project(self, impacts):
        """Property: API calls are grouped by project."""
        if not impacts:
            return
        
        # Format the impacts
        formatted = format_cross_project_impacts(impacts)
        
        # Extract unique projects
        projects = list(set(impact['project'] for impact in impacts))
        
        # Verify each project has an API call section
        for project_name in projects:
            project_api_calls = [i for i in impacts if i['project'] == project_name]
            
            if project_api_calls:
                # Find project section
                lines = formatted.split('\n')
                in_project_section = False
                found_api_section = False
                
                for line in lines:
                    if f"【项目】{project_name}" in line:
                        in_project_section = True
                    elif "【项目】" in line and in_project_section:
                        break
                    elif in_project_section and "▶ API 调用:" in line:
                        found_api_section = True
                        break
                
                self.assertTrue(found_api_section,
                              f"Project '{project_name}' should have API call section")


class TestProperty17_ReportContainsCrossProjectSection(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 17: Report Contains Cross-Project Section**
    
    For any analysis with cross-project impacts, the generated report should contain
    a dedicated cross-project impact section.
    
    **Validates: Requirements 5.1**
    """
    
    @given(mixed_impact_list())
    @settings(max_examples=100, deadline=None)
    def test_report_contains_cross_project_section(self, impacts):
        """Property: Report contains dedicated cross-project section when impacts exist."""
        if not impacts:
            # Empty impacts should return a message
            formatted = format_cross_project_impacts(impacts)
            self.assertIn("未检测到跨项目影响", formatted)
            return
        
        # Format the impacts
        formatted = format_cross_project_impacts(impacts)
        
        # Verify section header exists
        self.assertIn("跨项目影响分析结果", formatted,
                     "Report should contain cross-project analysis section header")
        
        # Verify summary line exists
        self.assertIn("总计发现", formatted,
                     "Report should contain summary of total impacts")
        
        # Verify project count
        num_projects = len(set(impact['project'] for impact in impacts))
        self.assertIn(f"涉及 {num_projects} 个项目", formatted,
                     f"Report should mention {num_projects} projects")
    
    def test_empty_impacts_returns_no_impact_message(self):
        """Property: Empty impacts list returns appropriate message."""
        formatted = format_cross_project_impacts([])
        self.assertEqual(formatted, "未检测到跨项目影响。",
                        "Empty impacts should return 'no impact detected' message")


class TestProperty18_ImpactDisplayGrouping(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 18: Impact Display Grouping**
    
    For any cross-project impact display, impacts should be organized by related project name.
    
    **Validates: Requirements 5.2**
    """
    
    @given(mixed_impact_list())
    @settings(max_examples=100, deadline=None)
    def test_impacts_organized_by_project_name(self, impacts):
        """Property: Impacts are organized by project name in display."""
        if not impacts:
            return
        
        # Format the impacts
        formatted = format_cross_project_impacts(impacts)
        
        # Extract project names
        project_names = sorted(set(impact['project'] for impact in impacts))
        
        # Find positions of project headers in formatted output
        lines = formatted.split('\n')
        project_positions = {}
        
        for i, line in enumerate(lines):
            for project_name in project_names:
                if f"【项目】{project_name}" in line:
                    project_positions[project_name] = i
        
        # Verify all projects appear
        self.assertEqual(len(project_positions), len(project_names),
                        "All projects should appear in formatted output")
        
        # Verify impacts for each project appear after project header
        for project_name in project_names:
            project_impacts = [i for i in impacts if i['project'] == project_name]
            project_pos = project_positions[project_name]
            
            # Find next project position or end of output
            next_pos = len(lines)
            for other_project, other_pos in project_positions.items():
                if other_pos > project_pos and other_pos < next_pos:
                    next_pos = other_pos
            
            # Extract project section
            project_section = '\n'.join(lines[project_pos:next_pos])
            
            # Verify all impacts from this project appear in this section
            for impact in project_impacts:
                self.assertIn(impact['file'], project_section,
                            f"Impact from project '{project_name}' should appear in its section")


class TestProperty19_ImpactEntryCompleteness(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 19: Impact Entry Completeness**
    
    For any impact entry, the display should include type, file, line, snippet, and detail fields.
    
    **Validates: Requirements 5.3**
    """
    
    @given(mixed_impact_list())
    @settings(max_examples=100, deadline=None)
    def test_impact_entries_contain_all_fields(self, impacts):
        """Property: Every impact entry contains all required fields in display."""
        if not impacts:
            return
        
        # Format the impacts
        formatted = format_cross_project_impacts(impacts)
        
        # Verify each impact's key information appears in formatted output
        for impact in impacts:
            # File path should appear
            self.assertIn(impact['file'], formatted,
                         f"Impact file '{impact['file']}' should appear in formatted output")
            
            # Line number should appear
            self.assertIn(str(impact['line']), formatted,
                         f"Impact line number {impact['line']} should appear in formatted output")
            
            # Snippet should appear
            self.assertIn(impact['snippet'], formatted,
                         f"Impact snippet should appear in formatted output")
            
            # Detail should appear
            self.assertIn(impact['detail'], formatted,
                         f"Impact detail should appear in formatted output")
            
            # For API calls, API endpoint should appear
            if impact['type'] == 'api_call' and 'api' in impact:
                self.assertIn(impact['api'], formatted,
                             f"API endpoint '{impact['api']}' should appear in formatted output")
    
    @given(class_reference_impact())
    @settings(max_examples=50, deadline=None)
    def test_class_reference_has_required_fields(self, impact):
        """Property: Class reference impacts have all required fields."""
        # Verify impact has all required fields
        required_fields = ['project', 'type', 'file', 'line', 'snippet', 'detail']
        for field in required_fields:
            self.assertIn(field, impact,
                         f"Class reference impact must have '{field}' field")
        
        # Verify type is correct
        self.assertEqual(impact['type'], 'class_reference',
                        "Type should be 'class_reference'")
    
    @given(api_call_impact())
    @settings(max_examples=50, deadline=None)
    def test_api_call_has_required_fields(self, impact):
        """Property: API call impacts have all required fields including 'api'."""
        # Verify impact has all required fields
        required_fields = ['project', 'type', 'file', 'line', 'snippet', 'detail', 'api']
        for field in required_fields:
            self.assertIn(field, impact,
                         f"API call impact must have '{field}' field")
        
        # Verify type is correct
        self.assertEqual(impact['type'], 'api_call',
                        "Type should be 'api_call'")


class TestProperty20_MainProjectVsCrossProjectDistinction(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 20: Main Project vs Cross-Project Distinction**
    
    For any analysis report, main project impacts and cross-project impacts should be
    clearly distinguished.
    
    **Validates: Requirements 5.5**
    """
    
    @given(mixed_impact_list())
    @settings(max_examples=100, deadline=None)
    def test_cross_project_section_clearly_labeled(self, impacts):
        """Property: Cross-project impacts are clearly labeled and distinguished."""
        if not impacts:
            return
        
        # Format the impacts
        formatted = format_cross_project_impacts(impacts)
        
        # Verify clear section header
        self.assertIn("跨项目影响分析结果", formatted,
                     "Cross-project section should have clear header")
        
        # Verify section separator
        self.assertIn("=" * 80, formatted,
                     "Cross-project section should have visual separator")
        
        # Verify project labels
        project_names = set(impact['project'] for impact in impacts)
        for project_name in project_names:
            self.assertIn(f"【项目】{project_name}", formatted,
                         f"Project '{project_name}' should be clearly labeled")
    
    def test_cross_project_formatting_distinguishes_from_main(self):
        """Property: Cross-project formatting is visually distinct."""
        # Create sample impacts
        impacts = [
            {
                'project': 'related-service-1',
                'type': 'class_reference',
                'file': 'src/main/java/com/example/Service.java',
                'line': 42,
                'snippet': 'import com.main.UserService;',
                'detail': 'References UserService class'
            },
            {
                'project': 'related-service-2',
                'type': 'api_call',
                'file': 'src/main/java/com/example/Controller.java',
                'line': 100,
                'snippet': 'restTemplate.getForObject("/api/user", User.class);',
                'detail': 'Calls user API',
                'api': 'GET /api/user'
            }
        ]
        
        formatted = format_cross_project_impacts(impacts)
        
        # Verify visual distinction
        self.assertIn("【项目】", formatted,
                     "Should use special markers for project names")
        self.assertIn("▶", formatted,
                     "Should use visual indicators for impact types")
        self.assertIn("-" * 80, formatted,
                     "Should use separators between projects")


if __name__ == '__main__':
    unittest.main()
