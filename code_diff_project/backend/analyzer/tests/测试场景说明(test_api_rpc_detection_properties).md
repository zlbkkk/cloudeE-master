# RPC 和 API 调用检测属性测试场景说明

## 概述

本文档说明了 `test_api_rpc_detection_properties.py` 中实现的属性测试场景。这些测试覆盖了跨项目分析中的 RPC 和 API 调用检测功能。

## 测试文件结构

`test_api_rpc_detection_properties.py` 包含 4 个测试类，共 9 个测试方法：
- **TestProperty13_APIEndpointIdentification** (1 个测试方法)
- **TestProperty14_RPCAndAPICallDetection** (5 个测试方法)
- **TestProperty15_CallRecordCompleteness** (1 个测试方法)
- **TestProperty16_CrossProjectDubboDependencyTracking** (2 个测试方法)

## 测试场景详解

### 1. 属性 13：API 端点识别

**测试类：TestProperty13_APIEndpointIdentification**

**目的**：验证系统能够正确识别 Spring 框架的 API 端点注解

**测试方法：test_identifies_api_endpoints_with_annotations**

这是一个基于属性的测试，使用 Hypothesis 生成随机的 Controller 类，验证系统能够正确解析各种 API 注解。

#### 测试场景 1：识别 @GetMapping 注解

**输入**：
```java
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class UserController {
    
    @GetMapping("/users")
    public String getUsers() {
        return "success";
    }
}
```

**期望结果**：
- 文件能够被成功解析
- 内容包含 `@GetMapping` 注解
- 内容包含路径 `/users`
- 完整 API 路径为 `/api/users`

#### 测试场景 2：识别带路径变量的 @PostMapping

**输入**：
```java
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class OrderController {
    
    @PostMapping("/orders/{orderId}")
    public String createOrder(@PathVariable Long orderId) {
        return "success";
    }
}
```

**期望结果**：
- 文件能够被成功解析
- 内容包含 `@PostMapping` 注解
- 内容包含 `@PathVariable` 注解
- 路径包含路径变量 `{orderId}`
- 完整 API 路径为 `/api/orders/{orderId}`

#### 测试场景 3：识别带请求参数的 @PutMapping

**输入**：
```java
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ProductController {
    
    @PutMapping("/products")
    public String updateProduct(@RequestParam String name) {
        return "success";
    }
}
```

**期望结果**：
- 文件能够被成功解析
- 内容包含 `@PutMapping` 注解
- 内容包含 `@RequestParam` 注解
- 路径为 `/products`
- 完整 API 路径为 `/api/products`

#### 测试场景 4：识别 @DeleteMapping 注解

**输入**：
```java
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class CommentController {
    
    @DeleteMapping("/comments/{id}")
    public String deleteComment(@PathVariable Long id) {
        return "success";
    }
}
```

**期望结果**：
- 文件能够被成功解析
- 内容包含 `@DeleteMapping` 注解
- 内容包含 `@PathVariable` 注解
- 路径包含路径变量 `{id}`
- 完整 API 路径为 `/api/comments/{id}`

#### 测试场景 5：识别 @RequestMapping 注解

**输入**：
```java
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class DataController {
    
    @RequestMapping("/data")
    public String getData() {
        return "success";
    }
}
```

**期望结果**：
- 文件能够被成功解析
- 内容包含 `@RequestMapping` 注解
- 路径为 `/data`
- 完整 API 路径为 `/api/data`

**验证需求**：需求 4.1 - API 端点识别

**测试执行**：
- 使用 Hypothesis 生成 50 个随机 Controller 示例
- 每个示例随机选择 HTTP 方法（GET/POST/PUT/DELETE/REQUEST）
- 随机决定是否包含路径变量和请求参数
- 验证所有生成的 Controller 都能被正确解析

### 2. 属性 14：RPC 和 API 调用检测

**测试类：TestProperty14_RPCAndAPICallDetection**

**目的**：验证系统能够检测各种 RPC 和 API 调用模式

#### 测试方法 1：test_detects_dubbo_reference_injection ⭐ Dubbo 核心

**输入 - Dubbo 服务接口**：
```java
package com.example.service;

public interface UserService {
    String getUserById(Long id);
    void updateData(String data);
}
```

**输入 - Dubbo 服务消费者**：
```java
package com.test.consumer;

import com.example.service.UserService;
import org.apache.dubbo.config.annotation.DubboReference;

public class TestConsumer {
    
    @DubboReference
    private UserService service;
    
    public String callService(Long id) {
        return service.getUserById(id);
    }
}
```

**期望结果**：
- LightStaticAnalyzer 能够找到 `com.example.service.UserService` 的使用情况
- 返回的 usages 列表长度 > 0
- usages 中包含 TestConsumer.java 文件
- 每个 usage 记录包含：
  - `path`: 文件路径（包含 TestConsumer.java）
  - `line`: 行号（指向 @DubboReference 或 private UserService 行）
  - `snippet`: 代码片段
  - `service`: 服务名称

**验证点**：
- ✅ 系统能识别 @DubboReference 注解
- ✅ 系统能追踪 Dubbo 服务接口的引用
- ✅ 这对于微服务架构的依赖分析至关重要

---

#### 测试方法 2：test_detects_dubbo_method_calls ⭐ Dubbo 核心

**输入 - Dubbo 服务接口**：
```java
package com.example.api;

public interface OrderService {
    String processOrder(Long orderId);
    void updateData(String data);
}
```

**输入 - 业务服务调用 Dubbo 方法**：
```java
package com.test.service;

import com.example.api.OrderService;
import org.apache.dubbo.config.annotation.DubboReference;

public class BusinessService {
    
    @DubboReference
    private OrderService remoteService;
    
    public String processData(Long id) {
        String result = remoteService.processOrder(id);
        return "Processed: " + result;
    }
}
```

**期望结果**：
- 文件内容包含 `remoteService.processOrder(id)` 方法调用
- 系统能够识别对 Dubbo 注入服务的方法调用
- 代码片段中包含完整的方法调用语句

**验证点**：
- ✅ 系统能识别 Dubbo 服务的方法调用
- ✅ 能够追踪从 Consumer 到 Provider 的调用链

---

#### 测试方法 3：test_detects_feign_client_definitions

**输入 - Feign Client 接口**：
```java
package com.example.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

@FeignClient(name = "user-service", url = "${user.service.url}")
public interface UserClient {
    
    @GetMapping("/api/users/{id}")
    String getUserById(@PathVariable Long id);
}
```

**期望结果**：
- 文件内容包含 `@FeignClient` 注解
- 文件内容包含 `@GetMapping` 注解
- 文件内容包含 API 路径 `/api/users/{id}`
- 文件内容包含 `@PathVariable` 注解

**验证点**：
- ✅ 系统能识别 Feign Client 声明式 HTTP 客户端
- ✅ 能够解析 Feign 接口中的 API 映射

---

#### 测试方法 4：test_detects_rest_template_calls

**输入 - RestTemplate 调用者**：
```java
package com.example.client;

import org.springframework.web.client.RestTemplate;
import org.springframework.beans.factory.annotation.Autowired;

public class ApiClient {
    
    @Autowired
    private RestTemplate restTemplate;
    
    public String fetchData(Long id) {
        String url = "http://user-service/api/users/" + id;
        return restTemplate.getForObject(url, String.class);
    }
}
```

**期望结果**：
- 文件内容包含 `RestTemplate` 类型声明
- 文件内容包含 `restTemplate.getForObject` 方法调用
- 能够识别 HTTP 调用模式

**验证点**：
- ✅ 系统能识别传统的 RestTemplate HTTP 客户端
- ✅ 能够追踪 getForObject、postForObject 等方法调用

---

#### 测试方法 5：test_detects_webclient_calls

**输入 - WebClient 调用者**：
```java
package com.example.reactive;

import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

public class ReactiveClient {
    
    private final WebClient webClient;
    
    public ReactiveClient(WebClient.Builder webClientBuilder) {
        this.webClient = webClientBuilder.baseUrl("http://user-service").build();
    }
    
    public Mono<String> fetchUser(Long id) {
        return webClient.get()
            .uri("/api/users/{id}", id)
            .retrieve()
            .bodyToMono(String.class);
    }
}
```

**期望结果**：
- 文件内容包含 `WebClient` 类型声明
- 文件内容包含 `webClient.get()` 方法调用
- 文件内容包含 `.retrieve()` 方法调用
- 能够识别响应式 HTTP 调用模式

**验证点**：
- ✅ 系统能识别响应式 WebClient HTTP 客户端
- ✅ 支持 Spring WebFlux 响应式编程模式

**验证需求**：需求 4.2 - RPC 和 API 调用检测

**测试执行**：
- 每个测试方法使用 Hypothesis 生成 20-30 个随机示例
- 验证所有生成的代码都能被正确解析和识别

### 3. 属性 15：调用记录完整性

**测试类：TestProperty15_CallRecordCompleteness**

**目的**：验证检测到的调用记录包含所有必需字段

#### 测试方法：test_dubbo_call_records_contain_required_fields

**输入 - Dubbo 服务接口**：
```java
package com.example.service;

public interface DataService {
    String fetchData(Long id);
    void updateData(String data);
}
```

**输入 - Dubbo 服务消费者**：
```java
package com.test.app;

import com.example.service.DataService;
import org.apache.dubbo.config.annotation.DubboReference;

public class AppService {
    
    @DubboReference
    private DataService dubboService;
    
    public void execute() {
        dubboService.fetchData(123L);
    }
}
```

**期望结果 - 每个 usage 记录必须包含以下字段**：

1. **path** (字符串类型)
   - 示例值：`"src/main/java/com/test/app/AppService.java"`
   - 验证：`assertIn('path', usage)`
   - 验证：`assertIsInstance(usage['path'], str)`

2. **line** (整数类型)
   - 示例值：`8` (指向 @DubboReference 或 private DataService 行)
   - 验证：`assertIn('line', usage)`
   - 验证：`assertIsInstance(usage['line'], int)`
   - 验证：`assertGreaterEqual(usage['line'], 0)`

3. **snippet** (字符串类型，非空)
   - 示例值：`"@DubboReference"` 或 `"private DataService dubboService;"`
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

**验证需求**：需求 4.3 - 调用记录完整性

**测试执行**：
- 使用 Hypothesis 生成 20 个随机 Dubbo 服务示例
- 验证每个 usage 记录都包含所有必需字段
- 验证字段值的有效性

### 4. 属性 16：跨项目 Dubbo 依赖追踪

**测试类：TestProperty16_CrossProjectDubboDependencyTracking**

**目的**：验证跨项目 Dubbo 依赖追踪功能 ⭐ Dubbo 核心

#### 测试方法 1：test_finds_dubbo_references_across_projects ⭐ 核心场景

这是跨项目分析的核心测试，验证当主项目的 Dubbo Provider 被修改时，系统能够找到所有关联项目中的 Consumer。

**输入 - 主项目（Provider 端）**

文件 1：`main-project/src/main/java/com/example/service/UserService.java`
```java
package com.example.service;

public interface UserService {
    String getUserById(Long id);
    void updateData(String data);
}
```

文件 2：`main-project/src/main/java/com/main/provider/UserServiceImpl.java`
```java
package com.main.provider;

import com.example.service.UserService;
import org.apache.dubbo.config.annotation.DubboService;

@DubboService
public class UserServiceImpl implements UserService {
    
    @Override
    public String getUserById(Long id) {
        return "result-" + id;
    }
    
    @Override
    public void updateData(String data) {
        System.out.println("Updating: " + data);
    }
}
```

**输入 - 关联项目（Consumer 端）**

文件：`related-project/src/main/java/com/related/consumer/RelatedConsumer.java`
```java
package com.related.consumer;

import com.example.service.UserService;
import org.apache.dubbo.config.annotation.DubboReference;

public class RelatedConsumer {
    
    @DubboReference
    private UserService remoteService;
    
    public String callRemote(Long id) {
        return remoteService.getUserById(id);
    }
}
```

**执行操作**：
```python
# 初始化 MultiProjectTracer，传入主项目和关联项目
tracer = MultiProjectTracer([main_project, related_project])

# 查找跨项目影响
impacts = tracer.find_cross_project_impacts(
    "com.example.service.UserService",  # 被修改的接口
    ["getUserById"]  # 被修改的方法
)
```

**期望结果**：

1. **impacts 列表长度 > 0**
   - 验证：`assertGreater(len(impacts), 0)`
   - 说明：找到了跨项目影响

2. **关联项目在结果中**
   - 期望：`impacts` 中包含 `related_project` 的影响记录
   - 验证：`assertIn(related_project_name, found_projects)`
   - 示例影响记录：
     ```python
     {
         "project": "test_project_xxx",  # 关联项目名称
         "type": "class_reference",
         "file": "src/main/java/com/related/consumer/RelatedConsumer.java",
         "line": 8,
         "snippet": "@DubboReference",
         "detail": "类 UserService 在 test_project_xxx 中被引用 (explicit import)"
     }
     ```

3. **主项目被排除**
   - 期望：`impacts` 中不包含主项目的影响
   - 验证：`assertNotIn(main_project_name, found_projects)`
   - 说明：跨项目分析只关注关联项目，不包括主项目自身

**验证点**：
- ✅ 当 Provider 实现被修改时，能找到所有 Consumer
- ✅ 跨项目依赖追踪准确
- ✅ 主项目正确排除
- ✅ 这是微服务影响分析的核心功能

---

#### 测试方法 2：test_tracks_dubbo_with_multiple_registries

这个测试验证系统能够处理使用不同注册中心的 Dubbo 服务。

**输入 - 主项目（使用 operation 注册中心）**

文件：`main-project/src/main/java/com/main/service/PaymentServiceImpl.java`
```java
package com.main.service;

import com.example.api.PaymentService;
import org.apache.dubbo.config.annotation.DubboService;

@DubboService(registry = "operation")
public class PaymentServiceImpl implements PaymentService {
    
    @Override
    public String processPayment(Long id) {
        return "operation-result-" + id;
    }
    
    @Override
    public void updateData(String data) {
        System.out.println("Operation registry: " + data);
    }
}
```

**输入 - 关联项目（使用相同注册中心）**

文件：`related-project/src/main/java/com/related/client/OperationClient.java`
```java
package com.related.client;

import com.example.api.PaymentService;
import org.apache.dubbo.config.annotation.DubboReference;

public class OperationClient {
    
    @DubboReference(registry = "operation")
    private PaymentService operationService;
    
    public String callOperation(Long id) {
        return operationService.processPayment(id);
    }
}
```

**执行操作**：
```python
# 初始化 MultiProjectTracer
tracer = MultiProjectTracer([main_project, related_project])

# 查找跨项目影响
impacts = tracer.find_cross_project_impacts(
    "com.example.api.PaymentService",
    ["processPayment"]
)
```

**期望结果**：

1. **文件内容包含 registry 参数**
   - 验证：`assertIn('registry = "operation"', content)`
   - 说明：正确识别了注册中心配置

2. **找到跨项目影响**
   - 验证：`assertGreater(len(impacts), 0)`
   - 说明：即使使用自定义注册中心，依然能追踪依赖

3. **影响记录完整**
   - 期望影响记录包含关联项目的 @DubboReference 引用
   - 验证系统能处理复杂的注册中心配置

**验证点**：
- ✅ 支持多注册中心场景
- ✅ 能够追踪使用不同注册中心的服务
- ✅ 适用于复杂的微服务部署环境（如：业务注册中心、运营注册中心分离）

**验证需求**：需求 4.2, 4.3 - 跨项目 Dubbo 依赖追踪

**测试执行**：
- test_finds_dubbo_references_across_projects：20 个随机示例
- test_tracks_dubbo_with_multiple_registries：15 个随机示例
- 验证所有场景下的跨项目依赖追踪准确性

## 测试输入输出总结表

| 测试方法 | 输入类型 | 关键输入特征 | 期望输出 | 验证点 |
|---------|---------|------------|---------|--------|
| **属性 13** | Spring Controller | @GetMapping, @PostMapping 等注解 | 文件解析成功，注解被识别 | API 端点识别 |
| **属性 14.1** | Dubbo Consumer | @DubboReference 注解 | usages 列表包含引用记录 | Dubbo 服务注入识别 |
| **属性 14.2** | Dubbo 方法调用 | remoteService.method() | 代码片段包含方法调用 | Dubbo 方法调用识别 |
| **属性 14.3** | Feign Client | @FeignClient 注解 | 文件包含 Feign 注解 | Feign 客户端识别 |
| **属性 14.4** | RestTemplate | restTemplate.getForObject() | 文件包含 RestTemplate 调用 | RestTemplate 识别 |
| **属性 14.5** | WebClient | webClient.get().retrieve() | 文件包含 WebClient 调用 | WebClient 识别 |
| **属性 15** | Dubbo 引用记录 | usage 字典 | 包含 path, line, snippet, service 字段 | 记录完整性 |
| **属性 16.1** | 主项目 Provider + 关联项目 Consumer | 跨项目结构 | impacts 包含关联项目，排除主项目 | 跨项目依赖追踪 |
| **属性 16.2** | 多注册中心配置 | registry = "operation" | 找到跨项目影响 | 多注册中心支持 |

## 测试覆盖的技术栈

### RPC 框架
- ✅ **Dubbo**：@DubboReference、@DubboService、多注册中心
- ✅ **Feign**：@FeignClient、声明式 HTTP 客户端

### HTTP 客户端
- ✅ **RestTemplate**：传统的同步 HTTP 客户端
- ✅ **WebClient**：响应式 HTTP 客户端

### API 注解
- ✅ **Spring MVC**：@RequestMapping、@GetMapping、@PostMapping、@PutMapping、@DeleteMapping
- ✅ **参数注解**：@PathVariable、@RequestParam

## 属性测试方法

所有测试使用 **Hypothesis** 进行基于属性的测试（Property-Based Testing）：

1. **随机生成测试数据**：
   - 随机生成有效的 Java 包名、类名、方法名
   - 随机生成 API 路径和 HTTP 方法
   - 随机生成 Dubbo 服务接口和实现

2. **创建临时项目**：
   - 在临时目录中创建完整的 Java 项目结构
   - 生成符合规范的 Java 源文件

3. **执行分析**：
   - 使用 LightStaticAnalyzer 和 ApiUsageTracer 进行分析
   - 使用 MultiProjectTracer 进行跨项目分析

4. **验证属性**：
   - 验证检测结果的完整性
   - 验证字段的正确性
   - 验证跨项目影响的准确性

## 测试配置

- **每个测试的示例数量**：20-50 个随机示例
- **超时设置**：None（允许测试充分运行）
- **清理机制**：每个测试后自动清理临时项目目录

## 重要性说明

### Dubbo 核心测试 ⭐

Dubbo 是阿里巴巴开源的高性能 RPC 框架，在中国的微服务架构中广泛使用。以下测试对于 Dubbo 应用至关重要：

1. **@DubboReference 检测**：Consumer 端服务注入
2. **@DubboService 检测**：Provider 端服务暴露
3. **跨项目依赖追踪**：当 Provider 修改时，找到所有 Consumer
4. **多注册中心支持**：支持复杂的服务注册场景

这些测试确保系统能够准确追踪 Dubbo 微服务之间的依赖关系，这对于影响分析和变更管理至关重要。

## 运行测试

```bash
# 在虚拟环境中运行所有测试（9 个测试方法）
.\code_diff_project\venv\Scripts\python.exe code_diff_project\backend\analyzer\tests\test_api_rpc_detection_properties.py
```

**预期输出**：
```
Ran 9 tests in ~4-5s
OK
```

## 测试结果

所有测试均已通过，验证了以下正确性属性：

- ✅ 属性 13：API 端点识别
- ✅ 属性 14：RPC 和 API 调用检测
- ✅ 属性 15：调用记录完整性
- ✅ 属性 16：跨项目 Dubbo 依赖追踪

## 未来扩展

可以考虑添加以下测试场景（优先级较低）：

- P1：MyBatis Mapper 调用识别
- P2：消息队列依赖测试（RabbitMQ、Kafka）
- P3：HTTP 原生调用识别（HttpURLConnection、OkHttp）
- P3：JPA Repository 方法调用识别
