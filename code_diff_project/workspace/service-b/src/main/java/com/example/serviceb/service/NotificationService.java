package com.example.serviceb.service;

import com.example.common.dto.UserDTO;
import com.example.common.dto.OrderDTO;
import com.example.common.service.UserService;
import com.example.serviceb.client.UserClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * 通知服务 - 使用 common-api 中的 UserDTO 和 UserService
 * 并调用 service-a 的用户服务和订单服务
 */
@Service
public class NotificationService {

    @Autowired
    private UserClient userClient;

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
     * 跨项目调用: 从 service-a 获取订单和用户信息
     */
    public String sendOrderNotification(Long orderId) {
        // 跨项目调用: 从 service-a 获取订单信息
        OrderDTO order = userClient.getOrderById(orderId);
        
        if (order == null) {
            return "Error: Order not found";
        }
        
        // 跨项目调用: 从 service-a 获取用户信息
        UserDTO user = userClient.getUserById(order.getUserId());
        
        if (user == null) {
            return "Error: User not found for order";
        }
        
        // 【新增】跨项目调用: 从 service-a 获取订单状态文本描述
        String statusText = userClient.getOrderStatusText(orderId);
        
        // 发送订单通知（使用新的状态文本）
        String message = String.format(
            "Order %s - Amount: $%.2f - Status: %s",
            order.getOrderNumber(),
            order.getTotalAmount(),
            statusText  // 使用从 service-a 获取的状态文本
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
}
