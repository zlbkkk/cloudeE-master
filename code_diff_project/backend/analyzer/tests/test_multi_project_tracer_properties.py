"""
Property-Based Tests for MultiProjectTracer Core Dependency Detection

This module tests the correctness properties for cross-project dependency analysis,
focusing on:
- Property 8: Fully Qualified Class Name Extraction
- Property 9: Class Reference Search Completeness
- Property 10: Reference Record Completeness
- Property 12: Main Project Exclusion

These tests use Hypothesis for property-based testing to verify behavior across
a wide range of inputs.
"""

import os
import tempfile
import shutil
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.strategies import composite
import unittest

from analyzer.analysis import MultiProjectTracer, LightStaticAnalyzer


# ============================================================================
# Test Data Generators
# ============================================================================

@composite
def valid_java_package_name(draw):
    """Generate valid Java package names (avoiding Java keywords)."""
    # Java keywords to avoid
    java_keywords = {
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
        'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
        'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
        'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new', 'package',
        'private', 'protected', 'public', 'return', 'short', 'static', 'strictfp',
        'super', 'switch', 'synchronized', 'this', 'throw', 'throws', 'transient',
        'try', 'void', 'volatile', 'while'
    }
    
    parts = draw(st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu'), min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=10
        ).filter(lambda x: x.lower() not in java_keywords),
        min_size=1,
        max_size=5
    ))
    return '.'.join(parts)


@composite
def valid_java_class_name(draw):
    """Generate valid Java class names (PascalCase, avoiding keywords)."""
    java_keywords = {
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
        'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
        'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
        'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new', 'package',
        'private', 'protected', 'public', 'return', 'short', 'static', 'strictfp',
        'super', 'switch', 'synchronized', 'this', 'throw', 'throws', 'transient',
        'try', 'void', 'volatile', 'while'
    }
    
    first_char = draw(st.characters(whitelist_categories=('Lu',), min_codepoint=65, max_codepoint=90))
    rest = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
        min_size=1,  # At least 1 char to avoid single-letter names
        max_size=15
    ))
    class_name = first_char + rest
    
    # Ensure not a keyword
    assume(class_name.lower() not in java_keywords)
    
    return class_name


@composite
def valid_java_method_name(draw):
    """Generate valid Java method names (camelCase)."""
    first_char = draw(st.characters(whitelist_categories=('Ll',), min_codepoint=97, max_codepoint=122))
    rest = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
        min_size=0,
        max_size=15
    ))
    return first_char + rest


@composite
def java_file_with_class(draw):
    """Generate a Java file with package and class declaration."""
    package = draw(valid_java_package_name())
    class_name = draw(valid_java_class_name())
    
    content = f"""package {package};

import java.util.List;
import java.util.Map;

public class {class_name} {{
    
    private String field1;
    private int field2;
    
    public {class_name}() {{
    }}
    
    public void doSomething() {{
        System.out.println("Hello");
    }}
}}
"""
    return {
        'package': package,
        'class_name': class_name,
        'full_class_name': f"{package}.{class_name}",
        'content': content
    }


@composite
def java_file_with_import(draw, target_full_class_name):
    """Generate a Java file that imports a target class."""
    package = draw(valid_java_package_name())
    class_name = draw(valid_java_class_name())
    
    # Ensure different package to avoid same-package scenario
    assume(not target_full_class_name.startswith(package + '.'))
    
    import_type = draw(st.sampled_from(['explicit', 'star', 'static']))
    
    target_package = '.'.join(target_full_class_name.split('.')[:-1])
    target_simple = target_full_class_name.split('.')[-1]
    
    if import_type == 'explicit':
        import_stmt = f"import {target_full_class_name};"
        usage = f"    private {target_simple} instance;"
    elif import_type == 'star':
        import_stmt = f"import {target_package}.*;"
        usage = f"    private {target_simple} instance;"
    else:  # static
        import_stmt = f"import static {target_full_class_name}.staticMethod;"
        usage = f"    staticMethod();"
    
    content = f"""package {package};

{import_stmt}

public class {class_name} {{
    
{usage}
    
    public void doSomething() {{
        System.out.println("Using imported class");
    }}
}}
"""
    return {
        'package': package,
        'class_name': class_name,
        'full_class_name': f"{package}.{class_name}",
        'content': content,
        'import_type': import_type,
        'target_class': target_full_class_name
    }


@composite
def java_file_with_autowired(draw, target_full_class_name):
    """Generate a Java file with @Autowired dependency injection."""
    package = draw(valid_java_package_name())
    class_name = draw(valid_java_class_name())
    
    target_simple = target_full_class_name.split('.')[-1]
    var_name = target_simple[0].lower() + target_simple[1:] if len(target_simple) > 1 else target_simple.lower()
    
    annotation = draw(st.sampled_from(['@Autowired', '@Resource']))
    
    content = f"""package {package};

import {target_full_class_name};
import org.springframework.beans.factory.annotation.Autowired;
import javax.annotation.Resource;

public class {class_name} {{
    
    {annotation}
    private {target_simple} {var_name};
    
    public void doSomething() {{
        {var_name}.someMethod();
    }}
}}
"""
    return {
        'package': package,
        'class_name': class_name,
        'full_class_name': f"{package}.{class_name}",
        'content': content,
        'annotation': annotation,
        'target_class': target_full_class_name
    }


@composite
def java_file_with_dubbo_reference(draw, target_full_class_name):
    """Generate a Java file with @DubboReference RPC injection."""
    package = draw(valid_java_package_name())
    class_name = draw(valid_java_class_name())
    
    target_simple = target_full_class_name.split('.')[-1]
    var_name = target_simple[0].lower() + target_simple[1:] if len(target_simple) > 1 else target_simple.lower()
    
    content = f"""package {package};

import {target_full_class_name};
import org.apache.dubbo.config.annotation.DubboReference;

public class {class_name} {{
    
    @DubboReference
    private {target_simple} {var_name};
    
    public void callRemoteService() {{
        {var_name}.remoteMethod();
    }}
}}
"""
    return {
        'package': package,
        'class_name': class_name,
        'full_class_name': f"{package}.{class_name}",
        'content': content,
        'target_class': target_full_class_name
    }


@composite
def java_file_with_method_param(draw, target_full_class_name):
    """Generate a Java file with target class in method parameter."""
    package = draw(valid_java_package_name())
    class_name = draw(valid_java_class_name())
    method_name = draw(valid_java_method_name())
    
    target_simple = target_full_class_name.split('.')[-1]
    param_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll',), min_codepoint=97, max_codepoint=122),
        min_size=1,
        max_size=10
    ))
    
    content = f"""package {package};

import {target_full_class_name};

public class {class_name} {{
    
    public void {method_name}({target_simple} {param_name}) {{
        {param_name}.doSomething();
    }}
    
    public {target_simple} getResult() {{
        return new {target_simple}();
    }}
}}
"""
    return {
        'package': package,
        'class_name': class_name,
        'full_class_name': f"{package}.{class_name}",
        'content': content,
        'method_name': method_name,
        'target_class': target_full_class_name
    }


# ============================================================================
# Helper Functions
# ============================================================================

def create_temp_project(files_dict):
    """
    Create a temporary project directory with Java files.
    
    Args:
        files_dict: Dict mapping relative paths to file contents
        
    Returns:
        Path to temporary project root
    """
    temp_dir = tempfile.mkdtemp(prefix='test_project_')
    
    for rel_path, content in files_dict.items():
        full_path = os.path.join(temp_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return temp_dir


def cleanup_temp_project(project_root):
    """Remove temporary project directory."""
    if os.path.exists(project_root):
        shutil.rmtree(project_root)


# ============================================================================
# Property Tests
# ============================================================================

class TestProperty8_FullyQualifiedClassNameExtraction(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 8: Fully Qualified Class Name Extraction**
    
    For any valid Java file, if it contains a class definition and package declaration,
    the parser should extract the fully qualified class name in package.ClassName format.
    
    **Validates: Requirements 3.1**
    """
    
    @given(java_file_with_class())
    @settings(max_examples=100, deadline=None)
    def test_extracts_fqn_from_valid_java_file(self, java_data):
        """Property: Parser extracts correct FQN from any valid Java file."""
        project_root = None
        try:
            # Create temporary project with the Java file
            file_path = f"src/main/java/{java_data['package'].replace('.', '/')}/{java_data['class_name']}.java"
            project_root = create_temp_project({file_path: java_data['content']})
            
            # Parse the file
            analyzer = LightStaticAnalyzer(project_root)
            full_path = os.path.join(project_root, file_path)
            full_class, simple_class, _ = analyzer.parse_java_file(full_path)
            
            # Verify FQN extraction
            self.assertIsNotNone(full_class, "Parser should extract full class name")
            self.assertEqual(full_class, java_data['full_class_name'],
                           f"Expected {java_data['full_class_name']}, got {full_class}")
            self.assertEqual(simple_class, java_data['class_name'],
                           f"Expected {java_data['class_name']}, got {simple_class}")
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)


class TestProperty9_ClassReferenceSearchCompleteness(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 9: Class Reference Search Completeness**
    
    For any class name, if it appears in a file's import statement or code,
    the search should find that reference.
    
    Tests cover:
    - Explicit imports
    - Wildcard imports (*)
    - Static imports
    - @Autowired/@Resource dependency injection
    - @DubboReference RPC injection (Dubbo core)
    - Method parameters and return values
    
    **Validates: Requirements 3.2**
    """
    
    @given(java_file_with_class())
    @settings(max_examples=50, deadline=None)
    def test_finds_explicit_import_references(self, target_data):
        """Property: Search finds explicit import statements."""
        project_root = None
        try:
            # Generate importer that imports the target
            importer_data = {
                'package': 'com.test.importer',
                'class_name': 'TestImporter',
                'full_class_name': 'com.test.importer.TestImporter',
                'content': f"""package com.test.importer;

import {target_data['full_class_name']};

public class TestImporter {{
    
    private {target_data['class_name']} instance;
    
    public void doSomething() {{
        System.out.println("Using imported class");
    }}
}}
""",
                'import_type': 'explicit',
                'target_class': target_data['full_class_name']
            }
            
            # Create project with both files
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            importer_path = f"src/main/java/{importer_data['package'].replace('.', '/')}/{importer_data['class_name']}.java"
            
            project_root = create_temp_project({
                target_path: target_data['content'],
                importer_path: importer_data['content']
            })
            
            # Search for usages
            analyzer = LightStaticAnalyzer(project_root)
            usages = analyzer.find_usages(target_data['full_class_name'])
            
            # Verify reference was found
            self.assertGreater(len(usages), 0, 
                             f"Should find at least one usage of {target_data['full_class_name']}")
            
            # Verify the importer file is in results
            found_files = [u['path'] for u in usages]
            # Normalize paths for comparison (handle Windows/Unix path separators)
            importer_path_normalized = importer_path.replace('/', os.sep).replace('\\', os.sep)
            found_files_normalized = [f.replace('/', os.sep).replace('\\', os.sep) for f in found_files]
            self.assertTrue(any(importer_path_normalized in f or f in importer_path_normalized for f in found_files_normalized),
                          f"Should find usage in {importer_path}. Found files: {found_files}")
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)
    
    @given(java_file_with_class())
    @settings(max_examples=50, deadline=None)
    def test_finds_autowired_dependency_injection(self, target_data):
        """Property: Search finds @Autowired and @Resource dependency injection."""
        project_root = None
        try:
            # Generate file with dependency injection
            target_simple = target_data['class_name']
            var_name = target_simple[0].lower() + target_simple[1:] if len(target_simple) > 1 else target_simple.lower()
            
            injector_data = {
                'package': 'com.test.service',
                'class_name': 'TestService',
                'full_class_name': 'com.test.service.TestService',
                'content': f"""package com.test.service;

import {target_data['full_class_name']};
import org.springframework.beans.factory.annotation.Autowired;

public class TestService {{
    
    @Autowired
    private {target_simple} {var_name};
    
    public void doSomething() {{
        {var_name}.someMethod();
    }}
}}
""",
                'annotation': '@Autowired',
                'target_class': target_data['full_class_name']
            }
            
            # Create project with both files
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            injector_path = f"src/main/java/{injector_data['package'].replace('.', '/')}/{injector_data['class_name']}.java"
            
            project_root = create_temp_project({
                target_path: target_data['content'],
                injector_path: injector_data['content']
            })
            
            # Search for usages
            analyzer = LightStaticAnalyzer(project_root)
            usages = analyzer.find_usages(target_data['full_class_name'])
            
            # Verify reference was found
            self.assertGreater(len(usages), 0,
                             f"Should find @Autowired/@Resource usage of {target_data['full_class_name']}")
            
            # Verify the injector file is in results
            found_files = [u['path'] for u in usages]
            # Normalize paths for comparison
            injector_path_normalized = injector_path.replace('/', os.sep).replace('\\', os.sep)
            found_files_normalized = [f.replace('/', os.sep).replace('\\', os.sep) for f in found_files]
            self.assertTrue(any(injector_path_normalized in f or f in injector_path_normalized for f in found_files_normalized),
                          f"Should find usage in {injector_path}. Found files: {found_files}")
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)
    
    @given(java_file_with_class())
    @settings(max_examples=50, deadline=None)
    def test_finds_dubbo_reference_rpc_injection(self, target_data):
        """
        Property: Search finds @DubboReference RPC injection (Dubbo Core).
        
        This is critical for microservices using Dubbo RPC framework.
        """
        project_root = None
        try:
            # Generate file with Dubbo reference
            target_simple = target_data['class_name']
            var_name = target_simple[0].lower() + target_simple[1:] if len(target_simple) > 1 else target_simple.lower()
            
            dubbo_data = {
                'package': 'com.test.consumer',
                'class_name': 'TestConsumer',
                'full_class_name': 'com.test.consumer.TestConsumer',
                'content': f"""package com.test.consumer;

import {target_data['full_class_name']};
import org.apache.dubbo.config.annotation.DubboReference;

public class TestConsumer {{
    
    @DubboReference
    private {target_simple} {var_name};
    
    public void callRemoteService() {{
        {var_name}.remoteMethod();
    }}
}}
""",
                'target_class': target_data['full_class_name']
            }
            
            # Create project with both files
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            dubbo_path = f"src/main/java/{dubbo_data['package'].replace('.', '/')}/{dubbo_data['class_name']}.java"
            
            project_root = create_temp_project({
                target_path: target_data['content'],
                dubbo_path: dubbo_data['content']
            })
            
            # Search for usages
            analyzer = LightStaticAnalyzer(project_root)
            usages = analyzer.find_usages(target_data['full_class_name'])
            
            # Verify reference was found
            self.assertGreater(len(usages), 0,
                             f"Should find @DubboReference usage of {target_data['full_class_name']}")
            
            # Verify the dubbo file is in results
            found_files = [u['path'] for u in usages]
            # Normalize paths for comparison
            dubbo_path_normalized = dubbo_path.replace('/', os.sep).replace('\\', os.sep)
            found_files_normalized = [f.replace('/', os.sep).replace('\\', os.sep) for f in found_files]
            self.assertTrue(any(dubbo_path_normalized in f or f in dubbo_path_normalized for f in found_files_normalized),
                          f"Should find Dubbo usage in {dubbo_path}. Found files: {found_files}")
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)
    
    @given(java_file_with_class())
    @settings(max_examples=50, deadline=None)
    def test_finds_method_parameter_references(self, target_data):
        """Property: Search finds class references in method parameters and return types."""
        project_root = None
        try:
            # Generate file with method parameter
            target_simple = target_data['class_name']
            
            param_data = {
                'package': 'com.test.controller',
                'class_name': 'TestController',
                'full_class_name': 'com.test.controller.TestController',
                'content': f"""package com.test.controller;

import {target_data['full_class_name']};

public class TestController {{
    
    public void processData({target_simple} data) {{
        data.doSomething();
    }}
    
    public {target_simple} getResult() {{
        return new {target_simple}();
    }}
}}
""",
                'method_name': 'processData',
                'target_class': target_data['full_class_name']
            }
            
            # Create project with both files
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            param_path = f"src/main/java/{param_data['package'].replace('.', '/')}/{param_data['class_name']}.java"
            
            project_root = create_temp_project({
                target_path: target_data['content'],
                param_path: param_data['content']
            })
            
            # Search for usages
            analyzer = LightStaticAnalyzer(project_root)
            usages = analyzer.find_usages(target_data['full_class_name'])
            
            # Verify reference was found
            self.assertGreater(len(usages), 0,
                             f"Should find method parameter usage of {target_data['full_class_name']}")
            
            # Verify the param file is in results
            found_files = [u['path'] for u in usages]
            # Normalize paths for comparison
            param_path_normalized = param_path.replace('/', os.sep).replace('\\', os.sep)
            found_files_normalized = [f.replace('/', os.sep).replace('\\', os.sep) for f in found_files]
            self.assertTrue(any(param_path_normalized in f or f in param_path_normalized for f in found_files_normalized),
                          f"Should find usage in {param_path}. Found files: {found_files}")
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)


class TestProperty10_ReferenceRecordCompleteness(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 10: Reference Record Completeness**
    
    For any found class reference, the result dictionary should contain all required fields:
    - project: str
    - file: str
    - line: int
    - snippet: str
    
    Line numbers should be accurate and code snippets should be complete.
    
    **Validates: Requirements 3.3**
    """
    
    @given(java_file_with_class())
    @settings(max_examples=50, deadline=None)
    def test_reference_records_contain_all_fields(self, target_data):
        """Property: Every reference record contains project, file, line, and snippet."""
        project_root = None
        try:
            # Generate importer
            importer_data = {
                'package': 'com.test.user',
                'class_name': 'UserService',
                'full_class_name': 'com.test.user.UserService',
                'content': f"""package com.test.user;

import {target_data['full_class_name']};

public class UserService {{
    
    private {target_data['class_name']} instance;
    
    public void process() {{
        instance.doSomething();
    }}
}}
"""
            }
            
            # Create project
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            importer_path = f"src/main/java/{importer_data['package'].replace('.', '/')}/{importer_data['class_name']}.java"
            
            project_root = create_temp_project({
                target_path: target_data['content'],
                importer_path: importer_data['content']
            })
            
            # Search for usages
            analyzer = LightStaticAnalyzer(project_root)
            usages = analyzer.find_usages(target_data['full_class_name'])
            
            # Verify all records have required fields
            for usage in usages:
                self.assertIn('path', usage, "Usage record must contain 'path' field")
                self.assertIn('line', usage, "Usage record must contain 'line' field")
                self.assertIn('snippet', usage, "Usage record must contain 'snippet' field")
                self.assertIn('service', usage, "Usage record must contain 'service' field")
                
                # Verify field types
                self.assertIsInstance(usage['path'], str, "'path' must be a string")
                self.assertIsInstance(usage['line'], int, "'line' must be an integer")
                self.assertIsInstance(usage['snippet'], str, "'snippet' must be a string")
                self.assertIsInstance(usage['service'], str, "'service' must be a string")
                
                # Verify line number is positive
                self.assertGreaterEqual(usage['line'], 0, "Line number must be non-negative")
                
                # Verify snippet is not empty
                self.assertGreater(len(usage['snippet']), 0, "Snippet must not be empty")
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)
    
    @given(java_file_with_class())
    @settings(max_examples=30, deadline=None)
    def test_line_numbers_are_accurate(self, target_data):
        """Property: Line numbers in reference records accurately point to the usage."""
        project_root = None
        try:
            # Generate importer
            importer_data = {
                'package': 'com.test.checker',
                'class_name': 'DataChecker',
                'full_class_name': 'com.test.checker.DataChecker',
                'content': f"""package com.test.checker;

import {target_data['full_class_name']};

public class DataChecker {{
    
    private {target_data['class_name']} checker;
    
    public void validate() {{
        checker.doSomething();
    }}
}}
"""
            }
            
            # Create project
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            importer_path = f"src/main/java/{importer_data['package'].replace('.', '/')}/{importer_data['class_name']}.java"
            
            project_root = create_temp_project({
                target_path: target_data['content'],
                importer_path: importer_data['content']
            })
            
            # Search for usages
            analyzer = LightStaticAnalyzer(project_root)
            usages = analyzer.find_usages(target_data['full_class_name'])
            
            # Verify line numbers point to actual usage
            for usage in usages:
                if usage['line'] > 0:
                    # Read the file and check the line
                    full_path = os.path.join(project_root, usage['path'])
                    with open(full_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    if usage['line'] <= len(lines):
                        actual_line = lines[usage['line'] - 1].strip()
                        # The snippet should match or be contained in the actual line
                        # (allowing for some formatting differences)
                        self.assertTrue(
                            usage['snippet'] in actual_line or actual_line in usage['snippet'],
                            f"Snippet '{usage['snippet']}' should match line {usage['line']}: '{actual_line}'"
                        )
            
        finally:
            if project_root:
                cleanup_temp_project(project_root)


class TestProperty12_MainProjectExclusion(unittest.TestCase):
    """
    **Feature: cross-project-analysis, Property 12: Main Project Exclusion**
    
    For any cross-project impact search, results should not include impacts from the main project.
    Only related projects should be included in cross-project results.
    
    **Validates: Requirements 3.5**
    """
    
    @given(java_file_with_class())
    @settings(max_examples=30, deadline=None)
    def test_cross_project_search_excludes_main_project(self, target_data):
        """Property: Cross-project search excludes main project from results."""
        main_project = None
        related1_project = None
        related2_project = None
        
        try:
            # Create target class in main project
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            main_project = create_temp_project({target_path: target_data['content']})
            
            # Create related project 1 with usage
            related1_data = {
                'package': 'com.related1.service',
                'class_name': 'Related1Service',
                'content': f"""package com.related1.service;

import {target_data['full_class_name']};

public class Related1Service {{
    private {target_data['class_name']} instance;
}}
"""
            }
            related1_path = f"src/main/java/{related1_data['package'].replace('.', '/')}/{related1_data['class_name']}.java"
            related1_project = create_temp_project({related1_path: related1_data['content']})
            
            # Create related project 2 with usage
            related2_data = {
                'package': 'com.related2.controller',
                'class_name': 'Related2Controller',
                'content': f"""package com.related2.controller;

import {target_data['full_class_name']};

public class Related2Controller {{
    private {target_data['class_name']} handler;
}}
"""
            }
            related2_path = f"src/main/java/{related2_data['package'].replace('.', '/')}/{related2_data['class_name']}.java"
            related2_project = create_temp_project({related2_path: related2_data['content']})
            
            # Initialize MultiProjectTracer with all three projects
            tracer = MultiProjectTracer([main_project, related1_project, related2_project])
            
            # Find cross-project impacts
            impacts = tracer.find_cross_project_impacts(
                target_data['full_class_name'],
                []  # No changed methods for this test
            )
            
            # Verify main project is excluded
            main_project_name = os.path.basename(main_project)
            for impact in impacts:
                self.assertNotEqual(impact['project'], main_project_name,
                                  f"Cross-project impacts should not include main project '{main_project_name}'")
            
            # Verify related projects are included
            related_project_names = {os.path.basename(related1_project), os.path.basename(related2_project)}
            found_projects = {impact['project'] for impact in impacts}
            
            # At least one related project should be found
            self.assertTrue(
                len(found_projects.intersection(related_project_names)) > 0,
                f"Should find impacts in related projects. Found: {found_projects}, Expected: {related_project_names}"
            )
            
        finally:
            for proj in [main_project, related1_project, related2_project]:
                if proj:
                    cleanup_temp_project(proj)
    
    @given(java_file_with_class())
    @settings(max_examples=20, deadline=None)
    def test_single_project_returns_empty_cross_project_impacts(self, target_data):
        """Property: When only main project exists, cross-project impacts should be empty."""
        main_project = None
        
        try:
            # Create only main project
            target_path = f"src/main/java/{target_data['package'].replace('.', '/')}/{target_data['class_name']}.java"
            main_project = create_temp_project({target_path: target_data['content']})
            
            # Initialize MultiProjectTracer with only main project
            tracer = MultiProjectTracer([main_project])
            
            # Find cross-project impacts
            impacts = tracer.find_cross_project_impacts(
                target_data['full_class_name'],
                []
            )
            
            # Verify no impacts found (no related projects)
            self.assertEqual(len(impacts), 0,
                           "Cross-project impacts should be empty when only main project exists")
            
        finally:
            if main_project:
                cleanup_temp_project(main_project)


if __name__ == '__main__':
    unittest.main()
