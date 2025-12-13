import javalang
import re
import os

def get_method_ranges(file_path):
    """
    解析 Java 文件，返回所有方法的 (method_name, start_line, end_line) 列表。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = javalang.parse.parse(content)
    except Exception as e:
        print(f"Parse error: {e}")
        return []

    methods = []
    # 获取所有方法节点
    for _, node in tree.filter(javalang.tree.MethodDeclaration):
        if node.name and node.position:
            methods.append({
                'name': node.name,
                'start_line': node.position.line
            })
    
    # 排序
    methods.sort(key=lambda x: x['start_line'])
    
    # 推断结束行 (简单的逻辑：直到下一个方法开始或文件结束)
    # 更严谨的做法是遍历方法体内的节点找到最大行号，或者利用括号匹配。
    # 这里我们用简单逻辑：当前方法结束行 = 下一个方法开始行 - 1
    # 最后一个方法结束行 = 文件总行数
    total_lines = len(content.splitlines())
    
    for i in range(len(methods)):
        if i < len(methods) - 1:
            methods[i]['end_line'] = methods[i+1]['start_line'] - 1
        else:
            methods[i]['end_line'] = total_lines
            
    return methods

def parse_diff_changed_lines(diff_text):
    """
    解析 Diff，返回所有变更（新增/修改）在【新文件】中的行号列表。
    """
    changed_lines = []
    current_line_num = 0
    
    for line in diff_text.splitlines():
        if line.startswith('@@'):
            # Parse header: @@ -old_start,old_len +new_start,new_len @@
            match = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                current_line_num = int(match.group(1))
        elif line.startswith('+') and not line.startswith('+++'):
            changed_lines.append(current_line_num)
            current_line_num += 1
        elif line.startswith('-') and not line.startswith('---'):
            # Deleted line, doesn't exist in new file, so we don't count it for method mapping
            pass
        else:
            # Context line
            current_line_num += 1
            
    return changed_lines

def identify_changed_methods(file_path, diff_text):
    methods = get_method_ranges(file_path)
    changed_lines = parse_diff_changed_lines(diff_text)
    
    affected_methods = set()
    
    print(f"Changed lines in new file: {changed_lines}")
    
    for line_num in changed_lines:
        for m in methods:
            if m['start_line'] <= line_num <= m['end_line']:
                affected_methods.add(m['name'])
                break # A line belongs to only one method
                
    return list(affected_methods)

# Mock Test
# 假设 UserManager.java 的内容
mock_java_path = "code_diff_project/workspace/cloudeE-master/cloudE-ucenter-provider/src/main/java/com/cloudE/ucenter/manager/UserManager.java"
mock_diff = """@@ -34,6 +34,9 @@ public class UserManager {
     java.util.List<Long> ids = new java.util.ArrayList<>();
     ids.add(userId);
     pointManager.distributePointsBatch(ids, 50, "USER_COMPENSATION");
+    
+    // [New Test Change] 新增跨服务调用: 补偿时额外增加积分
+    pointClient.addPoint(userId, 10, "COMPENSATION_EXTRA", 0L);
 }"""

print("Testing with Mock Diff...")
affected = identify_changed_methods(mock_java_path, mock_diff)
print(f"Identified Methods: {affected}")

