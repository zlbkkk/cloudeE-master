package com.example.serviceb.consumer;

import com.example.common.constant.QueueConstant;
import com.example.common.dto.OrderEventDTO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * 订单事件消费者
 * 监听 service-a 发送的订单事件消息
 * 模拟真实项目中的 RabbitMQ 消息消费场景
 * 
 * @author system
 * @date 2024-01-15
 */
@Component
@Slf4j
public class OrderEventConsumer {
    
    @Autowired
    private OrderEventService orderEventService;
    
    /**
     * 消费订单事件消息
     * 监听队列：order.event.queue
     * 
     * @param eventDTO 订单事件消息
     */
    @RabbitListener(queues = QueueConstant.ORDER_EVENT_QUEUE, concurrency = "1")
    public void consumeOrderEvent(OrderEventDTO eventDTO) {
        Long orderId = eventDTO.getOrderId();
        String orderNo = eventDTO.getOrderNo();
        String eventType = eventDTO.getEventType();
        
        log.info("收到订单事件消息，订单编号：{}, 事件类型：{}", orderNo, eventType);
        
        try {
            // 根据事件类型处理不同的业务逻辑
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
                default:
                    log.warn("未知的订单事件类型：{}", eventType);
            }
            
            log.info("订单事件处理完成，订单编号：{}, 事件类型：{}", orderNo, eventType);
            
        } catch (Exception e) {
            log.error("处理订单事件失败，订单编号：{}, 事件类型：{}, 错误信息：{}", 
                    orderNo, eventType, e.getMessage(), e);
            // 实际项目中这里可以实现重试机制或死信队列
        }
    }
}
