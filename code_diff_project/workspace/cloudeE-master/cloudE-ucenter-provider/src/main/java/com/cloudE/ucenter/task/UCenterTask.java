package com.cloudE.ucenter.task;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Configurable;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import com.cloudE.ucenter.manager.PointManager;
import javax.annotation.Resource;
import java.util.Collections;

/**
 * Created by carl_gao on 2017/5/17.
 */
@Component
@Configurable
@ConfigurationProperties(prefix = "ucTask")
public class UCenterTask {

    private static final Logger LOGGER = LoggerFactory.getLogger(UCenterTask.class);

    @Resource
    private PointManager pointManager;

    private Integer dynamicParameter;

    @Scheduled(cron = "0/5 * *  * * * ")
    public void dynamicParameterTest() {
        LOGGER.info("dynamicParameterTest,dynamicParameter:{}", dynamicParameter);
        if (dynamicParameter == 1) {
            //TODO 业务1
        } else if (dynamicParameter == 2) {
            //TODO 业务2
            // Task trigger point distribution
            pointManager.distributePointsBatch(Collections.singletonList(1001L), 10, "TASK_TRIGGER");
        }
    }


    public Integer getDynamicParameter() {
        return dynamicParameter;
    }

    public void setDynamicParameter(Integer dynamicParameter) {
        this.dynamicParameter = dynamicParameter;
    }
}
