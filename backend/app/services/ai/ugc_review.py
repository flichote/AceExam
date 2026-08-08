"""UGC review — AI-powered pre-screening for user-submitted questions (M5 T31).

D22 decision: AI only pre-screens, does not final-approve.
- verdict=pass + confidence < 0.95 → status=pending (human review pool)
- verdict=pass + confidence ≥ 0.95 → direct active
- verdict=reject → status=rejected + reject_reason

Output contract:
  {"verdict": "pass"|"reject", "confidence": 0~1, "issues": [{"field", "reason"}], "suggested_fix": "..."}
"""

import json
import logging
import re
from dataclasses import dataclass, field

from app.services.llm_gateway import LLMGateway, llm_gateway

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MIN_CONTENT_LENGTH = 15  # minimum meaningful question stem
AUTO_ACTIVE_THRESHOLD = 0.95  # D22: confidence ≥ 0.95 → direct active

# ── Output structures ────────────────────────────────────────────────────────


@dataclass
class ReviewIssue:
    """A specific issue found during review."""
    field: str       # "content" | "answer" | "options" | "knowledge_point" | "general"
    reason: str      # Human-readable reason


@dataclass
class UGCReviewResult:
    """Result of AI review for a UGC question submission."""
    verdict: str   # "pass" | "reject"
    confidence: float = 0.0   # 0..1
    issues: list[ReviewIssue] = field(default_factory=list)
    suggested_fix: str = ""


# ── Rule-based checks (fast path, no LLM calls) ──────────────────────────────


def _check_content_completeness(content: str) -> list[ReviewIssue]:
    """Check that the question stem is meaningful."""
    issues = []
    stripped = content.strip() if content else ""

    if not stripped:
        issues.append(ReviewIssue(field="content", reason="题干为空"))
        return issues

    if len(stripped) < MIN_CONTENT_LENGTH:
        issues.append(
            ReviewIssue(
                field="content",
                reason=f"题干过短（{len(stripped)} 字，最少 {MIN_CONTENT_LENGTH} 字）",
            )
        )

    # Check for gibberish: high proportion of non-meaningful chars
    meaningful = re.sub(r"[\s\d()\[\]{}，。；：""''！？、…—+*/=<>^-]", "", stripped)
    if len(meaningful) < 4:
        issues.append(ReviewIssue(field="content", reason="题干有效字符过少"))

    return issues


def _check_answer_consistency(
    qtype: str,
    answer: str | list | dict | None,
    options: list[dict] | None,
) -> list[ReviewIssue]:
    """Check that the answer is consistent with the question type and options."""
    issues = []

    if not answer:
        issues.append(ReviewIssue(field="answer", reason="答案为空"))
        return issues

    if qtype in ("single", "multi"):
        if not options:
            issues.append(ReviewIssue(field="options", reason="选择题缺少选项"))
            return issues

        option_keys = {opt.get("key", "") for opt in options if isinstance(opt, dict)}

        # Parse answer: can be string key or {"correct": "key"} dict
        answer_key = answer
        if isinstance(answer, dict):
            answer_key = answer.get("correct", answer.get("answer", ""))
        elif isinstance(answer, list):
            answer_key = answer

        if qtype == "single":
            if isinstance(answer_key, str):
                if answer_key not in option_keys:
                    issues.append(
                        ReviewIssue(
                            field="answer",
                            reason=f"单选题答案 '{answer_key}' 不在选项 {option_keys} 中",
                        )
                    )
            elif isinstance(answer_key, dict):
                correct = answer_key.get("correct", "")
                if correct not in option_keys:
                    issues.append(
                        ReviewIssue(
                            field="answer",
                            reason=f"单选题答案 '{correct}' 不在选项 {option_keys} 中",
                        )
                    )

        elif qtype == "multi":
            keys = answer_key if isinstance(answer_key, list) else [str(answer_key)]
            for k in keys:
                if k not in option_keys:
                    issues.append(
                        ReviewIssue(
                            field="answer",
                            reason=f"多选题答案 '{k}' 不在选项 {option_keys} 中",
                        )
                    )

    elif qtype == "blank":
        if isinstance(answer, str) and len(answer.strip()) < 1:
            issues.append(ReviewIssue(field="answer", reason="填空题答案为空"))

    return issues


def _check_numeric_validation(
    content: str,
    answer: str | dict | None,
) -> list[ReviewIssue]:
    """Rule-based numeric backward validation for calculation-style questions.

    Detects simple numeric patterns like "f(x)=x^3 at x=1" → derivative = 3x^2 = 3.
    This is a lightweight heuristic, not a full CAS.
    """
    issues = []

    # Only attempt for blank/numeric-style answers
    answer_str = ""
    if isinstance(answer, str):
        answer_str = answer.strip()
    elif isinstance(answer, dict):
        answer_str = str(answer.get("correct", "")).strip()

    if not answer_str:
        return issues

    # Heuristic: detect "f(x)=... 在 x=N 处" pattern → check derivative/integral
    # This is a lightweight check; real validation goes through LLM
    try:
        answer_val = float(answer_str)
    except ValueError:
        return issues  # not a numeric answer, skip

    # Simple power rule: f(x) = x^n → f'(x) = n*x^(n-1)
    m = re.search(r"f\s*\(\s*x\s*\)\s*=\s*x\s*\^\s*(\d+)", content)
    if m:
        power = int(m.group(1))
        # Find evaluation point
        at_match = re.search(r"x\s*=\s*(-?\d+)", content)
        if at_match:
            at = float(at_match.group(1))
            expected = power * (at ** (power - 1)) if power > 1 else power
            if abs(answer_val - expected) > 0.01:
                issues.append(
                    ReviewIssue(
                        field="answer",
                        reason=f"数值验算不匹配：f(x)=x^{power} 在 x={at} 处导数应为 {expected}，得到 {answer_val}",
                    )
                )

    return issues


# ── AI prompts ───────────────────────────────────────────────────────────────

_UGC_REVIEW_SYSTEM_PROMPT = """你是 AceExam 题库初审助手。用户提交了一道题目，请进行初审。

输出必须是严格的 JSON 对象：
{
  "verdict": "pass",     // "pass" | "reject"
  "confidence": 0.85,    // 确信度 [0, 1]
  "issues": [            // 发现的问题列表
    {"field": "content", "reason": "题干不完整，缺少关键条件"},
    {"field": "answer", "reason": "答案与解析矛盾"}
  ],
  "suggested_fix": ""    // pass 时可为空；reject 时给出修改建议（≤200字）
}

审查维度：
1. 题干完整性：是否包含完整的已知条件和所求问题？是否有歧义？
2. 答案正确性：答案在逻辑和数学上是否正确？选择题答案是否符合常规？
3. 知识点归属：题目内容是否与声明知识点匹配？
4. 题目质量：是否具有区分度和练习价值？是否过于简单/超纲？

规则：
- 轻微瑕疵（如缺少单位、格式不规范）但答案正确 → verdict=pass，confidence=0.7~0.9
- 答案明显错误、题干缺失关键条件 → verdict=reject，confidence=0.8~1.0
- 完全无法判断（如非学科问题、闲聊、广告）→ verdict=reject，confidence=1.0
- suggested_fix 只在 reject 时提供；pass 时可以为空
- 输出严格 JSON，不要包含 markdown 代码块标记
"""


# ── UGCReviewService ─────────────────────────────────────────────────────────


class UGCReviewService:
    """AI pre-screening for user-submitted questions (UGC).

    Dual-channel: rule-based fast checks + LLM deep review (flash by default,
    pro for low-confidence cases).

    Usage::

        reviewer = UGCReviewService()
        result = await reviewer.review(
            content="求函数 f(x)=x^3 在 x=1 处的导数",
            qtype="single",
            answer="C",
            options=[{"key":"A","text":"1"},{"key":"B","text":"2"},{"key":"C","text":"3"},{"key":"D","text":"0"}],
        )
    """

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway or llm_gateway

    async def review(
        self,
        content: str,
        qtype: str = "single",
        answer: str | list | dict | None = None,
        options: list[dict] | None = None,
        analysis: str = "",
        knowledge_point_name: str = "",
        use_pro: bool = False,
    ) -> UGCReviewResult:
        """Review a UGC question submission.

        Args:
            content: Question stem / body text.
            qtype: Question type (single, multi, blank, essay).
            answer: Expected answer.
            options: Choice options list.
            analysis: Provided solution/explanation.
            knowledge_point_name: Associated knowledge point name.
            use_pro: Use pro tier (for low-confidence re-review).

        Returns:
            UGCReviewResult with verdict, confidence, issues, and suggested_fix.
        """
        # Phase 1: rule-based fast checks
        rule_issues = []
        rule_issues.extend(_check_content_completeness(content))
        rule_issues.extend(_check_answer_consistency(qtype, answer, options))
        rule_issues.extend(_check_numeric_validation(content, answer))

        # Hard reject on empty content
        if any(i.reason == "题干为空" for i in rule_issues):
            return UGCReviewResult(
                verdict="reject",
                confidence=1.0,
                issues=rule_issues,
                suggested_fix="请提供完整的题目题干",
            )

        # Phase 2: AI deep review (flash by default, pro if requested)
        tier = "pro" if use_pro else "flash"
        ai_result = await self._ai_review(
            content=content,
            qtype=qtype,
            answer=answer,
            options=options,
            analysis=analysis,
            knowledge_point_name=knowledge_point_name,
            tier=tier,
        )

        # Merge: rule issues + AI issues
        ai_issues = [
            ReviewIssue(field=issue.get("field", "general"), reason=issue.get("reason", ""))
            for issue in ai_result.get("issues", [])
        ]

        all_issues = rule_issues + ai_issues

        # Determine final verdict
        ai_verdict = ai_result.get("verdict", "pass")
        ai_confidence = float(ai_result.get("confidence", 0.5))

        # Rule issues that are critical → reject
        has_critical_rule = any(
            "答案为空" in i.reason
            or "不在选项" in i.reason
            or "数值验算不匹配" in i.reason
            for i in rule_issues
        )

        if ai_verdict == "reject" or has_critical_rule:
            verdict = "reject"
            confidence = max(ai_confidence, 0.7) if has_critical_rule else ai_confidence
            suggested_fix = ai_result.get("suggested_fix", "")
        else:
            verdict = "pass"
            confidence = min(ai_confidence, 0.9) if rule_issues else ai_confidence
            # Downgrade confidence if rule issues exist
            if rule_issues:
                confidence = min(confidence, 0.85)
            suggested_fix = ""

        return UGCReviewResult(
            verdict=verdict,
            confidence=min(max(confidence, 0.0), 1.0),
            issues=all_issues,
            suggested_fix=suggested_fix,
        )

    # ── AI review ─────────────────────────────────────────────────────────

    async def _ai_review(
        self,
        content: str,
        qtype: str,
        answer: str | list | dict | None,
        options: list[dict] | None,
        analysis: str,
        knowledge_point_name: str,
        tier: str = "flash",
    ) -> dict:
        """Call LLM for deep review of question quality."""
        # Build answer text for prompt
        answer_text = json.dumps(answer, ensure_ascii=False) if answer else "无"
        options_text = json.dumps(options, ensure_ascii=False) if options else "无"

        user_prompt = (
            f"题目类型：{qtype}\n"
            f"题干：{content}\n"
            f"选项：{options_text}\n"
            f"答案：{answer_text}\n"
            f"解析：{analysis or '无'}\n"
            f"知识点：{knowledge_point_name or '未知'}\n\n"
            "请输出初审 JSON。"
        )

        messages = [
            {"role": "system", "content": _UGC_REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            llm_result = await self._gateway.chat(
                tier, messages, temperature=0.2, max_tokens=512,
            )
            content_out = llm_result.get("content", "")
            return self._parse_review_json(content_out)
        except Exception as exc:
            logger.warning("UGC review AI call failed (tier=%s): %s", tier, exc)
            # Fallback: pass with low confidence, defer to human
            return {
                "verdict": "pass",
                "confidence": 0.5,
                "issues": [],
                "suggested_fix": "",
            }

    # ── JSON parsing ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_review_json(content: str) -> dict:
        """Robustly extract review JSON from LLM output."""
        if not content:
            return {"verdict": "pass", "confidence": 0.5, "issues": [], "suggested_fix": ""}

        text = content.strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        parsed = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass

        if not isinstance(parsed, dict):
            return {"verdict": "pass", "confidence": 0.5, "issues": [], "suggested_fix": ""}

        # Validate verdict
        verdict = parsed.get("verdict", "pass")
        if verdict not in ("pass", "reject"):
            verdict = "pass"

        # Clamp confidence
        confidence = float(parsed.get("confidence", 0.5))
        confidence = min(max(confidence, 0.0), 1.0)

        # Normalize issues
        issues = parsed.get("issues", [])
        if not isinstance(issues, list):
            issues = []

        suggested_fix = str(parsed.get("suggested_fix", ""))[:500]

        return {
            "verdict": verdict,
            "confidence": confidence,
            "issues": issues,
            "suggested_fix": suggested_fix,
        }


# ── Module-level convenience singleton ───────────────────────────────────────

ugc_reviewer = UGCReviewService()
