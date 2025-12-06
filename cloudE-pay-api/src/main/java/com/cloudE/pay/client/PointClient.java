package com.cloudE.pay.client;

import com.cloudE.dto.BaseResult;
import org.springframework.cloud.netflix.feign.FeignClient;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(name = "cloudE-point-provider")
public interface PointClient {

    @RequestMapping(value = "/point/add", method = RequestMethod.POST)
    BaseResult<Boolean> addPoint(@RequestParam("userId") Long userId, @RequestParam("points") Integer points, @RequestParam("source") String source);
}
