# Code Diff Project

This project contains a Django backend and a React frontend.

## Structure

- `backend/`: Django project
- `frontend/`: React application
- `venv/`: Python virtual environment

## Setup

1.  **Backend**:
    ```bash
    ./venv/Scripts/activate
    cd backend
    python manage.py runserver
    ```

2.  **Frontend**:
    ```bash
    cd frontend
    npm start
    ```


## 跨项目影响分析功能

### 功能概述

跨项目影响分析功能允许系统在微服务架构中分析代码变更对多个相关项目的影响。当主项目中的代码发生变更时，系统会自动扫描所有关联的项目，识别类引用、API 调用和 RPC 依赖关系。

### 核心特性

- **项目关联管理**：配置主项目与关联项目之间的依赖关系
- **自动克隆/更新**：自动克隆和更新关联项目到最新代码
- **跨项目扫描**：扫描所有关联项目，查找类引用和 API 调用
- **Dubbo RPC 支持**：识别 @DubboReference 注解和 Dubbo 服务调用
- **智能影响分析**：使用 AI 分析跨项目影响并生成建议
- **并行处理**：支持并行克隆多个项目，提升性能

### 配置示例

#### 1. 配置项目关联关系

通过前端界面或 API 配置主项目与关联项目的关系：

```json
{
  "main_project_name": "order-service",
  "main_project_git_url": "git@git.example.com:microservices/order-service.git",
  "related_project_name": "payment-service",
  "related_project_git_url": "git@git.example.com:microservices/payment-service.git",
  "related_project_branch": "develop",
  "is_active": true
}
```

#### 2. 触发跨项目分析

在分析触发页面启用"跨项目分析"开关：

```json
{
  "mode": "git",
  "projectPath": "/path/to/order-service",
  "gitUrl": "git@git.example.com:microservices/order-service.git",
  "targetBranch": "develop",
  "baseCommit": "HEAD^",
  "targetCommit": "HEAD",
  "enableCrossProject": true
}
```

#### 3. 命令行使用

也可以通过命令行直接触发跨项目分析：

```bash
cd backend
python manage.py run_analysis \
  --mode git \
  --project-path /path/to/order-service \
  --git-url git@git.example.com:microservices/order-service.git \
  --target-branch develop \
  --base-commit HEAD^ \
  --target-commit HEAD \
  --enable-cross-project \
  --related-projects '[{"name":"payment-service","git_url":"git@git.example.com:microservices/payment-service.git","branch":"develop"}]'
```

### 使用说明

#### 步骤 1：配置项目关联

1. 登录系统，进入"项目关联管理"页面
2. 点击"添加关联"按钮
3. 填写主项目和关联项目的信息：
   - 主项目名称和 Git 地址
   - 关联项目名称和 Git 地址
   - 关联项目分支（默认为 master）
4. 点击"保存"完成配置

#### 步骤 2：触发分析

1. 进入"分析触发"页面
2. 填写分析参数（项目路径、Git URL、分支、提交范围等）
3. 启用"跨项目分析"开关
4. 系统会显示将要扫描的关联项目列表
5. 点击"开始分析"

#### 步骤 3：查看结果

分析完成后，报告会包含以下内容：

- **主项目影响**：主项目内部的代码变更影响
- **跨项目影响**：按关联项目分组的影响列表
  - 类引用：哪些关联项目引用了变更的类
  - API 调用：哪些关联项目调用了变更的 API
  - RPC 调用：哪些关联项目通过 Dubbo 调用了变更的服务
- **AI 建议**：基于跨项目影响的测试和部署建议

### 支持的依赖类型

#### 1. 类引用检测

- Import 语句（显式 import、通配符 import *）
- 依赖注入（@Autowired、@Resource）
- RPC 注入（@DubboReference）
- 方法参数和返回值中的类引用
- 继承和实现关系（extends、implements）

#### 2. API 调用检测

- RESTful API（@RequestMapping、@GetMapping、@PostMapping 等）
- Feign Client 调用
- RestTemplate 调用
- WebClient 调用（响应式编程）

#### 3. RPC 调用检测

- Dubbo 服务接口定义
- @DubboReference 服务注入
- Dubbo 方法调用
- 跨模块依赖（API 模块 + Service 模块）

### 工作原理

```
1. 用户启用跨项目分析
   ↓
2. 系统查询项目关联配置
   ↓
3. 并行克隆/更新关联项目
   ↓
4. 分析主项目代码变更
   ↓
5. 提取变更的类和方法
   ↓
6. 扫描关联项目查找引用
   ↓
7. 收集跨项目影响数据
   ↓
8. AI 生成影响分析报告
   ↓
9. 展示完整的影响分析结果
```

### 性能优化

- **并行克隆**：使用线程池并行克隆多个关联项目
- **索引缓存**：缓存项目索引，避免重复构建
- **增量更新**：已存在的项目只执行 git fetch 和 reset
- **智能过滤**：只扫描活动状态的关联项目

### 注意事项

1. **Git 访问权限**：确保系统有权限访问所有配置的 Git 仓库
2. **磁盘空间**：关联项目会被克隆到 `workspace` 目录，确保有足够的磁盘空间
3. **分析时间**：跨项目分析比单项目分析耗时更长，建议在必要时启用
4. **网络连接**：首次克隆项目需要稳定的网络连接
5. **分支配置**：确保配置的分支名称正确，避免克隆失败

### 故障排查

#### 问题：关联项目克隆失败

**可能原因**：
- Git URL 不正确
- 没有访问权限
- 网络连接问题
- 分支不存在

**解决方法**：
- 检查 Git URL 格式是否正确
- 确认 SSH 密钥已配置
- 检查网络连接
- 验证分支名称是否存在

#### 问题：未检测到跨项目影响

**可能原因**：
- 关联项目未启用
- 代码变更不涉及跨项目依赖
- 索引构建失败

**解决方法**：
- 检查项目关联的 is_active 状态
- 查看任务日志确认扫描是否成功
- 重新触发分析

### API 文档

#### 项目关联管理 API

```
GET    /api/project-relations/              # 列出所有关联
POST   /api/project-relations/              # 创建新关联
GET    /api/project-relations/{id}/         # 获取特定关联
PUT    /api/project-relations/{id}/         # 更新关联
DELETE /api/project-relations/{id}/         # 删除关联
GET    /api/project-relations/by-main-project/?main_git_url={url}  # 按主项目查询
```

#### 分析任务 API

```
POST   /api/tasks/trigger/                  # 触发分析任务
GET    /api/tasks/{id}/                     # 获取任务详情
GET    /api/tasks/{id}/reports/             # 获取任务报告
```

### 数据库表结构

#### project_relation 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| main_project_name | VARCHAR(255) | 主项目名称 |
| main_project_git_url | VARCHAR(500) | 主项目 Git 地址 |
| related_project_name | VARCHAR(255) | 关联项目名称 |
| related_project_git_url | VARCHAR(500) | 关联项目 Git 地址 |
| related_project_branch | VARCHAR(100) | 关联项目分支 |
| is_active | TINYINT(1) | 是否启用 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 技术架构

- **后端框架**：Django 3.x
- **前端框架**：React 18.x
- **数据库**：MySQL 5.7+
- **静态分析**：自定义 Java 解析器
- **AI 分析**：集成 LLM API
- **并发处理**：Python ThreadPoolExecutor
