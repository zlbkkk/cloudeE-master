# 重启 Django 服务器指南

## 问题
修改了 Python 代码后，Django 服务器仍在使用旧代码（字节码缓存）。

## 解决方案

### 方法 1：重启 Django 服务器（推荐）

1. 找到运行 Django 服务器的终端窗口
2. 按 `Ctrl+C` 停止服务器
3. 清理字节码缓存：
   ```bash
   cd code_diff_project/backend
   Get-ChildItem -Path . -Include __pycache__ -Recurse -Force | Remove-Item -Recurse -Force
   ```
4. 重新启动服务器：
   ```bash
   python manage.py runserver
   ```

### 方法 2：使用 Django 的自动重载功能

如果你的 Django 服务器是用 `runserver` 启动的，它应该会自动检测文件变化并重新加载。但有时字节码缓存会导致问题。

### 方法 3：强制清理所有缓存

```bash
# 清理 Python 字节码缓存
cd code_diff_project
Get-ChildItem -Path . -Include __pycache__,*.pyc -Recurse -Force | Remove-Item -Recurse -Force

# 重启服务器
cd backend
python manage.py runserver
```

## 验证修复是否生效

重启后，再次运行分析，你应该在日志中看到：

```
[UI入口提取] 开始为 API 提取 UI 入口信息: GET /orders/${orderId}/detail-report
[菜单路径提取] 开始提取菜单路径: ...
[菜单配置] 开始查找菜单配置文件，项目路径: ...
[菜单路径提取] 从配置文件中找到菜单路径: 报表中心 > 订单报告
[UI入口提取] 完成，菜单路径: 报表中心 > 订单报告
```

如果看到这些日志，说明新代码已经生效！
