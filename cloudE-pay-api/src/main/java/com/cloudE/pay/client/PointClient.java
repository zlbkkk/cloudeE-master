package com.cloudE.pay.client;

import com.cloudE.dto.BaseResult;
import org.springframework.cloud.netflix.feign.FeignClient;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.Map;

@FeignClient(name = "cloudE-point-provider")
public interface PointClient {

    @RequestMapping(value = "/point/add", method = RequestMethod.POST)
    BaseResult<Boolean> addPoint(@RequestParam("userId") Long userId, @RequestParam("points") Integer points, @RequestParam("source") String source);

    @RequestMapping(value = "/point/get", method = RequestMethod.GET)
    BaseResult<Integer> getPoints(@RequestParam("userId") Long userId);

    /**
     * 批量处理积分变动 (Complex Interface)
     * 用于大促活动期间的批量积分发放或扣减
     *
     * @param userIds 用户ID列表
     * @param amount 变动金额
     * @param operationType 操作类型 (ADD/DEDUCT/FREEZE)
     * @param source 来源渠道
     * @param async 是否异步处理
     * @param extraInfo 扩展信息JSON
     * @return 处理结果映射表
     */
    @RequestMapping(value = "/point/batch/update", method = RequestMethod.POST)
    BaseResult<Map<Long, Boolean>> ·(
            @RequestParam("userIds") List<Long> userIds,
            @RequestParam("amount") Integer amount,
            @RequestParam("operationType") String operationType,
            @RequestParam("source") String source,
            @RequestParam(value = "async", defaultValue = "false") Boolean async,
            @RequestParam(value = "extraInfo", required = false) String extraInfo
    );

    /**
     * 冻结用户积分 (新增接口)
     */
    @RequestMapping(value = "/point/freeze", method = RequestMethod.POST)
    BaseResult<Boolean> freezePoints(
            @RequestParam("userId") Long userId,
            @RequestParam("amount") Integer amount
    );
}
