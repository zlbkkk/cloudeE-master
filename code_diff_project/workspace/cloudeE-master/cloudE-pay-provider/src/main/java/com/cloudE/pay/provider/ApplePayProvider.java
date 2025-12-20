package com.cloudE.pay.provider;

import com.cloudE.dto.BaseResult;
import com.cloudE.pay.redis.RedisService;
import com.netflix.hystrix.contrib.javanica.annotation.HystrixCommand;
import com.netflix.hystrix.contrib.javanica.annotation.HystrixProperty;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;


@Api("apple支付")
@RestController
public class ApplePayProvider {

    private static final Logger log = LoggerFactory.getLogger(ApplePayProvider.class);


    @Resource
    private RedisService redisService;


    @ApiOperation(value = "apple充值", notes = "测试接口")
    @HystrixCommand(fallbackMethod = "rechargeFallBack", commandProperties = {
            @HystrixProperty(name = "execution.isolation.thread.timeoutInMilliseconds", value = "5000")})
    @PostMapping(value = "apple/recharge_v2")
    public BaseResult<Boolean> applePayRecharge(@RequestParam("userId") Long userId, @RequestParam("amount") Double amount) throws Exception {
        log.info("apple recharge {}", amount);
        
        // 增加金额限制逻辑，影响跨服务调用结果
        if (amount > 10000) {
             log.warn("Apple pay recharge amount limit exceeded for user: {}", userId);
             return new BaseResult<>(false, "充值金额超过限额");
        }
        
        redisService.set("apple_recharge_" + userId, amount.toString(), 3600);
        return new BaseResult<>(true);
    }

    private BaseResult<Boolean> rechargeFallBack(Long userId, Double amount, Throwable e) {
        log.error("user:{},apple recharge amount:{}, fail :{}", userId, amount, e.getMessage(), e);
        return new BaseResult<>(false, e.getMessage());
    }

}
