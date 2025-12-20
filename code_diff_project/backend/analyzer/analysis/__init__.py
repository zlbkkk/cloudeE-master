# analysis 模块
# 用于代码分析相关功能

from .utils import update_task_log, format_field
from .git_operations import get_git_diff, parse_diff
from .project_manager import clone_or_update_project
from .code_analyzer import (
    extract_changed_methods,
    extract_api_info,
    search_api_usages,
    get_project_structure,
    extract_controller_params
)
from .report_generator import (
    save_to_db,
    refine_report_with_static_analysis,
    print_code_comparison
)
from .ai_analyzer import analyze_with_llm, call_deepseek_api
from .api_tracer import ApiUsageTracer, ProjectStructureBuilder
from .multi_project_tracer import MultiProjectTracer
from .mybatis_analyzer import MybatisAnalyzer
from .static_parser import LightStaticAnalyzer

__all__ = [
    'update_task_log',
    'format_field',
    'get_git_diff',
    'parse_diff',
    'clone_or_update_project',
    'extract_changed_methods',
    'extract_api_info',
    'search_api_usages',
    'get_project_structure',
    'extract_controller_params',
    'save_to_db',
    'refine_report_with_static_analysis',
    'print_code_comparison',
    'analyze_with_llm',
    'call_deepseek_api',
    'ApiUsageTracer',
    'ProjectStructureBuilder',
    'MultiProjectTracer',
    'MybatisAnalyzer',
    'LightStaticAnalyzer',
]
