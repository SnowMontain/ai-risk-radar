#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI Project Risk Radar MVP

A lightweight multi-agent project risk analysis tool.
- ExtractorAgent: extracts facts and explicit risks
- CriticAgent: checks missed or implicit risks
- PlannerAgent: turns risks into action items
- Orchestrator: coordinates the agents and renders a report

Run:
  python -m src.ai_risk_radar --input examples/sample_project_note.txt

Optional OpenAI-compatible LLM mode:
  export OPENAI_API_KEY="your_key"
  export OPENAI_MODEL="gpt-4o-mini"
  python -m src.ai_risk_radar --input examples/sample_project_note.txt
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Risk:
    title: str
    severity: str
    evidence: str
    reason: str
    mitigation: str


@dataclass
class ActionItem:
    owner: str
    task: str
    priority: str
    due_hint: str


@dataclass
class AgentResult:
    agent: str
    output: Dict[str, Any]


class LLMClient:
    """Tiny OpenAI-compatible chat client using Python stdlib only."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1/chat/completions",
        )

    def available(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str) -> Optional[Dict[str, Any]]:
        if not self.available():
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as exc:
            print(f"[WARN] LLM call failed; using rule-based fallback: {exc}")
            return None


RISK_PATTERNS = [
    ("延期风险", "High", ["delay", "delayed", "deadline", "延期", "推迟", "来不及", "赶不上"]),
    ("依赖阻塞", "High", ["blocked", "blocker", "dependency", "依赖", "等待", "卡住", "阻塞"]),
    ("资源不足", "Medium", ["short staffed", "bandwidth", "人手不足", "缺人", "资源不足", "没有 bandwidth"]),
    ("范围膨胀", "Medium", ["scope creep", "新增需求", "临时需求", "范围扩大", "改需求"]),
    ("质量风险", "High", ["bug", "bugs", "defect", "缺陷", "测试失败", "不稳定", "回归失败"]),
    ("沟通风险", "Medium", ["unclear", "alignment", "ambiguity", "不清楚", "没对齐", "含糊"]),
    ("上线风险", "High", ["launch", "release", "rollout", "上线", "发布", "灰度"]),
]


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"[。！？\n.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def find_owner(text: str) -> str:
    names = re.findall(r"@?([A-Z][a-z]+|[\u4e00-\u9fa5]{2,4})\s*(?:负责|owner|Owner)", text)
    return names[0] if names else "待指定"


class ExtractorAgent:
    name = "ExtractorAgent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, text: str) -> AgentResult:
        system = """
你是项目风险提取 Agent。从项目文本中提取风险信号，输出 JSON：
{
  "facts": ["事实1"],
  "risks": [
    {
      "title": "风险标题",
      "severity": "High/Medium/Low",
      "evidence": "原文证据",
      "reason": "为什么这是风险",
      "mitigation": "缓解建议"
    }
  ]
}
"""
        result = self.llm.chat_json(system, text)
        if result:
            return AgentResult(self.name, result)

        sentences = split_sentences(text)
        facts = sentences[:8]
        risks: List[Dict[str, str]] = []
        lower_text = text.lower()

        for title, severity, keywords in RISK_PATTERNS:
            for kw in keywords:
                if kw.lower() in lower_text:
                    evidence = next(
                        (s for s in sentences if kw.lower() in s.lower()),
                        text[:120],
                    )
                    risks.append(asdict(Risk(
                        title=title,
                        severity=severity,
                        evidence=evidence,
                        reason=f"文本中出现“{kw}”相关信号，可能影响交付稳定性或时间线。",
                        mitigation="明确 owner、截止时间和阻塞升级路径，并在下一次同步会上复盘。",
                    )))
                    break

        return AgentResult(self.name, {"facts": facts, "risks": risks})


class CriticAgent:
    name = "CriticAgent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, text: str, extracted: Dict[str, Any]) -> AgentResult:
        system = """
你是项目审查 Agent。找出 ExtractorAgent 漏掉的隐性风险。输出 JSON：
{
  "missed_risks": [
    {
      "title": "风险标题",
      "severity": "High/Medium/Low",
      "evidence": "证据",
      "reason": "原因",
      "mitigation": "建议"
    }
  ],
  "questions": ["需要追问的问题"]
}
"""
        user = json.dumps({"project_text": text, "extracted_result": extracted}, ensure_ascii=False)
        result = self.llm.chat_json(system, user)
        if result:
            return AgentResult(self.name, result)

        missed: List[Dict[str, str]] = []
        questions: List[str] = []
        lower = text.lower()

        if "deadline" in lower or "截止" in text:
            questions.append("当前 deadline 是否有明确 owner、验收标准和回滚条件？")

        if "客户" in text or "customer" in lower:
            missed.append(asdict(Risk(
                title="客户预期管理风险",
                severity="Medium",
                evidence="文本中提到客户或外部交付。",
                reason="外部客户场景下，需求变动或沟通不充分容易导致验收偏差。",
                mitigation="建立客户确认机制：每次范围变化都记录为决策日志。",
            )))

        if "没有" in text and ("指标" in text or "metric" in lower):
            missed.append(asdict(Risk(
                title="成功标准不清晰",
                severity="High",
                evidence="文本中提到缺少指标或标准。",
                reason="没有可量化指标会导致上线后难以判断项目是否成功。",
                mitigation="补充 North Star metric、验收标准和回滚条件。",
            )))

        return AgentResult(self.name, {"missed_risks": missed, "questions": questions})


class PlannerAgent:
    name = "PlannerAgent"

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, risks: List[Dict[str, Any]]) -> AgentResult:
        system = """
你是项目行动计划 Agent。根据风险列表生成行动项。输出 JSON：
{
  "action_items": [
    {
      "owner": "负责人",
      "task": "行动项",
      "priority": "P0/P1/P2",
      "due_hint": "建议完成时间"
    }
  ]
}
"""
        result = self.llm.chat_json(system, json.dumps(risks, ensure_ascii=False))
        if result:
            return AgentResult(self.name, result)

        items = []
        for risk in risks:
            severity = risk.get("severity", "Medium")
            priority = "P0" if severity == "High" else "P1" if severity == "Medium" else "P2"
            items.append(asdict(ActionItem(
                owner="待指定",
                task=f"处理风险：{risk.get('title')}；建议：{risk.get('mitigation')}",
                priority=priority,
                due_hint="24-48 小时内" if priority == "P0" else "本周内",
            )))
        return AgentResult(self.name, {"action_items": items})


class RiskRadarOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.extractor = ExtractorAgent(self.llm)
        self.critic = CriticAgent(self.llm)
        self.planner = PlannerAgent(self.llm)

    def run(self, text: str) -> Dict[str, Any]:
        extract_result = self.extractor.run(text)
        critic_result = self.critic.run(text, extract_result.output)
        risks = self._dedupe_risks(
            extract_result.output.get("risks", []) + critic_result.output.get("missed_risks", [])
        )
        plan_result = self.planner.run(risks)

        return {
            "mode": "LLM" if self.llm.available() else "Rule-based fallback",
            "facts": extract_result.output.get("facts", []),
            "risks": risks,
            "questions": critic_result.output.get("questions", []),
            "action_items": plan_result.output.get("action_items", []),
            "agent_trace": [asdict(extract_result), asdict(critic_result), asdict(plan_result)],
        }

    @staticmethod
    def _dedupe_risks(risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique = []
        for risk in risks:
            key = risk.get("title", "").strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(risk)
        return unique


def render_markdown(report: Dict[str, Any]) -> str:
    lines = ["# AI 项目风险雷达报告", "", f"运行模式：**{report['mode']}**", ""]

    lines.extend(["## 1. 提取到的关键事实"])
    lines.extend([f"- {fact}" for fact in report["facts"]] or ["- 未提取到明确事实。"])
    lines.append("")

    lines.append("## 2. 风险清单")
    if report["risks"]:
        for idx, risk in enumerate(report["risks"], 1):
            lines.extend([
                f"### 风险 {idx}：{risk.get('title')}",
                f"- 严重级别：**{risk.get('severity')}**",
                f"- 证据：{risk.get('evidence')}",
                f"- 判断原因：{risk.get('reason')}",
                f"- 缓解建议：{risk.get('mitigation')}",
                "",
            ])
    else:
        lines.extend(["- 暂未发现明显风险。", ""])

    lines.append("## 3. 需要追问的问题")
    lines.extend([f"- {q}" for q in report["questions"]] or ["- 暂无。"])
    lines.append("")

    lines.append("## 4. 行动项")
    lines.extend([
        f"- [{a.get('priority')}] {a.get('task')}｜Owner：{a.get('owner')}｜时间：{a.get('due_hint')}"
        for a in report["action_items"]
    ] or ["- 暂无。"])

    return "\n".join(lines)


def analyze_text(text: str) -> Dict[str, Any]:
    return RiskRadarOrchestrator().run(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Project Risk Radar MVP")
    parser.add_argument("--input", "-i", type=str, help="Path to project note text file")
    parser.add_argument("--output-dir", "-o", type=str, default="outputs", help="Directory to save report files")
    parser.add_argument("--json-only", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    if args.input:
        text = Path(args.input).read_text(encoding="utf-8")
    else:
        print("Paste project note text. End with Ctrl-D / Ctrl-Z:")
        import sys
        text = sys.stdin.read()

    if not text.strip():
        raise SystemExit("No input text provided.")

    report = analyze_text(text)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    markdown = render_markdown(report)
    (out_dir / "risk_report.md").write_text(markdown, encoding="utf-8")
    (out_dir / "risk_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json_only else markdown)
    print(f"\nSaved files to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
