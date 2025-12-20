package com.cloudE.pay.provider;

import com.cloudE.dto.BaseResult;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.util.concurrent.ConcurrentHashMap;

@RestController
public class PointController {

    private static final Logger log = LoggerFactory.getLogger(PointController.class);
    // 模拟用户积分缓存锁，防止并发刷分
    private static final ConcurrentHashMap<Long, Long> USER_LOCK_MAP = new ConcurrentHashMap<>();

    /**
     * 核心积分增加接口 (Complex Logic V2)
     */
    @PostMapping("/point/add")
    public BaseResult<String> addPoint(@RequestParam("userId") Long userId, 
                                     @RequestParam("points") Integer points,
                                     @RequestParam(value = "source", required = false) String source) {
        log.info("Processing point addition: userId={}, points={}, source={}", userId, points, source);

        // 1. 并发锁校验 (模拟 Redis 分布式锁)
        if (USER_LOCK_MAP.putIfAbsent(userId, System.currentTimeMillis()) != null) {
            log.warn("Concurrent request rejected for user: {}", userId);
            return new BaseResult<>(false, "SYSTEM_BUSY");
        }

        try {
            // 2. 负数积分处理 (扣减逻辑)
            if (points < 0) {
                // 扣减积分需要强校验余额，这里模拟返回余额不足
                if (Math.abs(points) > 1000) { 
                    return new BaseResult<>(false, "INSUFFICIENT_BALANCE");
                }
                return new BaseResult<>(true, "DEDUCTED");
            }

            // 3. 复杂积分规则引擎
            // 规则A: 活动来源 (PROMOTION) 且积分 > 800 -> 触发自动风控，状态为 PENDING
            if ("PROMOTION".equalsIgnoreCase(source) && points > 800) {
                log.info("Promotion large points -> enters manual review");
                return new BaseResult<>(true, "PENDING_REVIEW"); // 注意：success=true 但 status=PENDING
            }

            // 规则A.1: VIP 奖金 (VIP_BONUS) -> 记录日志但通过
            if ("VIP_BONUS".equalsIgnoreCase(source)) {
                log.info("VIP bonus added");
            }

            // 规则B: 系统补偿 (SYSTEM_COMP) -> 无上限，直接通过
            if ("SYSTEM_COMP".equalsIgnoreCase(source)) {
                log.info("System compensation -> auto approved");
                return new BaseResult<>(true, "SUCCESS");
            }

            // 规则C: 普通来源 -> 单次上限 3000
            if (points > 3000) {
                log.warn("Normal source limit exceeded");
                return new BaseResult<>(false, "LIMIT_EXCEEDED");
            }
            
            // 规则D: 绝对风控熔断
            if (points > 10000) {
                 return new BaseResult<>(false, "RISK_CONTROL_REJECT");
            }

            return new BaseResult<>(true, "SUCCESS");

        } finally {
            // 释放锁
            USER_LOCK_MAP.remove(userId);
        }
    }
}

