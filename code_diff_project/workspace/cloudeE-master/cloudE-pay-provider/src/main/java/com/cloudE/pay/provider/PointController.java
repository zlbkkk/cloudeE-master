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
        
        if (points > 10000) {
            // [Modified] 修改了日志级别和内容，模拟风控升级
            log.error("Security Alert: Large point addition detected! userId={}", userId);
        }
        
        return new BaseResult<>(true);
    }

    @GetMapping("/point/history")
    public BaseResult<String> getPointHistory(@RequestParam("userId") Long userId) {
        return new BaseResult<>("History Data");
    }
}
