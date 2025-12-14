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
}

