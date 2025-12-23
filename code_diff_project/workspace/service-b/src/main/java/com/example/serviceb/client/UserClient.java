package com.example.serviceb.client;

import com.example.common.dto.UserDTO;
import com.example.common.dto.OrderDTO;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * 用户服务客户端 - 调用 service-a 的 API
 * 这是一个跨项目的 API 调用示例
 */
@Component
public class UserClient {
    
    private final RestTemplate restTemplate;
    private static final String SERVICE_A_URL = "http://localhost:8081/api/users";
    private static final String SERVICE_A_ORDER_URL = "http://localhost:8081/api/orders";
    
    public UserClient() {
        this.restTemplate = new RestTemplate();
    }
    
    /**
     * 调用 service-a 的获取用户接口
     * 跨项目调用: service-b -> service-a
     */
    public UserDTO getUserById(Long userId) {
        String url = SERVICE_A_URL + "/" + userId;
        try {
            return restTemplate.getForObject(url, UserDTO.class);
        } catch (Exception e) {
            System.err.println("Failed to get user: " + e.getMessage());
            return null;
        }
    }
    
    /**
     * 调用 service-a 的创建用户接口
     * 跨项目调用: service-b -> service-a
     */
    public UserDTO createUser(String username, String email) {
        String url = SERVICE_A_URL + "?username=" + username + "&email=" + email;
        try {
            return restTemplate.postForObject(url, null, UserDTO.class);
        } catch (Exception e) {
            System.err.println("Failed to create user: " + e.getMessage());
            return null;
        }
    }
    
    /**
     * 验证用户是否存在
     * 跨项目调用: service-b -> service-a
     */
    public boolean userExists(Long userId) {
        UserDTO user = getUserById(userId);
        return user != null && user.getId() != null;
    }
    
    /**
     * 调用 service-a 的获取订单接口
     * 跨项目调用: service-b -> service-a
     */
    public OrderDTO getOrderById(Long orderId) {
        String url = SERVICE_A_ORDER_URL + "/" + orderId;
        try {
            return restTemplate.getForObject(url, OrderDTO.class);
        } catch (Exception e) {
            System.err.println("Failed to get order: " + e.getMessage());
            return null;
        }
    }
    
    /**
     * 获取订单状态文本描述
     * 跨项目调用: service-b -> service-a (新增接口)
     */
    public String getOrderStatusText(Long orderId) {
        String url = SERVICE_A_ORDER_URL + "/" + orderId + "/status-text";
        try {
            return restTemplate.getForObject(url, String.class);
        } catch (Exception e) {
            System.err.println("Failed to get order status text: " + e.getMessage());
            return "未知状态";
        }
    }
}
