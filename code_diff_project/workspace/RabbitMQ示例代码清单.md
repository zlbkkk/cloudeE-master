# RabbitMQ 示例代码清单

## 📋 概述

本文档列出了为测试项目（common-api、service-a、service-b）添加的所有 RabbitMQ 相关代码文件。

这些代码完全模拟了真实项目（beehive-order-finance）中的发票 OCR 场景，用于测试系统的 RabbitMQ 跨服务影响分析能力。

---

## 📁 新增文件清单

### 1. common-api 项目

#### 1.1 队列常量定义
**文件**: `common-api/src/main/java/com/example/common/constant/QueueConstant.java`

**作用**: 定义 RabbitMQ 队列名称和路由键常量

**内容**:
```java
public class QueueConstant {
    // 订单事件队列
    public static final String ORDER_EVENT_QUEUE = "order.event.queue";
    // 订单事件路由键
    public static final String ORDER_EVENT_KEY = "order.event.key";
    // 订单通知队列
    public static final String ORDER_NOTIFICATION_QUEUE = "order.notification.queue";
    // 订单通知路由键
    public static final String ORDER_NOTIFICATION_KEY = "order.notification.key";
}
```

**对应真实项目**: `OrderFinanceQueueConstant.java`

---

#### 1.2 订单事件消息 DTO
**文件**: `common-api/src/main/java/com/example/common/dto/OrderEventDTO.java`

**作用**: 定义 RabbitMQ 消息的数据结构

**字段**:
- `orderId` - 订单ID
- `orderNo` - 订单编号
- `userId` - 用户ID
- `orderStatus` - 订单状态
- `amount` - 订单金额
- `eventType` - 事件类型（CREATED, PAID, CANCELLED, STATUS_UPDATED）
- `timestamp` - 事件时间戳

**对应真实项目**: `OfInvoiceOcrMsgDTO.java`

---

### 2. service-a 项目（消息生产者）

#### 2.1 修改 OrderServiceImpl
**文件**: `service-a/src/main/java/com/example/servicea/service/OrderServiceImpl.java`

**修改内容**:

1. **添加依赖注入**:
```java
@Autowired
private RabbitTemplate rabbitTemplate;

@Value("${spring.rabbitmq.template.exchange:order.exchange}")
private String exchangeName;
```

2. **添加消息发送方法**:
```java
private void sendOrderEventAsync(Long orderId, String orderNo, Long userId, String eventType, Double amount) {
    log.info("发送订单事件消息，订单编号：{}, 事件类型：{}", orderNo, eventType);
    
    OrderEventDTO eventDTO = OrderEventDTO.builder()
            .orderId(orderId)
            .orderNo(orderNo)
            .userId(userId)
            .orderStatus(eventType)
            .amount(amount)
            .eventType(eventType)
            .timestamp(System.currentTimeMillis())
            .build();
    
    rabbitTemplate.convertAndSend(
            exchangeName, 
            QueueConstant.ORDER_EVENT_KEY, 
            eventDTO
    );
    
    log.info("订单事件消息发送成功，订单编号：{}, 事件类型：{}", orderNo, eventType);
}
```

3. **在业务方法中调用**:
- `createOrder()` - 发送 CREATED 事件
- `updateOrderStatus()` - 发送 PAID/CANCELLED/STATUS_UPDATED 事件

**对应真实项目**: `OfInvoiceProviderImpl.cashInvoiceOcrAsync()`

---

### 3. service-b 项目（消息消费者）

#### 3.1 订单事件消费者
**文件**: `service-b/src/main/java/com/example/serviceb/consumer/OrderEventConsumer.java`

**作用**: 监听 RabbitMQ 队列，接收订单事件消息

**核心代码**:
```java
@Component
@Slf4j
public class OrderEventConsumer {
    
    @Autowired
    private OrderEventService orderEventService;
    
    @RabbitListener(queues = QueueConstant.ORDER_EVENT_QUEUE, concurrency = "1")
    public void consumeOrderEvent(OrderEventDTO eventDTO) {
        String orderNo = eventDTO.getOrderNo();
        String eventType = eventDTO.getEventType();
        
        log.info("收到订单事件消息，订单编号：{}, 事件类型：{}", orderNo, eventType);
        
        switch (eventType) {
            case "CREATED":
                orderEventService.handleOrderCreated(eventDTO);
                break;
            case "PAID":
                orderEventService.handleOrderPaid(eventDTO);
                break;
            case "CANCELLED":
                orderEventService.handleOrderCancelled(eventDTO);
                break;
            case "STATUS_UPDATED":
                orderEventService.handleOrderStatusUpdated(eventDTO);
                break;
        }
    }
}
```

**对应真实项目**: `OfInvoiceOcrConsumer.consumeOfInvoiceOcrMsg()`

---

#### 3.2 订单事件处理服务
**文件**: `service-b/src/main/java/com/example/serviceb/consumer/OrderEventService.java`

**作用**: 处理不同类型的订单事件

**方法**:
- `handleOrderCreated()` - 处理订单创建事件
- `handleOrderPaid()` - 处理订单支付事件
- `handleOrderCancelled()` - 处理订单取消事件
- `handleOrderStatusUpdated()` - 处理订单状态更新事件

**业务逻辑示例**:
```java
public void handleOrderCreated(OrderEventDTO eventDTO) {
    log.info("处理订单创建事件 - 订单编号：{}, 用户ID：{}, 金额：{}", 
            eventDTO.getOrderNo(), eventDTO.getUserId(), eventDTO.getAmount());
    
    // 业务逻辑：
    // 1. 发送订单创建通知给用户
    // 2. 记录订单创建日志
    // 3. 触发库存预留
    // 4. 发送短信/邮件通知
    
    log.info("订单创建事件处理完成 - 订单编号：{}", eventDTO.getOrderNo());
}
```

**对应真实项目**: `OfInvoiceOcrService.invoiceOcr()`

---

## 🔄 消息流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                         service-a (生产者)                        │
│                                                                   │
│  OrderController.createOrder()                                    │
│         ↓                                                         │
│  OrderServiceImpl.createOrder()                                   │
│         ↓                                                         │
│  sendOrderEventAsync()                                            │
│         ↓                                                         │
│  rabbitTemplate.convertAndSend(                                   │
│      exchange: "order.exchange",                                  │
│      routingKey: "order.event.key",                               │
│      message: OrderEventDTO                                       │
│  )                                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        RabbitMQ Broker                            │
│                                                                   │
│  Exchange: order.exchange                                         │
│         ↓                                                         │
│  Routing Key: order.event.key                                     │
│         ↓                                                         │
│  Queue: order.event.queue                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         service-b (消费者)                        │
│                                                                   │
│  @RabbitListener(queues = "order.event.queue")                    │
│         ↓                                                         │
│  OrderEventConsumer.consumeOrderEvent()                           │
│         ↓                                                         │
│  OrderEventService.handleOrderCreated()                           │
│         ↓                                                         │
│  业务处理：                                                        │
│  - 发送通知                                                        │
│  - 记录日志                                                        │
│  - 触发库存预留                                                    │
│  - 发送短信/邮件                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 与真实项目的对比

| 项目 | 真实项目 (beehive-order-finance) | 测试项目 (service-a/service-b) |
|------|----------------------------------|-------------------------------|
| **场景** | 发票 OCR 处理 | 订单事件处理 |
| **生产者** | OfInvoiceProviderImpl | OrderServiceImpl |
| **消费者** | OfInvoiceOcrConsumer | OrderEventConsumer |
| **消息 DTO** | OfInvoiceOcrMsgDTO | OrderEventDTO |
| **队列常量** | OrderFinanceQueueConstant | QueueConstant |
| **队列名称** | invoice.ocr.queue | order.event.queue |
| **路由键** | invoice.ocr.key | order.event.key |
| **并发数** | concurrency = "1" | concurrency = "1" |
| **Exchange** | ${spring.rabbitmq.template.exchange} | ${spring.rabbitmq.template.exchange:order.exchange} |

**结论**: 测试项目完全模拟了真实项目的 RabbitMQ 使用模式！

---

## 🧪 测试验证

### 验证点 1: 生产者识别
修改 `OrderServiceImpl.sendOrderEventAsync()` 方法，系统应该识别出：
- ✅ RabbitMQ 消息生产者
- ✅ Exchange 名称
- ✅ Routing Key: `order.event.key`
- ✅ 消息类型: `OrderEventDTO`

### 验证点 2: 消费者识别
修改 `OrderEventConsumer.consumeOrderEvent()` 方法，系统应该识别出：
- ✅ RabbitMQ 消息消费者
- ✅ Queue 名称: `order.event.queue`
- ✅ 消费方法: `consumeOrderEvent`
- ✅ 消息类型: `OrderEventDTO`

### 验证点 3: 生产者-消费者匹配
系统应该能够：
- ✅ 根据 routing key 匹配到 queue
- ✅ 匹配生产者和消费者
- ✅ 报告跨服务影响

### 验证点 4: 消息 DTO 追踪
修改 `OrderEventDTO`，系统应该识别出：
- ✅ 生产者使用: `OrderServiceImpl.sendOrderEventAsync()`
- ✅ 消费者使用: `OrderEventConsumer.consumeOrderEvent()`
- ✅ 影响范围: 两个服务

---

## 📝 使用说明

### 1. 查看代码
```bash
# 查看生产者代码
cat code_diff_project/workspace/service-a/src/main/java/com/example/servicea/service/OrderServiceImpl.java

# 查看消费者代码
cat code_diff_project/workspace/service-b/src/main/java/com/example/serviceb/consumer/OrderEventConsumer.java

# 查看消息 DTO
cat code_diff_project/workspace/common-api/src/main/java/com/example/common/dto/OrderEventDTO.java
```

### 2. 测试修改
```bash
# 修改生产者
cd code_diff_project/workspace/service-a
# 编辑 OrderServiceImpl.java
git add .
git commit -m "test: 修改订单事件消息生产者"

# 运行分析
cd ../..
python backend/analyzer/runner.py --project-path workspace/service-a --enable-cross-project --related-projects '[{"related_project_name":"service-b","related_project_git_url":"workspace/service-b","related_project_branch":"master"}]'
```

### 3. 查看报告
在前端页面查看分析报告，应该能看到：
- RabbitMQ 消息生产者信息
- RabbitMQ 消息消费者信息
- 跨服务影响分析
- 消息队列名称和消息类型

---

## 🎯 关键特性

### 1. 完全模拟真实场景
- ✅ 使用 `@Value` 从配置读取 exchange
- ✅ 使用常量类定义队列名称和路由键
- ✅ 使用 Builder 模式构建消息 DTO
- ✅ 使用 `@RabbitListener` 监听队列
- ✅ 设置并发数 `concurrency = "1"`

### 2. 业务场景完整
- ✅ 订单创建事件
- ✅ 订单支付事件
- ✅ 订单取消事件
- ✅ 订单状态更新事件

### 3. 代码结构清晰
- ✅ 生产者和消费者分离
- ✅ 消息 DTO 在 common-api 中共享
- ✅ 队列常量统一管理
- ✅ 事件处理逻辑独立封装

---

## 🔗 相关文档

- [RabbitMQ测试场景说明.md](./RabbitMQ测试场景说明.md) - 详细的测试步骤
- [跨项目依赖关系说明.md](./跨项目依赖关系说明.md) - 完整的依赖关系文档
- [已实现的跨服务调用场景总结.md](./已实现的跨服务调用场景总结.md) - 系统支持的所有场景

---

**文档版本**: v1.0  
**最后更新**: 2024-01-15  
**维护者**: 跨项目影响分析团队
