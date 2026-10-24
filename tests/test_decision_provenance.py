"""决策溯源:raw_data.decision_provenance 应该解释"这个结论怎么来的"。

真金白银复盘时，只看"买入/持有"不够；还要知道评级从哪里来、
置信度怎么算出来的、模型配置与数据注入情况如何。
"""

from __future__ import annotations

from types import SimpleNamespace

from src.modules.automation.tradingagents.decision import (
    _extract_confidence,
    map_state_to_result,
)


def _stock():
    return SimpleNamespace(symbol="600519", name="贵州茅台", market=SimpleNamespace(value="CN"))


def _result(decision_raw: str, final_state: dict | None = None) -> dict:
    return {
        "decision": decision_raw,
        "final_state": final_state or {},
        "cost_usd": 0.05,
    }


# ---- 评级来源 ----

def test_rating_source_prefers_state_final_rating():
    """v0.7 final_rating 是权威来源，应记为 state.final_rating。"""
    r = map_state_to_result(stock=_stock(), ta_result=_result("buy", {"final_rating": "buy"}))
    prov = r.raw_data["decision_provenance"]
    assert prov["rating_source"] == "state.final_rating"
    assert prov["upstream_rating"] == "buy"


def test_rating_source_marks_upstream_review():
    """上游 REVIEW 无法解析，来源记为 upstream.decision 且需要复核。"""
    r = map_state_to_result(stock=_stock(), ta_result=_result("REVIEW", {"final_trade_decision": "上游无法解析"}))
    prov = r.raw_data["decision_provenance"]
    assert prov["rating_source"] == "upstream.decision"
    assert prov["review_required"] is True


def test_rating_source_tracks_pm_text_label_then_upstream():
    """正文显式标签优先；标签缺失才回落到上游 decision。"""
    r = map_state_to_result(stock=_stock(), ta_result=_result("HOLD", {"final_trade_decision": "最终交易决策：买入"}))
    prov = r.raw_data["decision_provenance"]
    assert prov["rating_source"] == "pm_text.label"

    r2 = map_state_to_result(stock=_stock(), ta_result=_result("buy", {"final_trade_decision": "无标签正文"}))
    assert r2.raw_data["decision_provenance"]["rating_source"] == "upstream.decision"


def test_rating_source_falls_back_to_keyword_scan():
    """既无标签也无上游评级时，关键词扫描也要记录来源。"""
    r = map_state_to_result(stock=_stock(), ta_result=_result("xxxx", {"final_trade_decision": "建议 Overweight"}))
    prov = r.raw_data["decision_provenance"]
    assert prov["rating_source"] == "pm_text.keyword"
    assert prov["upstream_rating"] == "xxxx"


def test_unresolved_rating_is_marked_not_hold():
    """全部失败时标记 unresolved，而不是静默当成持有。"""
    r = map_state_to_result(stock=_stock(), ta_result=_result("", {"final_trade_decision": ""}))
    prov = r.raw_data["decision_provenance"]
    assert prov["rating_source"] == "unresolved"
    assert prov["review_required"] is True


# ---- 置信度来源 ----

def test_confidence_source_reports_explicit_pm_number():
    value, source = _extract_confidence({"final_trade_decision": "confidence: 7/10"}, "buy")
    assert value == 7.0
    assert source == "pm_text"


def test_confidence_source_reports_risk_and_trader_text():
    value, source = _extract_confidence(
        {"risk_debate_state": {"judge_decision": "置信度：6"}, "trader_investment_plan": "置信度 9"},
        "buy",
    )
    assert value == 6.0
    assert source == "risk_text"

    value2, source2 = _extract_confidence({"trader_investment_plan": "置信度 9"}, "buy")
    assert value2 == 9.0
    assert source2 == "trader_text"


def test_confidence_source_marks_inference_from_rating():
    value, source = _extract_confidence({"final_trade_decision": "无数字"}, "sell")
    assert value == 7.0
    assert source == "rating_inferred"


def test_confidence_source_defaults_when_nothing_is_known():
    value, source = _extract_confidence({"final_trade_decision": ""}, "")
    assert value == 5.0
    assert source == "default"


# ---- 调用方传入的溯源 ----

def test_provenance_carries_model_config_and_data_injection():
    """model_config 只取说明结论的字段；数据注入统计由调用方传入。"""
    run_settings = {
        "llm_provider": "openai_compatible",
        "deep_think_llm": "deepseek-chat",
        "quick_think_llm": "deepseek-chat",
        "max_debate_rounds": 1,
        "selected_analysts": ["market", "news"],
        "online_tools": True,
        "api_key": "sk-secret-should-not-leak",
    }
    r = map_state_to_result(
        stock=_stock(),
        ta_result=_result("buy", {"final_rating": "buy", "run_settings": run_settings}),
        provenance={
            "data_injection": {"kline_bars": 750, "kline_range": ["2023-07-26", "2025-07-01"], "quote": True, "financial": True},
            "run": {"timeout_minutes": 10, "debate_rounds": 1},
        },
    )
    prov = r.raw_data["decision_provenance"]
    model = prov["model_config"]
    assert model["deep_think_llm"] == "deepseek-chat"
    assert model["selected_analysts"] == ["market", "news"]
    assert model["max_debate_rounds"] == 1
    # 密钥类字段不进入溯源，避免落库泄露。
    assert "api_key" not in model
    assert prov["data_injection"]["kline_bars"] == 750
    assert prov["run"]["timeout_minutes"] == 10
    assert prov["confidence_source"] in {"pm_text", "risk_text", "trader_text", "rating_inferred", "default"}


def test_provenance_survives_missing_inputs():
    """无 run_settings / 无 provenance 时也要能出结构，不抛异常。"""
    r = map_state_to_result(stock=_stock(), ta_result=_result("buy", {}))
    prov = r.raw_data["decision_provenance"]
    assert prov["model_config"] == {}
    assert "data_injection" not in prov
    assert prov["rating_source"] == "state.final_rating" if "final_rating" in r.raw_data else True


def test_confidence_in_provenance_is_rounded():
    r = map_state_to_result(stock=_stock(), ta_result=_result("buy", {"final_rating": "buy", "final_trade_decision": "confidence: 6.66"}))
    assert r.raw_data["decision_provenance"]["confidence"] == 6.66
