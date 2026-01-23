# manageListPage 接口调用流程文档

## 概述

本文档详细梳理了 `manageListPage` 接口的完整调用流程，包括接口定义、调用位置、触发时机、菜单配置和路由配置等信息。

---

## 1. 接口定义

### 1.1 前端接口定义

**文件位置**：`beehive-order-finance-frontend-dev-2.25.0/src/api/orderApi/controller/ofCommonBalanceController.js`

**接口方法**：
```javascript
//分页查询额度
manageListPage(body) {
    return new Promise((resolve, reject) => {
        orderApi({
            url: `/ofCommonBalance/manageListPage`,
            method: 'POST',
            data: body
        }).then(data => {
            resolve(data.data || {})
        }).catch(err => {
            reject()
        })
    })
}
```

### 1.2 后端接口

**接口路径**：`POST /ofCommonBalance/manageListPage`

**后端控制器**：`OfCommonBalanceController.java`

---

## 2. 调用位置

### 2.1 主要调用页面

#### balanceManageHome.vue（额度授信管理页面）

**文件位置**：`beehive-order-finance-frontend-dev-2.25.0/src/views/orderFinancing/balanceManageHome.vue`

**调用方法**：`queryTableList(current, size)`

**调用代码**：
```javascript
queryTableList(current, size) {
  this.tableLoading = true
  this.tableList = []
  let queryCondition = this.getQueryCondition()
  orderApi.ofCommonBalanceController.manageListPage({
    current,
    size,
    queryCondition,
  }).then(data => {
    let {records = [], total} = data
    records.forEach((record, index) => {
      record.id = index + 1
      record.secondLevelFilterObj = {}
      record.secondLevelList.forEach(item => {
        item.statusDictParam = item.status && item.status.dictParam
        item.statusDisplayName = item.status && item.status.displayName
        if (this.balanceCategory === 'CITICBANK') {
          item.creditStatusDictParam = item.creditStatus && item.creditStatus.dictParam
        }
      })
    })
    this.tableList = records
    Object.assign(this.option, {
      page: current,
      pageSize: size,
      total: Number(total),
    })
  }).finally(() => {
    this.tableLoading = false
  })
}
```

#### balanceManageHomeNew.vue（新版本额度授信管理页面）

**文件位置**：`beehive-order-finance-frontend-dev-2.25.0/src/views/orderFinancing/balanceManageHomeNew.vue`

**调用位置**：第 735 行

---

## 3. 调用触发时机

`queryTableList` 方法在以下场景被调用：

### 3.1 页面初始化
- **触发时机**：页面挂载时（`mounted` 生命周期）
- **调用链**：`mounted()` → `init()` → `queryTableList()`
- **代码位置**：`balanceManageHome.vue` 第 259-298 行

### 3.2 用户交互触发

1. **点击搜索按钮**
   - 位置：查询条件区域的搜索按钮
   - 代码：`@click="queryTableList(1,option.pageSize)"`

2. **下拉框选择改变**
   - 被授信企业下拉框：`@change="queryTableList(1, option.pageSize)"`
   - 授信企业下拉框：`@change="queryTableList(1, option.pageSize)"`

3. **分页操作**
   - 页码改变：`@current-change="handleCurrentChange"`
   - 每页条数改变：`@size-change="handleSizeChange"`

4. **标签页切换**
   - 方法：`changeTab()`
   - 切换不同标签页时触发查询

5. **重置查询条件**
   - 方法：`emptyQuery()`
   - 重置后重新查询

---

## 4. 菜单配置

**重要说明**：该接口对应的页面 `/balanceManageHome` 配置在"准入授信"菜单项下，**不是"企业信息"菜单**。

"企业信息"菜单对应的URL是 `/companyInfo`，位于"用户中心"菜单下。

该接口出现在以下菜单配置中：

### 4.1 供应商菜单（SPY_ORDER_MENU）

**文件位置**：`beehive-order-finance-frontend-dev-2.25.0/src/views/container/components/menu.js`

**配置内容**：
```javascript
{
  menuName: "准入授信",
  url: "/balanceManageHome",
  icon: require("@/assets/img/图标/供应商菜单/准入授信.svg"),
}
```

### 4.2 核心企业菜单（CORE_ORDER_MENU）

**配置内容**：
```javascript
{
  menuName: "准入授信",
  url: "/balanceManageHome",
  icon: require("@/assets/img/图标/核心企业/准入授信.svg"),
}
```

### 4.3 资金方菜单（CPT_ORDER_MENU）

**配置内容**：
```javascript
{
  menuName: "准入授信",
  url: "/balanceManageHome",
  icon: require("@/assets/img/图标/资金方/准入授信.svg"),
}
```

### 4.4 农行定制菜单（CPT_ORDER_MENU_ABC）

**配置内容**：
```javascript
{
  menuName: "准入授信",
  url: "/balanceManageHome",
}
```

---

## 5. 路由配置

**文件位置**：`beehive-order-finance-frontend-dev-2.25.0/src/router/router.js`

**路由配置**：
```javascript
{
  path: "/balanceManageHome",
  component: balanceManageHome,
}
```

---

## 6. 接口参数说明

### 6.1 请求参数

```javascript
{
  current: Number,        // 当前页码
  size: Number,          // 每页条数
  queryCondition: {      // 查询条件
    ownership: String,   // 所属关系（ORDER/DEALER）
    spyCompanyId: Number, // 被授信企业ID（可选）
    cptCompanyId: Number, // 授信企业ID（可选）
    // ... 其他查询条件
  }
}
```

### 6.2 响应数据

```javascript
{
  records: Array,  // 数据列表
  total: Number    // 总记录数
}
```

---

## 7. 功能说明

### 7.1 接口功能
- **主要功能**：分页查询额度授信列表
- **业务场景**：额度授信管理页面的核心数据查询接口
- **支持角色**：供应商（SPY）、核心企业（CE）、资金方（CPT）

### 7.2 数据处理
- 对返回的数据进行格式化处理
- 为每条记录添加序号（id）
- 处理二级列表的筛选对象
- 处理状态字典参数和显示名称
- 特殊处理中信银行（CITICBANK）的授信状态

---

## 8. 相关文件清单

### 8.1 前端文件
- `src/api/orderApi/controller/ofCommonBalanceController.js` - 接口定义
- `src/views/orderFinancing/balanceManageHome.vue` - 主要调用页面
- `src/views/orderFinancing/balanceManageHomeNew.vue` - 新版本调用页面
- `src/views/container/components/menu.js` - 菜单配置
- `src/router/router.js` - 路由配置

### 8.2 后端文件
- `OfCommonBalanceController.java` - 后端控制器

---

## 9. 调用流程图

```
用户访问页面
    ↓
路由匹配 /balanceManageHome
    ↓
加载 balanceManageHome 组件
    ↓
mounted() 生命周期
    ↓
init() 初始化方法
    ↓
queryTableList() 查询列表
    ↓
调用 manageListPage 接口
    ↓
POST /ofCommonBalance/manageListPage
    ↓
返回数据并渲染表格
```

---

## 10. 注意事项

1. **页面缓存**：页面销毁时会保存查询条件和分页信息到 `PAGE_CACHE`
2. **加载状态**：接口调用时会设置 `tableLoading` 控制表格加载状态
3. **数据格式化**：返回的数据需要经过格式化处理才能显示
4. **特殊处理**：中信银行（CITICBANK）有特殊的授信状态处理逻辑
5. **多角色支持**：不同角色（SPY/CE/CPT）看到的菜单和功能可能不同

### 10.1 菜单路径说明（重要）

**⚠️ 重要提醒**：该接口对应的菜单路径是 **"准入授信"**，**不是"企业信息"**。

- ✅ **正确**：菜单路径 = "准入授信"
- ❌ **错误**：菜单路径 = "企业信息" 或 "用户中心 > 企业信息"

**原因说明**：
- `/balanceManageHome` 路由在菜单配置中明确对应 `menuName: "准入授信"`
- "企业信息"菜单对应的URL是 `/companyInfo`，位于"用户中心"菜单下
- 在生成测试用例或分析报告时，必须使用正确的菜单路径"准入授信"

**验证方法**：
可以通过以下方式验证菜单路径：
1. 查看 `menu.js` 配置文件，搜索 `url: "/balanceManageHome"`，对应的 `menuName` 就是正确的菜单路径
2. 实际访问系统，点击"准入授信"菜单项，URL会变为 `/balanceManageHome`

---

## 更新记录

- **创建时间**：2026-01-16
- **最后更新**：2026-01-16
- **文档版本**：v1.0


