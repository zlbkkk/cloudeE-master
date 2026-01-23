# Dubbo 调用关系详解

## 项目概述

本文档详细说明三个项目（common-api、service-a、service-b）之间的 Dubbo RPC 调用关系。

---

## 一、项目角色定位

### 1. common-api（接口契约层）
- **角色**: Dubbo 接口定义项目
- **职责**: 定义服务接口和数据传输对象（DTO）
- **被依赖方**: 被 service-a 和 service-b 同时依赖

### 2. service-a（服务提供者 Provider）
- **角色**: Dubbo 服务提供者
- **职责**: 实现 common-api 中定义的接口，提供订单服务
- **依赖**: common-api
- **暴露**: 通过 `@DubboService` 注解暴露服务

### 3. service-b（服务消费者 Consumer）
- **角色**: Dubbo 服务消费者
- **职责**: 调用 service-a 提供的订单服务
- **依赖**: common-api
- **引用**: 通过 `@DubboReference` 注解引用远程服务

---

## 二、Maven 依赖关系

### service-a 的 pom.xml
```xml
<dependencies>
    <!-- 依赖 common-api 获取接口定义 -->
    <dependency>
        <groupId>com.example</groupId>
        <artifactId>common-api</artifactId>
        <version>1.0.0</version>
    </dependency>
    
    <!-- Dubbo 依赖 -->
    <dependency>
        <groupId>org.apache.dubbo</groupId>
        <artifactId>dubbo-spring-boot-starter</artifactId>
    </dependency>
</dependencies>
```

### service-b 的 pom.xml
```xml
<dependencies>
    <!-- 依赖 common-api 获取接口定义 -->
    <dependency>
        <groupId>com.example</groupId>
        <artifactId>common-api</artifactId>
        <version>1.0.0</version>
    </dependency>
    
    <!-- Dubbo 依赖 -->
    <dependency>
        <groupId>org.apache.dubbo</groupId>
        <artifactId>dubbo-spring-boot-starter</artifactId>
    </dependency>
</dependencies>
```

---

## 三、代码层面的引用关系

### 1. common-api：定义接口契约

**文件**: `common-api/src/main/java/com/example/common/service/OrderService.java`

```java
package com.example.common.service;

import com.example.common.dto.OrderDTO;
import java.util.List;

/**
 * 订单服务接口
 * 用于跨项目共享订单服务定义
 */
public interface OrderService {
    
    /**
     * 根据订单ID获取订单
     */
    OrderDTO getOrderById(Long orderId);
    
    /**
     * 获取订单状态文本描述
     * 用于 Dubbo RPC 调用测试
     */
    String getOrderStatusText(Long orderId);
    
    /**
     * 获取订单详细信息（包含状态文本）
     */
    String getOrderDetails(Long orderId);
    
    /**
     * 获取订单摘要信息（用于测试 Dubbo RPC 调用）
     * @param orderId 订单ID
     * @return 订单摘要信息，格式：订单号-金额-状态
     */
    String getOrderSummary(Long orderId);
}
```

**关键点**:
- 这是一个纯 Java 接口，没有任何实现
- 定义了服务契约，规定了方法签名和返回类型
- 被 service-a 实现，被 service-b 调用

---

### 2. service-a：实现接口（Provider）

**文件**: `service-a/src/main/java/com/example/servicea/service/OrderServiceImpl.java`

**⚠️ 当前状态说明**：
- 当前代码中**只有 `@Service` 注解**，还没有添加 `@DubboService` 注解
- 这意味着当前的 Dubbo RPC 调用**尚未完全配置**
- 要真正实现 Dubbo RPC，需要添加 `@DubboService` 注解

**当前代码**：
```java
package com.example.servicea.service;

import com.example.common.dto.OrderDTO;
import com.example.common.service.OrderService;  // ← 引用 common-api 的接口
import org.springframework.stereotype.Service;

/**
 * 订单服务实现
 * 实现 common-api 中的 OrderService 接口
 */
@Service  // ← 当前只有 Spring 的 @Service 注解
public class OrderServiceImpl implements OrderService {

    @Override
    public String getOrderSummary(Long orderId) {
        OrderDTO order = getOrderById(orderId);
        if (order == null) {
            return "订单不存在";
        }
        
        String statusText = getOrderStatusText(orderId);
        
        // 返回简化的摘要信息
        return String.format(
            "%s-¥%.2f-%s",
            order.getOrderNumber(),
            order.getTotalAmount(),
            statusText
        );
    }
}
```

**完整的 Dubbo Provider 配置应该是**：
```java
package com.example.servicea.service;

import com.example.common.dto.OrderDTO;
import com.example.common.service.OrderService;
import org.apache.dubbo.config.annotation.DubboService;  // ← 需要导入 Dubbo 注解
import org.springframework.stereotype.Service;

@Service
@DubboService  // ← 需要添加这个注解才能暴露为 Dubbo 服务
public class OrderServiceImpl implements OrderService {
    // ... 实现代码
}
```

**关键点**:
1. **import 语句**: `import com.example.common.service.OrderService;` - 引用 common-api 的接口
2. **implements 关键字**: `implements OrderService` - 实现接口
3. **@Service 注解**: Spring Bean，可以被本地注入
4. **@DubboService 注解（需要添加）**: 将此服务暴露为 Dubbo RPC 服务，供其他服务调用

---

### 3. service-b：调用远程服务（Consumer）

**文件**: `service-b/src/main/java/com/example/serviceb/service/NotificationService.java`

**✅ 当前状态说明**：
- service-b 中**已经配置了 `@DubboReference` 注解**
- 但由于 service-a 还没有添加 `@DubboService`，所以 Dubbo 调用**目前无法正常工作**
- 这是一个**准备好的 Consumer 配置**，等待 Provider 端完成配置

**当前代码**：
```java
package com.example.serviceb.service;

import com.example.common.dto.OrderDTO;
import com.example.common.service.OrderService;  // ← 引用 common-api 的接口
import org.apache.dubbo.config.annotation.DubboReference;  // ← Dubbo 引用注解
import org.springframework.stereotype.Service;

/**
 * 通知服务 - 使用 Dubbo RPC 调用 service-a 的订单服务
 */
@Service
public class NotificationService {

    /**
     * 通过 Dubbo RPC 注入 OrderService
     * 这是跨服务调用的关键：service-b 通过 Dubbo 调用 service-a 的接口
     */
    @DubboReference  // ← 关键注解：引用远程 Dubbo 服务
    private OrderService orderService;

    /**
     * 发送订单摘要通知
     */
    public String sendOrderSummaryNotification(Long orderId) {
        // 【Dubbo RPC 调用】获取订单摘要信息
        // 这里调用的是 service-a 的 OrderServiceImpl.getOrderSummary()
        String orderSummary = orderService.getOrderSummary(orderId);
        
        // 【Dubbo RPC 调用】获取订单基本信息
        OrderDTO order = orderService.getOrderById(orderId);
        
        // 发送通知
        String message = String.format("订单摘要通知：%s", orderSummary);
        return sendEmailNotification(user, message);
    }
}
```

**关键点**:
1. **import 语句**: `import com.example.common.service.OrderService;` - 引用 common-api 的接口
2. **@DubboReference 注解**: 引用远程 Dubbo 服务，Dubbo 会自动创建代理对象
3. **调用方式**: `orderService.getOrderSummary(orderId)` - 看起来像本地调用，实际是远程 RPC 调用
4. **⚠️ 注意**: 目前由于 service-a 没有 `@DubboService`，这个调用会失败

---

### 4. service-b：暴露 HTTP API

**文件**: `service-b/src/main/java/com/example/serviceb/controller/NotificationController.java`

```java
package com.example.serviceb.controller;

import com.example.serviceb.service.NotificationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private NotificationService notificationService;

    /**
     * 发送订单摘要通知
     * 调用链：HTTP → Service → Dubbo RPC
     */
    @PostMapping("/order-summary")
    public String sendOrderSummaryNotification(@RequestParam Long orderId) {
        return notificationService.sendOrderSummaryNotification(orderId);
    }
}
```

---

## 四、完整调用链图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         完整调用链                                    │
└─────────────────────────────────────────────────────────────────────┘

1. HTTP 请求
   ↓
   POST /api/notifications/order-summary?orderId=123
   ↓
2. service-b: NotificationController.sendOrderSummaryNotification()
   ↓
3. service-b: NotificationService.sendOrderSummaryNotification()
   ↓
4. 【Dubbo RPC 调用】
   service-b → service-a
   orderService.getOrderSummary(123L)
   ↓
5. service-a: OrderServiceImpl.getOrderSummary()
   ↓
6. 【Dubbo RPC 调用】
   service-a 内部调用
   orderService.getOrderById(123L)
   ↓
7. service-a: OrderServiceImpl.getOrderById()
   ↓
8. 返回结果
   service-a → service-b → HTTP 响应
```

---

## 五、Dubbo 注解对比

| 注解 | 使用位置 | 作用 | 项目 |
|------|---------|------|------|
| `@DubboService` | service-a 的实现类 | 暴露服务为 Dubbo RPC 服务 | service-a (Provider) |
| `@DubboReference` | service-b 的字段 | 引用远程 Dubbo 服务 | service-b (Consumer) |

---

## 六、关键理解点

### 1. 为什么需要 common-api？
- **接口契约**: 定义统一的接口规范
- **解耦**: service-a 和 service-b 都依赖接口，而不是相互依赖
- **类型安全**: 编译时检查方法签名和参数类型

### 2. Dubbo 如何工作？

#### 服务发现机制（核心原理）

**问题：service-b 如何知道去 service-a 找 OrderService？**

答案：通过**注册中心**和**接口全限定类名匹配**

**完整流程**：

```
第1步：Provider 启动（service-a）
┌─────────────────────────────────────────────────────────────┐
│ service-a 启动                                               │
│ ↓                                                            │
│ @DubboService 注解扫描到 OrderServiceImpl                    │
│ ↓                                                            │
│ 提取接口信息：com.example.common.service.OrderService        │
│ ↓                                                            │
│ 向注册中心注册：                                              │
│   - 接口名：com.example.common.service.OrderService          │
│   - 提供者地址：192.168.1.100:20880                          │
│   - 协议：dubbo                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌──────────────┐
                    │  注册中心     │
                    │  (Nacos/ZK)  │
                    └──────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│ service-b 启动                                               │
│ ↓                                                            │
│ @DubboReference 注解扫描到 OrderService 字段                 │
│ ↓                                                            │
│ 提取接口信息：com.example.common.service.OrderService        │
│ ↓                                                            │
│ 向注册中心查询：谁提供了这个接口？                             │
│ ↓                                                            │
│ 注册中心返回：service-a (192.168.1.100:20880)                │
│ ↓                                                            │
│ 创建动态代理对象，指向 service-a                              │
└─────────────────────────────────────────────────────────────┘

第2步：Consumer 调用（service-b）
┌─────────────────────────────────────────────────────────────┐
│ orderService.getOrderSummary(123L)                          │
│ ↓                                                            │
│ Dubbo 代理对象拦截调用                                        │
│ ↓                                                            │
│ 序列化：接口名 + 方法名 + 参数                                │
│ ↓                                                            │
│ 网络传输 → service-a (192.168.1.100:20880)                  │
│ ↓                                                            │
│ service-a 接收请求                                           │
│ ↓                                                            │
│ 反序列化，找到 OrderServiceImpl.getOrderSummary()            │
│ ↓                                                            │
│ 执行方法，返回结果                                            │
│ ↓                                                            │
│ 序列化结果，网络传输 → service-b                              │
│ ↓                                                            │
│ service-b 反序列化，返回给调用方                              │
└─────────────────────────────────────────────────────────────┘
```

**关键点**：
1. **接口全限定类名匹配**：Provider 和 Consumer 必须使用**完全相同**的接口（包名+类名）
2. **注册中心是桥梁**：Provider 注册，Consumer 订阅，注册中心负责匹配
3. **动态代理**：Consumer 拿到的 `orderService` 不是真实对象，而是 Dubbo 创建的代理
4. **服务名不重要**：Dubbo 不关心服务叫 service-a 还是 service-b，只关心接口名

#### 配置示例

**service-a 的 application.yml**：
```yaml
dubbo:
  application:
    name: service-a  # 服务名（用于标识，但不是匹配依据）
  registry:
    address: nacos://127.0.0.1:8848  # 注册中心地址
  protocol:
    name: dubbo
    port: 20880  # Dubbo 协议端口
```

**service-b 的 application.yml**：
```yaml
dubbo:
  application:
    name: service-b
  registry:
    address: nacos://127.0.0.1:8848  # 必须是同一个注册中心
  protocol:
    name: dubbo
```

**注意**：
- 两个服务必须连接到**同一个注册中心**
- 接口的**包名和类名**必须完全一致
- 不需要在代码中指定 service-a 的地址，Dubbo 会自动从注册中心获取

### 3. 与本地调用的区别
```java
// 看起来像本地调用
String summary = orderService.getOrderSummary(123L);

// 实际上是远程调用
// 1. 网络传输
// 2. 序列化/反序列化
// 3. 可能失败（网络问题、服务不可用）
```

---

## 七、当前配置状态总结

### ⚠️ 重要说明

**当前 Dubbo 配置状态**：
- ✅ **common-api**: 接口定义完整
- ❌ **service-a**: 缺少 `@DubboService` 注解（Provider 端未完成）
- ✅ **service-b**: 已配置 `@DubboReference` 注解（Consumer 端已准备）

**要完成 Dubbo RPC 配置，需要**：
1. 在 service-a 的 `OrderServiceImpl` 类上添加 `@DubboService` 注解
2. 确保两个服务都配置了 Dubbo 注册中心（如 Nacos、Zookeeper）
3. 确保两个服务的 `application.yml` 中配置了 Dubbo 相关参数

### 依赖关系图

```
common-api (接口定义) ✅
    ↑           ↑
    |           |
service-a   service-b
(需要添加    (已配置
@DubboService) @DubboReference) ✅
    ↑           |
    |           |
    └───────────┘
      Dubbo RPC ⚠️
   (尚未完全配置)
```

### 核心要点
1. **common-api**: 定义接口契约（`OrderService.java`）✅
2. **service-a**: 实现接口 + **需要添加** `@DubboService` 暴露服务 ❌
3. **service-b**: 引用接口 + `@DubboReference` 调用服务 ✅
4. **调用链**: HTTP → Controller → Service → Dubbo RPC → Provider（需要完成配置）

---

**文档创建时间**: 2026-01-13  
**最后更新**: 2026-01-13
