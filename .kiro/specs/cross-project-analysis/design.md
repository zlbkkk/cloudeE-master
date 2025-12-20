# 设计文档

## 概述

跨项目影响分析功能扩展了现有的代码变更影响分析系统，以支持跨多个相关 Git 仓库分析代码变更。这对于微服务架构至关重要，因为一个服务中的更改可能会影响多个依赖服务或前端应用程序。

该设计遵循模块化方法，包含三个主要组件：
1. **项目关联管理**：用于配置项目关系的数据库模型和 API
2. **多项目追踪器**：协调跨多个仓库扫描的核心分析引擎
3. **增强的分析管道**：集成跨项目扫描的修改后的分析工作流

## 架构

### 高层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React)                             │
│  ┌──────────────────┐         ┌─────────────────────────┐  │
│  │ 项目关联         │         │  分析触发器             │  │
│  │  管理界面        │         │  (带跨项目开关)         │  │
│  │                  │         │                         │  │
│  └──────────────────┘         └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (Django)                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API 层 (ViewSets)                        │  │
│  │  - ProjectRelationViewSet                            │  │
│  │  - AnalysisTaskViewSet (增强版)                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           分析引擎                                     │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  run_analysis.py (管理命令)                    │  │  │
│  │  │  - Git 操作                                    │  │  │
│  │  │  - 项目克隆/更新                               │  │  │
│  │  │  - 多项目协调                                  │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                              │                         │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  MultiProjectTracer                            │  │  │
│  │  │  - 管理多个 ApiUsageTracer 实例                │  │  │
│  │  │  - 管理多个 StaticAnalyzer 实例                │  │  │
│  │  │  - 协调跨项目扫描                              │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │         │                              │               │  │
│  │         ▼                              ▼               │  │
│  │  ┌──────────────┐            ┌──────────────────┐    │  │
│  │  │ApiUsageTracer│            │ StaticAnalyzer   │    │  │
│  │  │(每个项目)    │            │ (每个项目)       │    │  │
│  │  └──────────────┘            └──────────────────┘    │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              数据层 (Models)                          │  │
│  │  - ProjectRelation                                    │  │
│  │  - AnalysisTask                                       │  │
│  │  - AnalysisReport (增强版)                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  MySQL 数据库    │
                    └──────────────────┘
```

### 分析工作流

```
1. 用户启用跨项目分析触发分析
                    ↓
2. 查询 ProjectRelation 表获取关联项目
                    ↓
3. 克隆/更新主项目
                    ↓
4. 在主项目上执行 git diff
                    ↓
5. 解析变更文件
                    ↓
6. 克隆/更新关联项目（并行）
                    ↓
7. 使用所有项目根目录初始化 MultiProjectTracer
                    ↓
8. 对于每个变更文件：
   a. 在主项目中分析（现有逻辑）
   b. 提取变更的类和方法
   c. 扫描关联项目以查找引用
   d. 收集跨项目影响
                    ↓
9. 使用跨项目上下文生成 AI 分析
                    ↓
10. 保存包含跨项目影响的报告
```

## 组件和接口

### 1. 数据库模型

#### ProjectRelation 模型

```python
class ProjectRelation(models.Model):
    """
    存储主项目与其关联项目之间的关系。
    """
    id: int (主键，自增)
    main_project_name: str (最大 255 字符)
    main_project_git_url: str (最大 500 字符)
    related_project_name: str (最大 255 字符)
    related_project_git_url: str (最大 500 字符)
    related_project_branch: str (最大 100 字符，默认='master')
    is_active: bool (默认=True)
    created_at: datetime (自动)
    updated_at: datetime (自动)
    
    # 约束：
    # - 唯一组合：(main_project_git_url, related_project_git_url)
```

#### AnalysisReport 模型（增强版）

```python
class AnalysisReport(models.Model):
    # ... 现有字段 ...
    
    # 新字段：
    source_project: str (最大 255 字符，默认='main')
    # 指示此影响来自主项目还是关联项目
```

### 2. API 端点

#### ProjectRelation 端点

```
GET    /api/project-relations/              # 列出所有关联
POST   /api/project-relations/              # 创建新关联
GET    /api/project-relations/{id}/         # 获取特定关联
PUT    /api/project-relations/{id}/         # 更新关联
PATCH  /api/project-relations/{id}/         # 部分更新
DELETE /api/project-relations/{id}/         # 删除关联
GET    /api/project-relations/by-main-project/?main_git_url={url}
                                            # 按主项目获取关联
```

#### 增强的分析任务端点

```
POST /api/tasks/trigger/
请求体：
{
  "mode": "git",
  "projectPath": "/path/to/project",
  "gitUrl": "git@git.example.com:org/repo.git",
  "targetBranch": "develop",
  "baseCommit": "HEAD^",
  "targetCommit": "HEAD",
  "enableCrossProject": true  // 新增
}

响应：
{
  "status": "Analysis started",
  "task_id": 123,
  "enable_cross_project": true,
  "related_projects_count": 2
}
```

### 3. 核心类

#### MultiProjectTracer

```python
class MultiProjectTracer:
    """
    协调多个项目的 API 和依赖追踪。
    """
    
    def __init__(self, project_roots: List[str]):
        """
        为所有项目初始化追踪器。
        
        参数：
            project_roots: 项目根目录的绝对路径列表
                          [主项目路径, 关联项目1路径, ...]
        """
        self.project_roots = project_roots
        self.tracers: Dict[str, ApiUsageTracer] = {}
        self.analyzers: Dict[str, LightStaticAnalyzer] = {}
        
    def find_class_usages_in_project(
        self, 
        project_root: str, 
        full_class_name: str
    ) -> List[Dict]:
        """
        在特定项目中查找类的使用情况。
        
        返回：
            使用情况字典列表，包含以下键：
            - path: str (文件路径)
            - line: int (行号)
            - snippet: str (代码片段)
        """
        
    def find_api_impacts_in_project(
        self,
        project_root: str,
        target_class: str,
        target_method: str
    ) -> List[Dict]:
        """
        在特定项目中查找 API 影响。
        
        返回：
            影响字典列表，包含以下键：
            - api: str (API 端点)
            - file: str (文件路径)
            - line: int (行号)
            - snippet: str (代码片段)
        """
        
    def find_cross_project_impacts(
        self,
        full_class_name: str,
        changed_methods: List[str]
    ) -> List[Dict]:
        """
        在所有关联项目中查找影响（不包括主项目）。
        
        参数：
            full_class_name: 完全限定的类名（例如，com.example.UserManager）
            changed_methods: 已修改的方法名称列表
            
        返回：
            影响字典列表，包含以下键：
            - project: str (项目名称)
            - type: str ('class_reference' 或 'api_call')
            - file: str (文件路径)
            - line: int (行号)
            - snippet: str (代码片段)
            - detail: str (人类可读的描述)
            - api: str (可选，用于 api_call 类型)
        """
```

#### 增强的 run_analysis 命令

```python
class Command(BaseCommand):
    def add_arguments(self, parser):
        # ... 现有参数 ...
        parser.add_argument(
            '--enable-cross-project',
            action='store_true',
            help='启用跨项目分析'
        )
        parser.add_argument(
            '--related-projects',
            type=str,
            default='[]',
            help='关联项目配置的 JSON 数组'
        )
        
    def handle(self, *args, **options):
        """
        主要分析工作流：
        1. 解析选项
        2. 从主项目获取 git diff
        3. 克隆/更新关联项目（如果启用）
        4. 初始化 MultiProjectTracer
        5. 分析每个变更文件
        6. 生成包含跨项目影响的报告
        """
```

## 数据模型

### 数据库架构

#### project_relation 表

```sql
CREATE TABLE `project_relation` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `main_project_name` VARCHAR(255) NOT NULL COMMENT '主项目名称',
  `main_project_git_url` VARCHAR(500) NOT NULL COMMENT '主项目Git地址',
  `related_project_name` VARCHAR(255) NOT NULL COMMENT '关联项目名称',
  `related_project_git_url` VARCHAR(500) NOT NULL COMMENT '关联项目Git地址',
  `related_project_branch` VARCHAR(100) DEFAULT 'master' COMMENT '关联项目分支',
  `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY `uk_main_related` (`main_project_git_url`, `related_project_git_url`),
  INDEX `idx_main_project` (`main_project_git_url`),
  INDEX `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目关联关系表';
```

#### analysis_report 表（修改）

```sql
ALTER TABLE analysis_report 
ADD COLUMN `source_project` VARCHAR(255) DEFAULT 'main' 
COMMENT '来源项目名称（main 或关联项目名称）';

CREATE INDEX `idx_source_project` ON analysis_report(`source_project`);
```

### 数据流

```
用户输入（前端）
    ↓
ProjectRelation 配置
    ↓ (存储在数据库中)
分析任务触发
    ↓ (查询 ProjectRelation)
关联项目列表
    ↓ (传递给 run_analysis)
Git 克隆/更新操作
    ↓ (创建本地副本)
MultiProjectTracer 初始化
    ↓ (构建索引)
跨项目扫描
    ↓ (查找影响)
影响数据结构
    ↓ (格式化为 AI 输入)
带跨项目上下文的 AI 分析
    ↓ (生成建议)
AnalysisReport 记录
    ↓ (保存到数据库)
前端显示
```



## 错误处理

### 1. Git 操作错误

**场景**：克隆或更新关联项目失败

**处理策略**：
- 记录详细错误信息（包括 Git URL、分支、错误消息）
- 继续处理其他关联项目
- 在任务日志中标记失败的项目
- 不中断主项目的分析流程

### 2. 索引构建错误

**场景**：为项目构建 ApiUsageTracer 或 StaticAnalyzer 索引失败

**处理策略**：
- 记录错误和堆栈跟踪
- 跳过该项目的跨项目扫描
- 继续分析其他项目
- 在报告中注明哪些项目未能成功扫描

### 3. 缓存操作错误

**场景**：加载或保存索引缓存失败

**处理策略**：
- 记录警告信息
- 回退到不使用缓存
- 重新构建索引
- 不影响分析结果的正确性

### 4. 数据库操作错误

**场景**：查询 ProjectRelation 或保存 AnalysisReport 失败

**处理策略**：
- 记录错误详情
- 对于查询失败：使用空的关联项目列表继续
- 对于保存失败：重试一次，失败则标记任务为 FAILED
- 向用户显示明确的错误消息

### 5. 并发操作错误

**场景**：并行克隆项目时部分操作失败

**处理策略**：
- 使用 ThreadPoolExecutor 的异常处理机制
- 收集所有成功和失败的结果
- 记录每个失败操作的详细信息
- 使用成功克隆的项目继续分析

## 测试策略

### 单元测试

#### 1. 模型测试
- **ProjectRelation 模型**
  - 测试创建、读取、更新、删除操作
  - 测试唯一性约束
  - 测试默认值

- **AnalysisReport 模型**
  - 测试 source_project 字段的默认值
  - 测试与其他字段的集成

#### 2. API 测试
- **ProjectRelationViewSet**
  - 测试 CRUD 端点
  - 测试 by-main-project 自定义端点
  - 测试过滤和排序

- **AnalysisTaskViewSet**
  - 测试 enableCrossProject 参数
  - 测试关联项目查询逻辑

#### 3. 核心逻辑测试
- **MultiProjectTracer**
  - 测试初始化多个项目
  - 测试 find_class_usages_in_project
  - 测试 find_api_impacts_in_project
  - 测试 find_cross_project_impacts

### 集成测试

#### 1. 端到端工作流测试
- 创建测试项目关联
- 触发跨项目分析
- 验证报告包含跨项目影响
- 验证日志记录正确

#### 2. Git 操作测试
- 测试克隆新项目
- 测试更新现有项目
- 测试处理无效 Git URL
- 测试并行克隆

#### 3. 缓存测试
- 测试缓存命中
- 测试缓存未命中
- 测试缓存失效
- 测试缓存保存失败

### 性能测试

#### 1. 扩展性测试
- 测试 1 个关联项目的分析时间
- 测试 5 个关联项目的分析时间
- 测试 10 个关联项目的分析时间

#### 2. 大型项目测试
- 测试包含 10 万行代码的项目
- 测试包含 1000 个类的项目
- 测试深层调用链（10+ 层）

#### 3. 并发测试
- 测试同时触发多个分析任务
- 测试并行克隆的资源使用
- 测试缓存的并发访问

## 正确性属性

*属性是一个特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的正式陈述。属性作为人类可读规范和机器可验证的正确性保证之间的桥梁。*


### 属性 1：项目关联持久化完整性

*对于任何*项目关联，当创建时包含所有必需字段（主项目名称、主项目 Git URL、关联项目名称、关联项目 Git URL、分支），则从数据库查询回来的记录应该包含所有相同的字段值。

**验证：需求 1.1**

### 属性 2：活动项目过滤正确性

*对于任何*主项目 Git URL 和一组项目关联（包含活动和非活动状态），按该 Git URL 查询应该只返回 is_active=True 且 main_project_git_url 匹配的关联。

**验证：需求 1.2**

### 属性 3：状态切换持久化

*对于任何*项目关联，切换其 is_active 状态后重新加载，新状态应该与切换后的值匹配。

**验证：需求 1.3**

### 属性 4：删除操作完整性

*对于任何*已存在的项目关联，删除后查询该关联应该返回不存在。

**验证：需求 1.4**

### 属性 5：唯一性约束强制

*对于任何*主项目 Git URL 和关联项目 Git URL 的组合，尝试创建第二个具有相同组合的关联应该失败。

**验证：需求 1.5**

### 属性 6：关联项目查询触发

*对于任何*启用跨项目分析的分析任务，系统应该查询并返回主项目的所有活动关联项目。

**验证：需求 2.1**

### 属性 7：分支切换正确性

*对于任何*关联项目和配置的分支名称，更新操作后，本地仓库的当前分支应该与配置的分支匹配。

**验证：需求 2.4**

### 属性 8：完全限定类名提取

*对于任何*有效的 Java 文件，如果它包含类定义和包声明，解析器应该提取出 package.ClassName 格式的完全限定类名。

**验证：需求 3.1**

### 属性 9：类引用搜索完整性

*对于任何*类名，如果它出现在文件的 import 语句或代码中，搜索应该找到该引用。

**验证：需求 3.2**

### 属性 10：引用记录完整性

*对于任何*找到的类引用，结果字典应该包含 project、file、line 和 snippet 字段。

**验证：需求 3.3**

### 属性 11：项目分组正确性

*对于任何*跨项目影响列表，来自同一项目的影响应该被分组在一起。

**验证：需求 3.4**

### 属性 12：主项目排除

*对于任何*跨项目影响搜索，结果中不应该包含主项目的影响。

**验证：需求 3.5**

### 属性 13：API 端点识别

*对于任何*带有 API 注解（如 @RequestMapping）的控制器方法，系统应该识别出对应的 API 端点。

**验证：需求 4.1**

### 属性 14：API 调用检测

*对于任何*API 端点，如果代码中存在对该端点的 HTTP 调用，搜索应该找到该调用。

**验证：需求 4.2**

### 属性 15：API 调用记录完整性

*对于任何*找到的 API 调用，结果字典应该包含 api、project、file、line 和 snippet 字段。

**验证：需求 4.3**

### 属性 16：API 调用分组

*对于任何*API 端点的多个调用者，结果应该按项目名称分组。

**验证：需求 4.4**

### 属性 17：报告包含跨项目部分

*对于任何*包含跨项目影响的分析，生成的报告应该包含专门的跨项目影响部分。

**验证：需求 5.1**

### 属性 18：影响显示分组

*对于任何*跨项目影响显示，影响应该按关联项目名称组织。

**验证：需求 5.2**

### 属性 19：影响条目完整性

*对于任何*影响条目，显示应该包含 type、file、line、snippet 和 detail 字段。

**验证：需求 5.3**

### 属性 20：主项目与跨项目区分

*对于任何*分析报告，主项目影响和跨项目影响应该被明确区分。

**验证：需求 5.5**

### 属性 21：条件分析范围

*对于任何*分析任务，当 enableCrossProject=False 时，只应该扫描主项目；当 enableCrossProject=True 时，应该扫描主项目和所有活动关联项目。

**验证：需求 6.2, 6.3**

### 属性 22：元数据记录

*对于任何*分析任务，enableCrossProject 标志的值应该被记录在任务元数据中。

**验证：需求 6.5**

### 属性 23：缓存键确定性

*对于任何*项目路径和 Git 提交哈希，生成的缓存键应该是确定性的（相同输入产生相同输出）。

**验证：需求 7.1**

### 属性 24：缓存优先加载

*对于任何*多项目追踪器初始化，系统应该先尝试加载缓存，只有在缓存不存在或无效时才构建新索引。

**验证：需求 7.2**

### 属性 25：缓存命中使用

*对于任何*有效的缓存索引，系统应该使用缓存而不是重建索引。

**验证：需求 7.3**

### 属性 26：提交变更缓存失效

*对于任何*项目，当 Git 提交哈希改变时，旧的缓存键应该不再匹配，导致缓存未命中。

**验证：需求 7.4**

### 属性 27：成功克隆添加到扫描列表

*对于任何*并行克隆操作，成功完成的项目路径应该被添加到扫描根列表中。

**验证：需求 8.2**

