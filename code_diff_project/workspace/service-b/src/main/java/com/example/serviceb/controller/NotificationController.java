package com.example.serviceb.controller;

import com.example.common.dto.UserDTO;
import com.example.serviceb.service.NotificationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 通知控制器 - 使用 common-api 中的 UserDTO
 */
@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private NotificationService notificationService;

    @PostMapping("/send")
    public String sendNotification(@RequestBody UserDTO user, @RequestParam String message) {
        return notificationService.sendEmailNotification(user, message);
    }

    @PostMapping("/welcome")
    public String sendWelcomeEmail(@RequestBody UserDTO user) {
        return notificationService.sendWelcomeEmail(user);
    }
}
