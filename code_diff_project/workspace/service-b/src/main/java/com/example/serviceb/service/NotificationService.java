package com.example.serviceb.service;

import com.example.common.dto.UserDTO;
import com.example.common.service.UserService;
import org.springframework.stereotype.Service;

/**
 * 通知服务 - 使用 common-api 中的 UserDTO 和 UserService
 */
@Service
public class NotificationService {

    /**
     * 发送邮件通知
     */
    public String sendEmailNotification(UserDTO user, String message) {
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
}
