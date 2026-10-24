"""价格提醒调度参数：默认值、上下界阻挡与环境变量覆盖。"""

from __future__ import annotations

from unittest.mock import patch

from src.modules.market.price_alert_scheduler import PriceAlertScheduler
from src.platform.runtime.config import Settings


def test_defaults_prioritise_latency():
    """默认值应把端到端延迟压低：扫描 20s、抖动 3s、投递 3s。"""
    s = PriceAlertScheduler()
    assert s.interval_seconds == 20
    assert s.jitter_seconds == 3
    assert s.delivery_interval_seconds == 3


def test_settings_expose_overrides(monkeypatch):
    """三个间隔都能用环境变量覆盖，便于按实测回退而不改代码。"""
    monkeypatch.setenv("PRICE_ALERT_SCAN_INTERVAL_SECONDS", "45")
    monkeypatch.setenv("PRICE_ALERT_SCAN_JITTER_SECONDS", "10")
    monkeypatch.setenv("PRICE_ALERT_DELIVERY_INTERVAL_SECONDS", "8")
    s = Settings()
    assert s.price_alert_scan_interval_seconds == 45
    assert s.price_alert_scan_jitter_seconds == 10
    assert s.price_alert_delivery_interval_seconds == 8


def test_interval_floor_blocks_source_hammering():
    """间隔太小时被阻挡，避免错配置把报价源打爆。"""
    assert PriceAlertScheduler(interval_seconds=1).interval_seconds == 5


def test_delivery_interval_floor():
    """投递轮询不能配成 0 或负数。"""
    assert PriceAlertScheduler(delivery_interval_seconds=0).delivery_interval_seconds == 1
    assert PriceAlertScheduler(delivery_interval_seconds=-5).delivery_interval_seconds == 1


def test_jitter_never_swallows_the_interval():
    """抖动不得超过间隔本身，否则扫描会被撑到无限等待。"""
    assert PriceAlertScheduler(interval_seconds=10, jitter_seconds=99).jitter_seconds == 5
    assert PriceAlertScheduler(interval_seconds=5, jitter_seconds=99).jitter_seconds == 2


def test_jitter_floor_is_zero():
    """抖动为 0 是合法配置（不错峰）。"""
    assert PriceAlertScheduler(jitter_seconds=0).jitter_seconds == 0
    assert PriceAlertScheduler(jitter_seconds=-3).jitter_seconds == 0


def test_scan_job_uses_configured_jitter():
    """扫描任务的 jitter 来自配置，不再写死 20。"""
    s = PriceAlertScheduler(interval_seconds=20, jitter_seconds=4)
    with patch.object(s.scheduler, 'add_job') as add_job, \
         patch.object(s.scheduler, 'start'), \
         patch('src.platform.scheduling.scheduler_registry.register'):
        s.start()
    calls = [c for c in add_job.call_args_list if c.args and c.args[0] == s._scan_job]
    assert calls, 'scan job was not registered'
    assert calls[0].kwargs['jitter'] == 4
    assert calls[0].kwargs['seconds'] == 20


def test_delivery_job_uses_configured_interval():
    """投递任务的间隔来自配置，不再写死 10。"""
    s = PriceAlertScheduler(delivery_interval_seconds=6)
    with patch.object(s.scheduler, 'add_job') as add_job, \
         patch.object(s.scheduler, 'start'), \
         patch('src.platform.scheduling.scheduler_registry.register'):
        s.start()
    calls = [c for c in add_job.call_args_list if c.args and c.args[0] == s._delivery_job]
    assert calls, 'delivery job was not registered'
    assert calls[0].kwargs['seconds'] == 6

