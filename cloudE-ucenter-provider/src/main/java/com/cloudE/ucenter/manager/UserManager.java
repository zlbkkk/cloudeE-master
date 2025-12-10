package com.cloudE.ucenter.manager;

import com.cloudE.entity.User;
import com.cloudE.mapper.UserMapper;
import com.cloudE.pay.client.PointClient;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.math.BigDecimal;

@Component
public class UserManager {

    @Resource
    private UserMapper userMapper;
    
    @Resource
    private PointManager pointManager;

    @Resource
    private PointClient pointClient;

    public User getUserByUserId(Long userId) {
        return userMapper.selectByPrimaryKey(userId);
    }
    
    public Integer getUserPoints(Long userId) {
        // Downstream call to PointClient.getPoints
        return pointClient.getPoints(userId).getData();
    }
    
    public void compensateUser(Long userId) {
        // Another downstream call to PointManager
        java.util.List<Long> ids = new java.util.ArrayList<>();
        ids.add(userId);
        pointManager.distributePointsBatch(ids, 50, "USER_COMPENSATION");
    }

·    /**
     * 发起用户间转账
     */
    public void initiateTransfer(Long fromUserId, Long toUserId, double amount) {
        User fromUser = userMapper.selectByPrimaryKey(fromUserId);
        if (fromUser != null && fromUser.getStatus() == 1) {
            pointManager.transferUserPoints(fromUserId, toUserId, BigDecimal.valueOf(amount));
        }
    }
}
