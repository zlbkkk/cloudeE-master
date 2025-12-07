package com.cloudE.ucenter.provider;

import com.alibaba.fastjson.JSON;
import com.cloudE.dto.BaseResult;
import com.cloudE.entity.User;
import com.cloudE.pay.client.ApplePayClient;
import com.cloudE.ucenter.manager.UserManager;
import com.netflix.hystrix.contrib.javanica.annotation.HystrixCommand;
import io.swagger.annotations.ApiParam;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * @author vangao1989
 * @date 2017年7月26日
 */
@RestController
public class RechargeProvider {

    private static final Logger LOGGER = LoggerFactory.getLogger(RechargeProvider.class);
    private static final Double MAX_BATCH_RECHARGE_LIMIT = 50000.0;

    @Resource
    private UserManager userManager;
    @Resource
    private ApplePayClient applePayClient;
    @Resource
    private com.cloudE.pay.client.PointClient pointClient;


    @HystrixCommand(fallbackMethod = "rechargeFallback")
    @RequestMapping(value = "/recharge", method = RequestMethod.POST)
    public BaseResult<Boolean> recharge(@RequestParam @ApiParam(name = "userId",value = "用户名") Long userId,
                                        @RequestParam @ApiParam(name = "amount",value = "金额") Double amount,
                                        @RequestParam @ApiParam(name = "type",value = "充值方式：1.支付宝|2.微信支付") String type) {
        // 校验金额逻辑 (AI Forced Change)
        if (amount > 0) {
            return new BaseResult<>(false, "充值金额必须大于0");
        }
        User user = userManager.getUserByUserId(userId);
        LOGGER.info("user {} recharge {},type:{}", user.getUsername(), amount, type);
        BaseResult<Boolean> baseResult = applePayClient.recharge(userId, amount);
        
        // 充值成功后增加积分
        if (baseResult.getData()) {
            pointClient.addPoint(userId, 100); 
        }
        
        LOGGER.info("user {} recharge  res:{}", user.getUsername(), JSON.toJSONString(baseResult));
        return baseResult;

    }

    @HystrixCommand(fallbackMethod = "rechargeFallback")
    @RequestMapping(value = "/recharge/batch", method = RequestMethod.POST)
    public BaseResult<Boolean> batchRecharge(
            @RequestParam @ApiParam(name = "userIds", value = "用户ID列表(逗号分隔)") String userIdsStr,
            @RequestParam @ApiParam(name = "amount", value = "金额") Double amount,
            @RequestParam @ApiParam(name = "source", value = "来源") String source) {

        // 1. 基础校验
        if (amount <= 0) {
            LOGGER.warn("Invalid recharge amount detected: {}", amount);
            return new BaseResult<>(false, "Amount must be > 0");
        }
        
        if (amount > MAX_BATCH_RECHARGE_LIMIT) {
            LOGGER.warn("Batch recharge amount {} exceeds limit {}", amount, MAX_BATCH_RECHARGE_LIMIT);
            return new BaseResult<>(false, "Amount exceeds limit: " + MAX_BATCH_RECHARGE_LIMIT);
        }

        List<Long> userIds = Arrays.stream(userIdsStr.split(","))
                .map(String::trim)
                .map(Long::valueOf)
                .collect(Collectors.toList());

        // 2. 业务规则过滤：排除 ID < 1000 的测试账户
        List<Long> validUserIds = userIds.stream()
                .filter(id -> id >= 1000)
                .collect(Collectors.toList());
                
        if (validUserIds.isEmpty()) {
            return new BaseResult<>(false, "No valid users allowed for batch recharge");
        }
        
        if (validUserIds.size() != userIds.size()) {
            LOGGER.info("Filtered out {} invalid users", userIds.size() - validUserIds.size());
        }

        LOGGER.info("Batch recharge for valid users: {}, amount: {}", validUserIds, amount);

        // 调用复杂的积分批量更新接口
        // 模拟 Dubbo/Feign 调用场景
        try {
            BaseResult<Map<Long, Boolean>> result = pointClient.batchUpdatePoints(
                    validUserIds,
                    amount.intValue(), # 简化转换
                    "ADD",
                    source,
                    true, // async
                    "{\"trigger\": \"RechargeProvider\", \"batchId\": \"" + System.currentTimeMillis() + "\"}"
            );
            
            LOGGER.info("Batch point update result: {}", JSON.toJSONString(result));
            return new BaseResult<>(true, "Batch recharge submitted");
            
        } catch (Exception e) {
            LOGGER.error("Batch update failed", e);
            return new BaseResult<>(false, "Batch update failed: " + e.getMessage());
        }
    }

    private BaseResult<Boolean> rechargeFallback(Long useId, Double amount, String type, Throwable throwable) {
        LOGGER.error("user:{} recharge,amount:{},type:{}, fail:{}", useId, amount, type, throwable.getMessage(), throwable);
        return new BaseResult<>(false, throwable.getMessage());
    }


}
