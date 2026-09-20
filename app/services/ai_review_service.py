"""出張申請の説明文をAIにレビューさせるサービス。

出張のマニュアルには「申請内容はAIレビュアーが確認する」と書いてあり、目的・訪問先・
業務内容が具体的に書かれていない申請は差し戻される。

Amazon Bedrock(Converse API)をboto3から直接呼ぶ。Strandsも検討したが、strands-agentsは
mcpを経由してpydantic>=2.7・httpx>=0.27を要求し、このサービスが固定しているpydantic 2.5 /
httpx 0.25 / FastAPI 0.104(starlette<0.28)のTestClientまで巻き込む必要があったため見送った。
Bedrockの呼び出し自体はNew RelicのAIモニタリングで可視化される(Pythonエージェント11.5.0は
Converse APIを計装している)。

GameDay当日にAWS側で問題が起きても演習が止まらないよう、例外・タイムアウト時は
「レビューを通す」側に倒す(fail-open)。
"""

from dataclasses import dataclass
from typing import Optional
import json
import logging

import newrelic.agent

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.config import Config as BotoConfig
    BOTO3_AVAILABLE = True
except ImportError:  # boto3が無い環境(テスト等)ではAIレビューを行わない
    BOTO3_AVAILABLE = False

SYSTEM_PROMPT = """あなたは日本企業の出張申請をチェックする審査担当者です。
申請の「説明」欄に、出張の目的・訪問先・そこで行う業務内容が具体的に書かれているかを判定してください。

差し戻す例:
- 空欄、「よろしくお願いします」「出張します」など中身が無いもの
- 「打ち合わせのため」のように、誰と何をするのか分からないもの

通す例:
- 目的・訪問先・業務内容のうち、少なくとも目的と業務内容が具体的に読み取れるもの

必ず次のJSONだけを出力してください。説明文やコードブロックは付けないでください。
{"approved": true または false, "reason": "差し戻す場合は、何を追記すればよいかを申請者への敬体の日本語で1〜2文。通す場合は空文字"}"""

_client = None


def _get_client():
    """Bedrock Runtimeクライアント(遅延生成・使い回し)。"""
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=settings.ai_review_region,
            config=BotoConfig(
                connect_timeout=settings.ai_review_connect_timeout_seconds,
                read_timeout=settings.ai_review_timeout_seconds,
                # 演習中に待たされないよう、リトライはしない
                retries={"max_attempts": 1},
            ),
        )
    return _client


@dataclass(frozen=True)
class AiReviewResult:
    approved: bool
    reason: Optional[str] = None


class AiReviewService:

    EMPTY_DESCRIPTION_REASON = (
        "出張の目的・訪問先・そこで行う業務内容を説明欄に具体的に記入してください。"
    )

    FALLBACK_REASON = (
        "説明が具体的ではありません。出張の目的・訪問先・そこで行う業務内容を記入してください。"
    )

    @staticmethod
    def review_business_trip(
        title: Optional[str],
        description: Optional[str],
        departure_city_name: Optional[str] = None,
        arrival_city_name: Optional[str] = None,
    ) -> AiReviewResult:
        """出張申請の説明文をレビューする。approved=Falseなら申請を受け付けない。"""
        if not settings.ai_review_enabled:
            return AiReviewResult(approved=True)

        # 空欄はモデルに聞くまでもないので、その場で差し戻す。
        if description is None or not description.strip():
            newrelic.agent.add_custom_attribute("ai_review_approved", False)
            newrelic.agent.add_custom_attribute("ai_review_skipped", "empty_description")
            return AiReviewResult(approved=False, reason=AiReviewService.EMPTY_DESCRIPTION_REASON)

        if not BOTO3_AVAILABLE:
            logger.warning("AiReviewService: boto3が利用できないためAIレビューをスキップします")
            newrelic.agent.add_custom_attribute("ai_review_skipped", "boto3_unavailable")
            return AiReviewResult(approved=True)

        prompt = AiReviewService._build_prompt(title, description, departure_city_name, arrival_city_name)

        try:
            response = _get_client().converse(
                modelId=settings.ai_review_model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 300, "temperature": 0.0},
            )
            text = AiReviewService._extract_text(response)
            result = AiReviewService._parse_result(text)
        except Exception as e:
            # AWS側の障害・権限不足・タイムアウトで演習が止まらないよう、通す側に倒す。
            logger.error(f"AiReviewService: AIレビューに失敗したため申請を通します: {e}")
            newrelic.agent.add_custom_attribute("ai_review_failed", str(e))
            return AiReviewResult(approved=True)

        newrelic.agent.add_custom_attribute("ai_review_approved", result.approved)
        if result.reason:
            newrelic.agent.add_custom_attribute("ai_review_reason", result.reason)

        return result

    @staticmethod
    def _build_prompt(
        title: Optional[str],
        description: Optional[str],
        departure_city_name: Optional[str],
        arrival_city_name: Optional[str],
    ) -> str:
        lines = [
            "次の出張申請を審査してください。",
            f"タイトル: {title or '(未入力)'}",
            f"出発地: {departure_city_name or '(未指定)'}",
            f"到着地: {arrival_city_name or '(未指定)'}",
            "説明:",
            description or "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _extract_text(response: dict) -> str:
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        return "".join(block.get("text", "") for block in blocks).strip()

    @staticmethod
    def _parse_result(text: str) -> AiReviewResult:
        """モデルの出力からJSONを取り出す。JSONとして読めない場合は差し戻し扱いにする。

        (空欄や中身の無い説明に対して、モデルが崩れた応答を返したときに素通りさせないため。
        AWS呼び出し自体が失敗した場合のfail-openとは区別している。)
        """
        payload = text
        if payload.startswith("```"):
            payload = payload.strip("`")
            if payload.startswith("json"):
                payload = payload[len("json"):]
        start = payload.find("{")
        end = payload.rfind("}")
        if start == -1 or end == -1:
            logger.warning(f"AiReviewService: JSONとして解釈できない応答でした: {text[:200]}")
            return AiReviewResult(approved=False, reason=AiReviewService.FALLBACK_REASON)

        try:
            parsed = json.loads(payload[start:end + 1])
        except json.JSONDecodeError:
            logger.warning(f"AiReviewService: JSONの解析に失敗しました: {text[:200]}")
            return AiReviewResult(approved=False, reason=AiReviewService.FALLBACK_REASON)

        approved = bool(parsed.get("approved"))
        reason = parsed.get("reason") or None

        return AiReviewResult(
            approved=approved,
            reason=None if approved else (reason or AiReviewService.FALLBACK_REASON),
        )
