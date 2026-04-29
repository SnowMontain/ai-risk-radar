[README.md](https://github.com/user-attachments/files/27191924/README.md)
# ai-risk-radar
一个使用多 Agent / AI 驱动的项目风险识别 MVP
# AI Risk Radar MVP

一个使用多 Agent / AI 驱动的项目风险识别 MVP。

## 解决的核心痛点

项目风险常常散落在会议纪要、周报、需求文档里，例如：延期、依赖阻塞、范围膨胀、质量问题、客户预期偏差。人工阅读容易漏掉隐性风险，也很难把风险转成可执行行动项。

## 核心逻辑流

```text
项目文本
  -> ExtractorAgent：抽取事实和显性风险
  -> CriticAgent：反向审查，补充隐性风险和追问问题
  -> PlannerAgent：把风险转换为行动项
  -> Orchestrator：汇总报告，输出 Markdown 和 JSON
```

特点：

- 多 Agent 协作。
- 有 LLM 时使用 OpenAI-compatible API。
- 没有 API key 时自动使用规则推理 fallback，可离线运行。
- 输出 `risk_report.md` 和 `risk_report.json`。

## 快速开始

```bash
cd ai-risk-radar-mvp
python -m src.ai_risk_radar --input examples/sample_project_note.txt
```

输出文件会生成到：

```text
outputs/risk_report.md
outputs/risk_report.json
```

## 使用真实 LLM

```bash
export OPENAI_API_KEY="your_key"
export OPENAI_MODEL="gpt-4o-mini"
python -m src.ai_risk_radar --input examples/sample_project_note.txt
```

如使用兼容 OpenAI Chat Completions 的服务：

```bash
export OPENAI_BASE_URL="https://your-provider.example.com/v1/chat/completions"
export OPENAI_API_KEY="your_key"
export OPENAI_MODEL="your_model"
```

## 直接粘贴文本运行

```bash
python -m src.ai_risk_radar
```

然后粘贴项目纪要，按 `Ctrl-D` 结束输入。

## 测试

```bash
python tests/test_basic.py
```

## 工程结构

```text
ai-risk-radar-mvp/
  README.md
  requirements.txt
  run.sh
  examples/
    sample_project_note.txt
  src/
    __init__.py
    ai_risk_radar.py
  tests/
    test_basic.py
```
