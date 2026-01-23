# UI测试用例去重功能设计文档

## 1. 系统架构

### 1.1 整体架构
```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend API Scanner                     │
│  (扫描前端代码，提取API调用信息)                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                Frontend Backend Mapper                       │
│  (建立前后端映射关系)                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Test Case Generator                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  generate_test_cases_batch()                          │  │
│  │  ├─ 生成测试用例                                       │  │
│  │  ├─ deduplicate_test_cases() ← 新增去重逻辑           │  │
│  │  └─ 返回去重后的测试用例                               │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      AI Analyzer                             │
│  (使用去重后的测试用例生成报告)                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

#### 1.2.1 TestCaseDeduplicator（新增类）
负责测试用例的去重逻辑，包括：
- 唯一性判断
- 优先级计算
- 去重执行

#### 1.2.2 TestCaseGenerator（修改）
在 `generate_test_cases_batch()` 方法中集成去重逻辑

## 2. 详细设计

### 2.1 数据模型

#### 2.1.1 TestCaseKey（新增）
用于唯一标识一个测试用例：
```python
@dataclass(frozen=True)
class TestCaseKey:
    """测试用例唯一键"""
    component_name: str  # 组件名称
    api_path: str        # API路径
    api_method: str      # HTTP方法
    
    def __hash__(self):
        return hash((self.component_name, self.api_path, self.api_method))
    
    def __eq__(self, other):
        return (self.component_name == other.component_name and
                self.api_path == other.api_path and
                self.api_method == other.api_method)
```

#### 2.1.2 TestCasePriority（新增）
用于计算测试用例的优先级：
```python
@dataclass
class TestCasePriority:
    """测试用例优先级信息"""
    has_port_prefix: bool      # 是否有端口前缀
    data_source: str           # 数据来源：'new_frontend', 'old_frontend', 'backend'
    menu_path_depth: int       # 菜单路径深度
    line_number: int           # 行号
    
    def calculate_score(self) -> float:
        """计算优先级分数"""
        score = 0.0
        
        # 端口信息（权重：100）
        if self.has_port_prefix:
            score += 100
        
        # 数据来源（权重：50）
        if self.data_source == 'new_frontend':
            score += 50
        elif self.data_source == 'old_frontend':
            score += 30
        # backend: 0分
        
        # 菜单路径完整性（权重：20）
        score += min(self.menu_path_depth * 5, 20)
        
        # 行号（权重：-0.001，越小越好）
        score -= self.line_number * 0.001
        
        return score
```

### 2.2 核心算法

#### 2.2.1 去重算法
```python
def deduplicate_test_cases(self, test_case_infos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    去重测试用例信息
    
    Args:
        test_case_infos: 测试用例信息列表
        
    Returns:
        去重后的测试用例信息列表
    """
    # 1. 按唯一键分组
    grouped_cases = {}  # key: TestCaseKey, value: List[Dict]
    
    for case_info in test_case_infos:
        key = self._create_test_case_key(case_info)
        if key not in grouped_cases:
            grouped_cases[key] = []
        grouped_cases[key].append(case_info)
    
    # 2. 对每组选择优先级最高的
    deduplicated_cases = []
    
    for key, cases in grouped_cases.items():
        if len(cases) == 1:
            # 只有一个，直接保留
            deduplicated_cases.append(cases[0])
        else:
            # 多个重复，选择优先级最高的
            best_case = self._select_best_case(cases)
            deduplicated_cases.append(best_case)
            
            # 记录被丢弃的测试用例
            for case in cases:
                if case != best_case:
                    self._log_discarded_case(case, best_case, key)
    
    return deduplicated_cases
```

#### 2.2.2 优先级比较算法
```python
def _select_best_case(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    从多个重复的测试用例中选择最佳的一个
    
    Args:
        cases: 重复的测试用例列表
        
    Returns:
        优先级最高的测试用例
    """
    best_case = None
    best_score = -float('inf')
    
    for case in cases:
        priority = self._calculate_priority(case)
        score = priority.calculate_score()
        
        if score > best_score:
            best_score = score
            best_case = case
    
    return best_case
```

#### 2.2.3 优先级计算算法
```python
def _calculate_priority(self, case_info: Dict[str, Any]) -> TestCasePriority:
    """
    计算测试用例的优先级
    
    Args:
        case_info: 测试用例信息
        
    Returns:
        TestCasePriority对象
    """
    # 1. 判断是否有端口前缀
    menu_path = case_info.get('menu_path', '')
    has_port_prefix = self._has_port_prefix(menu_path)
    
    # 2. 判断数据来源
    file_path = case_info.get('file_path', '')
    data_source = self._identify_data_source(file_path)
    
    # 3. 计算菜单路径深度
    menu_path_depth = menu_path.count('>') if menu_path else 0
    
    # 4. 获取行号
    line_number = case_info.get('line_number', 0)
    
    return TestCasePriority(
        has_port_prefix=has_port_prefix,
        data_source=data_source,
        menu_path_depth=menu_path_depth,
        line_number=line_number
    )
```

### 2.3 辅助方法

#### 2.3.1 端口前缀检测
```python
def _has_port_prefix(self, menu_path: str) -> bool:
    """
    检测菜单路径是否有端口前缀
    
    Args:
        menu_path: 菜单路径
        
    Returns:
        是否有端口前缀
    """
    if not menu_path:
        return False
    
    # 检测是否以 [xxx端] 开头
    port_prefixes = ['[核企端]', '[供应商端]', '[资方端]', '[资金方端]']
    return any(menu_path.startswith(prefix) for prefix in port_prefixes)
```

#### 2.3.2 数据来源识别
```python
def _identify_data_source(self, file_path: str) -> str:
    """
    识别测试用例的数据来源
    
    Args:
        file_path: 文件路径
        
    Returns:
        数据来源：'new_frontend', 'old_frontend', 'backend'
    """
    if not file_path:
        return 'backend'
    
    # 新版前端：包含 'dev-2.25.0' 或类似版本号
    if 'dev-' in file_path or re.search(r'-\d+\.\d+\.\d+', file_path):
        return 'new_frontend'
    
    # 旧版前端：不包含版本号
    if 'frontend' in file_path.lower():
        return 'old_frontend'
    
    # 后端：Controller 文件
    if 'Controller' in file_path:
        return 'backend'
    
    return 'backend'
```

#### 2.3.3 日志记录
```python
def _log_discarded_case(self, discarded_case: Dict[str, Any], 
                       kept_case: Dict[str, Any],
                       key: TestCaseKey):
    """
    记录被丢弃的测试用例
    
    Args:
        discarded_case: 被丢弃的测试用例
        kept_case: 保留的测试用例
        key: 测试用例唯一键
    """
    discarded_priority = self._calculate_priority(discarded_case)
    kept_priority = self._calculate_priority(kept_case)
    
    logger.info(
        f"[去重] 丢弃重复测试用例: "
        f"组件={key.component_name}, "
        f"API={key.api_method} {key.api_path}"
    )
    logger.debug(
        f"[去重] 被丢弃: "
        f"文件={discarded_case.get('file_path')}, "
        f"行号={discarded_case.get('line_number')}, "
        f"菜单={discarded_case.get('menu_path')}, "
        f"分数={discarded_priority.calculate_score():.3f}"
    )
    logger.debug(
        f"[去重] 保留: "
        f"文件={kept_case.get('file_path')}, "
        f"行号={kept_case.get('line_number')}, "
        f"菜单={kept_case.get('menu_path')}, "
        f"分数={kept_priority.calculate_score():.3f}"
    )
```

## 3. 集成方案

### 3.1 修改 TestCaseGenerator

#### 3.1.1 添加去重方法
在 `TestCaseGenerator` 类中添加去重相关方法：
```python
class TestCaseGenerator:
    # ... 现有代码 ...
    
    def deduplicate_test_cases(self, test_case_infos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重测试用例信息"""
        # 实现去重逻辑
        pass
    
    def _create_test_case_key(self, case_info: Dict[str, Any]) -> TestCaseKey:
        """创建测试用例唯一键"""
        pass
    
    def _calculate_priority(self, case_info: Dict[str, Any]) -> TestCasePriority:
        """计算测试用例优先级"""
        pass
    
    # ... 其他辅助方法 ...
```

#### 3.1.2 修改 generate_test_cases_batch
```python
def generate_test_cases_batch(self, api_calls: List[Dict[str, Any]]) -> List[TestCase]:
    """
    批量生成测试用例（带去重）
    
    Args:
        api_calls: API调用信息列表
        
    Returns:
        TestCase对象列表（已去重）
    """
    # 1. 去重API调用信息
    logger.info(f"[测试用例生成] 开始去重，原始数量: {len(api_calls)}")
    deduplicated_calls = self.deduplicate_test_cases(api_calls)
    logger.info(f"[测试用例生成] 去重完成，剩余数量: {len(deduplicated_calls)}")
    
    # 2. 生成测试用例（使用去重后的数据）
    test_cases = []
    for call in deduplicated_calls:
        # ... 现有的测试用例生成逻辑 ...
        pass
    
    return test_cases
```

### 3.2 不需要修改的部分
- `frontend_api_scanner.py`：不需要修改，继续扫描所有API调用
- `frontend_backend_mapper.py`：不需要修改，继续建立所有映射关系
- `ai_analyzer.py`：不需要修改，使用去重后的测试用例
- `runner.py`：不需要修改，调用流程保持不变

## 4. 测试策略

### 4.1 单元测试

#### 4.1.1 测试用例唯一键生成
```python
def test_create_test_case_key():
    """测试创建测试用例唯一键"""
    generator = TestCaseGenerator()
    
    case_info = {
        'component_name': 'ceOrderStandingBook',
        'api_path': '/order/pageOrder',
        'api_method': 'POST'
    }
    
    key = generator._create_test_case_key(case_info)
    
    assert key.component_name == 'ceOrderStandingBook'
    assert key.api_path == '/order/pageOrder'
    assert key.api_method == 'POST'
```

#### 4.1.2 测试优先级计算
```python
def test_calculate_priority():
    """测试优先级计算"""
    generator = TestCaseGenerator()
    
    # 测试用例1：新版前端，有端口前缀
    case1 = {
        'file_path': 'beehive-order-finance-frontend-dev-2.25.0/src/views/standingBook/components/ceOrderStandingBook.vue',
        'menu_path': '[核企端] 融资审核',
        'line_number': 100
    }
    priority1 = generator._calculate_priority(case1)
    score1 = priority1.calculate_score()
    
    # 测试用例2：旧版前端，无端口前缀
    case2 = {
        'file_path': 'beehive-order-finance-frontend/src/views/standingBook/components/ceOrderStandingBook.vue',
        'menu_path': '融资审核',
        'line_number': 100
    }
    priority2 = generator._calculate_priority(case2)
    score2 = priority2.calculate_score()
    
    # 测试用例1的分数应该更高
    assert score1 > score2
```

#### 4.1.3 测试去重逻辑
```python
def test_deduplicate_test_cases():
    """测试去重逻辑"""
    generator = TestCaseGenerator()
    
    # 准备测试数据：3个重复的测试用例
    test_cases = [
        {
            'component_name': 'ceOrderStandingBook',
            'api_path': '/order/pageOrder',
            'api_method': 'POST',
            'file_path': 'beehive-order-finance-frontend-dev-2.25.0/...',
            'menu_path': '[核企端] 融资审核',
            'line_number': 100
        },
        {
            'component_name': 'ceOrderStandingBook',
            'api_path': '/order/pageOrder',
            'api_method': 'POST',
            'file_path': 'beehive-order-finance-frontend/...',
            'menu_path': '融资审核',
            'line_number': 100
        },
        {
            'component_name': 'ceOrderStandingBook',
            'api_path': '/order/pageOrder',
            'api_method': 'POST',
            'file_path': 'Controller.java',
            'menu_path': '',
            'line_number': 50
        }
    ]
    
    # 执行去重
    deduplicated = generator.deduplicate_test_cases(test_cases)
    
    # 验证结果
    assert len(deduplicated) == 1
    assert deduplicated[0]['file_path'] == 'beehive-order-finance-frontend-dev-2.25.0/...'
    assert deduplicated[0]['menu_path'] == '[核企端] 融资审核'
```

### 4.2 集成测试

#### 4.2.1 端到端测试
```python
def test_end_to_end_deduplication():
    """端到端测试：从API调用到去重后的测试用例"""
    # 1. 准备测试数据（模拟前端扫描结果）
    api_calls = [...]
    
    # 2. 生成测试用例（包含去重）
    generator = TestCaseGenerator()
    test_cases = generator.generate_test_cases_batch(api_calls)
    
    # 3. 验证结果
    # - 没有重复的测试用例
    # - 保留的测试用例有端口前缀
    # - 保留的测试用例来自新版前端
    pass
```

### 4.3 性能测试

#### 4.3.1 大数据量测试
```python
def test_performance_with_large_dataset():
    """性能测试：1000个测试用例"""
    import time
    
    generator = TestCaseGenerator()
    
    # 生成1000个测试用例（包含重复）
    test_cases = generate_test_data(1000)
    
    # 测试去重性能
    start_time = time.time()
    deduplicated = generator.deduplicate_test_cases(test_cases)
    end_time = time.time()
    
    # 验证性能要求：< 1秒
    assert (end_time - start_time) < 1.0
```

## 5. 部署计划

### 5.1 开发环境测试
1. 在开发环境运行单元测试
2. 在开发环境运行集成测试
3. 验证日志输出

### 5.2 测试环境验证
1. 部署到测试环境
2. 使用真实数据进行测试
3. 收集反馈，调整优先级规则

### 5.3 生产环境部署
1. 备份现有代码
2. 部署新代码
3. 监控运行情况
4. 收集用户反馈

## 6. 监控和维护

### 6.1 监控指标
- 去重前后的测试用例数量
- 去重耗时
- 被丢弃的测试用例数量
- 用户反馈

### 6.2 维护计划
- 定期检查日志，确认去重逻辑正常工作
- 根据用户反馈调整优先级规则
- 持续优化性能

## 7. 正确性属性（Property-Based Testing）

### 7.1 属性1：去重后无重复
**描述**：去重后的测试用例列表中，不应该存在重复的测试用例

**形式化定义**：
```
∀ test_cases, deduplicated_cases = deduplicate(test_cases)
⇒ ∀ i, j ∈ [0, len(deduplicated_cases)), i ≠ j
⇒ key(deduplicated_cases[i]) ≠ key(deduplicated_cases[j])
```

**测试策略**：
- 生成随机的测试用例列表（包含重复）
- 执行去重
- 验证去重后的列表中没有重复的键

### 7.2 属性2：保留最优测试用例
**描述**：对于每组重复的测试用例，去重后保留的应该是优先级最高的

**形式化定义**：
```
∀ test_cases, deduplicated_cases = deduplicate(test_cases)
∀ key, cases_with_key = filter(test_cases, λc. key(c) == key)
⇒ kept_case = find(deduplicated_cases, λc. key(c) == key)
⇒ ∀ c ∈ cases_with_key, priority(kept_case) ≥ priority(c)
```

**测试策略**：
- 生成随机的测试用例列表（包含重复，且优先级不同）
- 执行去重
- 对每组重复的测试用例，验证保留的是优先级最高的

### 7.3 属性3：不丢失唯一测试用例
**描述**：去重不应该丢失任何唯一的测试用例

**形式化定义**：
```
∀ test_cases, deduplicated_cases = deduplicate(test_cases)
∀ key, unique_keys = {key(c) | c ∈ test_cases}
⇒ ∀ k ∈ unique_keys, ∃ c ∈ deduplicated_cases, key(c) == k
```

**测试策略**：
- 生成随机的测试用例列表（包含唯一和重复的）
- 执行去重
- 验证所有唯一的键都在去重后的列表中

### 7.4 属性4：优先级计算的单调性
**描述**：优先级计算应该满足单调性：更好的特征应该导致更高的分数

**形式化定义**：
```
∀ case1, case2,
  case1.has_port_prefix = True ∧ case2.has_port_prefix = False
  ∧ case1.data_source = case2.data_source
  ∧ case1.menu_path_depth = case2.menu_path_depth
  ∧ case1.line_number = case2.line_number
⇒ priority(case1) > priority(case2)
```

**测试策略**：
- 生成成对的测试用例，只改变一个特征
- 验证优先级分数的大小关系符合预期

## 8. 附录

### 8.1 示例数据

#### 8.1.1 重复测试用例示例
```python
# 测试用例1：新版前端，有端口前缀
{
    'component_name': 'ceOrderStandingBook',
    'api_path': '/order/pageOrder',
    'api_method': 'POST',
    'file_path': 'beehive-order-finance-frontend-dev-2.25.0/src/views/standingBook/components/ceOrderStandingBook.vue',
    'menu_path': '[核企端] 融资审核',
    'line_number': 100
}

# 测试用例2：旧版前端，无端口前缀
{
    'component_name': 'ceOrderStandingBook',
    'api_path': '/order/pageOrder',
    'api_method': 'POST',
    'file_path': 'beehive-order-finance-frontend/src/views/standingBook/components/ceOrderStandingBook.vue',
    'menu_path': '融资审核',
    'line_number': 100
}

# 测试用例3：后端注释，无菜单路径
{
    'component_name': 'ceOrderStandingBook',
    'api_path': '/order/pageOrder',
    'api_method': 'POST',
    'file_path': 'OfOrderController.java',
    'menu_path': '',
    'line_number': 50
}
```

#### 8.1.2 去重后的结果
```python
# 保留测试用例1（优先级最高）
{
    'component_name': 'ceOrderStandingBook',
    'api_path': '/order/pageOrder',
    'api_method': 'POST',
    'file_path': 'beehive-order-finance-frontend-dev-2.25.0/src/views/standingBook/components/ceOrderStandingBook.vue',
    'menu_path': '[核企端] 融资审核',
    'line_number': 100
}
```

### 8.2 配置选项（未来扩展）
```python
# 去重配置
DEDUPLICATION_CONFIG = {
    'enabled': True,  # 是否启用去重
    'weights': {
        'port_prefix': 100,      # 端口前缀权重
        'new_frontend': 50,      # 新版前端权重
        'old_frontend': 30,      # 旧版前端权重
        'menu_depth': 5,         # 菜单深度权重（每层）
        'line_number': -0.001    # 行号权重
    },
    'log_discarded': True  # 是否记录被丢弃的测试用例
}
```
