import os
import javalang
import glob
from loguru import logger

class LightStaticAnalyzer:
    def __init__(self, project_root):
        self.project_root = project_root

    def parse_java_file(self, file_path):
        """
        解析 Java 文件，获取包名和类名
        """
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None, None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = javalang.parse.parse(content)
            
            package_name = ''
            if tree.package:
                package_name = tree.package.name
            
            class_name = ''
            for path, node in tree.filter(javalang.tree.ClassDeclaration):
                class_name = node.name
                break # 只取主类
            
            if package_name and class_name:
                full_name = f"{package_name}.{class_name}"
                logger.info(f"Parsed Class: {full_name}")
                return full_name, class_name
            else:
                logger.warning(f"Failed to extract Package/Class from: {file_path}")
                
        except Exception as e:
            logger.error(f"Parse Error in {file_path}: {e}")
            # 解析失败不阻断流程
            pass
            
        return None, None

    def find_usages(self, target_full_class_name):
        """
        在项目中查找谁 Import 了这个类
        返回文件列表
        """
        if not target_full_class_name:
            return []
            
        logger.info(f"Scanning imports for: {target_full_class_name} ...")
        usages = []
        # 简单的文本扫描，查找 "import com.example.MyClass"
        # 这种方式比解析所有文件的 AST 快得多，且对“引用”关系的判断足够准确
        import_stmt = f"import {target_full_class_name}"
        
        # 遍历所有 Java 文件
        scan_count = 0
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith(".java"):
                    scan_count += 1
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if import_stmt in content:
                                # 记录相对路径
                                rel_path = os.path.relpath(file_path, self.project_root)
                                usages.append(rel_path)
                                logger.success(f"-> Found usage in: {rel_path}")
                    except:
                        continue
        
        logger.info(f"Scan complete. Found {len(usages)} usages in {scan_count} files.")
        return usages

    def get_context_for_file(self, file_path):
        """
        获取单个文件的静态分析上下文
        """
        try:
            full_class, simple_class = self.parse_java_file(file_path)
            if not full_class:
                return ""
            
            usages = self.find_usages(full_class)
            if not usages:
                return f"[Static Analysis] Class {simple_class} ({full_class}) has no explicit imports found in other files.\n"
            
            usage_str = ", ".join(usages[:10]) # 限制数量防止 Prompt 过长
            if len(usages) > 10:
                usage_str += "..."
                
            return f"[Static Analysis] Class {simple_class} ({full_class}) is explicitly imported by: {usage_str}.\n"
        except Exception as e:
            return ""
