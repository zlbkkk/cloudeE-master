"""
测试用例模板生成器

基于前端API调用信息生成标准化的测试用例模板，提供详细的测试指导。
不使用复杂的AST解析，而是基于已有的API信息（路径、方法、组件）生成测试步骤。
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from loguru import logger


@dataclass
class TestStep:
    """测试步骤"""
    step_number: int         # 步骤编号
    step_type: str           # 步骤类型：'navigate', 'locate', 'action', 'verify_api', 'verify_ui'
    description: str         # 步骤描述
    details: Dict[str, Any]  # 详细信息


@dataclass
class TestData:
    """测试数据"""
    data_type: str           # 数据类型：'normal', 'boundary', 'invalid'
    description: str         # 数据描述
    example: Any             # 示例值
    expected_result: str     # 预期结果


@dataclass
class VerificationPoint:
    """验证点"""
    category: str            # 类别：'api_response', 'ui_state', 'data_format'
    description: str         # 验证描述
    expected: str            # 预期结果


@dataclass
class TestCase:
    """测试用例"""
    test_id: str                          # 测试用例ID
    title: str                            # 测试标题
    priority: str                         # 优先级：'P0', 'P1', 'P2'
    test_type: str                        # 测试类型：'UI', 'API', 'Integration'
    api_info: Dict[str, str]              # API信息（method, path）
    component_info: Dict[str, str]        # 组件信息（name, file_path, line_number）
    steps: List[TestStep]                 # 测试步骤列表
    test_data: List[TestData]             # 测试数据列表
    verification_points: List[VerificationPoint]  # 验证点列表
    preconditions: Optional[str] = None   # 前置条件
    notes: Optional[str] = None           # 备注
    # 新增字段：端信息（可选，向后兼容）
    company_type: Optional[str] = None    # 端类型：'SPY', 'CPT', 'CE'
    company_type_name: Optional[str] = None  # 端名称：'供应商端', '资金方端', '核心企业端'


class TestCaseGenerator:
    """测试用例生成器"""
    
    def __init__(self, project_path: Optional[str] = None):
        """
        初始化生成器
        
        Args:
            project_path: 项目根路径（可选，用于查找菜单配置文件）
        """
        self.test_case_counter = 0
        
        # 核心业务关键词（用于判断API重要性）
        self.core_business_keywords = [
            'order', 'payment', 'transaction', 'invoice', 'finance',
            '订单', '支付', '交易', '发票', '财务', '融资',
            'user', 'login', 'auth', 'register',
            '用户', '登录', '认证', '注册'
        ]
        
        # 次要业务关键词
        self.secondary_keywords = [
            'list', 'query', 'search', 'detail', 'info',
            '列表', '查询', '搜索', '详情', '信息'
        ]
        
        # 菜单配置文件解析结果缓存
        self._route_to_company_types: Dict[str, List[str]] = {}
        self._route_menu_to_company_type: Dict[tuple, str] = {}  # {(route, menu_name): company_type}
        
        # 如果提供了项目路径，尝试加载菜单配置
        if project_path:
            self._load_menu_config(project_path)
    
    def _determine_priority_and_type(self, 
                                    has_frontend_call: bool,
                                    api_method: str,
                                    api_path: str,
                                    call_count: int = 1,
                                    is_core_business: bool = False,
                                    menu_path: str = None) -> tuple:
        """
        确定测试优先级和类型
        
        优先级分级规则：
        - P0（必测）：被前端调用的核心业务写操作（如订单提交、支付、登录等）
        - P1（重要）：被前端调用的核心业务查询、被前端调用的高频API、未被前端调用的核心业务写操作
        - P2（可选）：未被前端调用的次要API
        
        测试类型分类：
        - UI测试：需要前端交互的测试（被前端调用）
        - 接口测试：可以直接调用API的测试（未被前端调用）
        - 集成测试：涉及多个API或复杂业务流程的测试
        
        Args:
            has_frontend_call: 是否被前端调用
            api_method: HTTP方法
            api_path: API路径
            call_count: 被调用次数
            is_core_business: 是否为核心业务
            menu_path: 菜单路径
            
        Returns:
            (priority, test_type) 元组
        """
        # 1. 判断是否为核心业务API
        is_core = is_core_business or self._is_core_business_api(api_path, menu_path)
        
        # 2. 判断是否为写操作（POST/PUT/DELETE比GET更重要）
        is_write_operation = api_method.upper() in ['POST', 'PUT', 'PATCH', 'DELETE']
        
        # 3. 判断是否被多次调用（高频API更重要）
        is_high_frequency = call_count > 3
        
        # 4. 确定优先级
        if has_frontend_call:
            # 被前端调用的API
            if is_core and is_write_operation:
                # 核心业务的写操作 -> P0（最高优先级）
                priority = 'P0'
            elif is_high_frequency:
                # 高频调用 -> P0
                priority = 'P0'
            else:
                # 普通查询或次要业务 -> P1
                priority = 'P1'
        else:
            # 未被前端调用的API
            if is_core and is_write_operation:
                priority = 'P1'  # 核心业务的写操作 -> P1
            else:
                priority = 'P2'  # 其他 -> P2
        
        # 5. 确定测试类型
        if has_frontend_call:
            # 被前端调用 -> UI测试
            if is_write_operation and is_core:
                test_type = 'Integration'  # 核心写操作可能涉及多个步骤 -> 集成测试
            else:
                test_type = 'UI'
        else:
            # 未被前端调用 -> 接口测试
            test_type = 'API'
        
        logger.debug(f"API {api_method} {api_path} - 优先级: {priority}, 类型: {test_type}, "
                    f"核心业务: {is_core}, 写操作: {is_write_operation}, 高频: {is_high_frequency}")
        
        return priority, test_type
    
    def _is_core_business_api(self, api_path: str, menu_path: str = None) -> bool:
        """
        判断是否为核心业务API
        
        Args:
            api_path: API路径
            menu_path: 菜单路径
            
        Returns:
            是否为核心业务
        """
        # 转换为小写便于匹配
        path_lower = api_path.lower()
        menu_lower = menu_path.lower() if menu_path else ''
        
        # 检查核心业务关键词
        for keyword in self.core_business_keywords:
            if keyword.lower() in path_lower or keyword.lower() in menu_lower:
                return True
        
        return False
    
    def generate_test_case(self, 
                          api_method: str, 
                          api_path: str,
                          component_name: str,
                          file_path: str,
                          line_number: int,
                          call_type: str = 'axios',
                          has_frontend_call: bool = True,
                          trigger_element: str = None,
                          trigger_text: str = None,
                          page_route: str = None,
                          menu_path: str = None,
                          call_count: int = 1,
                          is_core_business: bool = False,
                          company_type: Optional[str] = None,
                          company_type_name: Optional[str] = None) -> TestCase:
        """
        生成测试用例
        
        Args:
            api_method: HTTP方法（GET, POST, PUT, DELETE）
            api_path: API路径
            component_name: 组件名称
            file_path: 文件路径
            line_number: 行号
            call_type: 调用类型（axios, fetch, custom-xxx）
            has_frontend_call: 是否被前端调用
            trigger_element: 触发元素类型（button, link, form）
            trigger_text: 触发元素文本
            page_route: 页面路由
            menu_path: 菜单路径
            call_count: API被调用次数（用于判断重要性）
            is_core_business: 是否为核心业务API
            company_type: 端类型（可选，如未提供则自动识别）
            company_type_name: 端名称（可选，如未提供则自动生成）
            
        Returns:
            TestCase对象
        """
        self.test_case_counter += 1
        
        # 如果未提供端信息，尝试自动识别
        if not company_type and page_route:
            company_types = self._identify_company_type(page_route, menu_path)
            if company_types:
                # 如果识别到多个端，默认使用第一个（批量生成时会为每个端生成测试用例）
                company_type = company_types[0]
                company_type_name = self._get_company_type_name(company_type)
                logger.debug(f"[测试用例生成] 自动识别端类型: {page_route} -> {company_type}")
        
        # 如果提供了 company_type 但没有 company_type_name，自动生成
        if company_type and not company_type_name:
            company_type_name = self._get_company_type_name(company_type)
        
        # 确定优先级和测试类型（使用增强的分级逻辑）
        priority, test_type = self._determine_priority_and_type(
            has_frontend_call=has_frontend_call,
            api_method=api_method,
            api_path=api_path,
            call_count=call_count,
            is_core_business=is_core_business,
            menu_path=menu_path
        )
        
        # 根据HTTP方法选择对应的模板生成器
        if api_method.upper() == 'GET':
            return self._generate_get_test_case(
                api_method, api_path, component_name, file_path, 
                line_number, call_type, priority, test_type,
                trigger_element, trigger_text, page_route, menu_path,
                company_type, company_type_name
            )
        elif api_method.upper() == 'POST':
            return self._generate_post_test_case(
                api_method, api_path, component_name, file_path, 
                line_number, call_type, priority, test_type,
                trigger_element, trigger_text, page_route, menu_path,
                company_type, company_type_name
            )
        elif api_method.upper() in ['PUT', 'PATCH']:
            return self._generate_put_test_case(
                api_method, api_path, component_name, file_path, 
                line_number, call_type, priority, test_type,
                trigger_element, trigger_text, page_route, menu_path,
                company_type, company_type_name
            )
        elif api_method.upper() == 'DELETE':
            return self._generate_delete_test_case(
                api_method, api_path, component_name, file_path, 
                line_number, call_type, priority, test_type,
                trigger_element, trigger_text, page_route, menu_path,
                company_type, company_type_name
            )
        else:
            # 默认生成通用测试用例
            return self._generate_generic_test_case(
                api_method, api_path, component_name, file_path, 
                line_number, call_type, priority, test_type,
                trigger_element, trigger_text, page_route, menu_path,
                company_type, company_type_name
            )
    
    def _generate_get_test_case(self, api_method: str, api_path: str, 
                               component_name: str, file_path: str,
                               line_number: int, call_type: str,
                               priority: str, test_type: str,
                               trigger_element: str, trigger_text: str,
                               page_route: str, menu_path: str,
                               company_type: Optional[str] = None,
                               company_type_name: Optional[str] = None) -> TestCase:
        """生成GET请求测试用例（查询/列表页面）"""
        
        test_id = f"TC_{self.test_case_counter:04d}"
        
        # 构建更友好的测试标题（支持端信息）
        if trigger_text:
            base_title = f"测试{component_name}组件的'{trigger_text}'功能"
        else:
            base_title = f"测试{component_name}组件的数据查询功能"
        
        title = self._build_title_with_company_type(
            base_title, company_type_name, menu_path, trigger_text
        )
        
        # 构建访问路径描述
        access_path = self._build_access_path(menu_path, page_route, trigger_element, trigger_text)
        
        # 生成测试步骤
        steps = [
            TestStep(
                step_number=1,
                step_type='navigate',
                description=f"访问页面",
                details={
                    'component': component_name,
                    'file': file_path,
                    'page_route': page_route or '（需手动确认页面路径）',
                    'menu_path': menu_path or '（需手动确认菜单路径）',
                    'company_type': company_type,
                    'company_type_name': company_type_name,
                    'access_instruction': access_path,
                    'action': f'使用{company_type_name}账号登录系统，通过"{menu_path or "对应菜单"}"菜单访问页面' if company_type_name else '打开浏览器，按照访问路径导航到目标页面'
                }
            ),
            TestStep(
                step_number=2,
                step_type='locate',
                description="定位触发查询的元素",
                details={
                    'element_type': trigger_element or '按钮/链接/搜索框',
                    'element_text': trigger_text or '（需手动确认触发元素）',
                    'action': f"找到'{trigger_text}'元素" if trigger_text else '找到触发API调用的UI元素'
                }
            ),
            TestStep(
                step_number=3,
                step_type='action',
                description="执行查询操作",
                details={
                    'actions': [f"点击'{trigger_text}'" if trigger_text else '点击查询按钮', '输入搜索条件（如需要）', '选择筛选项（如需要）'],
                    'note': '根据实际UI交互方式选择'
                }
            ),
            TestStep(
                step_number=4,
                step_type='verify_api',
                description=f"验证API调用：{api_method} {api_path}",
                details={
                    'method': api_method,
                    'path': api_path,
                    'call_type': call_type,
                    'line': line_number
                }
            ),
            TestStep(
                step_number=5,
                step_type='verify_ui',
                description="验证UI数据展示",
                details={
                    'checks': [
                        '数据列表正确渲染',
                        '数据内容与API响应一致',
                        '加载状态正确显示',
                        '空数据状态处理正确'
                    ]
                }
            )
        ]
        
        # 生成测试数据
        test_data = [
            TestData(
                data_type='normal',
                description='正常查询参数',
                example={'page': 1, 'pageSize': 10},
                expected_result='返回符合条件的数据列表'
            ),
            TestData(
                data_type='boundary',
                description='边界值测试',
                example={'page': 1, 'pageSize': 100},
                expected_result='返回最大允许数量的数据'
            ),
            TestData(
                data_type='boundary',
                description='空结果测试',
                example={'keyword': '不存在的关键词'},
                expected_result='返回空列表，UI显示"暂无数据"'
            ),
            TestData(
                data_type='invalid',
                description='无效参数测试',
                example={'page': -1, 'pageSize': 0},
                expected_result='返回400错误或使用默认参数'
            )
        ]
        
        # 生成验证点
        verification_points = [
            VerificationPoint(
                category='api_response',
                description='HTTP状态码验证',
                expected='200 OK'
            ),
            VerificationPoint(
                category='api_response',
                description='响应数据格式验证',
                expected='JSON格式，包含data、total、page等字段'
            ),
            VerificationPoint(
                category='ui_state',
                description='加载状态验证',
                expected='查询时显示loading，完成后隐藏'
            ),
            VerificationPoint(
                category='ui_state',
                description='数据展示验证',
                expected='数据正确渲染到列表/表格中'
            ),
            VerificationPoint(
                category='ui_state',
                description='空数据处理验证',
                expected='无数据时显示友好提示'
            )
        ]
        
        return TestCase(
            test_id=test_id,
            title=title,
            priority=priority,
            test_type=test_type,
            api_info={'method': api_method, 'path': api_path},
            component_info={
                'name': component_name,
                'file_path': file_path,
                'line_number': str(line_number),
                'call_type': call_type
            },
            steps=steps,
            test_data=test_data,
            verification_points=verification_points,
            preconditions=f'使用{company_type_name}账号登录系统（如需要）' if company_type_name else '用户已登录系统（如需要）',
            notes=f'该测试用例基于{file_path}第{line_number}行的API调用生成',
            company_type=company_type,
            company_type_name=company_type_name
        )

    
    def _generate_post_test_case(self, api_method: str, api_path: str,
                                component_name: str, file_path: str,
                                line_number: int, call_type: str,
                                priority: str, test_type: str,
                                trigger_element: str, trigger_text: str,
                                page_route: str, menu_path: str,
                                company_type: Optional[str] = None,
                                company_type_name: Optional[str] = None) -> TestCase:
        """生成POST请求测试用例（创建/提交表单）"""
        
        test_id = f"TC_{self.test_case_counter:04d}"
        
        # 构建更友好的测试标题（支持端信息）
        if trigger_text:
            base_title = f"测试{component_name}组件的'{trigger_text}'功能"
        else:
            base_title = f"测试{component_name}组件的数据提交功能"
        
        title = self._build_title_with_company_type(
            base_title, company_type_name, menu_path, trigger_text
        )
        
        # 构建访问路径描述
        access_path = self._build_access_path(menu_path, page_route, trigger_element, trigger_text)
        
        # 构建访问路径描述
        access_path = self._build_access_path(menu_path, page_route, trigger_element, trigger_text)
        
        # 生成测试步骤
        steps = [
            TestStep(
                step_number=1,
                step_type='navigate',
                description=f"访问页面",
                details={
                    'component': component_name,
                    'file': file_path,
                    'page_route': page_route or '（需手动确认页面路径）',
                    'menu_path': menu_path or '（需手动确认菜单路径）',
                    'access_instruction': access_path,
                    'action': '打开浏览器，按照访问路径导航到目标页面'
                }
            ),
            TestStep(
                step_number=2,
                step_type='locate',
                description="定位表单元素",
                details={
                    'element_types': ['输入框', '下拉框', '单选框', '复选框', '文件上传'],
                    'trigger_element': trigger_element or '表单',
                    'trigger_text': trigger_text or '（需手动确认触发元素）',
                    'action': '找到所有需要填写的表单字段'
                }
            ),
            TestStep(
                step_number=3,
                step_type='action',
                description="填写表单数据",
                details={
                    'actions': [
                        '填写必填字段',
                        '填写可选字段',
                        '选择下拉选项',
                        '上传文件（如需要）'
                    ],
                    'note': '使用测试数据表中的数据'
                }
            ),
            TestStep(
                step_number=4,
                step_type='action',
                description="提交表单",
                details={
                    'actions': ['点击提交按钮', '触发表单提交事件'],
                    'note': '确保表单验证通过'
                }
            ),
            TestStep(
                step_number=5,
                step_type='verify_api',
                description=f"验证API调用：{api_method} {api_path}",
                details={
                    'method': api_method,
                    'path': api_path,
                    'call_type': call_type,
                    'line': line_number,
                    'check_payload': '验证请求体包含正确的表单数据'
                }
            ),
            TestStep(
                step_number=6,
                step_type='verify_ui',
                description="验证UI反馈",
                details={
                    'checks': [
                        '显示成功提示消息',
                        '表单重置或跳转到列表页',
                        '提交按钮状态变化（禁用→启用）',
                        '错误时显示错误提示'
                    ]
                }
            )
        ]
        
        # 生成测试数据
        test_data = [
            TestData(
                data_type='normal',
                description='正常提交数据',
                example={
                    'name': '测试名称',
                    'description': '测试描述',
                    'status': 'active'
                },
                expected_result='提交成功，返回201或200状态码'
            ),
            TestData(
                data_type='boundary',
                description='最小必填字段',
                example={'name': '最小数据'},
                expected_result='只填写必填字段也能成功提交'
            ),
            TestData(
                data_type='boundary',
                description='最大长度测试',
                example={'name': 'A' * 255, 'description': 'B' * 1000},
                expected_result='接受最大长度的输入'
            ),
            TestData(
                data_type='invalid',
                description='缺少必填字段',
                example={'description': '缺少name字段'},
                expected_result='返回400错误，提示必填字段缺失'
            ),
            TestData(
                data_type='invalid',
                description='数据格式错误',
                example={'name': 123, 'email': 'invalid-email'},
                expected_result='返回400错误，提示数据格式不正确'
            )
        ]
        
        # 生成验证点
        verification_points = [
            VerificationPoint(
                category='api_response',
                description='HTTP状态码验证',
                expected='201 Created 或 200 OK'
            ),
            VerificationPoint(
                category='api_response',
                description='响应数据验证',
                expected='返回创建的资源ID或完整对象'
            ),
            VerificationPoint(
                category='api_response',
                description='请求体验证',
                expected='请求体包含所有表单字段，格式正确'
            ),
            VerificationPoint(
                category='ui_state',
                description='提交状态验证',
                expected='提交时按钮禁用，显示loading'
            ),
            VerificationPoint(
                category='ui_state',
                description='成功反馈验证',
                expected='显示成功提示，表单重置或跳转'
            ),
            VerificationPoint(
                category='ui_state',
                description='错误处理验证',
                expected='失败时显示错误信息，表单保持填写状态'
            )
        ]
        
        return TestCase(
            test_id=test_id,
            title=title,
            priority=priority,
            test_type=test_type,
            api_info={'method': api_method, 'path': api_path},
            component_info={
                'name': component_name,
                'file_path': file_path,
                'line_number': str(line_number),
                'call_type': call_type
            },
            steps=steps,
            test_data=test_data,
            verification_points=verification_points,
            preconditions=f'使用{company_type_name}账号登录系统，具有创建权限' if company_type_name else '用户已登录系统，具有创建权限',
            company_type=company_type,
            company_type_name=company_type_name,
            notes=f'该测试用例基于{file_path}第{line_number}行的API调用生成'
        )
    
    def _generate_put_test_case(self, api_method: str, api_path: str,
                               component_name: str, file_path: str,
                               line_number: int, call_type: str,
                               priority: str, test_type: str,
                               trigger_element: str, trigger_text: str,
                               page_route: str, menu_path: str,
                               company_type: Optional[str] = None,
                               company_type_name: Optional[str] = None) -> TestCase:
        """生成PUT/PATCH请求测试用例（更新操作）"""
        
        test_id = f"TC_{self.test_case_counter:04d}"
        
        # 构建更友好的测试标题（支持端信息）
        if trigger_text:
            base_title = f"测试{component_name}组件的'{trigger_text}'功能"
        else:
            base_title = f"测试{component_name}组件的数据更新功能"
        
        title = self._build_title_with_company_type(
            base_title, company_type_name, menu_path, trigger_text
        )
        
        # 构建访问路径描述
        access_path = self._build_access_path(menu_path, page_route, trigger_element, trigger_text)
        
        # 生成测试步骤
        steps = [
            TestStep(
                step_number=1,
                step_type='navigate',
                description=f"访问包含{component_name}组件的页面",
                details={
                    'component': component_name,
                    'file': file_path,
                    'action': '打开浏览器，导航到编辑页面'
                }
            ),
            TestStep(
                step_number=2,
                step_type='locate',
                description="定位目标数据",
                details={
                    'actions': [
                        '从列表中选择要编辑的数据',
                        '点击编辑按钮',
                        '进入编辑表单'
                    ],
                    'note': '确保表单已加载现有数据'
                }
            ),
            TestStep(
                step_number=3,
                step_type='action',
                description="修改表单数据",
                details={
                    'actions': [
                        '修改需要更新的字段',
                        '保持其他字段不变',
                        '验证修改后的数据'
                    ],
                    'note': '使用测试数据表中的数据'
                }
            ),
            TestStep(
                step_number=4,
                step_type='action',
                description="提交更新",
                details={
                    'actions': ['点击保存/更新按钮'],
                    'note': '确保表单验证通过'
                }
            ),
            TestStep(
                step_number=5,
                step_type='verify_api',
                description=f"验证API调用：{api_method} {api_path}",
                details={
                    'method': api_method,
                    'path': api_path,
                    'call_type': call_type,
                    'line': line_number,
                    'check_payload': '验证请求体包含更新的字段'
                }
            ),
            TestStep(
                step_number=6,
                step_type='verify_ui',
                description="验证更新结果",
                details={
                    'checks': [
                        '显示更新成功提示',
                        '返回列表页或详情页',
                        '数据已更新为新值',
                        '未修改的字段保持不变'
                    ]
                }
            )
        ]
        
        # 生成测试数据
        test_data = [
            TestData(
                data_type='normal',
                description='正常更新数据',
                example={
                    'id': 1,
                    'name': '更新后的名称',
                    'status': 'inactive'
                },
                expected_result='更新成功，返回200状态码'
            ),
            TestData(
                data_type='boundary',
                description='只更新单个字段',
                example={'id': 1, 'status': 'active'},
                expected_result='只更新指定字段，其他字段不变'
            ),
            TestData(
                data_type='invalid',
                description='更新不存在的资源',
                example={'id': 99999, 'name': '测试'},
                expected_result='返回404错误'
            ),
            TestData(
                data_type='invalid',
                description='无效的更新数据',
                example={'id': 1, 'name': ''},
                expected_result='返回400错误，提示数据验证失败'
            )
        ]
        
        # 生成验证点
        verification_points = [
            VerificationPoint(
                category='api_response',
                description='HTTP状态码验证',
                expected='200 OK'
            ),
            VerificationPoint(
                category='api_response',
                description='响应数据验证',
                expected='返回更新后的完整对象'
            ),
            VerificationPoint(
                category='ui_state',
                description='更新状态验证',
                expected='更新时显示loading状态'
            ),
            VerificationPoint(
                category='ui_state',
                description='成功反馈验证',
                expected='显示更新成功提示'
            ),
            VerificationPoint(
                category='data_format',
                description='数据一致性验证',
                expected='更新后的数据与提交的数据一致'
            )
        ]
        
        return TestCase(
            test_id=test_id,
            title=title,
            priority=priority,
            test_type=test_type,
            api_info={'method': api_method, 'path': api_path},
            component_info={
                'name': component_name,
                'file_path': file_path,
                'line_number': str(line_number),
                'call_type': call_type
            },
            steps=steps,
            test_data=test_data,
            verification_points=verification_points,
            preconditions=f'使用{company_type_name}账号登录系统，具有更新权限，目标数据已存在' if company_type_name else '用户已登录系统，具有更新权限，目标数据已存在',
            company_type=company_type,
            company_type_name=company_type_name,
            notes=f'该测试用例基于{file_path}第{line_number}行的API调用生成'
        )
    
    def _generate_delete_test_case(self, api_method: str, api_path: str,
                                  component_name: str, file_path: str,
                                  line_number: int, call_type: str,
                                  priority: str, test_type: str,
                                  trigger_element: str, trigger_text: str,
                                  page_route: str, menu_path: str,
                                  company_type: Optional[str] = None,
                                  company_type_name: Optional[str] = None) -> TestCase:
        """生成DELETE请求测试用例（删除操作）"""
        
        test_id = f"TC_{self.test_case_counter:04d}"
        
        # 构建更友好的测试标题（支持端信息）
        if trigger_text:
            base_title = f"测试{component_name}组件的'{trigger_text}'功能"
        else:
            base_title = f"测试{component_name}组件的数据删除功能"
        
        title = self._build_title_with_company_type(
            base_title, company_type_name, menu_path, trigger_text
        )
        
        # 构建访问路径描述
        access_path = self._build_access_path(menu_path, page_route, trigger_element, trigger_text)
        
        # 生成测试步骤
        steps = [
            TestStep(
                step_number=1,
                step_type='navigate',
                description=f"访问包含{component_name}组件的页面",
                details={
                    'component': component_name,
                    'file': file_path,
                    'action': '打开浏览器，导航到目标页面'
                }
            ),
            TestStep(
                step_number=2,
                step_type='locate',
                description="定位要删除的数据",
                details={
                    'actions': [
                        '从列表中找到目标数据',
                        '定位删除按钮或操作菜单'
                    ],
                    'note': '确保目标数据存在'
                }
            ),
            TestStep(
                step_number=3,
                step_type='action',
                description="执行删除操作",
                details={
                    'actions': [
                        '点击删除按钮',
                        '在确认对话框中点击确认'
                    ],
                    'note': '注意是否有二次确认'
                }
            ),
            TestStep(
                step_number=4,
                step_type='verify_api',
                description=f"验证API调用：{api_method} {api_path}",
                details={
                    'method': api_method,
                    'path': api_path,
                    'call_type': call_type,
                    'line': line_number,
                    'check_params': '验证请求包含正确的资源ID'
                }
            ),
            TestStep(
                step_number=5,
                step_type='verify_ui',
                description="验证删除结果",
                details={
                    'checks': [
                        '显示删除成功提示',
                        '目标数据从列表中移除',
                        '列表自动刷新',
                        '删除失败时显示错误提示'
                    ]
                }
            )
        ]
        
        # 生成测试数据
        test_data = [
            TestData(
                data_type='normal',
                description='正常删除数据',
                example={'id': 1},
                expected_result='删除成功，返回200或204状态码'
            ),
            TestData(
                data_type='invalid',
                description='删除不存在的资源',
                example={'id': 99999},
                expected_result='返回404错误'
            ),
            TestData(
                data_type='invalid',
                description='删除被引用的资源',
                example={'id': 1},
                expected_result='返回409错误，提示资源被引用无法删除'
            ),
            TestData(
                data_type='boundary',
                description='批量删除',
                example={'ids': [1, 2, 3]},
                expected_result='所有指定的资源都被删除'
            )
        ]
        
        # 生成验证点
        verification_points = [
            VerificationPoint(
                category='api_response',
                description='HTTP状态码验证',
                expected='200 OK 或 204 No Content'
            ),
            VerificationPoint(
                category='ui_state',
                description='确认对话框验证',
                expected='删除前显示确认对话框'
            ),
            VerificationPoint(
                category='ui_state',
                description='删除状态验证',
                expected='删除时显示loading状态'
            ),
            VerificationPoint(
                category='ui_state',
                description='成功反馈验证',
                expected='显示删除成功提示，数据从列表移除'
            ),
            VerificationPoint(
                category='data_format',
                description='数据一致性验证',
                expected='删除后无法再查询到该数据'
            )
        ]
        
        return TestCase(
            test_id=test_id,
            title=title,
            priority=priority,
            test_type=test_type,
            api_info={'method': api_method, 'path': api_path},
            component_info={
                'name': component_name,
                'file_path': file_path,
                'line_number': str(line_number),
                'call_type': call_type
            },
            steps=steps,
            test_data=test_data,
            verification_points=verification_points,
            preconditions=f'使用{company_type_name}账号登录系统，具有删除权限，目标数据已存在' if company_type_name else '用户已登录系统，具有删除权限，目标数据已存在',
            company_type=company_type,
            company_type_name=company_type_name,
            notes=f'该测试用例基于{file_path}第{line_number}行的API调用生成'
        )
    
    def _generate_generic_test_case(self, api_method: str, api_path: str,
                                   component_name: str, file_path: str,
                                   line_number: int, call_type: str,
                                   priority: str, test_type: str,
                                   trigger_element: str, trigger_text: str,
                                   page_route: str, menu_path: str,
                                   company_type: Optional[str] = None,
                                   company_type_name: Optional[str] = None) -> TestCase:
        """生成通用测试用例（其他HTTP方法）"""
        
        test_id = f"TC_{self.test_case_counter:04d}"
        
        # 构建更友好的测试标题（支持端信息）
        if trigger_text:
            base_title = f"测试{component_name}组件的'{trigger_text}'功能"
        else:
            base_title = f"测试{component_name}组件的API调用功能"
        
        title = self._build_title_with_company_type(
            base_title, company_type_name, menu_path, trigger_text
        )
        
        # 构建访问路径描述
        access_path = self._build_access_path(menu_path, page_route, trigger_element, trigger_text)
        
        # 生成通用测试步骤
        steps = [
            TestStep(
                step_number=1,
                step_type='navigate',
                description=f"访问包含{component_name}组件的页面",
                details={
                    'component': component_name,
                    'file': file_path,
                    'action': '打开浏览器，导航到目标页面'
                }
            ),
            TestStep(
                step_number=2,
                step_type='locate',
                description="定位触发API调用的元素",
                details={
                    'element_types': ['按钮', '链接', '表单'],
                    'action': '找到触发API调用的UI元素'
                }
            ),
            TestStep(
                step_number=3,
                step_type='action',
                description="执行操作",
                details={
                    'actions': ['点击按钮', '提交表单', '触发事件'],
                    'note': '根据实际UI交互方式选择'
                }
            ),
            TestStep(
                step_number=4,
                step_type='verify_api',
                description=f"验证API调用：{api_method} {api_path}",
                details={
                    'method': api_method,
                    'path': api_path,
                    'call_type': call_type,
                    'line': line_number
                }
            ),
            TestStep(
                step_number=5,
                step_type='verify_ui',
                description="验证UI反馈",
                details={
                    'checks': [
                        '显示操作结果',
                        'UI状态正确更新',
                        '错误时显示错误提示'
                    ]
                }
            )
        ]
        
        # 生成测试数据
        test_data = [
            TestData(
                data_type='normal',
                description='正常操作',
                example={},
                expected_result='操作成功'
            )
        ]
        
        # 生成验证点
        verification_points = [
            VerificationPoint(
                category='api_response',
                description='HTTP状态码验证',
                expected='2xx 成功状态码'
            ),
            VerificationPoint(
                category='ui_state',
                description='UI反馈验证',
                expected='显示操作结果'
            )
        ]
        
        return TestCase(
            test_id=test_id,
            title=title,
            priority=priority,
            test_type=test_type,
            api_info={'method': api_method, 'path': api_path},
            component_info={
                'name': component_name,
                'file_path': file_path,
                'line_number': str(line_number),
                'call_type': call_type
            },
            steps=steps,
            test_data=test_data,
            verification_points=verification_points,
            preconditions=f'使用{company_type_name}账号登录系统（如需要）' if company_type_name else '用户已登录系统（如需要）',
            notes=f'该测试用例基于{file_path}第{line_number}行的API调用生成',
            company_type=company_type,
            company_type_name=company_type_name
        )
    
    def generate_test_cases_batch(self, api_calls: List[Dict[str, Any]]) -> List[TestCase]:
        """
        批量生成测试用例
        
        Args:
            api_calls: API调用信息列表，每个元素包含：
                - api_method: HTTP方法
                - api_path: API路径
                - component_name: 组件名称
                - file_path: 文件路径
                - line_number: 行号
                - call_type: 调用类型
                - trigger_element: 触发元素类型（可选）
                - trigger_text: 触发元素文本（可选）
                - page_route: 页面路由（可选）
                - menu_path: 菜单路径（可选）
                - call_count: 调用次数（可选）
                - is_core_business: 是否核心业务（可选）
                
        Returns:
            TestCase对象列表
        """
        test_cases = []
        
        for call in api_calls:
            try:
                # 获取端信息（如果已提供）
                company_type = call.get('company_type')
                company_type_name = call.get('company_type_name')
                
                # 如果未提供端信息，尝试自动识别
                if not company_type:
                    page_route = call.get('page_route')
                    menu_path = call.get('menu_path')
                    if page_route:
                        company_types = self._identify_company_type(page_route, menu_path)
                        if company_types:
                            # 如果识别到多个端，为每个端生成一个测试用例
                            for ct in company_types:
                                ct_name = self._get_company_type_name(ct)
                                test_case = self.generate_test_case(
                                    api_method=call.get('api_method', 'GET'),
                                    api_path=call.get('api_path', ''),
                                    component_name=call.get('component_name', 'Unknown'),
                                    file_path=call.get('file_path', ''),
                                    line_number=call.get('line_number', 0),
                                    call_type=call.get('call_type', 'axios'),
                                    has_frontend_call=True,
                                    trigger_element=call.get('trigger_element'),
                                    trigger_text=call.get('trigger_text'),
                                    page_route=page_route,
                                    menu_path=menu_path,
                                    call_count=call.get('call_count', 1),
                                    is_core_business=call.get('is_core_business', False),
                                    company_type=ct,
                                    company_type_name=ct_name
                                )
                                test_cases.append(test_case)
                            continue
                
                # 如果只有一个端或未识别到端，生成一个测试用例
                test_case = self.generate_test_case(
                    api_method=call.get('api_method', 'GET'),
                    api_path=call.get('api_path', ''),
                    component_name=call.get('component_name', 'Unknown'),
                    file_path=call.get('file_path', ''),
                    line_number=call.get('line_number', 0),
                    call_type=call.get('call_type', 'axios'),
                    has_frontend_call=True,
                    trigger_element=call.get('trigger_element'),
                    trigger_text=call.get('trigger_text'),
                    page_route=call.get('page_route'),
                    menu_path=call.get('menu_path'),
                    call_count=call.get('call_count', 1),
                    is_core_business=call.get('is_core_business', False),
                    company_type=company_type,
                    company_type_name=company_type_name
                )
                test_cases.append(test_case)
            except Exception as e:
                logger.warning(f"生成测试用例失败: {e}, API调用: {call}")
        
        return test_cases
    
    def test_case_to_dict(self, test_case: TestCase) -> Dict[str, Any]:
        """
        将TestCase对象转换为字典格式（用于JSON序列化）
        
        Args:
            test_case: TestCase对象
            
        Returns:
            字典格式的测试用例
        """
        return {
            'test_id': test_case.test_id,
            'title': test_case.title,
            'priority': test_case.priority,
            'test_type': test_case.test_type,
            'api_info': test_case.api_info,
            'component_info': test_case.component_info,
            'steps': [
                {
                    'step_number': step.step_number,
                    'step_type': step.step_type,
                    'description': step.description,
                    'details': step.details
                }
                for step in test_case.steps
            ],
            'test_data': [
                {
                    'data_type': data.data_type,
                    'description': data.description,
                    'example': data.example,
                    'expected_result': data.expected_result
                }
                for data in test_case.test_data
            ],
            'verification_points': [
                {
                    'category': vp.category,
                    'description': vp.description,
                    'expected': vp.expected
                }
                for vp in test_case.verification_points
            ],
            'preconditions': test_case.preconditions,
            'notes': test_case.notes,
            'company_type': test_case.company_type,
            'company_type_name': test_case.company_type_name
        }
    
    def _build_access_path(self, menu_path: str, page_route: str, 
                          trigger_element: str, trigger_text: str) -> str:
        """
        构建完整的访问路径描述
        
        Returns:
            访问路径描述，如："菜单：订单管理 > 订单列表，然后点击'查询'按钮"
        """
        parts = []
        
        # 1. 菜单路径
        if menu_path:
            parts.append(f"菜单：{menu_path}")
        elif page_route:
            parts.append(f"访问页面：{page_route}")
        
        # 2. 触发元素
        if trigger_text:
            if trigger_element == 'button':
                parts.append(f"点击'{trigger_text}'按钮")
            elif trigger_element == 'link':
                parts.append(f"点击'{trigger_text}'链接")
            elif trigger_element == 'form':
                parts.append(f"提交'{trigger_text}'表单")
            else:
                parts.append(f"触发'{trigger_text}'")
        
        if parts:
            return '，然后'.join(parts)
        else:
            return "（需手动确认访问路径和触发方式）"
    
    # ==================== 标题生成辅助方法（新增） ====================
    
    def _build_title_with_company_type(self, base_title: str, 
                                       company_type_name: Optional[str] = None,
                                       menu_path: Optional[str] = None,
                                       trigger_text: Optional[str] = None) -> str:
        """
        构建包含端信息的测试用例标题
        
        Args:
            base_title: 基础标题
            company_type_name: 端名称（如 '供应商端'）
            menu_path: 菜单路径（如 '融资还款' 或 '资产管理 > 订单管理'）
            trigger_text: 触发文本（如 '查询'）
            
        Returns:
            包含端信息的标题，如果没有端信息则返回原标题
        """
        if not company_type_name:
            return base_title
        
        # 提取菜单名称（如果菜单路径包含层级，使用最后一级）
        menu_name = None
        if menu_path:
            menu_parts = [m.strip() for m in menu_path.split('>')]
            menu_name = menu_parts[-1] if menu_parts else None
        
        # 构建标题：格式为 "{端名称} - {菜单名称} - {功能描述}"
        if menu_name and trigger_text:
            return f"{company_type_name} - {menu_name} - {trigger_text}"
        elif menu_name:
            return f"{company_type_name} - {menu_name} - 数据查询"
        elif trigger_text:
            return f"{company_type_name} - {trigger_text}"
        else:
            return f"{company_type_name} - {base_title}"
    
    # ==================== 菜单配置解析相关方法（新增） ====================
    
    def _load_menu_config(self, project_path: str):
        """
        加载并解析菜单配置文件，建立路由到端的映射关系
        
        Args:
            project_path: 项目根路径
        """
        import os
        import re
        
        # 查找菜单配置文件（支持多种可能的路径）
        possible_paths = [
            os.path.join(project_path, 'src', 'views', 'container', 'components', 'menu.js'),
            os.path.join(project_path, 'src', 'router', 'menu.js'),
            os.path.join(project_path, 'src', 'config', 'menu.js'),
            os.path.join(project_path, 'src', 'menu.js'),
        ]
        
        # 规范化所有路径
        possible_paths = [os.path.normpath(p) for p in possible_paths]
        
        menu_file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                menu_file_path = path
                break
        
        if not menu_file_path:
            logger.warning(f"[菜单解析] 未找到菜单配置文件，尝试的路径: {possible_paths}")
            return
        
        try:
            with open(menu_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"[菜单解析] 成功加载菜单配置文件: {menu_file_path}")
            self._parse_menu_config(content)
        except Exception as e:
            logger.warning(f"[菜单解析] 读取菜单配置文件失败 {menu_file_path}: {e}")
    
    def _parse_menu_config(self, content: str):
        """
        解析菜单配置文件内容，建立路由到端的映射关系
        
        通过识别注释（如 '// 供应商菜单'）和常量名（如 'SPY_ORDER_MENU'）来确定端类型
        
        Args:
            content: 菜单配置文件内容
        """
        import re
        
        # 当前解析的端类型
        current_company_type = None
        
        # 按行解析
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # 方法1：识别注释中的端类型（优先级高）
            if '// 供应商菜单' in line:
                current_company_type = 'SPY'
                logger.debug(f"[菜单解析] 第{i+1}行：识别到供应商菜单")
            elif '// 核心企业菜单' in line:
                current_company_type = 'CE'
                logger.debug(f"[菜单解析] 第{i+1}行：识别到核心企业菜单")
            elif '// 资金方' in line:
                current_company_type = 'CPT'
                logger.debug(f"[菜单解析] 第{i+1}行：识别到资金方菜单")
            
            # 方法2：识别常量名中的端类型（作为备用判断）
            if 'SPY_ORDER_MENU' in line and current_company_type != 'SPY':
                current_company_type = 'SPY'
                logger.debug(f"[菜单解析] 第{i+1}行：通过常量名识别到供应商菜单")
            elif 'CORE_ORDER_MENU' in line and current_company_type != 'CE':
                current_company_type = 'CE'
                logger.debug(f"[菜单解析] 第{i+1}行：通过常量名识别到核心企业菜单")
            elif 'CPT_ORDER_MENU' in line and current_company_type != 'CPT':
                current_company_type = 'CPT'
                logger.debug(f"[菜单解析] 第{i+1}行：通过常量名识别到资金方菜单")
            
            # 解析路由和菜单名称（url字段和menuName字段）
            if current_company_type:
                # 匹配格式：url: "/orderPaymentManageBook" 或 url: '/orderPaymentManageBook'
                url_match = re.search(r'url:\s*["\']([^"\']+)["\']', line)
                # 匹配格式：menuName: "还款管理" 或 menuName: '还款管理'
                menu_match = re.search(r'menuName:\s*["\']([^"\']+)["\']', line)
                
                if url_match:
                    route = url_match.group(1)
                    menu_name = menu_match.group(1) if menu_match else None
                    
                    # 建立路由到端的映射（一个路由可能对应多个端）
                    if route not in self._route_to_company_types:
                        self._route_to_company_types[route] = []
                    if current_company_type not in self._route_to_company_types[route]:
                        self._route_to_company_types[route].append(current_company_type)
                    
                    # 建立 (路由, 菜单名称) 到端的精确映射
                    if menu_name:
                        key = (route, menu_name)
                        self._route_menu_to_company_type[key] = current_company_type
                        logger.debug(f"[菜单解析] 映射: {route} + '{menu_name}' -> {current_company_type}")
                    else:
                        logger.debug(f"[菜单解析] 映射: {route} -> {current_company_type}")
        
        logger.info(f"[菜单解析] 解析完成，共建立 {len(self._route_to_company_types)} 个路由映射，"
                   f"{len(self._route_menu_to_company_type)} 个精确映射")
    
    def _identify_company_type(self, page_route: str, menu_path: str) -> List[str]:
        """
        根据路由和菜单路径识别端类型
        
        优先使用菜单配置文件解析的结果，如果没有则使用备用规则
        
        Args:
            page_route: 页面路由
            menu_path: 菜单路径（如 "融资还款" 或 "资产管理 > 订单管理"）
            
        Returns:
            端类型列表，如 ['SPY', 'CE'] 或 ['CPT']，如果无法确定则返回空列表
        """
        if not page_route:
            return []
        
        # 1. 优先使用精确映射（路由 + 菜单名称）
        if menu_path:
            # 从菜单路径中提取菜单名称（可能包含层级，如 "资产管理 > 订单管理"）
            menu_names = [m.strip() for m in menu_path.split('>')]
            for menu_name in menu_names:
                key = (page_route, menu_name)
                if key in self._route_menu_to_company_type:
                    company_type = self._route_menu_to_company_type[key]
                    logger.debug(f"[端识别] 通过精确映射识别: {page_route} + '{menu_name}' -> {company_type}")
                    return [company_type]
        
        # 2. 使用路由映射（如果路由对应多个端，尝试通过菜单名称进一步判断）
        if page_route in self._route_to_company_types:
            company_types = self._route_to_company_types[page_route]
            
            # 如果路由对应多个端，尝试通过菜单名称进一步判断
            if len(company_types) > 1 and menu_path:
                # 例如：'/orderPaymentManageBook' 对应 ['SPY', 'CE']
                # 如果菜单名称是"还款管理"，应该是SPY
                # 如果菜单名称是"融资还款"，应该是CE
                menu_lower = menu_path.lower()
                if '还款管理' in menu_path and 'SPY' in company_types:
                    logger.debug(f"[端识别] 通过菜单名称判断: '{menu_path}' -> SPY")
                    return ['SPY']
                elif '融资还款' in menu_path and 'CE' in company_types:
                    logger.debug(f"[端识别] 通过菜单名称判断: '{menu_path}' -> CE")
                    return ['CE']
                elif '付款管理' in menu_path and 'CE' in company_types:
                    logger.debug(f"[端识别] 通过菜单名称判断: '{menu_path}' -> CE")
                    return ['CE']
                elif '核企付款管理' in menu_path and 'CPT' in company_types:
                    logger.debug(f"[端识别] 通过菜单名称判断: '{menu_path}' -> CPT")
                    return ['CPT']
            
            logger.debug(f"[端识别] 通过路由映射识别: {page_route} -> {company_types}")
            return company_types
        
        # 3. 备用规则：硬编码的映射（如果菜单配置文件解析失败）
        route_mapping = {
            '/orderPaymentManageBookCPT': ['CPT'],
            '/paymentManagementCE': ['CE'],
            '/paymentManagementCPT': ['CPT'],
        }
        
        if page_route in route_mapping:
            logger.debug(f"[端识别] 通过备用规则识别: {page_route} -> {route_mapping[page_route]}")
            return route_mapping[page_route]
        
        # 4. 如果无法确定，返回空列表
        logger.debug(f"[端识别] 无法确定端类型: route={page_route}, menu={menu_path}")
        return []
    
    def _get_company_type_name(self, company_type: str) -> str:
        """
        获取端的显示名称
        
        Args:
            company_type: 端类型代码（'SPY', 'CPT', 'CE'）
            
        Returns:
            端的显示名称（'供应商端', '资金方端', '核心企业端'）
        """
        mapping = {
            'SPY': '供应商端',
            'CPT': '资金方端',
            'CE': '核心企业端'
        }
        return mapping.get(company_type, '')
