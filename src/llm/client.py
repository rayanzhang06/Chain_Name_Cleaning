"""
LLM 客户端 - 集成 Kimi API

提供与大语言模型的交互功能，用于名称匹配。
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple

from anthropic import Anthropic


logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM 客户端 - 封装 Kimi API 调用

    功能：
    - 单次请求
    - 批量请求
    - 提示词管理
    - 响应解析
    - Token 计数
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "kimi-k2-thinking-turbo",
        temperature: float = 0.1,
        max_tokens: int = 4000,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥（可选，默认从环境变量读取）
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key or os.getenv("KIMI_API_KEY")
        if not self.api_key:
            raise ValueError("未找到 API 密钥，请设置 KIMI_API_KEY 环境变量")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

        # 初始化客户端
        self.client = Anthropic(api_key=self.api_key)

        logger.info(f"LLM 客户端初始化完成: {model}")

    def create_message(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建消息

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 其他参数

        Returns:
            响应字典
        """
        # 构建消息列表
        messages = [{"role": "user", "content": prompt}]

        # 构建请求参数
        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        # 添加系统提示词（如果支持）
        if system_prompt:
            request_params["system"] = system_prompt

        # 调用 API
        try:
            response = self.client.messages.create(**request_params)

            # 解析响应
            result = {
                'success': True,
                'content': response.content[0].text,
                'model': response.model,
                'usage': {
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                }
            }

            logger.info(f"LLM 请求成功: 输入 tokens={result['usage']['input_tokens']}, "
                       f"输出 tokens={result['usage']['output_tokens']}")

            return result

        except Exception as e:
            logger.error(f"LLM 请求失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None
            }

    def match_abbreviation(
        self,
        full_name: str,
        province: str,
        candidate_abbreviations: List[str],
        system_prompt: Optional[str] = None,
        history_examples: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        匹配简称（核心方法）

        Args:
            full_name: 连锁药店全称
            province: 省份
            candidate_abbreviations: 候选简称列表
            system_prompt: 系统提示词（可选）
            history_examples: 历史案例列表（可选）

        Returns:
            匹配结果字典
        """
        # 构建提示词
        prompt = self._build_match_prompt(
            full_name=full_name,
            province=province,
            candidate_abbreviations=candidate_abbreviations,
            history_examples=history_examples
        )

        # 调用 LLM
        response = self.create_message(
            prompt=prompt,
            system_prompt=system_prompt or self._get_default_system_prompt()
        )

        if not response['success']:
            return {
                'success': False,
                'abbreviation': None,
                'confidence': 'Low',
                'error': response.get('error')
            }

        # 解析响应
        parsed = self._parse_match_response(response['content'])

        return {
            'success': True,
            'full_name': full_name,
            'abbreviation': parsed.get('abbreviation'),
            'confidence': parsed.get('confidence', 'Low'),
            'reasoning': parsed.get('reasoning', ''),
            'usage': response['usage']
        }

    def _build_match_prompt(
        self,
        full_name: str,
        province: str,
        candidate_abbreviations: List[str],
        history_examples: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        构建匹配提示词

        Args:
            full_name: 连锁药店全称
            province: 省份
            candidate_abbreviations: 候选简称列表
            history_examples: 历史案例

        Returns:
            提示词字符串
        """
        # 候选库列表
        candidates_str = "\n".join([
            f"{i+1}. {abbr}" for i, abbr in enumerate(candidate_abbreviations)
        ])

        # 历史案例
        history_str = ""
        if history_examples:
            history_items = []
            for ex in history_examples[:5]:  # 最多 5 个案例
                history_items.append(
                    f"  - 全称: {ex.get('full_name')}\n"
                    f"    简称: {ex.get('abbreviation')}\n"
                    f"    确认次数: {ex.get('count', 1)}"
                )
            history_str = "\n### 历史确认案例\n" + "\n".join(history_items)

        # 构建提示词
        prompt = f"""请将以下连锁药店全称匹配到正确的简称。

## 目标省份
{province}

## 连锁药店全称
{full_name}

## 候选简称库（必须从中选择）
{candidates_str}

{history_str}

## 任务要求
1. **严格约束**: 只能从上述候选简称库中选择，严禁编造或使用库外简称
2. **省份匹配**: 简称必须属于目标省份【{province}】
3. **找不到匹配时留空**: 如果候选库中没有合适的简称，必须返回空值（null 或空字符串）

## 输出格式
请严格按照以下 JSON 格式输出：
```json
{{
    "abbreviation": "选择的简称或空字符串",
    "confidence": "High/Medium/Low",
    "reasoning": "选择理由（简要说明）"
}}
```

**注意**:
- 如果全称明确匹配某个候选简称，返回 High confidence
- 如果匹配不太确定，返回 Medium confidence
- 如果没有匹配，返回空字符串和 Low confidence
"""

        return prompt

    def _get_default_system_prompt(self) -> str:
        """
        获取默认系统提示词

        Returns:
            系统提示词字符串
        """
        return """你是一个专业的医药连锁名称匹配助手。

核心原则：
1. 严禁编造简称 - 所有简称必须来自候选库
2. 省份必须严格匹配 - 只能从目标省份的候选库中选择
3. 找不到匹配时留空 - 必须返回空值或 null

输出要求：
- 始终返回有效的 JSON 格式
- 简称必须完全匹配候选库中的某一项
- 理由要简洁明了
"""

    def _parse_match_response(self, response: str) -> Dict[str, Any]:
        """
        解析匹配响应

        Args:
            response: LLM 响应文本

        Returns:
            解析后的字典
        """
        # 尝试提取 JSON
        try:
            # 提取 JSON 部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)

                return {
                    'abbreviation': parsed.get('abbreviation', '').strip() or None,
                    'confidence': parsed.get('confidence', 'Low'),
                    'reasoning': parsed.get('reasoning', '')
                }
            else:
                logger.warning(f"响应中未找到 JSON: {response}")
                return {
                    'abbreviation': None,
                    'confidence': 'Low',
                    'reasoning': '解析失败'
                }

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 响应: {response}")
            return {
                'abbreviation': None,
                'confidence': 'Low',
                'reasoning': f'JSON 解析错误: {e}'
            }

    def batch_match_abbreviations(
        self,
        items: List[Dict[str, Any]],
        candidate_abbreviations_dict: Dict[str, List[str]],
        system_prompt: Optional[str] = None,
        history_mappings: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        批量匹配简称

        Args:
            items: 待匹配项列表，每项包含 full_name 和 province
            candidate_abbreviations_dict: 候选简称字典 {省份: [简称列表]}
            system_prompt: 系统提示词（可选）
            history_mappings: 历史映射字典

        Returns:
            匹配结果列表
        """
        results = []

        for item in items:
            full_name = item.get('full_name')
            province = item.get('province')

            if not full_name or not province:
                logger.warning(f"缺少必填字段: {item}")
                results.append({
                    'success': False,
                    'full_name': full_name,
                    'abbreviation': None,
                    'error': '缺少必填字段'
                })
                continue

            # 获取该省份的候选简称
            candidates = candidate_abbreviations_dict.get(province, [])

            if not candidates:
                logger.warning(f"省份 [{province}] 没有候选简称")
                results.append({
                    'success': False,
                    'full_name': full_name,
                    'province': province,
                    'abbreviation': None,
                    'error': '该省份没有候选简称'
                })
                continue

            # 检查历史映射
            history_examples = None
            if history_mappings and full_name in history_mappings:
                mapping = history_mappings[full_name]
                # 如果历史确认次数足够，直接使用
                if mapping.get('confirmation_count', 0) >= 3:
                    results.append({
                        'success': True,
                        'full_name': full_name,
                        'province': province,
                        'abbreviation': mapping['abbreviation'],
                        'confidence': mapping.get('confidence', 'High'),
                        'match_method': 'history',
                        'reasoning': '使用历史确认映射'
                    })
                    continue

            # 调用 LLM 匹配
            result = self.match_abbreviation(
                full_name=full_name,
                province=province,
                candidate_abbreviations=candidates,
                system_prompt=system_prompt,
                history_examples=self._prepare_history_examples(
                    history_mappings, province
                )
            )

            result['match_method'] = 'llm'
            results.append(result)

        logger.info(f"批量匹配完成: {len(results)} 条")
        return results

    def _prepare_history_examples(
        self,
        history_mappings: Optional[Dict[str, Dict[str, Any]]],
        province: str,
        max_count: int = 5
    ) -> Optional[List[Dict[str, str]]]:
        """
        准备历史案例

        Args:
            history_mappings: 历史映射字典
            province: 省份
            max_count: 最大案例数

        Returns:
            历史案例列表或 None
        """
        if not history_mappings:
            return None

        examples = []
        for full_name, mapping in history_mappings.items():
            if mapping.get('confirmation_count', 0) >= 3:
                examples.append({
                    'full_name': full_name,
                    'abbreviation': mapping['abbreviation'],
                    'count': mapping['confirmation_count']
                })

            if len(examples) >= max_count:
                break

        return examples if examples else None


# 便捷函数
def quick_match(
    full_name: str,
    province: str,
    candidate_abbreviations: List[str],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    快速匹配（便捷函数）

    Args:
        full_name: 连锁药店全称
        province: 省份
        candidate_abbreviations: 候选简称列表
        api_key: API 密钥（可选）

    Returns:
        匹配结果
    """
    client = LLMClient(api_key=api_key)
    return client.match_abbreviation(
        full_name=full_name,
        province=province,
        candidate_abbreviations=candidate_abbreviations
    )
