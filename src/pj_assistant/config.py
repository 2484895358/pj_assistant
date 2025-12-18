from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Selectors:
    table: str
    pending_button: str
    modal: str
    teacher_tabs: str
    active_block: str
    question_block: str
    comment_textarea: str
    done_text: str
    submit_button: str
    success_confirm_button: str


@dataclass(frozen=True)
class Delays:
    min: int
    max: int


@dataclass(frozen=True)
class BrowserConfig:
    headless: bool
    slow_mo_ms: int


@dataclass(frozen=True)
class AppConfig:
    login_url: str
    list_url: str
    browser: BrowserConfig
    rating_text: str
    comment_templates: list[str]
    delays_ms: Delays
    manual_submit_max_wait_s: int
    selectors: Selectors


def load_config(path: str | Path) -> AppConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    sel = data.get("selectors", {})
    delays = data.get("delays_ms", {})
    browser = data.get("browser", {})

    selectors = Selectors(
        table=sel.get("table", "#kcpjDataTable"),
        pending_button=sel.get("pending_button", 'td:last-child button:text-is("评价")'),
        modal=sel.get("modal", ".modal:visible"),
        teacher_tabs=sel.get("teacher_tabs", ".title .jsxx"),
        active_block=sel.get("active_block", ".pjst .jslb.active"),
        question_block=sel.get("question_block", '.tm[data-fs="5"]'),
        comment_textarea=sel.get("comment_textarea", "textarea.form-control.da"),
        done_text=sel.get("done_text", ".tmtj span"),
        submit_button=sel.get("submit_button", ".modal-footer button.sure"),
        success_confirm_button=sel.get(
            "success_confirm_button",
            ".layui-layer-btn0, .bootbox-accept, button:has-text('确定'), a:has-text('确定')",
        ),
    )

    cfg = AppConfig(
        login_url=str(data["login_url"]),
        list_url=str(data["list_url"]),
        browser=BrowserConfig(
            headless=bool(browser.get("headless", False)),
            slow_mo_ms=int(browser.get("slow_mo_ms", 0)),
        ),
        rating_text=str(data.get("rating_text", "很满意")),
        comment_templates=[str(x) for x in data.get("comment_templates", [])],
        delays_ms=Delays(
            min=int(delays.get("min", 100)),
            max=int(delays.get("max", 350)),
        ),
        manual_submit_max_wait_s=int(data.get("manual_submit_max_wait_s", 0)),
        selectors=selectors,
    )

    if not cfg.comment_templates:
        raise ValueError("comment_templates 不能为空")

    if cfg.delays_ms.min < 0 or cfg.delays_ms.max < cfg.delays_ms.min:
        raise ValueError("delays_ms 配置不合法")

    return cfg
