package com.example.serviceb.service;

import com.example.common.dto.UserDTO;
import com.example.common.dto.OrderDTO;
import com.example.common.service.OrderService;
import com.example.serviceb.client.UserClient;
import org.apache.dubbo.config.annotation.DubboReference;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;

/**
 * 通知服务 - 使用 Dubbo RPC 调用 service-a 的订单服务
 * 测试场景：Dubbo RPC 跨服务调用
 */
@Service
public class NotificationService {

    @Autowired
    private UserClient userClient;
    
    /**
     * 通过 Dubbo RPC 注入 OrderService
     * 这是跨服务调用的关键：service-b 通过 Dubbo 调用 service-a 的接口
     */
    @DubboReference
    private OrderService orderService;

    /**
     * 发送邮件通知
     * 跨项目调用: 先验证用户是否存在（调用 service-a）
     */
    public String sendEmailNotification(UserDTO user, String message) {
        // 跨项目调用: 验证用户是否存在
        if (user.getId() != null && !userClient.userExists(user.getId())) {
            return "Error: User does not exist";
        }
        
        // 使用 UserDTO 的 getEmail() 方法
        String email = user.getEmail();
        
        // 模拟发送邮件
        System.out.println("Sending email to: " + email);
        System.out.println("Message: " + message);
        
        return "Email sent to " + user.getUsername() + " at " + email;
    }

    /**
     * 发送欢迎邮件
     */
    public String sendWelcomeEmail(UserDTO user) {
        // 使用 UserDTO 的多个方法
        String welcomeMessage = String.format(
            "Welcome %s! Your account has been created successfully. " +
            "We've sent a confirmation email to %s",
            user.getUsername(),
            user.getEmail()
        );
        
        return sendEmailNotification(user, welcomeMessage);
    }
    
    /**
     * 发送通知（被 service-a 调用）
     */
    public String sendNotification(UserDTO user, String message) {
        return sendEmailNotification(user, message);
    }
    
    /**
     * 发送批量通知
     * 跨项目调用: 从 service-a 获取用户信息
     */
    public String sendBulkNotification(Long userId, String message) {
        // 跨项目调用: 从 service-a 获取用户详细信息
        UserDTO user = userClient.getUserById(userId);
        
        if (user == null) {
            return "Error: User not found";
        }
        
        return sendEmailNotification(user, message);
    }
    
    /**
     * 发送订单通知（通过订单号）
     * 跨项目调用: 从 service-a 获取订单和用户信息
     */
    public String sendOrderNotification(Long userId, String orderNumber) {
        // 跨项目调用: 从 service-a 获取用户信息
        UserDTO user = userClient.getUserById(userId);
        
        if (user == null) {
            return "Error: User not found";
        }
        
        // 发送订单通知
        String message = String.format(
            "Your order %s has been processed successfully",
            orderNumber
        );
        
        return sendEmailNotification(user, message);
    }
    
    /**
     * 发送订单通知（通过订单ID）
     * 【Dubbo RPC 调用测试场景】
     * 跨项目调用链：
     * 1. 通过 Dubbo 调用 service-a 的 orderService.getOrderById()
     * 2. 通过 Dubbo 调用 service-a 的 orderService.getOrderStatusText()
     * 3. 通过 HTTP 调用 service-a 的 userClient.getUserById()
     */
    public String sendOrderNotification(Long orderId) {
        // 【Dubbo RPC 调用 1】从 service-a 获取订单信息
        OrderDTO order = orderService.getOrderById(orderId);
        
        if (order == null) {
            return "Error: Order not found";
        }
        
        // 跨项目调用: 从 service-a 获取用户信息
        UserDTO user = userClient.getUserById(order.getUserId());
        
        if (user == null) {
            return "Error: User not found for order";
        }
        
        // 【Dubbo RPC 调用 2】从 service-a 获取订单状态文本
        // 这是我们要测试的关键调用！
        String statusText = orderService.getOrderStatusText(orderId);
        
        // 发送订单通知
        String message = String.format(
            "订单 %s - 金额: ¥%.2f - 状态: %s",
            order.getOrderNumber(),
            order.getTotalAmount(),
            statusText  // 使用 Dubbo 调用获取的状态文本
        );
        
        return sendEmailNotification(user, message);
    }
    
    
    /**
     * 【新增方法】发送订单状态变更通知
     * 【Dubbo RPC 调用测试场景】
     * 这个方法也会调用 orderService.getOrderStatusText()
     */
    public String sendOrderStatusChangeNotification(Long orderId, Integer newStatus) {
        // 【Dubbo RPC 调用 1】获取订单信息
        OrderDTO order = orderService.getOrderById(orderId);
        if (order == null) {
            return "Error: Order not found";
        }
        
        // 跨项目调用: 获取用户信息
        UserDTO user = userClient.getUserById(order.getUserId());
        if (user == null) {
            return "Error: User not found";
        }
        
        // 【Dubbo RPC 调用 2】获取新状态的文本描述
        String statusText = orderService.getOrderStatusText(orderId);
        
        String message = String.format(
            "您的订单 %s 状态已更新为: %s",
            order.getOrderNumber(),
            statusText
        );
        
        return sendEmailNotification(user, message);
    }
    
    /**
     * 【新增方法】获取订单详细信息并发送通知
     * 【完整调用链测试场景】HTTP API → Service → Dubbo RPC
     * 这个方法会被 Controller 暴露为 HTTP 接口
     */
    public String sendOrderDetailsNotification(Long orderId) {
        // 【Dubbo RPC 调用】获取订单详细信息（包含状态文本）
        String orderDetails = orderService.getOrderDetails(orderId);
        
        if (orderDetails.contains("订单不存在")) {
            return "Error: Order not found";
        }
        
        // 【Dubbo RPC 调用】获取订单基本信息
        OrderDTO order = orderService.getOrderById(orderId);
        
        // 跨项目调用: 获取用户信息
        UserDTO user = userClient.getUserById(order.getUserId());
        if (user == null) {
            return "Error: User not found";
        }
        
        // 发送包含订单详情的通知
        String message = String.format(
            "订单详情通知：\n%s",
            orderDetails
        );
        
        return sendEmailNotification(user, message);
    }
    
    /**
     * 批量发送通知
     * 跨项目调用: 验证每个用户是否存在
     */
    public String sendBatchNotifications(java.util.List<UserDTO> users, String message) {
        int successCount = 0;
        int failCount = 0;
        
        for (UserDTO user : users) {
            // 跨项目调用: 验证用户是否存在
            if (user.getId() != null && userClient.userExists(user.getId())) {
                sendEmailNotification(user, message);
                successCount++;
            } else {
                failCount++;
            }
        }
        
        return String.format("Batch notification sent: %d succeeded, %d failed", successCount, failCount);
    }
    
    /**
     * 【新增方法】发送订单摘要通知
     * 【完整调用链测试】HTTP API → Service → Dubbo RPC
     * 
     * 调用链：
     * 1. HTTP: POST /api/notifications/order-summary?orderId=123
     * 2. Service: NotificationService.sendOrderSummaryNotification(123L)
     * 3. Dubbo RPC: OrderService.getOrderSummary(123L) [service-a]
     * 4. Dubbo RPC: OrderService.getOrderById(123L) [service-a]
     */
    public String sendOrderSummaryNotification(Long orderId) {
        // 【Dubbo RPC 调用】获取订单摘要信息
        String orderSummary = orderService.getOrderSummary(orderId);
        
        if (orderSummary.contains("订单不存在")) {
            return "Error: Order not found";
        }
        
        // 【Dubbo RPC 调用】获取订单基本信息
        OrderDTO order = orderService.getOrderById(orderId);
        
        // 跨项目调用: 获取用户信息
        UserDTO user = userClient.getUserById(order.getUserId());
        if (user == null) {
            return "Error: User not found";
        }
        
        // 发送包含订单摘要的通知
        String message = String.format(
            "订单摘要通知：%s",
            orderSummary
        );
        
        return sendEmailNotification(user, message);
    }
}
