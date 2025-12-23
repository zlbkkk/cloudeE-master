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
}
