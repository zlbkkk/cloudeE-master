package com.cloudE.ucenter.manager;

import com.cloudE.entity.User;
import com.cloudE.mapper.UserMapper;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

@Component
public class UserManager {

    @Resource
    private UserMapper userMapper;
    
    @Resource
    private PointManager pointManager;
    
    @Resource
    private com.cloudE.pay.client.PointClient pointClient;

    public User getUserByUserId(Long userId) {
        return userMapper.selectByPrimaryKey(userId);
    }
    
    public void compensateUser(Long userId) {
        // Another downstream call to PointManager
        java.util.List<Long> ids = new java.util.ArrayList<>();
        ids.add(userId);
        pointManager.distributePointsBatch(ids, 50, "USER_COMPENSATION");
        
        // Direct call to PointClient (Cross-Service)
        pointClient.addPoint(userId, 100, "COMPENSATION", 3600L, "REQ_" + userId);
    }

}
