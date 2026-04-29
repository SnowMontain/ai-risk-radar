from src.ai_risk_radar import analyze_text


def test_basic_risk_detection():
    text = "项目延期，测试环境不稳定，客户下周要 demo，但我们没有成功指标。"
    report = analyze_text(text)
    assert report["risks"]
    assert report["action_items"]


if __name__ == "__main__":
    test_basic_risk_detection()
    print("OK")
