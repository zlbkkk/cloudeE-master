# paymentManagementPage 接口测试用例（改进版）

## 接口信息
- **接口路径**: `POST /order-scfPc-web/ofRepayment/paymentManagementPage`
- **接口功能**: 还款/付款管理分页查询

## 调用该接口的前端页面说明

### 1. 供应商端（SPY）- 还款管理
- **路由**: `/orderPaymentManageBook`
- **菜单名称**: "还款管理"
- **页面组件**: `orderPaymentManageBook.vue` 或 `orderPaymentManageBookABC.vue`
- **角色类型**: `companyType === 'SPY'`

### 2. 资金方端（CPT）- 还款管理
- **路由**: `/orderPaymentManageBookCPT`
- **菜单名称**: "还款管理"
- **页面组件**: `orderPaymentManageBookCPT.vue`
- **角色类型**: `companyType === 'CPT'`

### 3. 核心企业端（CE）- 融资还款
- **路由**: `/orderPaymentManageBook`
- **菜单名称**: "融资还款"
- **页面组件**: `orderPaymentManageBook.vue` 或 `orderPaymentManageBookABC.vue`
- **角色类型**: `companyType === 'CE'`

### 4. 核心企业端（CE）- 付款管理
- **路由**: `/paymentManagementCE`
- **菜单名称**: "付款管理"
- **页面组件**: `paymentManagementCE.vue`
- **角色类型**: `companyType === 'CE'`

---

## 测试场景

### 场景1：供应商端 - 还款管理菜单 - 正常分页查询

**测试端**: 供应商端（SPY）  
**路由路径**: `/orderPaymentManageBook`  
**菜单名称**: "还款管理"  
**页面标题**: "还款管理"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用供应商账号登录系统，通过"还款管理"菜单访问还款管理页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为1，每页大小为10，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 10, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面上的还款列表显示正常，包含10条数据，分页信息（总条数、当前页等）显示准确 |

---

### 场景2：供应商端 - 还款管理菜单 - 带查询条件分页查询

**测试端**: 供应商端（SPY）  
**路由路径**: `/orderPaymentManageBook`  
**菜单名称**: "还款管理"  
**页面标题**: "还款管理"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用供应商账号登录系统，通过"还款管理"菜单访问还款管理页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 在查询条件中，输入"供应商企业1"作为融资企业名称，设置当前页码为1，每页大小为5，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 5, "queryCondition": {"cashCompanyName":"供应商企业1"}}` |
| Step 5 (验证UI反馈) | 验证页面上的还款列表显示正常，包含5条数据，且所有数据的"融资企业名称"字段均为"供应商企业1" |

---

### 场景3：资金方端 - 还款管理菜单 - 异常分页参数校验(页码)

**测试端**: 资金方端（CPT）  
**路由路径**: `/orderPaymentManageBookCPT`  
**菜单名称**: "还款管理"  
**页面标题**: "还款管理"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用资金方账号登录系统，通过"还款管理"菜单访问还款管理页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为0，每页大小为10，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 0, "size": 10, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面显示错误提示，如"页码不能为空且必须大于0"，列表数据未更新 |

---

### 场景4：资金方端 - 还款管理菜单 - 异常分页参数校验(每页大小)

**测试端**: 资金方端（CPT）  
**路由路径**: `/orderPaymentManageBookCPT`  
**菜单名称**: "还款管理"  
**页面标题**: "还款管理"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用资金方账号登录系统，通过"还款管理"菜单访问还款管理页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为1，每页大小为101，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 101, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面显示错误提示，如"每页大小必须在1-100之间"，列表数据未更新 |

---

### 场景5：核心企业端 - 融资还款菜单 - 分页边界值校验(每页大小为1)

**测试端**: 核心企业端（CE）  
**路由路径**: `/orderPaymentManageBook`  
**菜单名称**: "融资还款"  
**页面标题**: "融资还款"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用核心企业账号登录系统，通过"融资还款"菜单访问融资还款页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为1，每页大小为1，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 1, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面上的还款列表显示正常，包含1条数据，分页信息显示准确 |

---

### 场景6：核心企业端 - 付款管理菜单 - 分页边界值校验(每页大小为100)

**测试端**: 核心企业端（CE）  
**路由路径**: `/paymentManagementCE`  
**菜单名称**: "付款管理"  
**页面标题**: "付款管理"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用核心企业账号登录系统，通过"付款管理"菜单访问付款管理页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为1，每页大小为100，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 100, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面上的付款列表显示正常，包含最多100条数据（如果数据不足100条则显示实际条数），分页信息显示准确 |

---

## 补充测试场景建议

### 场景7：核心企业端 - 融资还款菜单 - 正常分页查询

**测试端**: 核心企业端（CE）  
**路由路径**: `/orderPaymentManageBook`  
**菜单名称**: "融资还款"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用核心企业账号登录系统，通过"融资还款"菜单访问融资还款页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为1，每页大小为10，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 10, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面上的还款列表显示正常，包含10条数据，分页信息显示准确 |

---

### 场景8：资金方端 - 还款管理菜单 - 正常分页查询

**测试端**: 资金方端（CPT）  
**路由路径**: `/orderPaymentManageBookCPT`  
**菜单名称**: "还款管理"

| 步骤 | 操作说明 |
|------|---------|
| Step 1 (访问页面) | 使用资金方账号登录系统，通过"还款管理"菜单访问还款管理页面 |
| Step 2 (定位元素) | 定位页面上的"搜索"按钮 |
| Step 3 (执行操作) | 设置当前页码为1，每页大小为10，点击"搜索"按钮 |
| Step 4 (验证API调用) | 验证调用了 `POST /order-scfPc-web/ofRepayment/paymentManagementPage` 接口，请求体为：`{"current": 1, "size": 10, "queryCondition": {}}` |
| Step 5 (验证UI反馈) | 验证页面上的还款列表显示正常，包含10条数据，分页信息显示准确 |

---

## 测试用例设计说明

### 如何判断是哪个端？

1. **通过路由路径判断**：
   - `/orderPaymentManageBook` → 可能是供应商端（SPY）或核心企业端（CE）
   - `/orderPaymentManageBookCPT` → 资金方端（CPT）
   - `/paymentManagementCE` → 核心企业端（CE）

2. **通过菜单名称判断**：
   - "还款管理" → 供应商端（SPY）或资金方端（CPT）
   - "融资还款" → 核心企业端（CE）
   - "付款管理" → 核心企业端（CE）

3. **通过登录账号类型判断**：
   - 供应商账号 → `companyType === 'SPY'`
   - 资金方账号 → `companyType === 'CPT'`
   - 核心企业账号 → `companyType === 'CE'`

4. **通过页面显示的字段判断**：
   - 供应商端：显示"资金方"、"交易对手"字段
   - 资金方端：显示"融资企业"、"交易对手"字段
   - 核心企业端：显示"融资企业"、"资金方"字段

### 测试数据准备

- **供应商端测试账号**: 需要准备 `companyType === 'SPY'` 的测试账号
- **资金方端测试账号**: 需要准备 `companyType === 'CPT'` 的测试账号
- **核心企业端测试账号**: 需要准备 `companyType === 'CE'` 的测试账号

### 注意事项

1. 不同端的查询条件字段可能不同，需要根据实际页面字段调整测试用例
2. 不同端的列表显示字段可能不同，验证时需要关注对应端的字段
3. 核心企业端有两个不同的页面（融资还款和付款管理），需要分别测试
4. 测试时需要确保使用对应角色的账号登录，否则可能无法访问对应页面

