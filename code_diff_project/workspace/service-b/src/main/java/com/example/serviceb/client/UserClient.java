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
     * 场景6测试：修改接口方法签名 - 返回类型从 String 改为对象
     */
    public String getOrderStatusText(Long orderId) {
        String url = SERVICE_A_ORDER_URL + "/" + orderId + "/status-text";
        try {
            // 场景6测试：接口返回类型已变更，需要适配
            // 原来返回 String，现在返回 OrderStatusResponse 对象
            // 这里暂时保持返回 String，实际应该改为返回对象
            return restTemplate.getForObject(url, String.class);
        } catch (Exception e) {
            System.err.println("Failed to get order status text: " + e.getMessage());
            return "未知状态";
        }
    }
    
    /**
     * 场景6测试：新增接口方法 - 获取订单详情
     */
    public String getOrderDetails(Long orderId, Boolean includeUser) {
        String url = SERVICE_A_ORDER_URL + "/" + orderId + "/details?includeUser=" + includeUser;
        try {
            return restTemplate.getForObject(url, String.class);
        } catch (Exception e) {
            System.err.println("Failed to get order details: " + e.getMessage());
            return null;
        }
    }
    
    /**
     * 场景6测试：修改请求路径 - 获取用户订单列表（路径已变更）
     */
    public OrderDTO[] getUserOrders(Long userId) {
        // 场景6测试：路径从 /user/{userId} 改为 /by-user/{userId}
        String url = SERVICE_A_ORDER_URL + "/by-user/" + userId;
        try {
            return restTemplate.getForObject(url, OrderDTO[].class);
        } catch (Exception e) {
            System.err.println("Failed to get user orders: " + e.getMessage());
            return new OrderDTO[0];
        }
    }
    
    /**
     * 场景6测试：新增接口方法 - 获取用户详细信息（包含订单）
     */
    public UserDTO getUserWithOrders(Long userId) {
        String url = SERVICE_A_URL + "/" + userId + "?includeOrders=true";
        try {
            return restTemplate.getForObject(url, UserDTO.class);
        } catch (Exception e) {
            System.err.println("Failed to get user with orders: " + e.getMessage());
            return null;
        }
    }
    
    /**
     * 场景6测试：修改接口参数 - 创建用户（新增手机号参数）
     */
    public UserDTO createUserWithPhone(String username, String email, String phoneNumber) {
        String url = SERVICE_A_URL + "?username=" + username + "&email=" + email + "&phoneNumber=" + phoneNumber;
        try {
            return restTemplate.postForObject(url, null, UserDTO.class);
        } catch (Exception e) {
            System.err.println("Failed to create user with phone: " + e.getMessage());
            return null;
        }
    }
}
