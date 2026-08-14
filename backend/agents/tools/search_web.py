import logging

from ddgs import DDGS
from langchain_core.tools import tool

logger = logging.getLogger("tools.search_web")


@tool(parse_docstring=True)
def search_web(query: str) -> str:
    """搜索网络获取实时信息，适合查询新闻、天气、最新事件等。

    Args:
        query: 搜索关键词
    """
    news_keywords = [
        "新闻",
        "动态",
        "最新",
        "今天",
        "事件",
        "发生",
        "价格",
        "天气",
        "股价",
        "近况",
        "怎么样",
        "情况",
        "破产",
        "裁员",
        "融资",
        "倒闭",
        "收购",
        "上市",
    ]
    is_news = any(keyword in query for keyword in news_keywords)

    try:
        with DDGS(timeout=5) as ddgs:
            if is_news:
                results = list(ddgs.news(query, max_results=5, timelimit="w"))
            else:
                results = list(ddgs.text(query, max_results=5, timelimit="m"))
            if results:
                return "\n".join([f"{item['title']}: {item['body']}" for item in results])
    except Exception as exc:
        logger.warning(
            "联网搜索失败，尝试降级: %s", type(exc).__name__,
            extra={"evt": "search_error", "error_type": type(exc).__name__, "is_news": is_news},
        )
        if is_news:
            try:
                with DDGS(timeout=5) as ddgs:
                    results = list(ddgs.text(f"{query} 最新新闻", max_results=5, timelimit="d"))
                if results:
                    return "\n".join([f"{item['title']}: {item['body']}" for item in results])
            except Exception as retry_exc:
                logger.warning(
                    "搜索降级重试也失败: %s", type(retry_exc).__name__,
                    extra={"evt": "search_retry_error", "error_type": type(retry_exc).__name__},
                )
        return "搜索失败，网络连接超时，请稍后重试。"

    return "没有找到相关结果"
