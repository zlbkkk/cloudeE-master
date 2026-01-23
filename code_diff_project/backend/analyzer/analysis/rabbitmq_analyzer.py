"""
RabbitMQ 消息队列分析器

识别 RabbitMQ 消息的生产者和消费者，用于跨服务异步调用分析
"""

import os
import re
import javalang
from loguru import logger


class RabbitMQAnalyzer:
    """
    RabbitMQ 消息队列分析器
    
    识别模式：
    1. 消息生产者：rabbitTemplate.convertAndSend(exchange, routingKey, message)
    2. 消息消费者：@RabbitListener(queues = "queueName")
    """
    
    def __init__(self, project_root):
        self.project_root = project_root
    
    def find_message_producers(self, target_class_name=None, target_method_name=None):
        """
        查找 RabbitMQ 消息生产者
        
        参数:
            target_class_name: 目标类名（可选），如果指定则只查找该类中的消息发送
            target_method_name: 目标方法名（可选），如果指定则只查找该方法中的消息发送
        
        返回:
            消息生产者列表，每个元素包含:
                - file: 文件路径
                - class: 类名
                - method: 方法名
                - line: 行号
                - snippet: 代码片段
                - exchange: 交换机名称
                - routing_key: 路由键
                - message_type: 消息类型（如果能推断）
        """
        producers = []
        
        for root, dirs, files in os.walk(self.project_root):
            # 忽略常见的非源码目录
            for ignore in ["target", "node_modules", ".git", "venv", "__pycache__", "code_diff_project"]:
                if ignore in dirs:
                    dirs.remove(ignore)
            
            for file in files:
                if not file.endswith(".java"):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except:
                    continue
                
                # 快速检查：文件中是否包含 RabbitTemplate
                if 'RabbitTemplate' not in content and 'rabbitTemplate' not in content:
                    continue
                
                # 解析文件
                found_in_file = self._parse_file_for_producers(
                    file_path, content, target_class_name, target_method_name
                )
                producers.extend(found_in_file)
        
        return producers
    
    def _parse_file_for_producers(self, file_path, content, target_class_name, target_method_name):
        """
        解析文件，查找 RabbitMQ 消息生产者
        """
        found = []
        
        try:
            tree = javalang.parse.parse(content)
        except:
            return []
        
        lines = content.splitlines()
        
        # 获取当前文件的类名
        current_class_name = None
        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            current_class_name = node.name
            break
        
        if not current_class_name:
            return []
        
        # 如果指定了目标类名，检查是否匹配
        if target_class_name and current_class_name != target_class_name:
            return []
        
        # 遍历所有方法
        for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
            method_name = method_node.name
            
            # 如果指定了目标方法名，检查是否匹配
            if target_method_name and method_name != target_method_name:
                continue
            
            # 在方法体中查找 rabbitTemplate.convertAndSend 调用
            for _, invoke_node in method_node.filter(javalang.tree.MethodInvocation):
                # 检查是否为 convertAndSend 方法
                if invoke_node.member != 'convertAndSend':
                    continue
                
                # 检查是否为 rabbitTemplate 调用
                if not invoke_node.qualifier or invoke_node.qualifier != 'rabbitTemplate':
                    continue
                
                # 获取行号和代码片段
                line_num = invoke_node.position.line if invoke_node.position else 0
                snippet = lines[line_num - 1].strip() if line_num > 0 and line_num <= len(lines) else "Code snippet not available"
                
                # 提取参数：exchange, routingKey, message
                exchange = None
                routing_key = None
                message_type = None
                
                if invoke_node.arguments and len(invoke_node.arguments) >= 2:
                    # 第一个参数：exchange
                    exchange_arg = invoke_node.arguments[0]
                    exchange = self._extract_argument_value(exchange_arg, content)
                    
                    # 第二个参数：routingKey
                    routing_key_arg = invoke_node.arguments[1]
                    routing_key = self._extract_argument_value(routing_key_arg, content)
                    
                    # 第三个参数：message（如果有）
                    if len(invoke_node.arguments) >= 3:
                        message_arg = invoke_node.arguments[2]
                        message_type = self._infer_message_type(message_arg)
                
                found.append({
                    'file': file_path,
                    'class': current_class_name,
                    'method': method_name,
                    'line': line_num,
                    'snippet': snippet,
                    'exchange': exchange or 'Unknown',
                    'routing_key': routing_key or 'Unknown',
                    'message_type': message_type or 'Unknown',
                    'type': 'rabbitmq_producer'
                })
                
                logger.info(f"Found RabbitMQ producer: {current_class_name}.{method_name} -> exchange={exchange}, routingKey={routing_key}")
        
        return found
    
    def _extract_argument_value(self, arg_node, content):
        """
        提取参数值（字符串字面量或变量名）
        """
        if isinstance(arg_node, javalang.tree.Literal):
            # 字符串字面量
            if arg_node.value:
                return arg_node.value.strip('"').strip("'")
        elif isinstance(arg_node, javalang.tree.MemberReference):
            # 变量引用
            return arg_node.member
        elif hasattr(arg_node, 'member'):
            # 其他类型的成员引用
            return arg_node.member
        
        return None
    
    def _infer_message_type(self, message_arg):
        """
        推断消息类型
        """
        # 如果是方法调用（如 builder().build()）
        if isinstance(message_arg, javalang.tree.MethodInvocation):
            # 尝试获取方法调用链
            if hasattr(message_arg, 'qualifier'):
                return f"MethodCall: {message_arg.qualifier}"
        
        # 如果是类实例化
        elif isinstance(message_arg, javalang.tree.ClassCreator):
            if hasattr(message_arg, 'type') and hasattr(message_arg.type, 'name'):
                return message_arg.type.name
        
        # 如果是变量引用
        elif isinstance(message_arg, javalang.tree.MemberReference):
            return f"Variable: {message_arg.member}"
        
        return None
    
    def find_message_consumers(self, exchange=None, routing_key=None):
        """
        查找 RabbitMQ 消息消费者
        
        参数:
            exchange: 交换机名称（可选）
            routing_key: 路由键（可选）
        
        返回:
            消息消费者列表，每个元素包含:
                - file: 文件路径
                - class: 类名
                - method: 方法名
                - line: 行号
                - snippet: 代码片段
                - queue: 队列名称
                - binding: 绑定信息（如果能推断）
        """
        consumers = []
        
        for root, dirs, files in os.walk(self.project_root):
            # 忽略常见的非源码目录
            for ignore in ["target", "node_modules", ".git", "venv", "__pycache__", "code_diff_project"]:
                if ignore in dirs:
                    dirs.remove(ignore)
            
            for file in files:
                if not file.endswith(".java"):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except:
                    continue
                
                # 快速检查：文件中是否包含 @RabbitListener
                if '@RabbitListener' not in content and '@RabbitHandler' not in content:
                    continue
                
                # 解析文件
                found_in_file = self._parse_file_for_consumers(file_path, content)
                consumers.extend(found_in_file)
        
        return consumers
    
    def _parse_file_for_consumers(self, file_path, content):
        """
        解析文件，查找 RabbitMQ 消息消费者
        """
        found = []
        
        try:
            tree = javalang.parse.parse(content)
        except:
            return []
        
        lines = content.splitlines()
        
        # 获取当前文件的类名
        current_class_name = None
        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            current_class_name = node.name
            break
        
        if not current_class_name:
            return []
        
        # 遍历所有方法
        for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
            method_name = method_node.name
            
            # 检查方法是否有 @RabbitListener 注解
            if not method_node.annotations:
                continue
            
            for ann in method_node.annotations:
                if ann.name not in ['RabbitListener', 'RabbitHandler']:
                    continue
                
                # 提取队列名称
                queue_name = None
                if ann.element:
                    if isinstance(ann.element, list):
                        for elem in ann.element:
                            if elem.name == 'queues':
                                if hasattr(elem.value, 'value'):
                                    queue_name = elem.value.value.strip('"').strip("'")
                                elif isinstance(elem.value, javalang.tree.Literal):
                                    queue_name = elem.value.value.strip('"').strip("'")
                    elif hasattr(ann.element, 'value'):
                        queue_name = ann.element.value.strip('"').strip("'")
                
                # 获取行号和代码片段
                line_num = method_node.position.line if method_node.position else 0
                snippet = lines[line_num - 1].strip() if line_num > 0 and line_num <= len(lines) else "Code snippet not available"
                
                found.append({
                    'file': file_path,
                    'class': current_class_name,
                    'method': method_name,
                    'line': line_num,
                    'snippet': snippet,
                    'queue': queue_name or 'Unknown',
                    'type': 'rabbitmq_consumer'
                })
                
                logger.info(f"Found RabbitMQ consumer: {current_class_name}.{method_name} -> queue={queue_name}")
        
        return found
    
    def find_cross_project_message_flow(self, producer_info):
        """
        查找跨项目的消息流
        
        给定一个消息生产者，查找可能的消费者
        
        参数:
            producer_info: 生产者信息字典，包含 exchange 和 routing_key
        
        返回:
            可能的消费者列表
        """
        exchange = producer_info.get('exchange')
        routing_key = producer_info.get('routing_key')
        
        # 查找所有消费者
        all_consumers = self.find_message_consumers()
        
        # TODO: 实现更复杂的匹配逻辑
        # 需要解析 RabbitMQ 配置文件（如 application.yml）来确定队列与交换机的绑定关系
        # 目前简单返回所有消费者
        
        return all_consumers
