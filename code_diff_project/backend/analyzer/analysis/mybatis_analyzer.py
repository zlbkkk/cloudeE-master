import os
import re
import xml.etree.ElementTree as ET
from loguru import logger

class MybatisAnalyzer:
    """
    MyBatis XML 分析器
    用于将 XML 的变更映射回 Java Mapper 接口的方法
    """

    def __init__(self, repo_path):
        self.repo_path = repo_path

    def analyze_xml_change(self, file_path, diff_content):
        """
        分析 XML 变更，返回受影响的 Java 方法列表
        返回格式: [{'class_name': 'com.dao.UserMapper', 'method_name': 'selectUser'}]
        """
        full_path = os.path.join(self.repo_path, file_path)
        if not os.path.exists(full_path):
            return []

        try:
            # 1. 解析 XML 获取 namespace (对应 Java Interface)
            tree = ET.parse(full_path)
            root = tree.getroot()
            
            # MyBatis 的根节点通常是 <mapper namespace="...">
            namespace = root.get('namespace')
            if not namespace:
                return []

            # 2. 分析 diff 内容，提取变更的 SQL ID
            changed_ids = self._extract_changed_ids_from_diff(diff_content)
            
            affected_methods = []
            for sql_id in changed_ids:
                affected_methods.append({
                    'class_name': namespace, # Mapper 接口全名
                    'method_name': sql_id,   # 方法名
                    'type': 'MyBatis XML'
                })
                
            return affected_methods

        except Exception as e:
            logger.error(f"Error analyzing MyBatis XML {file_path}: {str(e)}")
            return []

    def _extract_changed_ids_from_diff(self, diff_content):
        """
        从 diff 文本中提取受影响的 tag id (select/update/insert/delete)
        这是一个简化版的启发式分析
        """
        changed_ids = set()
        
        # 正则匹配 MyBatis 的主要标签 ID
        # 例如: <select id="selectUser" ...>
        id_pattern = re.compile(r'<(select|insert|update|delete|sql)\s+.*?id=["\']([^"\']+)["\']', re.DOTALL)
        
        # 简单策略：如果 diff 中包含某个 id 的定义行，或者在某个 id 的范围内，则认为该 id 变更
        # 这里为了稳健，我们扫描 diff 中出现的 id
        # 注意：这里需要更复杂的逻辑来精准定位，目前使用正则匹配 diff 中的 id 引用
        
        lines = diff_content.split('\n')
        for line in lines:
            # 只关注新增或修改的行
            if line.startswith('+') or line.startswith('-'):
                # 尝试在变更行中匹配 id="..."
                match = re.search(r'id=["\']([^"\']+)["\']', line)
                if match:
                    changed_ids.add(match.group(1))
        
        # 如果 diff 没直接改 id 行，而是改了 SQL 内容，我们需要知道当前行属于哪个 id 块
        # 这需要读取完整文件做行号映射 (Context Analysis)，比较复杂。
        # 降级策略：如果解析不到具体的 ID，但文件有变动，我们可以解析文件里所有的 ID (偏保守，但安全)，
        # 或者尝试用正则去匹配 diff 上下文里的 id。
        
        if not changed_ids:
            # 尝试从 diff 上下文 (以空格开头的行) 寻找最近的 id
            # 这是一个简单的回溯查找
            content_str = diff_content
            # 查找所有 id，假设变更影响了文件里的逻辑，我们可以做的更细，
            # 但目前版本如果没匹配到具体 id，返回空可能漏测。
            # 暂时：使用正则全文匹配 diff 块中出现过的 id (包括上下文)
            matches = id_pattern.findall(diff_content)
            for _, extracted_id in matches:
                changed_ids.add(extracted_id)

        return list(changed_ids)
