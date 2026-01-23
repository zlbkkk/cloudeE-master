# RabbitMQ 跨服务消息队列测试场景

## 📋 概述

本文档说明如何测试系统对 RabbitMQ 消息队列的跨服务影响分析能力。

测试项目已经添加了完整的 RabbitMQ 示例代码，模拟真实项目（beehive-order-finance）中的发票 OCR 场景。

---

## 🎯 测试目标

验证系统能够：
1. ✅ 识别 RabbitMQ 消息生产者（`rabbitTemplate.convertAndSend`）
2. ✅ 识别 RabbitMQ 消息消费者（`@RabbitListener`）
3. ✅ 匹配生产者和消费者（通过 exchange、routing key、queue）
4. ✅ 追踪消息 DTO 的使用
5. ✅ 报告跨服务影响范围

---

## 📁 相关文件

### common-api（共享定义）
```
common-api/src/main/java/com/example/common/
├── constant/
│   └── QueueConstant.java          # 队列常量定义
└── dto/
    └── OrderEventDTO.java          # 订单事件消息 DTO
```

### service-a（消息生产者）
```
service-a/src/main/java/com/example/servicea/service/
└── OrderServiceImpl.java           # 发送订单事件消息
```

### service-b（消息消费者）
```
service-b/src/main/java/com/example/serviceb/consumer/
├── OrderEventConsumer.java         # 监听订单事件队列
└── OrderEventService.java          # 处理订单事件业务逻辑
```

---

## 🔄 消息流程

```
service-a (生产者)
    ↓
OrderServiceImpl.sendOrderEventAsync()
    ↓
rabbitTemplate.convertAndSend(exchange, "order.event.key", OrderEventDTO)
    ↓
RabbitMQ Exchange
    ↓
order.event.queue (队列)
    ↓
@RabbitListener(queues = "order.event.queue")
    ↓
OrderEventConsumer.consumeOrderEvent()
    ↓
OrderEventService.handleOrderXXX()
    ↓
service-b (消费者)
```

---

## 🧪 测试场景

### 场景 1: 修改消息生产者（推荐优先测试）

**目标**: 验证系统能识别消息生产者的变更，并追踪到消费者

**步骤**:

1. **修改文件**: `service-a/src/main/java/com/example/servicea/service/OrderServiceImpl.java`

2. **修改内容**: 在 `sendOrderEventAsync()` 方法中添加新字段
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
            .priority(1)  // 新增：优先级字段
            .build();
    
    // 发送消息到 RabbitMQ
    rabbitTemplate.convertAndSend(
            exchangeName, 
            QueueConstant.ORDER_EVENT_KEY, 
            eventDTO
    );
    
    log.info("订单事件消息发送成功，订单编号：{}, 事件类型：{}", orderNo, eventType);
}
```

3. **提交变更**:
```bash
cd code_diff_project/workspace/service-a
git add .
git commit -m "test: 修改订单事件消息，添加优先级字段"
```

4. **运行跨项目分析**:
```bash
cd code_diff_project
python backend/analyzer/runner.py \
    --project-path workspace/service-a \
    --enable-cross-project \
    --related-projects '[
        {
            "related_project_name": "service-b",
            "related_project_git_url": "workspace/service-b",
            "related_project_branch": "master"
        },
        {
            "related_project_name": "common-api",
            "related_project_git_url": "workspace/common-api",
            "related_project_branch": "master"
        }
    ]'
```

**预期结果**:
```json
{
  "rabbitmq_impacts": [
    {
      "type": "rabbitmq_producer",
      "file_path": "service-a/.../OrderServiceImpl.java",
      "line_number": 180,
      "method_name": "sendOrderEventAsync",
      "exchange": "${spring.rabbitmq.template.exchange}",
      "routing_key": "order.event.key",
      "message_type": "OrderEventDTO",
      "related_consumers": [
        {
          "service_name": "service-b",
          "file_path": "service-b/.../OrderEventConsumer.java",
          "line_number": 35,
          "queue": "order.event.queue",
          "consumer_method": "consumeOrderEvent"
        }
      ]
    }
  ]
}
```

---

### 场景 2: 修改消息 DTO

**目标**: 验证系统能识别消息格式变更，并追踪到所有使用方

**步骤**:

1. **修改文件**: `common-api/src/main/java/com/example/common/dto/OrderEventDTO.java`

2. **修改内容**: 添加新字段
```java
/**
 * 配送地址（新增字段）
 */
private String deliveryAddress;

/**
 * 备注信息（新增字段）
 */
private String remark;
```

3. **提交变更**:
```bash
cd code_diff_project/workspace/common-api
git add .
git commit -m "test: OrderEventDTO 添加配送地址和备注字段"
```

4. **运行跨项目分析**

**预期结果**:
- 识别出 `OrderEventDTO` 被修改
- 追踪到生产者：`service-a/OrderServiceImpl.sendOrderEventAsync()`
- 追踪到消费者：`service-b/OrderEventConsumer.consumeOrderEvent()`
- 报告影响：消息格式变更可能导致版本兼容性问题

---

### 场景 3: 修改消息消费者

**目标**: 验证系统能识别消费者变更，并追踪到生产者

**步骤**:

1. **修改文件**: `service-b/src/main/java/com/example/serviceb/consumer/OrderEventService.java`

2. **修改内容**: 在 `handleOrderCreated()` 方法中添加新逻辑
```java
public void handleOrderCreated(OrderEventDTO eventDTO) {
    log.info("处理订单创建事件 - 订单编号：{}, 用户ID：{}, 金额：{}", 
            eventDTO.getOrderNo(), eventDTO.getUserId(), eventDTO.getAmount());
    
    // 新增业务逻辑：发送短信通知
    smsService.sendOrderCreatedSms(eventDTO.getUserId(), eventDTO.getOrderNo());
    
    // 新增业务逻辑：记录审计日志
    auditService.logOrderCreated(eventDTO);
    
    // 新增业务逻辑：触发库存预留
    inventoryService.reserveStock(eventDTO.getOrderId());
    
    log.info("订单创建事件处理完成 - 订单编号：{}", eventDTO.getOrderNo());
}
```

3. **提交变更**:
```bash
cd code_diff_project/workspace/service-b
git add .
git commit -m "test: 订单创建事件处理增加短信通知和库存预留"
```

4. **运行跨项目分析**

**预期结果**:
- 识别出消费者逻辑变更
- 追踪到消息来源：`service-a/OrderServiceImpl.sendOrderEventAsync()`
- 报告影响：消费者处理逻辑变更，需要测试消息消费流程

---

### 场景 4: 修改队列常量

**目标**: 验证系统能识别队列配置变更的影响

**步骤**:

1. **修改文件**: `common-api/src/main/java/com/example/common/constant/QueueConstant.java`

2. **修改内容**: 修改队列名称
```java
/**
 * 订单事件队列（修改队列名称）
 */
public static final String ORDER_EVENT_QUEUE = "order.event.queue.v2";

/**
 * 订单事件路由键（修改路由键）
 */
public static final String ORDER_EVENT_KEY = "order.event.key.v2";
```

3. **提交变更**:
```bash
cd code_diff_project/workspace/common-api
git add .
git commit -m "test: 修改订单事件队列名称和路由键"
```

4. **运行跨项目分析**

**预期结果**:
- 识别出队列常量被修改
- 追踪到使用此常量的生产者和消费者
- 报告影响：队列名称不匹配会导致消息无法送达

---

## 📊 验证要点

### 1. 生产者识别
系统应该能够识别：
- ✅ `rabbitTemplate.convertAndSend()` 调用
- ✅ Exchange 名称
- ✅ Routing Key
- ✅ 消息类型（DTO 类名）
- ✅ 发送位置（文件路径、行号、方法名）

### 2. 消费者识别
系统应该能够识别：
- ✅ `@RabbitListener` 注解
- ✅ Queue 名称
- ✅ 消费方法名
- ✅ 消息类型（参数类型）
- ✅ 消费位置（文件路径、行号）

### 3. 生产者-消费者匹配
系统应该能够：
- ✅ 根据 exchange + routing key 匹配到 queue
- ✅ 根据 queue 匹配生产者和消费者
- ✅ 识别消息 DTO 的使用关系

### 4. 跨服务影响报告
系统应该报告：
- ✅ 生产者所在服务
- ✅ 消费者所在服务
- ✅ 消息队列名称
- ✅ 消息类型
- ✅ 影响范围描述

---

## 🎓 与真实项目的对比

### 真实项目（beehive-order-finance）
```java
// 生产者
@Value("${spring.rabbitmq.template.exchange}")
private String exchangeName;

rabbitTemplate.convertAndSend(
    exchangeName, 
    OrderFinanceQueueConstant.INVOICE_OCR_KEY,
    OfInvoiceOcrMsgDTO.builder()
        .ofProjectNo(ofProjectNo)
        .fileId(fileId)
        .build()
);

// 消费者
@RabbitListener(queues = OrderFinanceQueueConstant.INVOICE_OCR_QUEUE, concurrency = "1")
public void consumeOfInvoiceOcrMsg(OfInvoiceOcrMsgDTO msgDTO) {
    // 处理发票 OCR
}
```

### 测试项目（service-a/service-b）
```java
// 生产者
@Value("${spring.rabbitmq.template.exchange:order.exchange}")
private String exchangeName;

rabbitTemplate.convertAndSend(
    exchangeName, 
    QueueConstant.ORDER_EVENT_KEY,
    OrderEventDTO.builder()
        .orderId(orderId)
        .orderNo(orderNo)
        .build()
);

// 消费者
@RabbitListener(queues = QueueConstant.ORDER_EVENT_QUEUE, concurrency = "1")
public void consumeOrderEvent(OrderEventDTO eventDTO) {
    // 处理订单事件
}
```

**结论**: 测试项目完全模拟了真实项目的 RabbitMQ 使用模式！

---

## 🚀 快速测试命令

```bash
# 1. 进入 service-a 目录
cd code_diff_project/workspace/service-a

# 2. 修改 OrderServiceImpl.java（添加注释或修改日志）
# 例如：在 sendOrderEventAsync 方法中添加一行注释

# 3. 提交变更
git add .
git commit -m "test: 测试 RabbitMQ 消息生产者变更"

# 4. 运行分析
cd ../..
python backend/analyzer/runner.py \
    --project-path workspace/service-a \
    --enable-cross-project \
    --related-projects '[{"related_project_name":"service-b","related_project_git_url":"workspace/service-b","related_project_branch":"master"},{"related_project_name":"common-api","related_project_git_url":"workspace/common-api","related_project_branch":"master"}]'

# 5. 查看分析报告
# 在前端页面查看报告，应该能看到 RabbitMQ 相关的跨服务影响
```

---

## ✅ 成功标准

测试成功的标志：
1. ✅ 系统识别出 `rabbitTemplate.convertAndSend` 调用
2. ✅ 系统识别出 `@RabbitListener` 注解
3. ✅ 系统匹配生产者和消费者
4. ✅ 报告中包含 RabbitMQ 相关的跨服务影响
5. ✅ 报告中包含消息队列名称、消息类型等详细信息

---

## 📝 注意事项

1. **队列匹配逻辑**: 系统通过 exchange + routing key 匹配到 queue，再匹配消费者
2. **消息类型**: 系统会提取消息 DTO 的类名，用于追踪消息格式变更
3. **并发数**: `@RabbitListener` 的 `concurrency` 参数不影响识别
4. **Exchange 配置**: 支持从配置文件读取 exchange 名称（`${spring.rabbitmq.template.exchange}`）

---

## 🔗 相关文档

- [跨项目依赖关系说明.md](./跨项目依赖关系说明.md) - 完整的依赖关系文档
- [已实现的跨服务调用场景总结.md](./已实现的跨服务调用场景总结.md) - 系统支持的所有场景

---

**文档版本**: v1.0  
**最后更新**: 2024-01-15  
**维护者**: 跨项目影响分析团队
