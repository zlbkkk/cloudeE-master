import subprocess
import os
import sys
import json
import urllib.request
import urllib.error

# --- DeepSeek API 配置 ---
DEEPSEEK_API_KEY = "sk-onjbfk7nV3bpqi8hZD9stZ8AFlJ9eUu0dyP1iAEpeWdrlTAo"
# 注意: 这里的 URL 必须是完整的 API 终端地址
DEEPSEEK_API_URL = "https://www.chataiapi.com/v1/chat/completions"
# DeepSeek-V3 (指向 deepseek-chat) 是目前最强、最适合 RAG 的模型
DEEPSEEK_MODEL = "deepseek-chat" 
USE_DEEPSEEK_API = True

def get_git_diff():
    """
    获取最近一次提交的 Diff 信息
    """
    try:
        # 获取当前 HEAD 和上一次提交 HEAD^ 之间的差异
        # 仅针对 src 目录下的 .java 文件
        cmd = ["git", "diff", "HEAD^", "HEAD", "--", "*.java"]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        print("Error: 无法获取 Git Diff，请确保这是一个 Git 仓库且至少有一次提交。")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def parse_diff(diff_text):
    """
    简单的 Diff 解析，按文件拆分
    """
    files_diff = {}
    current_file = None
    buffer = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files_diff[current_file] = "\n".join(buffer)
            
            # 提取文件名 a/path/to/File.java b/path/to/File.java
            parts = line.split()
            if len(parts) >= 4:
                # 取 b/ 路径
                current_file = parts[-1].lstrip("b/")
                buffer = []
        
        buffer.append(line)
    
    # 最后一个文件
    if current_file:
        files_diff[current_file] = "\n".join(buffer)
        
    return files_diff

def call_deepseek_api(messages):
    """
    调用 DeepSeek API
    使用标准库 urllib 避免依赖
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.1
    }
    
    try:
        req = urllib.request.Request(
            DEEPSEEK_API_URL, 
            data=json.dumps(data).encode('utf-8'), 
            headers=headers, 
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                print("API 返回结果异常:", result)
                return None
            
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} - {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

def analyze_with_llm(filename, diff_content):
    print(f"\n🤖 正在使用 DeepSeek ({DEEPSEEK_MODEL}) 分析 {filename} ...")
    
    prompt = f"""
    # Role
    你是一名资深的 Java 测试开发工程师。
    
    # Task
    开发人员修改了文件: {filename}。请根据提供的 Git Diff 分析变更内容，并给出测试建议。
    
    # Git Diff
    {diff_content}
    
    # Requirement
    请返回一个纯 JSON 格式的响应，不要包含 Markdown 格式化（如 ```json），格式如下：
    {{
        "summary": "一句话概括变更内容",
        "impact": "分析可能受影响的功能模块",
        "risk_level": "HIGH/MEDIUM/LOW",
        "test_cases": [
            "测试用例1",
            "测试用例2",
            "测试用例3"
        ]
    }}
    """
    
    messages = [
        {"role": "system", "content": "你是一个能够进行精准测试分析的AI助手。请只输出 JSON。"},
        {"role": "user", "content": prompt}
    ]
    
    response_content = call_deepseek_api(messages)
    
    if not response_content:
        return None
        
    # 尝试解析 JSON
    try:
        # 清理可能存在的 markdown 标记
        cleaned_content = response_content.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_content)
    except json.JSONDecodeError:
        print("解析 AI 响应失败，原始响应:")
        print(response_content)
        # 如果解析失败，返回原始文本作为 summary，避免程序崩溃
        return {
            "summary": "AI 响应格式解析失败",
            "impact": str(response_content)[:100] + "...",
            "risk_level": "UNKNOWN",
            "test_cases": ["请查看控制台原始输出"]
        }

def main():
    print("=== 精准测试分析助手 (DeepSeek版) ===")
    
    # 1. 获取 Diff
    diff_text = get_git_diff()
    if not diff_text:
        print("未检测到 Java 文件的变更 (Git Diff 为空)。")
        print("提示：请确保你已经 commit 了你的代码变更。")
        return

    # 2. 解析 Diff
    files_map = parse_diff(diff_text)
    print(f"检测到 {len(files_map)} 个 Java 文件发生变更。\n")

    # 3. 逐个分析
    for filename, content in files_map.items():
        if USE_DEEPSEEK_API:
            report = analyze_with_llm(filename, content)
        else:
            # Fallback (如果不使用 API)
            print("API 开关未打开")
            continue
            
        if report:
            print("-" * 40)
            print(f"【分析报告】: {filename}")
            print(f"变更摘要: {report.get('summary', 'N/A')}")
            print(f"风险等级: {report.get('risk_level', 'N/A')}")
            print(f"影响分析: {report.get('impact', 'N/A')}")
            print("测试建议:")
            for idx, suggestion in enumerate(report.get('test_cases', []), 1):
                print(f"  {idx}. {suggestion}")
            print("-" * 40)

if __name__ == "__main__":
    main()
