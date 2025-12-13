package com.cloudE.pay.provider;

import com.cloudE.dto.BaseResult;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
public class PointController {

    private static final Logger log = LoggerFactory.getLogger(PointController.class);

    /**
     * 新增积分接口 (位于根目录业务代码)
     */
    @PostMapping("/point/add")
    public BaseResult<Boolean> addPoint(@RequestParam("userId") Long userId, 
                                      @RequestParam("points") Integer points) {
        log.info("Production PointController - Adding points: {}", points);
        
        // [Logic Change] 生产环境业务逻辑：大于2000分需人工审核
        if (points > 2000) {
            log.warn("High value point addition pending approval.");
            return new BaseResult<>(false, "Pending Approval");
        }
        
        return new BaseResult<>(true);
    }
}

