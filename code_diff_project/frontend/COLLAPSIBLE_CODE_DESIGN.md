# 可折叠代码片段设计文档

## 功能概述

实现了一个可折叠的代码上下文显示组件，默认只显示目标行（调用行），点击按钮可展开显示上下文代码（上下各2行）。

## 设计特点

### 1. 默认状态（收起）
- **只显示目标行**：高亮显示实际调用的代码行
- **简洁界面**：不占用过多空间
- **清晰标识**：使用琥珀色（amber）高亮目标行，左侧有竖线标记
- **展开提示**：顶部有"展开上下文"按钮，底部有提示文字

### 2. 展开状态
- **完整上下文**：显示目标行的上下各2行代码
- **层次分明**：
  - 上文：深色背景（slate-800/50）
  - 目标行：琥珀色高亮（amber-500/10）+ 左侧琥珀色竖线
  - 下文：深色背景（slate-800/50）
- **行号显示**：每行左侧显示行号，便于定位
- **收起按钮**：顶部按钮变为"收起上下文"

### 3. 交互设计
- **点击切换**：点击顶部按钮在展开/收起之间切换
- **平滑过渡**：使用 Tailwind 的 transition 实现平滑动画
- **悬停效果**：上下文行悬停时背景变深，提供视觉反馈
- **独立控制**：多个代码块可以独立展开/收起

## 视觉设计

### 颜色方案
```
背景色：
- 主容器：slate-900（深色）
- 头部：slate-800（稍浅）
- 上下文：slate-800/50（半透明）
- 目标行：amber-500/10（琥珀色半透明）

文字色：
- 行号（上下文）：slate-600
- 代码（上下文）：slate-400
- 行号（目标行）：amber-500（加粗）
- 代码（目标行）：slate-100（加粗）

边框色：
- 外边框：slate-700
- 分隔线：slate-700/50
- 目标行左侧：amber-500（2px）
```

### 尺寸规范
```
容器：
- 最大宽度：max-w-xl（36rem / 576px）
- 圆角：rounded-lg（0.5rem）
- 阴影：shadow-md

间距：
- 头部内边距：px-3 py-1.5
- 代码内边距：px-3 py-1（上下文）/ px-3 py-1.5（目标行）
- 行号宽度：w-8（2rem）
- 行号右边距：mr-3

字体：
- 代码字体：font-mono
- 代码大小：text-[11px]
- 行高：leading-relaxed
- 按钮字体：text-[10px] uppercase tracking-wider
```

## 数据结构

### 后端返回格式（新）
```json
{
  "call_snippet_data": [
    {
      "target_line": 19,
      "target_code": "public String sendNotification(@RequestBody UserDTO user, @RequestParam String message) {",
      "context_before": [
        { "line": 17, "code": "    @Autowired" },
        { "line": 18, "code": "    private NotificationService notificationService;" }
      ],
      "context_after": [
        { "line": 20, "code": "        return notificationService.sendEmail(user, message);" },
        { "line": 21, "code": "    }" }
      ]
    }
  ]
}
```

### 兼容旧格式
组件会自动检测数据格式：
- 如果是字符串（旧格式），直接显示为纯文本
- 如果是结构化数据（新格式），使用可折叠界面

## 组件使用

### 导入
```javascript
import CollapsibleCodeSnippet from './CollapsibleCodeSnippet';
```

### 使用示例
```javascript
<CollapsibleCodeSnippet 
    snippetData={data.call_snippet_data || data.call_snippet}
    fileName={data.file_path ? data.file_path.split(/[/\\]/).pop() : 'Snippet'}
    lineNumber={data.line_number}
/>
```

### Props 说明
- `snippetData`: 代码片段数据（支持新旧两种格式）
- `fileName`: 文件名（显示在头部）
- `lineNumber`: 行号（显示在头部，可选）

## 实现文件

### 后端
- `code_diff_project/backend/analyzer/analysis/ai_analyzer.py`
  - `merge_downstream_line_numbers()` 函数：生成结构化数据

### 前端
- `code_diff_project/frontend/src/components/CollapsibleCodeSnippet.js`
  - 可折叠代码片段组件
- `code_diff_project/frontend/src/components/FlowchartModal.js`
  - 使用新组件替换旧的代码显示

## 优势

1. **界面简洁**：默认只显示关键信息，不占用过多空间
2. **按需展开**：需要时可以查看完整上下文
3. **视觉清晰**：目标行高亮，层次分明
4. **交互友好**：点击切换，操作简单
5. **向后兼容**：支持旧格式数据，平滑过渡
6. **独立控制**：多个代码块可以独立展开/收起

## 效果预览

### 收起状态
```
┌─────────────────────────────────────────────┐
│ 📄 NotificationController.java :L19  ▼展开上下文│
├─────────────────────────────────────────────┤
│ ▌19  public String sendNotification(...)    │ ← 琥珀色高亮
├─────────────────────────────────────────────┤
│        点击上方按钮查看完整上下文                    │
└─────────────────────────────────────────────┘
```

### 展开状态
```
┌─────────────────────────────────────────────┐
│ 📄 NotificationController.java :L19  ▲收起上下文│
├─────────────────────────────────────────────┤
│ 17      @Autowired                          │ ← 深色背景
│ 18      private NotificationService...      │
├─────────────────────────────────────────────┤
│ ▌19  public String sendNotification(...)    │ ← 琥珀色高亮
├─────────────────────────────────────────────┤
│ 20          return notificationService...   │ ← 深色背景
│ 21      }                                   │
└─────────────────────────────────────────────┘
```

## 后续优化建议

1. **可配置行数**：允许用户配置显示的上下文行数（当前固定为2行）
2. **全部展开/收起**：添加全局按钮一键展开/收起所有代码块
3. **代码高亮**：集成语法高亮库（如 Prism.js）
4. **复制功能**：添加复制代码按钮
5. **跳转功能**：点击文件名跳转到源文件（如果支持）
