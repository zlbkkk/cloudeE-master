# GitLab 自动发现配置指南

## 问题诊断

如果你看到以下错误：
```
第 1 页请求失败: Expecting value: line 1 column 1 (char 0)
[Warning] 未发现任何项目，组织: 'beehive'
```

这通常意味着 **Git 服务器地址填写错误**。

## 正确的配置方式

### 1. Git 服务器地址

**❌ 错误示例：**
```
https://git.hrlyit.com/beehive/beehive-order-finance.git
```
这是一个具体项目的仓库地址，不是服务器根地址！

**✅ 正确示例：**
```
https://git.hrlyit.com
```
只填写 GitLab 服务器的根地址，不要包含任何项目路径或 `.git` 后缀。

### 2. 组织/群组名称

填写你想要扫描的 GitLab 群组（Group）名称：
```
beehive
```

### 3. 访问 Token

需要创建一个具有以下权限的 Personal Access Token：
- `read_api` - 读取 API 权限
- `read_repository` - 读取仓库权限

#### 如何创建 Token：

1. 登录 GitLab
2. 点击右上角头像 → Settings
3. 左侧菜单选择 "Access Tokens"
4. 填写 Token 信息：
   - Name: 随便填，如 "Code Diff Analyzer"
   - Expires at: 选择过期时间
   - Scopes: 勾选 `read_api` 和 `read_repository`
5. 点击 "Create personal access token"
6. **立即复制生成的 Token**（只显示一次！）

### 4. 默认分支

通常填写：
```
master
```
或
```
main
```

## 完整配置示例

```
Git 服务器地址: https://git.hrlyit.com
组织/群组名称: beehive
Git 服务器类型: GitLab
访问 Token: glpat-xxxxxxxxxxxxxxxxxxxx
默认分支: master
```

## API 调用说明

配置正确后，系统会调用以下 GitLab API：
```
GET https://git.hrlyit.com/api/v4/groups/beehive/projects
```

如果配置错误（如填写了完整的项目地址），会尝试调用：
```
GET https://git.hrlyit.com/beehive/beehive-order-finance.git/api/v4/groups/beehive/projects
```
这个地址是无效的，会返回 HTML 错误页面而不是 JSON，导致解析失败。

## 常见问题

### Q1: Token 权限不足
**错误信息：** HTTP 401 或 403

**解决方案：**
- 确保 Token 包含 `read_api` 权限
- 确保 Token 未过期
- 确保你的账号有权限访问该群组

### Q2: 群组名称错误
**错误信息：** HTTP 404

**解决方案：**
- 检查群组名称拼写是否正确
- 确认群组是否存在
- 确认你的账号有权限访问该群组

### Q3: 服务器地址错误
**错误信息：** Expecting value: line 1 column 1 (char 0)

**解决方案：**
- 只填写服务器根地址，不要包含项目路径
- 不要包含 `.git` 后缀
- 确保地址以 `https://` 或 `http://` 开头

## 测试连接

配置完成后，建议先点击"测试连接"按钮（如果有），确认配置正确后再点击"发现项目"。
