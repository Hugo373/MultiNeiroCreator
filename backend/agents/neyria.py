from zhipuai import ZhipuAI

from core.config import API_KEY

client = ZhipuAI(api_key=API_KEY) if API_KEY else None


def build_system_prompt(profile: str, context: str) -> str:
    profile_section = f"\n用户信息：\n{profile}" if profile else ""
    prompt = f"""你是Neyria，用户的私人AI助手，说话不考虑用户体验，不要有情绪。{profile_section}

工具使用规则：
- 涉及实时信息、新闻、天气、最新事件时，必须调用search_web工具
- 涉及数学计算时，调用calculate工具
- 用户追问或质疑某个事实时，必须重新调用search_web验证，不能依赖上下文记忆
- 如果搜索结果包含非中文内容，回答时自动翻译成中文
"""
    if context:
        prompt += f"\n\n参考以下资料回答问题：\n{context}"
        prompt += "\n- 格式要求：请务必使用 Markdown 格式输出。"
    return prompt
