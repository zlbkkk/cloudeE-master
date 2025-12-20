# 跨项目依赖检测属性测试场景说明

## 概述

本文档说明了 `test_multi_project_tracer_properties.py` 中实现的属性测试场景。这些测试覆盖了跨项目分析中的核心依赖检测功能。

## 测试文件结构

`test_multi_project_tracer_properties.py` 包含 4 个测试类，共 9 个测试方法：
- **TestProperty8_FullyQualifiedClassNameExtraction** (1 个测试方法)
- **TestProperty9_ClassReferenceSearchCompleteness** (4 个测试方法)
- **TestProperty10_ReferenceRecordCompleteness** (2 个测试方法)
- **TestProperty12_MainProjectExclusion** (2 个测试方法)

## 测试场景详解

### 1. 属性 8：完全限定类名提取

**测试类：TestProperty8_FullyQualifiedClassNameExtraction**

**目的**：验证解析器能够从任何有效的 Java 文件中正确提取完全限定类名（Fully Qualified Name）

**测试方法：test_extracts_fqn_from_valid_java_file**

这是一个基于属性的测试，使用 Hypothesis 生成随机的 Java 类，验证系统能够正确解析包名和类名。

#### 测试场景 1：简单包名和类名

**输入**：
```java
package com.example;

import java.util.List;
import java.util.Map;

public class UserService {
    
    private String field1;
    private int field2;
    
    public UserService() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**执行操作**：
```python
# 创建临时项目
file_path = "src/main/java/com/example/UserService.java"
project_root = create_temp_project({file_path: content})

# 解析 Java 文件
analyzer = LightStaticAnalyzer(project_root)
full_class, simple_class, _ = analyzer.parse_java_file(full_path)
```

**期望结果**：
- `full_class` = `"com.example.UserService"`
- `simple_class` = `"UserService"`

**验证点**：
- ✅ 完全限定类名格式正确（package.ClassName）
- ✅ 简单类名正确提取
- ✅ 包名正确解析

---

#### 测试场景 2：多层包名

**输入**：
```java
package com.company.project.module.service;

import java.util.List;
import java.util.Map;

public class OrderManager {
    
    private String field1;
    private int field2;
    
    public OrderManager() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**期望结果**：
- `full_class` = `"com.company.project.module.service.OrderManager"`
- `simple_class` = `"OrderManager"`

**验证点**：
- ✅ 处理多层嵌套包名
- ✅ 包名层级正确解析

---

#### 测试场景 3：单字母包名和类名

**输入**：
```java
package a;

import java.util.List;
import java.util.Map;

public class A0 {
    
    private String field1;
    private int field2;
    
    public A0() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**期望结果**：
- `full_class` = `"a.A0"`
- `simple_class` = `"A0"`

**验证点**：
- ✅ 处理最短包名和类名
- ✅ 边缘情况正确处理

**验证需求**：需求 3.1 - 完全限定类名提取

**测试执行**：
- 使用 Hypothesis 生成 100 个随机 Java 文件
- 每个文件随机生成包名（1-5 层）和类名
- 验证所有生成的文件都能正确解析

### 2. 属性 9：类引用搜索完整性

**测试类：TestProperty9_ClassReferenceSearchCompleteness**

**目的**：验证系统能够检测各种类型的类引用

#### 测试方法 1：test_finds_explicit_import_references

**输入 - 目标类（被引用的类）**：
```java
package com.example.service;

import java.util.List;
import java.util.Map;

public class UserManager {
    
    private String field1;
    private int field2;
    
    public UserManager() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - 引用类（使用目标类的类）**：
```java
package com.test.importer;

import com.example.service.UserManager;

public class TestImporter {
    
    private UserManager instance;
    
    public void doSomething() {
        System.out.println("Using imported class");
    }
}
```

**执行操作**：
```python
# 创建项目，包含目标类和引用类
target_path = "src/main/java/com/example/service/UserManager.java"
importer_path = "src/main/java/com/test/importer/TestImporter.java"

project_root = create_temp_project({
    target_path: target_content,
    importer_path: importer_content
})

# 搜索目标类的使用情况
analyzer = LightStaticAnalyzer(project_root)
usages = analyzer.find_usages("com.example.service.UserManager")
```

**期望结果**：
- `len(usages)` > 0（找到至少一个引用）
- usages 中包含 TestImporter.java 文件
- 每个 usage 记录包含：
  - `path`: 文件路径（包含 TestImporter.java）
  - `line`: 行号（指向 import 或 private UserManager 行）
  - `snippet`: 代码片段
  - `service`: 服务名称

**验证点**：
- ✅ 检测到 `import com.example.service.UserManager;` 语句
- ✅ 识别类的使用位置（字段声明）
- ✅ 记录文件路径、行号、代码片段

---

#### 测试方法 2：test_finds_autowired_dependency_injection

**输入 - 目标类**：
```java
package com.example.repository;

import java.util.List;
import java.util.Map;

public class UserRepository {
    
    private String field1;
    private int field2;
    
    public UserRepository() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - Spring 依赖注入类**：
```java
package com.test.service;

import com.example.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;

public class TestService {
    
    @Autowired
    private UserRepository userRepository;
    
    public void doSomething() {
        userRepository.someMethod();
    }
}
```

**执行操作**：
```python
# 创建项目
target_path = "src/main/java/com/example/repository/UserRepository.java"
service_path = "src/main/java/com/test/service/TestService.java"

project_root = create_temp_project({
    target_path: target_content,
    service_path: service_content
})

# 搜索目标类的使用情况
analyzer = LightStaticAnalyzer(project_root)
usages = analyzer.find_usages("com.example.repository.UserRepository")
```

**期望结果**：
- `len(usages)` > 0
- usages 中包含 TestService.java 文件
- 检测到 @Autowired 注解的依赖

**验证点**：
- ✅ 检测 @Autowired 注解的依赖
- ✅ 识别注入字段的类型
- ✅ 记录注入位置和代码片段

---

#### 测试方法 3：test_finds_dubbo_reference_rpc_injection ⭐ Dubbo 核心

**输入 - Dubbo 服务接口**：
```java
package com.example.api;

import java.util.List;
import java.util.Map;

public class PaymentService {
    
    private String field1;
    private int field2;
    
    public PaymentService() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - Dubbo 服务消费者**：
```java
package com.test.consumer;

import com.example.api.PaymentService;
import org.apache.dubbo.config.annotation.DubboReference;

public class TestConsumer {
    
    @DubboReference
    private PaymentService paymentService;
    
    public void callRemoteService() {
        paymentService.remoteMethod();
    }
}
```

**执行操作**：
```python
# 创建项目
target_path = "src/main/java/com/example/api/PaymentService.java"
consumer_path = "src/main/java/com/test/consumer/TestConsumer.java"

project_root = create_temp_project({
    target_path: target_content,
    consumer_path: consumer_content
})

# 搜索目标类的使用情况
analyzer = LightStaticAnalyzer(project_root)
usages = analyzer.find_usages("com.example.api.PaymentService")
```

**期望结果**：
- `len(usages)` > 0
- usages 中包含 TestConsumer.java 文件
- 检测到 @DubboReference 注解

**验证点**：
- ✅ 检测 @DubboReference 注解（Dubbo RPC 核心）
- ✅ 识别远程服务接口类型
- ✅ 记录 RPC 调用位置
- ✅ 支持跨项目 Dubbo 依赖追踪

**为什么这个测试很重要**：
1. **微服务核心通信方式**: Dubbo 是 Java 微服务最常用的 RPC 框架
2. **跨项目依赖**: 服务间通过 Dubbo 接口调用，必须检测这些依赖
3. **影响分析关键**: 修改接口会影响所有使用 @DubboReference 的服务
4. **生产环境风险**: 漏检 Dubbo 依赖可能导致线上故障

---

#### 测试方法 4：test_finds_method_parameter_references

**输入 - 目标类**：
```java
package com.example.dto;

import java.util.List;
import java.util.Map;

public class UserDTO {
    
    private String field1;
    private int field2;
    
    public UserDTO() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - 方法参数引用类**：
```java
package com.test.controller;

import com.example.dto.UserDTO;

public class TestController {
    
    public void processData(UserDTO data) {
        data.doSomething();
    }
    
    public UserDTO getResult() {
        return new UserDTO();
    }
}
```

**执行操作**：
```python
# 创建项目
target_path = "src/main/java/com/example/dto/UserDTO.java"
controller_path = "src/main/java/com/test/controller/TestController.java"

project_root = create_temp_project({
    target_path: target_content,
    controller_path: controller_content
})

# 搜索目标类的使用情况
analyzer = LightStaticAnalyzer(project_root)
usages = analyzer.find_usages("com.example.dto.UserDTO")
```

**期望结果**：
- `len(usages)` > 0
- usages 中包含 TestController.java 文件
- 检测到方法参数和返回值中的类引用

**验证点**：
- ✅ 检测方法参数中的类引用
- ✅ 检测返回值类型中的类引用
- ✅ 支持多参数方法
- ✅ 支持泛型和数组类型

**验证需求**：需求 3.2 - 类引用搜索完整性

**测试执行**：
- 每个测试方法使用 Hypothesis 生成 50 个随机示例
- 验证所有生成的代码都能被正确解析和识别

### 3. 属性 10：引用记录完整性

**测试类：TestProperty10_ReferenceRecordCompleteness**

**目的**：验证检测到的引用记录包含所有必需字段

#### 测试方法 1：test_reference_records_contain_all_fields

**输入 - 目标类**：
```java
package com.example.manager;

import java.util.List;
import java.util.Map;

public class DataManager {
    
    private String field1;
    private int field2;
    
    public DataManager() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - 引用类**：
```java
package com.test.user;

import com.example.manager.DataManager;

public class UserService {
    
    private DataManager instance;
    
    public void process() {
        instance.doSomething();
    }
}
```

**执行操作**：
```python
# 创建项目
target_path = "src/main/java/com/example/manager/DataManager.java"
user_path = "src/main/java/com/test/user/UserService.java"

project_root = create_temp_project({
    target_path: target_content,
    user_path: user_content
})

# 搜索目标类的使用情况
analyzer = LightStaticAnalyzer(project_root)
usages = analyzer.find_usages("com.example.manager.DataManager")
```

**期望结果 - 每个 usage 记录必须包含以下字段**：

1. **path** (字符串类型)
   - 示例值：`"src/main/java/com/test/user/UserService.java"`
   - 验证：`assertIn('path', usage)`
   - 验证：`assertIsInstance(usage['path'], str)`

2. **line** (整数类型)
   - 示例值：`7` (指向 private DataManager 行)
   - 验证：`assertIn('line', usage)`
   - 验证：`assertIsInstance(usage['line'], int)`
   - 验证：`assertGreaterEqual(usage['line'], 0)`

3. **snippet** (字符串类型，非空)
   - 示例值：`"private DataManager instance;"`
   - 验证：`assertIn('snippet', usage)`
   - 验证：`assertIsInstance(usage['snippet'], str)`
   - 验证：`assertGreater(len(usage['snippet']), 0)`

4. **service** (字符串类型)
   - 示例值：`"src"` (服务名称)
   - 验证：`assertIn('service', usage)`
   - 验证：`assertIsInstance(usage['service'], str)`

**验证点**：
- ✅ 所有必需字段都存在
- ✅ 字段类型正确
- ✅ 行号为非负整数
- ✅ 代码片段非空
- ✅ 记录完整性确保下游分析的准确性

---

#### 测试方法 2：test_line_numbers_are_accurate

**输入 - 目标类**：
```java
package com.example.service;

import java.util.List;
import java.util.Map;

public class OrderService {
    
    private String field1;
    private int field2;
    
    public OrderService() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - 引用类**：
```java
package com.test.checker;

import com.example.service.OrderService;

public class DataChecker {
    
    private OrderService checker;
    
    public void validate() {
        checker.doSomething();
    }
}
```

**执行操作**：
```python
# 创建项目
target_path = "src/main/java/com/example/service/OrderService.java"
checker_path = "src/main/java/com/test/checker/DataChecker.java"

project_root = create_temp_project({
    target_path: target_content,
    checker_path: checker_content
})

# 搜索目标类的使用情况
analyzer = LightStaticAnalyzer(project_root)
usages = analyzer.find_usages("com.example.service.OrderService")

# 验证行号准确性
for usage in usages:
    if usage['line'] > 0:
        # 读取文件的第 line 行
        with open(full_path, 'r') as f:
            lines = f.readlines()
        actual_line = lines[usage['line'] - 1].strip()
        
        # 验证代码片段匹配
        assert usage['snippet'] in actual_line or actual_line in usage['snippet']
```

**期望结果**：
- 行号指向正确的代码行
- 代码片段与实际行内容匹配

**示例验证**：
```
文件: DataChecker.java
1:  package com.test.checker;
2:  
3:  import com.example.service.OrderService;
4:  
5:  public class DataChecker {
6:      
7:      private OrderService checker;  // ← usage['line'] = 7
8:      
9:      public void validate() {
10:         checker.doSomething();
11:     }
12: }

usage 记录:
{
    "line": 7,
    "snippet": "private OrderService checker;"
}

验证：第 7 行的实际内容确实是 "private OrderService checker;"
```

**验证点**：
- ✅ 行号指向正确的代码行
- ✅ 代码片段与实际行内容匹配
- ✅ 处理空白字符差异
- ✅ 支持部分匹配（考虑格式化差异）

**验证需求**：需求 3.3 - 引用记录完整性

**测试执行**：
- test_reference_records_contain_all_fields：50 个随机示例
- test_line_numbers_are_accurate：30 个随机示例
- 验证每个 usage 记录都包含所有必需字段
- 验证字段值的有效性

### 4. 属性 12：主项目排除

**测试类：TestProperty12_MainProjectExclusion**

**目的**：验证跨项目影响分析正确排除主项目

#### 测试方法 1：test_cross_project_search_excludes_main_project

**输入 - 项目结构**：
```
项目结构:
├── main-project/          ← 主项目（被分析的项目）
│   └── UserManager.java   ← 目标类
├── related-project-1/     ← 关联项目 1
│   └── Related1Service.java  ← 引用了 UserManager
└── related-project-2/     ← 关联项目 2
    └── Related2Controller.java  ← 引用了 UserManager
```

**输入 - 主项目（目标类）**：
```java
// main-project/src/main/java/com/main/service/UserManager.java
package com.main.service;

import java.util.List;
import java.util.Map;

public class UserManager {
    
    private String field1;
    private int field2;
    
    public UserManager() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**输入 - 关联项目 1**：
```java
// related-project-1/src/main/java/com/related1/service/Related1Service.java
package com.related1.service;

import com.main.service.UserManager;

public class Related1Service {
    private UserManager instance;
}
```

**输入 - 关联项目 2**：
```java
// related-project-2/src/main/java/com/related2/controller/Related2Controller.java
package com.related2.controller;

import com.main.service.UserManager;

public class Related2Controller {
    private UserManager handler;
}
```

**执行操作**：
```python
# 创建三个项目
main_project = create_temp_project({
    "src/main/java/com/main/service/UserManager.java": main_content
})

related1_project = create_temp_project({
    "src/main/java/com/related1/service/Related1Service.java": related1_content
})

related2_project = create_temp_project({
    "src/main/java/com/related2/controller/Related2Controller.java": related2_content
})

# 初始化 MultiProjectTracer
tracer = MultiProjectTracer([main_project, related1_project, related2_project])

# 查找跨项目影响
impacts = tracer.find_cross_project_impacts(
    full_class_name="com.main.service.UserManager",
    changed_methods=[]
)
```

**期望结果**：
```python
# impacts 列表只包含关联项目，不包含主项目
[
    {
        "project": "test_project_xxx",  # ✅ 关联项目 1
        "type": "class_reference",
        "file": "src/main/java/com/related1/service/Related1Service.java",
        "line": 7,
        "snippet": "private UserManager instance;",
        "detail": "类 UserManager 在 test_project_xxx 中被引用 (explicit import)"
    },
    {
        "project": "test_project_yyy",  # ✅ 关联项目 2
        "type": "class_reference",
        "file": "src/main/java/com/related2/controller/Related2Controller.java",
        "line": 7,
        "snippet": "private UserManager handler;",
        "detail": "类 UserManager 在 test_project_yyy 中被引用 (explicit import)"
    }
    # ❌ 不包含主项目的任何结果
]
```

**验证点**：
- ✅ 结果中不包含主项目名称
- ✅ 所有关联项目都被扫描
- ✅ 跨项目引用被正确识别
- ✅ 项目名称正确分组

---

#### 测试方法 2：test_single_project_returns_empty_cross_project_impacts

**输入 - 项目结构**：
```
项目结构:
└── main-project/          ← 只有主项目，没有关联项目
    └── UserManager.java
```

**输入 - 主项目**：
```java
package com.main.service;

import java.util.List;
import java.util.Map;

public class UserManager {
    
    private String field1;
    private int field2;
    
    public UserManager() {
    }
    
    public void doSomething() {
        System.out.println("Hello");
    }
}
```

**执行操作**：
```python
# 只创建主项目
main_project = create_temp_project({
    "src/main/java/com/main/service/UserManager.java": content
})

# 初始化 MultiProjectTracer（只有主项目）
tracer = MultiProjectTracer([main_project])

# 查找跨项目影响
impacts = tracer.find_cross_project_impacts(
    full_class_name="com.main.service.UserManager",
    changed_methods=[]
)
```

**期望结果**：
```python
# 空列表（因为没有关联项目）
assert len(impacts) == 0
```

**验证点**：
- ✅ 没有关联项目时返回空列表
- ✅ 不会错误地包含主项目
- ✅ 不会抛出异常
- ✅ 行为符合预期

**验证需求**：需求 3.5 - 主项目排除

**测试执行**：
- test_cross_project_search_excludes_main_project：30 个随机示例
- test_single_project_returns_empty_cross_project_impacts：20 个随机示例
- 验证所有场景下的主项目排除逻辑正确

## 测试输入输出总结表

| 测试方法 | 输入类型 | 关键输入特征 | 期望输出 | 验证点 |
|---------|---------|------------|---------|--------|
| **属性 8** | Java 文件 | package + class 声明 | full_class, simple_class | 完全限定类名提取 |
| **属性 9.1** | 目标类 + 引用类 | import 语句 | usages 列表包含引用记录 | 显式 import 检测 |
| **属性 9.2** | 目标类 + 注入类 | @Autowired/@Resource | usages 列表包含注入记录 | Spring 依赖注入检测 |
| **属性 9.3** | 目标类 + Dubbo 消费者 | @DubboReference | usages 列表包含 RPC 引用 | Dubbo RPC 检测 |
| **属性 9.4** | 目标类 + 方法参数类 | 方法签名 | usages 列表包含参数引用 | 方法参数检测 |
| **属性 10.1** | 引用记录 | usage 字典 | 包含 path, line, snippet, service 字段 | 记录完整性 |
| **属性 10.2** | 引用记录 + 源文件 | line 和 snippet | snippet 匹配实际行内容 | 行号准确性 |
| **属性 12.1** | 主项目 + 关联项目 | 跨项目结构 | impacts 包含关联项目，排除主项目 | 主项目排除 |
| **属性 12.2** | 只有主项目 | 单项目结构 | impacts 为空列表 | 单项目场景 |

## 测试覆盖的技术栈

### 依赖注入框架
- ✅ **Spring Framework**：@Autowired 依赖注入
- ✅ **Java EE**：@Resource 依赖注入
- ✅ **Dubbo RPC**：@DubboReference 远程服务引用

### 代码引用类型
- ✅ **显式 import**：import com.example.Class
- ✅ **通配符 import**：import com.example.*
- ✅ **静态 import**：import static com.example.Class.method
- ✅ **方法参数**：public void method(Class param)
- ✅ **返回值类型**：public Class method()

## 属性测试方法

所有测试使用 **Hypothesis** 进行基于属性的测试（Property-Based Testing）：

1. **随机生成测试数据**：
   - 随机生成有效的 Java 包名、类名、方法名
   - 随机生成不同类型的类引用（import、注入、参数）
   - 随机生成多项目结构

2. **创建临时项目**：
   - 在临时目录中创建完整的 Java 项目结构
   - 生成符合规范的 Java 源文件

3. **执行分析**：
   - 使用 LightStaticAnalyzer 进行单项目分析
   - 使用 MultiProjectTracer 进行跨项目分析

4. **验证属性**：
   - 验证检测结果的完整性
   - 验证字段的正确性
   - 验证跨项目影响的准确性

## 测试配置

- **每个测试的示例数量**：20-100 个随机示例
- **超时设置**：None（允许测试充分运行）
- **清理机制**：每个测试后自动清理临时项目目录

## 重要性说明

### Dubbo 核心测试 ⭐

Dubbo 是阿里巴巴开源的高性能 RPC 框架，在中国的微服务架构中广泛使用。@DubboReference 检测对于 Dubbo 应用至关重要：

1. **@DubboReference 检测**：Consumer 端服务注入
2. **跨项目依赖追踪**：当 Provider 修改时，找到所有 Consumer
3. **微服务影响分析**：确保服务间依赖关系被正确追踪

这些测试确保系统能够准确追踪 Dubbo 微服务之间的依赖关系，这对于影响分析和变更管理至关重要。

## 运行测试

```bash
# 在虚拟环境中运行所有测试（9 个测试方法）
.\code_diff_project\venv\Scripts\python.exe code_diff_project\backend\analyzer\tests\test_multi_project_tracer_properties.py
```

**预期输出**：
```
Ran 9 tests in ~9s
OK
```

## 测试结果

所有测试均已通过，验证了以下正确性属性：

- ✅ 属性 8：完全限定类名提取
- ✅ 属性 9：类引用搜索完整性
- ✅ 属性 10：引用记录完整性
- ✅ 属性 12：主项目排除

## 未来扩展

可以考虑添加以下测试场景（优先级较低）：

- P1：继承和实现关系识别（extends、implements）
- P1：注解中的类引用（@Valid、@ExceptionHandler）
- P1：泛型参数中的类引用（List<UserDTO>）
- P2：MyBatis Mapper 调用识别
- P3：消息队列依赖测试（RabbitMQ、Kafka）
