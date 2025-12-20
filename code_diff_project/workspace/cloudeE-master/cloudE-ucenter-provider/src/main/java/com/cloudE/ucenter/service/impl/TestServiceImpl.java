package com.cloudE.ucenter.service.impl;

import com.cloudE.ucenter.service.TestService;
import com.cloudE.entity.User;
import com.cloudE.mapper.UserMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class TestServiceImpl implements TestService {

    @Autowired
    private UserMapper userMapper;

    @Override
    public User getUserByUsername(String username) {
        // Call the new mapper method
        return userMapper.selectByUsername(username);
    }

    /**
     * 新增方法: 根据用户ID获取用户信息
     * 用于测试代码变更分析工具是否能检测到下游依赖
     * 
     * @param userId 用户ID
     * @return 用户信息
     */
    public User getUserById(Long userId) {
        if (userId == null || userId <= 0) {
            throw new IllegalArgumentException("用户ID不能为空或小于等于0");
        }
        // 调用 UserMapper 的方法
        return userMapper.selectByPrimaryKey(userId);
    }
}

