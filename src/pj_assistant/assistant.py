from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect

from .config import AppConfig


@dataclass(frozen=True)
class CourseRow:
    course_code: str
    course_name: str
    teacher_name: str


def _td_text(tds, index: int) -> str:
    if index < 0 or index >= tds.count():
        return ""
    return tds.nth(index).inner_text().strip()


def _resolve_scope(page: Page, cfg: AppConfig, logger: logging.Logger):
    scopes = [("page", page)]
    for i, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        scopes.append((f"frame[{i}] {frame.url}", frame))

    for name, scope in scopes:
        try:
            if scope.locator(cfg.selectors.table).count():
                logger.info("table scope=%s selector=%s", name, cfg.selectors.table)
                return scope
        except Exception:
            continue

    # Fallback: find a table that has "评价" buttons (common for many portals).
    fallback = 'table:has(button:has-text("评价"))'
    for name, scope in scopes:
        try:
            if scope.locator(fallback).count():
                logger.info("table scope=%s selector=%s (fallback)", name, fallback)
                return scope
        except Exception:
            continue

    # Extra fallback: find a table that has "评价" buttons.
    fallback_eval = 'table:has(button:has-text("评价"))'
    for name, scope in scopes:
        try:
            if scope.locator(fallback_eval).count():
                logger.info("table scope=%s selector=%s (fallback)", name, fallback_eval)
                return scope
        except Exception:
            continue

    # Extra fallback: find a table that has "评价" buttons (for Chinese portals).
    fallback_eval = 'table:has(button:has-text("评价"))'
    for name, scope in scopes:
        try:
            if scope.locator(fallback_eval).count():
                logger.info("table scope=%s selector=%s (fallback)", name, fallback_eval)
                return scope
        except Exception:
            continue

    return page


def _resolve_scope_fast(page: Page, cfg: AppConfig, logger: logging.Logger):
    scopes = [("page", page)]
    for i, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        scopes.append((f"frame[{i}] {frame.url}", frame))

    for name, scope in scopes:
        try:
            if scope.locator(cfg.selectors.table).count():
                logger.info("table scope=%s selector=%s", name, cfg.selectors.table)
                return scope
        except Exception:
            continue

    fallback = 'table:has(button:has-text("评价"))'
    for name, scope in scopes:
        try:
            if scope.locator(fallback).count():
                logger.info("table scope=%s selector=%s (fallback)", name, fallback)
                return scope
        except Exception:
            continue

    return page


def _iter_scopes(page: Page):
    yield ("page", page)
    for i, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        yield (f"frame[{i}] {frame.url}", frame)


def _find_table(scope, cfg: AppConfig):
    table = scope.locator(cfg.selectors.table)
    if table.count():
        return table.first

    # Locate by "评价" button and walk up to its table.
    pending_eval = scope.locator('button:has-text("评价"), a:has-text("评价")')
    if pending_eval.count():
        return pending_eval.first.locator("xpath=ancestor::table[1]")

    fallback_eval = scope.locator('table:has-text("评价")')
    if fallback_eval.count():
        return fallback_eval.first

    # Try find by "评价" action button and walk up to its table.
    pending = scope.locator('button:has-text("评价"), a:has-text("评价")')
    if pending.count():
        return pending.first.locator("xpath=ancestor::table[1]")

    # Before the last resort: locate by "评价" button/text.
    pending_eval = scope.locator('button:has-text("评价"), a:has-text("评价")')
    if pending_eval.count():
        return pending_eval.first.locator("xpath=ancestor::table[1]")

    # Last resort: any table that contains the keyword text.
    fallback_eval = scope.locator('table:has-text("评价")')
    if fallback_eval.count():
        return fallback_eval.first
    fallback = scope.locator('table:has-text("评价")')
    if fallback.count():
        return fallback.first

    return None


def _find_table_fast(scope, cfg: AppConfig):
    table = scope.locator(cfg.selectors.table)
    if table.count():
        return table.first

    pending = scope.locator('button:has-text("评价"), a:has-text("评价")')
    if pending.count():
        return pending.first.locator("xpath=ancestor::table[1]")

    fallback = scope.locator('table:has-text("评价")')
    if fallback.count():
        return fallback.first

    return None


def _wait_for_table(page: Page, cfg: AppConfig, logger: logging.Logger, timeout_ms: int = 30_000):
    deadline = time.monotonic() + timeout_ms / 1000
    last_url = None

    while time.monotonic() < deadline:
        url = page.url
        if url != last_url:
            last_url = url
            logger.info("url=%s", url)

        scope = _resolve_scope_fast(page, cfg, logger)
        table = _find_table_fast(scope, cfg)
        if table is not None and table.count():
            try:
                expect(table).to_be_visible(timeout=1_000)
                return scope, table
            except Exception:
                pass

        time.sleep(0.1)

    # One final attempt so Playwright can include its detailed call log in the exception.
    scope = _resolve_scope_fast(page, cfg, logger)
    table = _find_table_fast(scope, cfg)
    if table is None:
        table = scope.locator(cfg.selectors.table).first
    expect(table).to_be_visible(timeout=1_000)
    return scope, table


def _safe_click(locator, logger: logging.Logger) -> None:
    try:
        locator.click(timeout=2_000)
        return
    except PlaywrightTimeoutError:
        pass

    # Many portals use DataTables FixedColumns: the "fixed" duplicate cell may overlay the original,
    # causing Playwright to report "intercepts pointer events". A forced click or JS click works.
    try:
        logger.info("click retry: force")
        try:
            locator.scroll_into_view_if_needed(timeout=2_000)
        except Exception:
            pass
        try:
            locator.hover(timeout=1_000)
        except Exception:
            pass
        locator.click(timeout=2_000, force=True)
        return
    except PlaywrightTimeoutError:
        logger.info("click retry: js")
        try:
            locator.evaluate("el => el.click()")
            return
        except Exception:
            locator.evaluate(
                """el => el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}))"""
            )


def _safe_click_handle(handle, logger: logging.Logger) -> None:
    try:
        handle.click(timeout=2_000)
        return
    except PlaywrightTimeoutError:
        pass

    try:
        logger.info("click retry(handle): force")
        try:
            handle.scroll_into_view_if_needed(timeout=2_000)
        except Exception:
            pass
        try:
            handle.hover(timeout=1_000)
        except Exception:
            pass
        handle.click(timeout=2_000, force=True)
        return
    except PlaywrightTimeoutError:
        logger.info("click retry(handle): js")
        try:
            handle.evaluate("el => el.click()")
            return
        except Exception:
            handle.evaluate(
                """el => el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}))"""
            )


def _tab_looks_active(class_attr: str) -> bool:
    c = (class_attr or "").lower()
    return any(x in c for x in ("active", "btn-primary", "btn-success", "btn-info", "selected"))


def _wait_teacher_tab_switched(modal_locator, cfg: AppConfig, before_progress: str | None, timeout_s: float = 5.0) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            done = modal_locator.locator(cfg.selectors.done_text)
            if done.count():
                now = done.first.inner_text().strip()
                if before_progress is None or now != before_progress:
                    return
        except Exception:
            pass
        time.sleep(0.1)


def _wait_tab_active_locator(tab, timeout_s: float = 5.0) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            if (tab.get_attribute("aria-selected") or "").lower() == "true":
                return
        except Exception:
            pass
        try:
            if _tab_looks_active(tab.get_attribute("class") or ""):
                return
        except Exception:
            pass
        try:
            parent = tab.locator("xpath=ancestor::*[self::li or self::div][1]")
            if parent.count() and _tab_looks_active(parent.get_attribute("class") or ""):
                return
        except Exception:
            pass
        time.sleep(0.1)


def _wait_tab_active_handle(handle, timeout_s: float = 5.0) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            if (handle.get_attribute("aria-selected") or "").lower() == "true":
                return
        except Exception:
            pass
        try:
            if _tab_looks_active(handle.get_attribute("class") or ""):
                return
        except Exception:
            pass
        time.sleep(0.1)


def _collect_teacher_tabs(modal_locator, logger: logging.Logger):
    # Heuristic for portals that render teacher "tabs" as a row of name buttons.
    # We pick short Chinese-looking labels near the top of the modal.
    name_re = re.compile(r"^[\u4e00-\u9fa5·]{2,8}$")
    skip_text = {
        "提交",
        "取消",
        "关闭",
        "保存",
        # Common rating option labels (avoid mis-detecting question options as "teacher tabs").
        "很满意",
        "满意",
        "一般",
        "不满意",
        "很不满意",
    }

    try:
        modal_box = modal_locator.bounding_box() or {}
        top_y = float(modal_box.get("y", 0.0))
    except Exception:
        top_y = 0.0

    # Prefer explicit teacher elements if present (GXU portal uses span.jsxx[data-gh]).
    explicit = modal_locator.locator(".title .jsxx[data-gh], span.jsxx[data-gh]")
    if explicit.count():
        candidates = explicit
    else:
        candidates = modal_locator.locator("button, a, span").filter(has_text=name_re)
    handles = candidates.element_handles()
    selected: list[tuple[float, str, object]] = []
    seen: set[str] = set()

    for h in handles:
        try:
            txt = (h.inner_text() or "").strip().replace("\n", " ")
        except Exception:
            continue
        if not txt or txt in skip_text or txt in seen:
            continue

        try:
            box = h.bounding_box()
        except Exception:
            box = None
        if box and float(box.get("y", 1e9)) > top_y + 220:
            # Likely question options rather than teacher tabs.
            continue

        seen.add(txt)
        x = float(box.get("x", 0.0)) if box else 0.0
        selected.append((x, txt, h))

    if selected:
        selected.sort(key=lambda t: t[0])
        logger.info("teacher tabs (heuristic)=%s names=%s", len(selected), [t[1] for t in selected])
    return [(t[1], t[2]) for t in selected]


def _wait_for_explicit_teacher_tabs(scope, timeout_s: float = 5.0):
    start = time.monotonic()
    last_count = -1
    while time.monotonic() - start < timeout_s:
        tabs = scope.locator(".title .jsxx[data-gh]")
        try:
            c = tabs.count()
        except Exception:
            c = 0
        if c != last_count:
            last_count = c
        if c:
            return tabs
        time.sleep(0.1)
    return scope.locator(".title .jsxx[data-gh]")


def _wait_for_modal(page: Page, cfg: AppConfig, logger: logging.Logger, timeout_ms: int = 30_000):
    candidates = [
        cfg.selectors.modal,
        ".modal.pjModal",
        ".pjModal",
        ".modal.in",
        ".modal",
    ]
    deadline = time.monotonic() + timeout_ms / 1000

    while time.monotonic() < deadline:
        for scope_name, scope in _iter_scopes(page):
            for sel in candidates:
                try:
                    loc = scope.locator(sel)
                    if loc.count() == 0:
                        continue
                    if loc.first.is_visible():
                        logger.info("modal scope=%s selector=%s", scope_name, sel)
                        return scope, loc.first
                except Exception:
                    continue
        time.sleep(0.1)

    raise RuntimeError(f"未找到评教弹窗（selector={cfg.selectors.modal}）")


def _rand_delay(cfg: AppConfig) -> None:
    ms = random.randint(cfg.delays_ms.min, cfg.delays_ms.max)
    time.sleep(ms / 1000)


def _dismiss_success_dialog(page: Page, logger: logging.Logger) -> bool:
    keywords = ["提交成功", "系统提示"]
    confirm_texts = ["确认", "确定"]
    close_selectors = [
        "button.close",
        ".layui-layer-close",
        ".layui-layer-ico",
        ".el-message-box__headerbtn",
        ".swal2-confirm",
    ]

    for scope_name, scope in _iter_scopes(page):
        try:
            hit = scope.locator(f'text="{keywords[0]}"')
            if hit.count() == 0:
                continue

            container = hit.first.locator(
                "xpath=ancestor-or-self::*[(self::div or self::section or self::article) and "
                "(contains(@class,'modal') or contains(@class,'layui') or contains(@class,'el-message-box') "
                "or contains(@class,'swal2') or @role='dialog')][1]"
            )
            if container.count() == 0:
                container = scope

            for txt in confirm_texts:
                btn = container.first.locator(f'button:visible:has-text("{txt}"), a:visible:has-text("{txt}")').first
                if btn.count():
                    logger.info("dismiss success dialog scope=%s button=%s", scope_name, txt)
                    _safe_click(btn, logger)
                    return True

            for sel in close_selectors:
                btn = container.first.locator(f"{sel}:visible").first
                if btn.count():
                    logger.info("dismiss success dialog scope=%s close=%s", scope_name, sel)
                    _safe_click(btn, logger)
                    return True
        except Exception:
            continue

    return False


def _wait_modal_closed(page: Page, modal_locator, max_wait_s: int, logger: logging.Logger) -> None:
    start = time.monotonic()
    last_print = 0.0
    while True:
        try:
            visible = modal_locator.is_visible()
        except Exception:
            # modal 被销毁时 locator 查询可能抛异常，视为关闭
            return
        if not visible:
            return

        # After you click "提交", a success dialog may require an extra "确认/确定" click.
        _dismiss_success_dialog(page, logger)

        now = time.monotonic()
        if now - last_print >= 10:
            last_print = now
            # Avoid being perceived as "stuck": print periodic status while waiting.
            try:
                aria_hidden = modal_locator.get_attribute("aria-hidden")
            except Exception:
                aria_hidden = None
            print(
                f"[wait] modal still open (aria-hidden={aria_hidden})... 请在页面里点【提交】并等待弹窗关闭"
            )
        if max_wait_s and (time.monotonic() - start) > max_wait_s:
            raise TimeoutError("等待手动提交超时")
        time.sleep(0.1)


def _prefill_active_block(modal_locator, cfg: AppConfig, logger: logging.Logger) -> None:
    active = modal_locator.locator(cfg.selectors.active_block)
    expect(active).to_be_visible()

    def _click_questions(q_locator) -> int:
        q_total = q_locator.count()
        filled = 0
        skipped = 0
        for i in range(q_total):
            q = q_locator.nth(i)
            radios = q.locator("input[type=radio]")
            if radios.count() == 0:
                skipped += 1
                continue

            preferred = q.locator(f'label:has-text("{cfg.rating_text}")')
            if preferred.count():
                _safe_click(preferred.first, logger)
            else:
                labels = q.locator("label")
                if labels.count():
                    _safe_click(labels.nth(labels.count() - 1), logger)
                else:
                    radios.nth(radios.count() - 1).check(force=True)
            _rand_delay(cfg)
            filled += 1

        logger.info("questions total=%s filled=%s skipped(no-radio)=%s", q_total, filled, skipped)
        return filled

    # First try configured selector; if progress shows not complete, broaden to all ".tm".
    questions = active.locator(cfg.selectors.question_block)
    _click_questions(questions)

    comment = active.locator(cfg.selectors.comment_textarea)
    expect(comment).to_be_visible()
    comment.fill(random.choice(cfg.comment_templates))

    def _parse_progress(text: str) -> tuple[int, int] | None:
        # Accept "已做：10/11" / "已做: 10/11" and similar.
        m = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if not m:
            return None
        return int(m.group(1)), int(m.group(2))

    # 如果页面有“已做：x/11”，尽量校验到满
    done = active.locator(cfg.selectors.done_text)
    if done.count():
        txt = done.first.inner_text().strip()
        logger.info("progress=%s", txt)
        parsed = _parse_progress(txt)
        if parsed and parsed[0] < parsed[1]:
            # Some portals count additional questions not matched by default selector.
            all_questions = active.locator(".tm:has(input[type=radio])")
            if all_questions.count():
                logger.info("progress not complete; retry with .tm total=%s", all_questions.count())
                _click_questions(all_questions)
                txt2 = done.first.inner_text().strip()
                logger.info("progress(after retry)=%s", txt2)


def assist_page(page: Page, cfg: AppConfig, logger: logging.Logger) -> None:
    scope, table = _wait_for_table(page, cfg, logger, timeout_ms=30_000)

    rows = table.locator("tbody tr")
    logger.info("rows=%s", rows.count())

    # Faster than scanning every row: repeatedly take the first matching "评价" button.
    while True:
        btns = table.locator(cfg.selectors.pending_button)
        if btns.count() == 0:
            return
        btn = btns.first

        row = btn.locator("xpath=ancestor::tr[1]")
        tds = row.locator("td")
        course = CourseRow(
            course_code=_td_text(tds, 0),
            course_name=_td_text(tds, 1),
            teacher_name=_td_text(tds, 7),
        )

        logger.info("open pending course=%s teacher=%s", course.course_name, course.teacher_name)
        _safe_click(btn, logger)

        modal_scope, modal = _wait_for_modal(page, cfg, logger, timeout_ms=30_000)

        # GXU portal renders teacher "tabs" outside the .modal element (still in the same frame),
        # so locate them from the modal scope instead of the modal root.
        explicit_tabs = _wait_for_explicit_teacher_tabs(modal_scope, timeout_s=5.0)
        if explicit_tabs.count():
            tab_info = explicit_tabs.evaluate_all(
                "els => els.map(e => [e.getAttribute('data-gh'), (e.textContent || '').trim()])"
            )
            logger.info("teacher tabs(explicit)=%s", len(tab_info))
            for gh, name in tab_info:
                if not gh:
                    continue
                if name:
                    logger.info("prefill teacher tab=%s", name)

                tab = modal_scope.locator(f'.title .jsxx[data-gh="{gh}"]').first
                _safe_click(tab, logger)
                expect(modal_scope.locator(f'.title .jsxx.active[data-gh="{gh}"]')).to_be_visible(timeout=5_000)
                try:
                    active_block = modal.locator(f'.pjst .jslb.active[data-gh="{gh}"]')
                    if active_block.count():
                        expect(active_block.first).to_be_visible(timeout=5_000)
                except Exception:
                    pass
                page.wait_for_timeout(50)
                _prefill_active_block(modal, cfg, logger)

            submit_btn = modal.locator(cfg.selectors.submit_button)
            expect(submit_btn).to_be_visible()
            logger.info("Auto submitting (explicit tabs)...")
            _safe_click(submit_btn, logger)

            # Robust Success Popup Handling
            _confirmed = False
            _deadline = time.monotonic() + 5.0  # Try for 5 seconds
            while time.monotonic() < _deadline:
                # 1. Try Keyboard Enter (often works for focused alerts)
                try:
                    page.keyboard.press("Enter")
                except Exception:
                    pass

                # 2. Try finding button by selector OR by simple text "确定"
                for scope_chk in [modal_scope, page]:
                    try:
                        # Combine user selector with generic "确定" button search
                        candidates = scope_chk.locator(cfg.selectors.success_confirm_button).or_(
                            scope_chk.locator('button:visible:has-text("确定"), a:visible:has-text("确定"), span:visible:text-is("确定")')
                        )
                        if candidates.count() > 0 and candidates.first.is_visible():
                            logger.info("Found confirm button, clicking...")
                            _safe_click(candidates.first, logger)
                            _confirmed = True
                            break
                    except Exception:
                        pass
                
                if _confirmed:
                    break
                
                # Check if modal is already gone (maybe Enter key worked)
                if not modal.is_visible():
                    break
                time.sleep(0.5)

            expect(modal).to_be_hidden(timeout=10_000)

            _rand_delay(cfg)
            continue

        # Fallback: detect teacher tabs by text heuristics in the same frame (teacher tab row can be outside .modal).
        teacher_tabs = _collect_teacher_tabs(modal_scope, logger)
        if teacher_tabs:
            if len(teacher_tabs) > 1:
                for name, h in teacher_tabs:
                    logger.info("prefill teacher tab=%s", name)
                    _safe_click_handle(h, logger)
                    _wait_tab_active_handle(h, timeout_s=2.0)
                    page.wait_for_timeout(50)
                    _rand_delay(cfg)
                    _prefill_active_block(modal, cfg, logger)
            else:
                _prefill_active_block(modal, cfg, logger)
        else:
            _prefill_active_block(modal, cfg, logger)

        submit_btn = modal.locator(cfg.selectors.submit_button)
        expect(submit_btn).to_be_visible()
        logger.info("Auto submitting...")
        _safe_click(submit_btn, logger)

        # Robust Success Popup Handling
        _confirmed = False
        _deadline = time.monotonic() + 5.0  # Try for 5 seconds
        while time.monotonic() < _deadline:
            # 1. Try Keyboard Enter (often works for focused alerts)
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass

            # 2. Try finding button by selector OR by simple text "确定"
            for scope_chk in [modal_scope, page]:
                try:
                    # Combine user selector with generic "确定" button search
                    candidates = scope_chk.locator(cfg.selectors.success_confirm_button).or_(
                        scope_chk.locator('button:visible:has-text("确定"), a:visible:has-text("确定"), span:visible:text-is("确定")')
                    )
                    if candidates.count() > 0 and candidates.first.is_visible():
                        logger.info("Found confirm button, clicking...")
                        _safe_click(candidates.first, logger)
                        _confirmed = True
                        break
                except Exception:
                    pass
            
            if _confirmed:
                break
            
            # Check if modal is already gone (maybe Enter key worked)
            if not modal.is_visible():
                break
            time.sleep(0.5)

        expect(modal).to_be_hidden(timeout=10_000)

        _rand_delay(cfg)


def assist_all_pages(page: Page, cfg: AppConfig, logger: logging.Logger) -> None:
    page.goto(cfg.list_url, wait_until="domcontentloaded")

    while True:
        scope = _resolve_scope_fast(page, cfg, logger)
        assist_page(page, cfg, logger)

        next_btn = scope.locator("#kcpjDataTable_next")
        if next_btn.count() == 0:
            next_btn = scope.locator(
                'a:has-text("后一页"), a:has-text("下一页"), button:has-text("后一页"), button:has-text("下一页")'
            )
        if next_btn.count() == 0:
            return

        el = next_btn.first
        classes = (el.get_attribute("class") or "")
        aria_disabled = (el.get_attribute("aria-disabled") or "")
        parent_classes = ""
        try:
            parent_classes = (el.locator("xpath=..").get_attribute("class") or "")
        except Exception:
            parent_classes = ""

        if "disabled" in classes or "disabled" in parent_classes or aria_disabled.lower() == "true":
            return

        el.click()
        page.wait_for_timeout(500)
