"""市场扫描只覆盖配置的市场：无持仓/自选的市场不拉榜、不拉 K 线、不用种子池。"""

from __future__ import annotations

import pytest

from src.modules.strategy.entry_candidates import (
    _configured_scan_markets,
    _load_market_scan_inputs,
    _load_market_scan_seed_inputs,
)


def test_default_scan_markets_is_cn_only(monkeypatch):
    """默认只扫 CN，避免为没有持仓的 HK/US 白采并刷失败日志。"""
    monkeypatch.delenv("MARKET_SCAN_MARKETS", raising=False)
    assert _configured_scan_markets() == ["CN"]


def test_scan_markets_honours_explicit_config(monkeypatch):
    """显式配置多个市场时按固定顺序返回，不受配置书写顺序影响。"""
    monkeypatch.setenv("MARKET_SCAN_MARKETS", "US,CN")
    assert _configured_scan_markets() == ["CN", "US"]


def test_scan_markets_falls_back_when_config_is_empty(monkeypatch):
    """配置留空时回落全部市场，保持原有行为。"""
    monkeypatch.setenv("MARKET_SCAN_MARKETS", "")
    assert set(_configured_scan_markets()) == {"CN", "HK", "US"}


def test_scan_markets_ignores_unknown_codes(monkeypatch):
    """无法识别的市场代码被忽略，而不是让扫描静默失败。"""
    monkeypatch.setenv("MARKET_SCAN_MARKETS", "CN,ZZ")
    assert _configured_scan_markets() == ["CN"]


def test_scan_markets_all_invalid_falls_back_to_all(monkeypatch):
    """整条配置都无效时回落全部市场，避免扫描空转。"""
    monkeypatch.setenv("MARKET_SCAN_MARKETS", "ZZ,YY")
    assert set(_configured_scan_markets()) == {"CN", "HK", "US"}


def test_seed_pool_skipped_for_unconfigured_market():
    """种子池不再为未配置市场构造候选。"""
    assert _load_market_scan_seed_inputs(market="HK", limit=60) == {}
    assert _load_market_scan_seed_inputs(market="US", limit=60) == {}


class _FakeCollector:
    """记录被访问的市场，替代真实东财发现接口。"""

    def __init__(self, *args, **kwargs):
        pass

    async def fetch_hot_stocks(self, *, market, mode, limit):
        _FakeCollector.seen.append(market)
        return []


_FakeCollector.seen: list[str] = []


@pytest.fixture
def fake_collector(monkeypatch):
    """把发现采集器换成记录型假实现。"""
    _FakeCollector.seen = []
    monkeypatch.setattr(
        "src.modules.strategy.entry_candidates.EastMoneyDiscoveryCollector", _FakeCollector
    )
    return _FakeCollector


def test_default_scan_only_touches_configured_market(monkeypatch, fake_collector):
    """不显式传 markets 时，只访问配置里的市场。"""
    monkeypatch.setenv("MARKET_SCAN_MARKETS", "CN")
    _load_market_scan_inputs(limit_per_market=20)
    assert fake_collector.seen == ["CN", "CN"]


def test_explicit_markets_still_win_over_config(monkeypatch, fake_collector):
    """调用方显式传 markets 时仍按调用方意愿执行（API/手动刷新可跨市场）。"""
    monkeypatch.setenv("MARKET_SCAN_MARKETS", "CN")
    _load_market_scan_inputs(limit_per_market=20, markets=["HK", "US"])
    assert fake_collector.seen == ["HK", "HK", "US", "US"]

