import os
import javalang
import glob
import re
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
            base_path = ''

            # Try finding ClassDeclaration
            for path, node in tree.filter(javalang.tree.ClassDeclaration):
                class_name = node.name
                # Extract Class-level @RequestMapping
                if node.annotations:
                    for ann in node.annotations:
                        if ann.name == 'RequestMapping' or ann.name.endswith('.RequestMapping'):
                            if ann.element:
                                if isinstance(ann.element, list) and len(ann.element) > 0:
                                     # @RequestMapping(value="/path")
                                     for elem in ann.element:
                                         if elem.name == 'value' or elem.name == 'path':
                                             if hasattr(elem.value, 'value'):
                                                 base_path = elem.value.value.strip('"')
                                elif hasattr(ann.element, 'value'):
                                     # @RequestMapping("/path")
                                     base_path = ann.element.value.strip('"')
                break 
            
            # If not found, try InterfaceDeclaration
            if not class_name:
                for path, node in tree.filter(javalang.tree.InterfaceDeclaration):
                    class_name = node.name
                    break

            if package_name and class_name:
                full_name = f"{package_name}.{class_name}"
                logger.info(f"Parsed Class: {full_name}, Base Path: {base_path}")
                return full_name, class_name, base_path
            else:
                logger.warning(f"Failed to extract Package/Class from: {file_path}")
                
        except Exception as e:
            logger.error(f"Parse Error in {file_path}: {e}")
            # 解析失败不阻断流程
            pass
            
        return None, None, None

    def find_usages(self, target_full_class_name):
        """
        在项目中查找谁 Import 了这个类，或者使用了全限定名
        返回详细使用信息列表: [{'path': '...', 'service': '...'}]
        """
        if not target_full_class_name:
            return []
            
        logger.info(f"Scanning imports/usages for: {target_full_class_name} ...")
        usages = []
        # 搜索模式：
        # 1. import com.example.MyClass
        # 2. com.example.MyClass varName
        import_stmt = f"import {target_full_class_name}"
        fqn_usage = target_full_class_name
        
        # 遍历所有 Java 文件
        scan_count = 0
        for root, dirs, files in os.walk(self.project_root):
            if ".git" in dirs: dirs.remove(".git")
            if "target" in dirs: dirs.remove("target")
            if "code_diff_project" in dirs: dirs.remove("code_diff_project")

            for file in files:
                if file.endswith(".java"):
                    scan_count += 1
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            found_type = None
                            
                            # Check explicit import
                            if import_stmt in content:
                                found_type = "explicit import"
                            # Check FQN usage
                            elif fqn_usage in content and not content.startswith(f"package {target_full_class_name}"):
                                full_class, _ = self.parse_java_file(file_path)
                                if full_class != target_full_class_name:
                                    found_type = "FQN"
                            
                            # Advanced Check: Same Package & Star Import
                            if not found_type and '.' in target_full_class_name:
                                target_pkg = target_full_class_name.rsplit('.', 1)[0]
                                target_simple = target_full_class_name.rsplit('.', 1)[1]
                                
                                if target_simple in content:
                                    pkg_match = re.search(r'package\s+([\w.]+);', content)
                                    current_pkg = pkg_match.group(1) if pkg_match else ""
                                    
                                    if current_pkg == target_pkg and f"class {target_simple}" not in content:
                                        found_type = "same package"
                                    
                                    if not found_type:
                                        star_import = f"import {target_pkg}.*;"
                                        if star_import in content:
                                            found_type = "star import"

                            if found_type:
                                rel_path = os.path.relpath(file_path, self.project_root)
                                # 假设第一级目录是服务名
                                service_name = rel_path.split(os.sep)[0]
                                
                                # Extract snippet - Scan whole file to find best usage (Method Call > Declaration > Import)
                                snippet = ""
                                line_num = 0
                                best_score = -1
                                
                                lines = content.splitlines()
                                target_simple = target_full_class_name.split('.')[-1]
                                # Heuristic: Also search for camelCase variable name (e.g. PointManager -> pointManager)
                                target_var = target_simple[0].lower() + target_simple[1:] if target_simple else ""

                                for i, line in enumerate(lines):
                                    current_score = 0
                                    clean_line = line.strip()
                                    
                                    # Check if this line is relevant
                                    is_match = False
                                    
                                    # Once we know the file uses the class, we search for ANY relevant token
                                    # 1. FQN or Import statement
                                    if import_stmt in line or fqn_usage in line: is_match = True
                                    # 2. Simple Class Name (e.g. PointManager)
                                    elif target_simple in line: is_match = True
                                    # 3. Variable Name (e.g. pointManager)
                                    elif target_var and target_var in line: is_match = True
                                    
                                    if not is_match: continue

                                    # Score the match
                                    if clean_line.startswith("import "):
                                        current_score = 0
                                    elif clean_line.startswith(("private ", "public ", "protected ", "@")):
                                        current_score = 1
                                    elif "(" in clean_line:
                                        # Likely a method call or instantiation
                                        current_score = 10
                                    else:
                                        current_score = 2
                                    
                                    # Update best if better
                                    if current_score > best_score:
                                        best_score = current_score
                                        snippet = clean_line
                                        line_num = i + 1
                                        # If we found a call, that's usually good enough, but let's see if we can find more?
                                        # No, sticking to first "Call" found is fine.
                                        if current_score == 10: break

                                if not snippet:
                                    snippet = f"Detected by Static Analysis ({found_type})"

                                usages.append({
                                    "path": rel_path,
                                    "service": service_name,
                                    "type": found_type,
                                    "file_name": file,
                                    "snippet": snippet,
                                    "line": line_num
                                })
                                logger.success(f"-> Found usage ({found_type}) in: {rel_path} (Service: {service_name})")

                    except:
                        continue
        
        logger.info(f"Scan complete. Found {len(usages)} usages in {scan_count} files.")
        return usages

    def get_context_for_file(self, file_path):
        """
        获取单个文件的静态分析上下文
        返回 (context_text, usages_list)
        """
        try:
            full_class, simple_class, base_path = self.parse_java_file(file_path)
            if not full_class:
                return "", []
            
            context_text = ""
            if base_path:
                context_text += f"[Static Analysis] Class Base Request Path: /{base_path.lstrip('/')}\n"
            
            usages = self.find_usages(full_class)
            if not usages:
                context_text += f"[Static Analysis] Class {simple_class} ({full_class}) has no explicit imports found in other files.\n"
                return context_text, []
            
            usage_str_list = [f"{u['path']} (Service: {u['service']})" for u in usages[:10]]
            usage_str = ", ".join(usage_str_list)
            if len(usages) > 10:
                usage_str += "..."
                
            context_text += f"[Static Analysis] Class {simple_class} ({full_class}) is used by: {usage_str}.\n"
            return context_text, usages
        except Exception as e:
            logger.error(f"Context generation failed: {e}")
            return "", []

