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
     * 修改点：增加大额积分预警逻辑
     */
    @PostMapping("/point/add")
    public BaseResult<Boolean> addPoint(@RequestParam("userId") Long userId, 
                                      @RequestParam("points") Integer points, 
                                      @RequestParam("source") String source,
                                      @RequestParam(value = "expireSeconds", required = false) Long expireSeconds,
                                      @RequestParam("requestId") String requestId) {
        log.info("Adding points for user: {}, points: {}", userId, points);
        
        // 模拟业务逻辑变更：大额积分增加风控校验
        if (points > 10000) {
            log.warn("Large point addition detected! Needs approval.");
            // 模拟可能的逻辑改变，比如抛出异常或者进入审核流程
            // return new BaseResult<>(false, "Points too large, pending approval");
        }
        
        return new BaseResult<>(true);
    }

    /**
     * 查询用户积分历史（模拟新接口变更）
     */
    @GetMapping("/point/history")
    public BaseResult<String> getPointHistory(@RequestParam("userId") Long userId) {
        log.info("Querying point history for user: {}", userId);
        // 新增业务逻辑：增加缓存查询
        return new BaseResult<>("Mock History Data from Cache");
    }
}

