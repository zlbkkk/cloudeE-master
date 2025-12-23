# 跨项目影响分析测试项目

## 项目结构

本目录包含3个 Spring Boot 项目，用于测试跨项目影响分析功能：

### 1. common-api (公共 API 项目)
- **作用**: 提供公共的 DTO 和服务接口
- **关键文件**:
  - `UserDTO.java`: 用户数据传输对象
  - `UserService.java`: 用户服务接口

### 2. service-a (服务 A - 用户管理服务)
- **作用**: 用户管理服务
- **依赖**: common-api
- **关键文件**:
  - `UserController.java`: 使用 `UserDTO` 和 `UserService`
  - `UserServiceImpl.java`: 实现 `UserService` 接口

### 3. service-b (服务 B - 用户通知服务)
- **作用**: 用户通知服务
- **依赖**: common-api
- **关键文件**:
  - `NotificationController.java`: 使用 `UserDTO`
  - `NotificationService.java`: 使用 `UserDTO` 的方法

## 测试场景

### 场景 1: 修改 UserDTO 添加新字段

**修改文件**: `common-api/src/main/java/com/example/common/dto/UserDTO.java`

**添加新字段**:
```java
private String phoneNumber;

public String getPhoneNumber() {
    return phoneNumber;
}

public void setPhoneNumber(String phoneNumber) {
    this.phoneNumber = phoneNumber;
}
```

**预期影响**:
- ✅ service-a 的 `UserController.java` 和 `UserServiceImpl.java` 会受影响
- ✅ service-b 的 `NotificationController.java` 和 `NotificationService.java` 会受影响

### 场景 2: 修改 UserService 接口添加新方法

**修改文件**: `common-api/src/main/java/com/example/common/service/UserService.java`

**添加新方法**:
```java
/**
 * 更新用户信息
 */
UserDTO updateUser(Long id, String username, String email);
```

**预期影响**:
- ✅ service-a 的 `UserServiceImpl.java` 需要实现新方法
- ⚠️ service-b 不直接实现接口，但可能需要调用新方法

## 如何测试

1. **配置项目关联**:
   - 在系统中配置 service-a 和 service-b 都依赖 common-api

2. **执行分析**:
   - 对 common-api 项目进行代码变更
   - 启用跨项目分析
   - 查看分析报告

3. **验证结果**:
   - 检查是否识别出 service-a 和 service-b 中受影响的文件
   - 验证风险等级评估是否准确

## 项目依赖关系

```
common-api (被依赖)
    ↑
    ├── service-a (依赖 common-api)
    └── service-b (依赖 common-api)
```

## 注意事项

- 这些项目是简化的测试项目，不需要实际运行
- 重点是测试代码依赖关系的识别
- 可以通过修改 common-api 中的代码来触发跨项目影响分析
