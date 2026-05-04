"""
DeepSeek API 客户端封装
- Chat Completions API (OpenAI兼容)
- 指数退避重试、超时处理
- 结构化错误返回
"""

import os
import json
import time
from typing import Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """获取或初始化DeepSeek客户端"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=60.0,
        )
    return _client


def chat_json(
    messages: list[dict[str, str]],
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    调用 DeepSeek Chat API，要求返回 JSON 结构化输出。

    Returns:
        {"ok": True, "content": dict, "usage": {...}} 或
        {"ok": False, "error": str, "raw_response": str}
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            client = get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                "completion_tokens": response.usage.completion_tokens if response.usage else None,
            }

            # 清理可能的 markdown 代码块包裹
            content_str = raw_content.strip()
            if content_str.startswith("```json"):
                content_str = content_str[7:]
            elif content_str.startswith("```"):
                content_str = content_str[3:]
            if content_str.endswith("```"):
                content_str = content_str[:-3]
            content_str = content_str.strip()

            parsed = json.loads(content_str)
            return {"ok": True, "content": parsed, "usage": usage, "model": model}

        except json.JSONDecodeError as e:
            last_error = f"JSON解析失败: {e}"
            if attempt == max_retries:
                return {"ok": False, "error": last_error, "raw_response": content_str if "content_str" in dir() else ""}

        except Exception as e:
            last_error = f"API调用失败: {type(e).__name__}: {e}"
            if attempt < max_retries:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                return {"ok": False, "error": last_error, "raw_response": ""}

    return {"ok": False, "error": last_error or "未知错误", "raw_response": ""}


def chat_text(
    messages: list[dict[str, str]],
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    调用 DeepSeek Chat API，返回纯文本结果（不走JSON模式）。
    """
    for attempt in range(max_retries + 1):
        try:
            client = get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw_content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                "completion_tokens": response.usage.completion_tokens if response.usage else None,
            }
            return {"ok": True, "content": raw_content, "usage": usage, "model": model}

        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                return {"ok": False, "error": f"API调用失败: {type(e).__name__}: {e}", "raw_response": ""}

    return {"ok": False, "error": "未知错误", "raw_response": ""}
