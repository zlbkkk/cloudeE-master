package com.cloudE.ucenter.manager;

import com.alibaba.fastjson.JSON;
import com.cloudE.dto.BaseResult;
import com.cloudE.pay.client.PointClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * 积分管理层
 * 用于处理复杂的积分业务逻辑，封装远程调用
 */
@Component
public class PointManager {

    private static final Logger LOGGER = LoggerFactory.getLogger(PointManager.class);

    @Resource
    private PointClient pointClient;

    /**
     * 批量发放积分（带重试和日志）
     * [Modified] Added 'forceSync' parameter to control sync/async behavior
     */
    public boolean distributePointsBatch(List<Long> userIds, Integer points, String source, boolean forceSync) {
        LOGGER.info("Manager distributing points to {} users, amount: {}, sync: {}", userIds.size(), points, forceSync);
        
        // 构造扩展信息
        String extraInfo = String.format("{\"manager_version\": \"v3\", \"timestamp\": %d, \"force_sync\": %b}", 
                System.currentTimeMillis(), forceSync);
        
        try {
            // 远程调用
            BaseResult<Map<Long, Boolean>> result = pointClient.batchUpdatePoints(
                    userIds,
                    points,
                    "ADD",
                    source,
                    !forceSync, // 如果强制同步，则异步设为false
                    extraInfo
            );
            
            if (result.isSuccess()) {
                LOGGER.info("Point distribution success: {}", JSON.toJSONString(result.getData()));
                return true;
            } else {
                LOGGER.warn("Point distribution failed: {}", result.getMessage());
                return false;
            }
        } catch (Exception e) {
            LOGGER.error("Remote call exception", e);
            return false;
        }
    }
    
    public void freezeUserPoints(Long userId, Integer amount) {
        LOGGER.info("Freezing points for user {}", userId);
        pointClient.freezePoints(userId, amount);
    }
}
