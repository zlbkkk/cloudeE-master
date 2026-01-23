# Requirements Document

## Introduction

本功能旨在通过分析前端代码中的 API 调用，自动识别后端接口与前端 UI 组件的关联关系，并生成具体的 UI 测试路径指导。系统将自动发现前端项目，识别 API 调用位置，提取 UI 上下文信息，最终生成可操作的测试步骤，帮助测试人员从前端界面入口进行端到端测试。

## Glossary

- **Frontend Project（前端项目）**: 包含前端代码的项目目录，通常包含 package.json 文件
- **API Call（API 调用）**: 前端代码中通过 axios、fetch 等方式调用后端接口的代码
- **UI Component（UI 组件）**: 前端框架（React/Vue/Angular）中的组件文件
- **Test Path（测试路径）**: 从前端界面入口到触发 API 调用的完整操作步骤
- **UI Context（UI 上下文）**: API 调用所在的 UI 环境信息，包括按钮文本、表单字段、页面路由等
- **Frontend-Backend Mapping（前后端映射）**: 后端 API 端点与前端调用位置的对应关系

## Requirements

### Requirement 1: 前端项目自动发现

**User Story:** 作为系统，我希望能够自动发现 workspace 中的前端项目，以便无需用户手动配置即可进行前端分析

#### Acceptance Criteria

1. WHEN 系统启动分析任务 THEN 系统 SHALL 扫描 workspace 目录下的所有子目录
2. WHEN 系统发现包含 package.json 文件的目录 THEN 系统 SHALL 识别该目录为潜在的前端项目
3. WHEN 系统检测到前端项目 THEN 系统 SHALL 识别前端框架类型（React、Vue、Angular）
4. WHEN 系统识别前端框架类型 THEN 系统 SHALL 提取项目的 API 基础路径配置
5. WHEN 系统完成前端项目发现 THEN 系统 SHALL 记录所有发现的前端项目信息

### Requirement 2: 前端 API 调用识别（阶段 1 - MVP）

**User Story:** 作为系统，我希望能够识别前端代码中的 API 调用，以便建立前后端的关联关系

#### Acceptance Criteria

1. WHEN 系统分析前端项目 THEN 系统 SHALL 扫描所有 JavaScript 和 TypeScript 文件
2. WHEN 系统扫描前端文件 THEN 系统 SHALL 识别 axios 库的 API 调用（axios.get、axios.post、axios.put、axios.delete）
3. WHEN 系统扫描前端文件 THEN 系统 SHALL 识别 fetch API 的调用（fetch 函数）
4. WHEN 系统识别到 API 调用 THEN 系统 SHALL 提取 API 路径、HTTP 方法、调用位置（文件路径和行号）
5. WHEN 系统提取 API 调用信息 THEN 系统 SHALL 提取调用所在的组件名称

### Requirement 3: 前后端映射关系建立（阶段 1 - MVP）

**User Story:** 作为系统，我希望能够将后端 API 与前端调用位置关联起来，以便生成准确的测试建议

#### Acceptance Criteria

1. WHEN 系统完成后端 API 分析 THEN 系统 SHALL 获取所有受影响的后端 API 端点列表
2. WHEN 系统完成前端 API 调用识别 THEN 系统 SHALL 获取所有前端 API 调用列表
3. WHEN 系统进行前后端映射 THEN 系统 SHALL 匹配后端 API 路径与前端调用的 API 路径
4. WHEN 系统匹配 API 路径 THEN 系统 SHALL 处理路径参数（如 /api/orders/{id} 与 /api/orders/123）
5. WHEN 系统完成映射 THEN 系统 SHALL 生成前后端关联关系数据结构

### Requirement 4: 基础测试建议生成（阶段 1 - MVP）

**User Story:** 作为测试人员，我希望系统能够告诉我哪些 API 被前端调用了，以便我知道应该进行 UI 测试还是接口测试

#### Acceptance Criteria

1. WHEN 后端 API 被前端调用 THEN 系统 SHALL 在测试策略中标注该 API 被前端组件调用
2. WHEN 系统生成测试建议 THEN 系统 SHALL 显示调用该 API 的前端组件名称和文件路径
3. WHEN 后端 API 未被前端调用 THEN 系统 SHALL 建议进行接口测试或单元测试
4. WHEN 后端 API 被多个前端组件调用 THEN 系统 SHALL 列出所有调用位置
5. WHEN 系统生成测试策略 THEN 系统 SHALL 区分 UI 测试和接口测试的优先级

### Requirement 5: UI 上下文信息提取（阶段 2 - 增强）

**User Story:** 作为测试人员，我希望系统能够提取 API 调用所在的 UI 上下文信息，以便我了解如何触发该 API 调用

#### Acceptance Criteria

1. WHEN 系统识别到 API 调用 THEN 系统 SHALL 分析调用所在的函数或方法
2. WHEN 系统分析调用函数 THEN 系统 SHALL 识别触发该函数的事件类型（onClick、onSubmit、onChange 等）
3. WHEN 系统识别到事件触发 THEN 系统 SHALL 提取触发元素的文本内容（按钮文本、链接文本）
4. WHEN API 调用在表单提交中 THEN 系统 SHALL 提取表单字段信息（字段名称、标签文本、输入类型）
5. WHEN 系统提取 UI 上下文 THEN 系统 SHALL 识别组件所在的页面路由

### Requirement 6: 页面路由识别（阶段 2 - 增强）

**User Story:** 作为测试人员，我希望系统能够识别组件所在的页面路由，以便我知道应该访问哪个页面进行测试

#### Acceptance Criteria

1. WHEN 系统分析 React 项目 THEN 系统 SHALL 解析 React Router 的路由配置
2. WHEN 系统分析 Vue 项目 THEN 系统 SHALL 解析 Vue Router 的路由配置
3. WHEN 系统分析 Angular 项目 THEN 系统 SHALL 解析 Angular Router 的路由配置
4. WHEN 系统识别组件 THEN 系统 SHALL 查找该组件对应的路由路径
5. WHEN 组件被多个路由使用 THEN 系统 SHALL 列出所有可能的路由路径

### Requirement 7: 测试步骤生成（阶段 2 - 增强）

**User Story:** 作为测试人员，我希望系统能够生成具体的测试步骤，以便我可以直接按照步骤进行测试

#### Acceptance Criteria

1. WHEN 系统完成 UI 上下文提取 THEN 系统 SHALL 生成访问页面的步骤（包含路由路径）
2. WHEN 系统识别到按钮触发 THEN 系统 SHALL 生成点击按钮的步骤（包含按钮文本）
3. WHEN 系统识别到表单提交 THEN 系统 SHALL 生成填写表单的步骤（包含字段名称和示例值）
4. WHEN 系统生成测试步骤 THEN 系统 SHALL 按照用户操作的逻辑顺序排列步骤
5. WHEN 系统生成测试步骤 THEN 系统 SHALL 包含验证点说明（预期结果）

### Requirement 8: 测试策略优化

**User Story:** 作为测试人员，我希望系统能够根据前端调用情况优化测试策略，以便我优先进行最有价值的测试

#### Acceptance Criteria

1. WHEN 后端 API 被前端调用 THEN 系统 SHALL 将该 API 的测试优先级设置为 P0（UI 测试）
2. WHEN 后端 API 未被前端调用但是公开接口 THEN 系统 SHALL 将测试优先级设置为 P1（接口测试）
3. WHEN 后端方法是内部方法且未被前端调用 THEN 系统 SHALL 将测试优先级设置为 P2（单元测试）
4. WHEN 系统生成测试策略 THEN 系统 SHALL 在测试策略矩阵中明确标注测试类型（UI 测试/接口测试/单元测试）
5. WHEN 系统生成测试策略 THEN 系统 SHALL 将 UI 测试步骤放在最前面

### Requirement 9: 报告展示增强

**User Story:** 作为测试人员，我希望在分析报告中能够清晰地看到前端调用信息和测试路径，以便快速了解如何进行测试

#### Acceptance Criteria

1. WHEN 系统生成分析报告 THEN 系统 SHALL 在测试策略部分增加"前端调用信息"章节
2. WHEN 显示前端调用信息 THEN 系统 SHALL 显示调用组件、文件路径、行号
3. WHEN 显示 UI 测试步骤 THEN 系统 SHALL 使用有序列表格式清晰展示操作步骤
4. WHEN 显示测试路径 THEN 系统 SHALL 使用醒目的样式突出显示（如使用不同颜色或图标）
5. WHEN 报告包含多个测试场景 THEN 系统 SHALL 按照测试类型分组展示（UI 测试、接口测试、单元测试）

### Requirement 10: 错误处理和边界情况

**User Story:** 作为系统，我希望能够优雅地处理各种异常情况，以便保证分析的稳定性

#### Acceptance Criteria

1. WHEN 前端项目不存在 THEN 系统 SHALL 跳过前端分析并继续后端分析
2. WHEN 前端代码解析失败 THEN 系统 SHALL 记录错误日志并继续分析其他文件
3. WHEN API 路径无法匹配 THEN 系统 SHALL 使用模糊匹配算法尝试匹配
4. WHEN UI 上下文信息提取失败 THEN 系统 SHALL 降级为基础的调用位置信息
5. WHEN 路由配置无法解析 THEN 系统 SHALL 提示用户手动确认页面路径
