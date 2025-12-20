# 实施计划

## 已完成的基础设施 (Tasks 1-4)

- [x] 1. 数据库层实现
  - 创建 ProjectRelation 模型和数据库迁移
  - 修改 AnalysisReport 模型添加 source_project 字段
  - 执行数据库迁移
  - _需求：1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.1 创建 ProjectRelation 模型
  - 在 `code_diff_project/backend/analyzer/models.py` 中添加 ProjectRelation 类
  - 定义所有字段：main_project_name, main_project_git_url, related_project_name, related_project_git_url, related_project_branch, is_active, created_at, updated_at
  - 设置 Meta 类：db_table, unique_together, ordering, verbose_name
  - 实现 __str__ 方法
  - _需求：1.1_

- [x] 1.2 修改 AnalysisReport 模型
  - 在 `code_diff_project/backend/analyzer/models.py` 中的 AnalysisReport 类添加 source_project 字段
  - 设置默认值为 'main'
  - 添加 help_text 说明
  - _需求：5.5_

- [x] 1.3 生成并执行数据库迁移
  - 运行 `python manage.py makemigrations`
  - 运行 `python manage.py migrate`
  - 验证表结构正确创建
  - _需求：1.1, 1.5_

- [ ]* 1.4 编写 ProjectRelation 模型的属性测试
  - **属性 1：项目关联持久化完整性**
  - **验证：需求 1.1**

- [ ]* 1.5 编写 ProjectRelation 唯一性约束的属性测试
  - **属性 5：唯一性约束强制**
  - **验证：需求 1.5**

- [x] 2. API 接口层实现
  - 创建 ProjectRelationSerializer
  - 创建 ProjectRelationViewSet
  - 注册路由
  - _需求：1.1, 1.2, 1.3, 1.4_

- [x] 2.1 创建 ProjectRelationSerializer
  - 在 `code_diff_project/backend/analyzer/serializers.py` 中添加 ProjectRelationSerializer
  - 使用 ModelSerializer
  - 包含所有字段
  - _需求：1.1_

- [x] 2.2 创建 ProjectRelationViewSet
  - 在 `code_diff_project/backend/analyzer/views.py` 中添加 ProjectRelationViewSet
  - 实现标准 CRUD 操作
  - 实现 get_by_main_project 自定义 action
  - 添加错误处理
  - _需求：1.2, 1.3, 1.4_

- [x] 2.3 注册 API 路由
  - 在 `code_diff_project/backend/analyzer/urls.py` 中注册 ProjectRelationViewSet
  - 测试所有端点可访问
  - _需求：1.1, 1.2, 1.3, 1.4_

- [ ]* 2.4 编写 API 端点的属性测试
  - **属性 2：活动项目过滤正确性**
  - **属性 3：状态切换持久化**
  - **属性 4：删除操作完整性**
  - **验证：需求 1.2, 1.3, 1.4**

- [x] 3. 核心分析逻辑 - MultiProjectTracer
  - 创建 MultiProjectTracer 类
  - 实现多项目索引管理
  - 实现跨项目影响查找
  - _需求：3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 10.1, 10.2_

- [x] 3.1 创建 MultiProjectTracer 基础结构
  - 创建 `code_diff_project/backend/analyzer/multi_project_tracer.py` 文件
  - 实现 __init__ 方法，接受 project_roots 列表
  - 为每个项目创建 ApiUsageTracer 和 LightStaticAnalyzer 实例
  - 添加错误处理和日志记录
  - _需求：10.1, 10.2_

- [x] 3.2 实现 find_class_usages_in_project 方法
  - 在指定项目中查找类的使用情况
  - 返回包含 path, line, snippet 的字典列表
  - 处理项目不存在的情况
  - _需求：3.2, 3.3_

- [x] 3.3 实现 find_api_impacts_in_project 方法
  - 在指定项目中查找 API 影响
  - 返回包含 api, file, line, snippet 的字典列表
  - 处理项目不存在的情况
  - _需求：4.2, 4.3_

- [x] 3.4 实现 find_cross_project_impacts 方法
  - 遍历所有关联项目（跳过主项目）
  - 查找类引用和 API 调用
  - 合并结果并按项目分组
  - 返回统一格式的影响列表
  - _需求：3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4_

- [x] 3.5 编写核心依赖检测的属性测试（P0 - 必须覆盖）







  - **属性 8：完全限定类名提取**
    - 测试从 Java 文件中提取 `package.ClassName` 格式的类名
    - 验证包声明和类定义的正确解析
  - **属性 9：类引用搜索完整性（核心场景）**
    - 测试 import 语句识别（显式 import、通配符 import *、静态 import）
    - 测试 @Autowired/@Resource 依赖注入识别
    - 测试 @DubboReference RPC 注入识别 ⭐ **Dubbo 核心**
    - 测试方法参数和返回值中的类引用
  - **属性 10：引用记录完整性**
    - 验证每个引用记录包含：project、file、line、snippet 字段
    - 验证行号准确性和代码片段完整性
  - **属性 12：主项目排除**
    - 验证跨项目搜索时不包含主项目的影响
    - 测试多项目场景下的正确过滤
  - **验证：需求 3.1, 3.2, 3.3, 3.5**

- [x] 3.6 编写 RPC 和 API 调用检测的属性测试（P0 - 必须覆盖）









  - **属性 13：API 端点识别**
    - 测试 @RequestMapping/@GetMapping/@PostMapping 等注解识别
    - 测试路径变量（@PathVariable）和请求参数（@RequestParam）识别
    - 测试 RESTful 路径解析（如 /api/users/{id}）
  - **属性 14：RPC 和 API 调用检测（核心场景）**
    - 测试 @DubboReference 服务注入识别 ⭐ **Dubbo 核心**
    - 测试 Dubbo 方法调用识别（如 userProvider.getUser()）⭐ **Dubbo 核心**
    - 测试 Dubbo 接口与实现类的映射关系 ⭐ **Dubbo 核心**
    - 测试 Feign Client 接口定义和调用识别
    - 测试 RestTemplate 调用识别（getForObject、postForObject 等）
    - 测试 WebClient 调用识别（响应式编程）
  - **属性 15：调用记录完整性**
    - 验证 Dubbo 调用记录包含：interface、method、file、line、snippet
    - 验证 API 调用记录包含：api、file、line、snippet
    - 验证跨项目调用的 project 字段准确性
  - **属性 16：跨项目 Dubbo 依赖追踪** ⭐ **Dubbo 核心**
    - 测试主项目 Provider 实现修改时，能找到关联项目中的 @DubboReference 引用
    - 测试跨模块依赖（API 模块接口 + Service 模块实现）
    - 测试多注册中心场景（registry = "operation" 等）
  - **验证：需求 4.1, 4.2, 4.3**

- [ ]* 3.7 编写扩展场景的属性测试（P1 - 应该覆盖）
  - **类引用扩展场景**
    - 测试继承和实现关系识别（extends、implements）
    - 测试注解中的类引用（@Valid、@ExceptionHandler 等）
    - 测试泛型参数中的类引用（List<UserDTO>、Map<String, UserDTO>）
  - **MyBatis Mapper 调用识别**
    - 测试 @Mapper 接口方法调用识别
    - 测试 XML Mapper 中的 SQL ID 调用识别
    - 测试 Mapper 方法与 Service 层的调用链
  - **验证：需求 3.2, 3.3**

- [ ]* 3.8 编写消息队列依赖测试（P2 - 可选覆盖）
  - 测试 RabbitMQ @RabbitListener 消费者识别
  - 测试 Kafka @KafkaListener 消费者识别
  - 测试消息发送方识别（rabbitTemplate.send、kafkaTemplate.send）
  - 测试消息队列的生产者-消费者依赖关系
  - **验证：需求 3.2, 4.2**

- [ ]* 3.9 编写边缘场景的属性测试（P3 - 暂不覆盖）
  - 测试 HTTP 原生调用识别（HttpURLConnection、Apache HttpClient、OkHttp）
  - 测试 JPA Repository 方法调用识别
  - 测试 @ConfigurationProperties 配置类依赖
  - 测试 @Value 注解配置项依赖
  - **验证：需求 3.2**

- [x] 4. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户

## 待实现的核心功能 (Tasks 5-10)

- [x] 5. 增强 run_analysis 命令 - 参数和配置




  - 添加跨项目分析命令行参数
  - 解析关联项目配置
  - _需求：6.1, 6.5_

- [x] 5.1 添加命令行参数





  - 在 `code_diff_project/backend/analyzer/management/commands/run_analysis.py` 的 add_arguments 方法中添加 --enable-cross-project 参数
  - 添加 --related-projects 参数接受 JSON 配置
  - _需求：6.1_

- [x] 5.2 解析和验证参数


  - 在 handle 方法开始处解析 enable_cross_project 和 related_projects_json
  - 使用 json.loads 解析关联项目配置
  - 添加日志输出配置信息
  - _需求：6.1, 6.5_

- [x] 6. 增强 run_analysis 命令 - 项目克隆和更新





  - 实现关联项目的克隆逻辑
  - 实现关联项目的更新逻辑
  - 实现并行克隆优化


  - _需求：2.1, 2.2, 2.3, 2.4, 2.5, 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 6.1 实现串行克隆/更新逻辑




  - 创建 workspace 目录（如果不存在）
  - 遍历关联项目列表
  - 对不存在的项目执行 git clone
  - 对已存在的项目执行 git fetch


  - 切换到配置的分支并 reset
  - 添加错误处理，失败不中断整体流程
  - _需求：2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 6.2 优化为并行克隆（可选）
  - 创建 clone_or_update_project 辅助函数
  - 使用 ThreadPoolExecutor 并行执行
  - 收集成功和失败的结果
  - 更新任务日志
  - _需求：8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 6.3 编写项目克隆的属性测试







  - **属性 7：分支切换正确性**
  - **属性 27：成功克隆添加到扫描列表**
  - **验证：需求 2.4, 8.2**

- [x] 7. 增强 run_analysis 命令 - 多项目追踪器集成


  - 初始化 MultiProjectTracer
  - 处理单项目和多项目模式
  - _需求：6.2, 6.3, 10.1_

- [x] 7.1 初始化多项目追踪器


  - 构建 scan_roots 列表（主项目 + 成功克隆的关联项目）
  - 根据 scan_roots 数量决定使用 MultiProjectTracer 还是 ApiUsageTracer
  - 添加初始化日志和错误处理
  - _需求：6.2, 6.3, 10.1_

- [x] 7.2 更新分析循环以支持多项目


  - 修改 analyze_with_llm 方法签名，添加 scan_roots 参数
  - 传递正确的追踪器实例（MultiProjectTracer 或 ApiUsageTracer）
  - _需求：6.2, 6.3_

- [x] 7.3 编写多项目模式的属性测试





  - **属性 21：条件分析范围**
  - **验证：需求 6.2, 6.3**

- [x] 8. 增强 analyze_with_llm 方法 - 跨项目影响分析




  - 提取变更的类和方法
  - 调用 MultiProjectTracer 查找跨项目影响
  - 格式化跨项目影响信息
  - 集成到 AI prompt
  - _需求：3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 8.1 提取变更的类和方法


  - 检查文件类型（.java）
  - 使用 LightStaticAnalyzer 解析 Java 文件
  - 提取完全限定类名
  - 提取变更的方法列表（使用现有的 extract_changed_methods 方法）
  - _需求：3.1_

- [x] 8.2 调用跨项目影响查找


  - 检查是否为多项目模式（tracer 是否为 MultiProjectTracer 实例）
  - 调用 tracer.find_cross_project_impacts
  - 处理异常并记录日志
  - _需求：3.2, 3.3, 3.4, 3.5, 4.2, 4.3, 4.4_

- [x] 8.3 格式化跨项目影响信息


  - 按项目分组影响
  - 格式化为人类可读的文本
  - 区分类引用和 API 调用
  - 包含文件路径、行号、代码片段
  - _需求：5.1, 5.2, 5.3, 5.5_


- [x] 8.4 集成到 downstream_info

  - 将格式化的跨项目影响添加到 downstream_info 字符串
  - 确保 AI prompt 包含跨项目上下文
  - _需求：5.1, 5.2, 5.3_


- [x] 8.5 添加详细日志记录

  - 记录跨项目分析开始
  - 记录每个项目的扫描进度
  - 记录发现的影响数量
  - 记录错误和警告
  - 更新任务日志
  - _需求：9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 8.6 编写跨项目影响格式化的属性测试










  - **属性 11：项目分组正确性**
  - **属性 16：API 调用分组**
  - **属性 17：报告包含跨项目部分**
  - **属性 18：影响显示分组**
  - **属性 19：影响条目完整性**
  - **属性 20：主项目与跨项目区分**
  - **验证：需求 3.4, 4.4, 5.1, 5.2, 5.3, 5.5**

- [ ] 9. 检查点 - 确保所有测试通过




  - 确保所有测试通过，如有问题请询问用户

- [x] 10. 修改 views.py 触发逻辑




  - 接收 enableCrossProject 参数
  - 查询关联项目
  - 传递参数给 run_analysis 命令
  - _需求：2.1, 6.1, 6.5_

- [x] 10.1 修改 trigger_analysis 方法


  - 在 `code_diff_project/backend/analyzer/views.py` 中修改 trigger_analysis 方法
  - 从请求中获取 enableCrossProject 参数
  - 查询 ProjectRelation 获取关联项目列表
  - 记录日志
  - _需求：2.1, 6.1_

- [x] 10.2 更新任务创建逻辑


  - 在任务的 log_details 中记录跨项目分析状态
  - 传递 enable_cross_project 和 related_projects 给后台线程
  - _需求：6.5_

- [x] 10.3 修改 call_command 调用


  - 添加 enable_cross_project 参数
  - 添加 related_projects 参数（JSON 序列化）
  - 确保参数正确传递
  - _需求：6.1, 6.5_

- [x] 10.4 编写触发逻辑的属性测试






  - **属性 6：关联项目查询触发**
  - **属性 22：元数据记录**
  - **验证：需求 2.1, 6.5**

## 可选优化功能 (Tasks 11)

- [ ] 11. 实现索引缓存优化（可选）
  - 实现缓存键生成
  - 实现缓存加载和保存
  - 实现缓存失效逻辑
  - _需求：7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 11.1 在 MultiProjectTracer 中添加缓存支持
  - 定义 CACHE_DIR 常量
  - 实现 _get_cache_key 方法（基于项目路径和 Git 提交哈希）
  - 实现 _save_cache 方法
  - 修改 __init__ 方法，先尝试加载缓存
  - 添加错误处理
  - _需求：7.1, 7.2, 7.3, 7.4, 7.5_

- [ ]* 11.2 编写缓存机制的属性测试
  - **属性 23：缓存键确定性**
  - **属性 24：缓存优先加载**
  - **属性 25：缓存命中使用**
  - **属性 26：提交变更缓存失效**
  - **验证：需求 7.1, 7.2, 7.3, 7.4**

## 前端实现 (Tasks 12-13)

- [x] 12. 前端 - 项目关联管理页面




  - 创建 ProjectRelations 组件
  - 实现 CRUD 功能
  - 添加路由
  - _需求：1.1, 1.2, 1.3, 1.4_

- [x] 12.1 创建 ProjectRelations 组件


  - 创建 `code_diff_project/frontend/src/pages/ProjectRelations.jsx` 文件
  - 实现表格显示项目关联列表
  - 实现添加关联的模态框
  - 实现删除功能
  - 实现启用/禁用切换
  - 使用 Ant Design 或现有 UI 组件库
  - _需求：1.1, 1.2, 1.3, 1.4_



- [x] 12.2 添加路由和菜单




  - 在 App.js 或路由配置中添加 /project-relations 路由
  - 在导航菜单中添加"项目关联管理"菜单项
  - _需求：1.1_

- [ ]* 12.3 编写前端组件的单元测试
  - 测试表格渲染
  - 测试添加功能
  - 测试删除功能
  - 测试状态切换

- [x] 13. 前端 - 修改分析触发页面




  - 添加跨项目分析开关
  - 显示关联项目列表
  - 传递参数到后端
  - _需求：6.1, 6.4_

- [x] 13.1 添加跨项目分析开关


  - 在分析触发页面中添加状态 enableCrossProject
  - 添加 Switch/Checkbox 组件
  - 添加说明文本
  - _需求：6.1, 6.4_



- [x] 13.2 实现关联项目查询和显示

  - 实现 handleGitUrlChange 函数
  - 当 Git URL 改变且跨项目分析启用时，查询关联项目


  - 显示将要扫描的关联项目列表
  - _需求：6.4_


- [x] 13.3 修改提交逻辑




  - 在 handleSubmit 中包含 enableCrossProject 参数
  - 发送到后端 API
  - _需求：6.1_

- [x] 13.4 编写前端交互的单元测试









  - 测试开关切换
  - 测试关联项目显示
  - 测试参数传递

## 集成测试和部署 (Tasks 14-16)

- [ ] 14. 最终检查点 - 端到端测试
  - 确保所有测试通过，如有问题请询问用户

- [x] 15. 集成测试和验证





  - 执行完整的端到端测试
  - 验证所有功能正常工作
  - 性能测试
  - _需求：所有_

- [x] 15.1 配置测试项目关联



  - 在数据库中插入测试数据
  - 验证前端可以正确显示和管理
  - _需求：1.1, 1.2, 1.3, 1.4_


- [x] 15.2 执行跨项目分析测试


  - 触发一个启用跨项目分析的任务
  - 验证关联项目被正确克隆/更新
  - 验证 MultiProjectTracer 正确初始化
  - 验证跨项目影响被正确识别
  - 验证报告包含跨项目影响部分
  - _需求：2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5_


- [x] 15.3 测试错误处理




  - 测试无效 Git URL
  - 测试克隆失败的情况
  - 测试索引构建失败
  - 验证错误被正确记录且不中断分析
  - _需求：2.5_


- [ ] 15.4 性能测试
  - 测试单项目分析时间（基线）
  - 测试 2 个关联项目的分析时间
  - 测试 5 个关联项目的分析时间
  - 验证缓存机制有效（如果实现）
  - 验证并行克隆提升性能（如果实现）
  - _需求：7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ]* 15.5 编写端到端集成测试
  - 测试完整工作流
  - 测试多种场景
  - 测试边界情况

- [x] 16. 文档和部署准备




  - 更新 README
  - 编写部署文档
  - 准备数据库迁移脚本

- [x] 16.1 更新项目文档



  - 在 README 中添加跨项目分析功能说明
  - 添加配置示例
  - 添加使用说明

  - _需求：所有_

- [x] 16.2 准备部署脚本




  - 创建数据库迁移 SQL 脚本
  - 创建部署检查清单
  - 准备回滚方案
  - _需求：所有_
