package com.cloudE.pay.provider;

import com.cloudE.dto.BaseResult;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
public class PointController {

    private static final Logger log = LoggerFactory.getLogger(PointController.class);

    /**
     * 新增积分接口
     */
    @PostMapping("/point/add")
    public BaseResult<Boolean> addPoint(@RequestParam("userId") Long userId, 
                                      @RequestParam("points") Integer points, 
                                      @RequestParam("source") String source,
                                      @RequestParam(value = "expireSeconds", required = false) Long expireSeconds,
                                      @RequestParam("requestId") String requestId) {
        log.info("Adding points for user: {}, points: {}", userId, points);
        
        // [Logic Change 1] 核心风控拦截：单次积分超过5000直接拦截
        if (points > 5000) {
            log.error("Security Alert: Point addition rejected due to limit exceeded! userId={}", userId);
            return new BaseResult<>(false, "Points limit exceeded (Max 5000)");
        }
        
        // [Logic Change 2] 业务逻辑增强：特定渠道双倍积分
        int finalPoints = points;
        if ("APP_ACTIVITY".equals(source)) {
            finalPoints = points * 2;
            log.info("Applying 2x multiplier for APP_ACTIVITY source. Final points: {}", finalPoints);
        }
        
        // TODO: 调用底层Service入库 (模拟)
        // pointService.save(userId, finalPoints);
        
        return new BaseResult<>(true);
    }

    @GetMapping("/point/history")
    public BaseResult<String> getPointHistory(@RequestParam("userId") Long userId) {
        return new BaseResult<>("History Data");
    }
}
