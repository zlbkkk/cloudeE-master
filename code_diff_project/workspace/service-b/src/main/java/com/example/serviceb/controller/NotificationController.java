package com.example.serviceb.controller;

import com.example.common.dto.UserDTO;
import com.example.serviceb.service.NotificationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 通知控制器
 * 提供通知相关的 REST API
 * 这些接口会被 service-a 调用
 */
@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private NotificationService notificationService;

    /**
     * 发送欢迎邮件
     * 被 service-a 的 NotificationClient.sendWelcomeEmail() 调用
     */
    @PostMapping("/welcome")
    public String sendWelcomeEmail(@RequestBody UserDTO user) {
        return notificationService.sendWelcomeEmail(user);
    }

    /**
     * 发送通知
     * 被 service-a 的 NotificationClient.sendNotification() 调用
     */
    @PostMapping("/send")
    public String sendNotification(
            @RequestBody UserDTO user,
            @RequestParam String message) {
        return notificationService.sendNotification(user, message);
    }

    /**
     * 发送订单通知
     */
    @PostMapping("/order")
    public String sendOrderNotification(
            @RequestParam Long userId,
            @RequestParam String orderNumber) {
        return notificationService.sendOrderNotification(userId, orderNumber);
    }

    /**
     * 批量发送通知
     */
    @PostMapping("/batch")
    public String sendBatchNotifications(
            @RequestBody java.util.List<UserDTO> users,
            @RequestParam String message) {
        return notificationService.sendBatchNotifications(users, message);
    }
    
    /**
     * 【新增接口】发送订单详情通知
     * 【完整调用链测试】HTTP API → Service → Dubbo RPC
     * 
     * 调用链：
     * 1. HTTP: POST /api/notifications/order-details?orderId=123
     * 2. Service: NotificationService.sendOrderDetailsNotification(123L)
     * 3. Dubbo RPC: OrderService.getOrderDetails(123L) [service-a]
     * 4. Dubbo RPC: OrderService.getOrderById(123L) [service-a]
     */
    @PostMapping("/order-details")
    public String sendOrderDetailsNotification(@RequestParam Long orderId) {
        return notificationService.sendOrderDetailsNotification(orderId);
    }
    
    /**
     * 【新增接口】发送订单摘要通知
     * 【完整调用链测试】HTTP API → Service → Dubbo RPC
     * 
     * 调用链：
     * 1. HTTP: POST /api/notifications/order-summary?orderId=123
     * 2. Service: NotificationService.sendOrderSummaryNotification(123L)
     * 3. Dubbo RPC: OrderService.getOrderSummary(123L) [service-a]
     * 4. Dubbo RPC: OrderService.getOrderById(123L) [service-a]
     */
    @PostMapping("/order-summary")
    public String sendOrderSummaryNotification(@RequestParam Long orderId) {
        return notificationService.sendOrderSummaryNotification(orderId);
    }

    /**
     * 【新增接口】发送订单状态历史通知
     * 【完整调用链测试】HTTP API → Service → Dubbo RPC（调用新增方法）
     *
     * 调用链：
     * 1. HTTP: POST /api/notifications/order-status-history?orderId=123
     * 2. Service: NotificationService.sendOrderStatusHistoryNotification(123L)
     * 3. Dubbo RPC: OrderService.getOrderStatusHistory(123L) [service-a]
     * 4. Dubbo RPC: OrderService.getOrderById(123L) [service-a]
     */
    @PostMapping("/order-status-history")
    public String sendOrderStatusHistoryNotification(@RequestParam Long orderId) {
        return notificationService.sendOrderStatusHistoryNotification(orderId);
    }
}
