from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pj_assistant.assistant import assist_all_pages  # noqa: E402
from pj_assistant.config import load_config  # noqa: E402


def _setup_logger() -> logging.Logger:
    Path("logs").mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path("logs") / f"run_{ts}.log"

    logger = logging.getLogger("pj_assistant")
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    sh = logging.StreamHandler()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.info("log=%s", log_path)
    return logger


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--storage", default="storage_state.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    logger = _setup_logger()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.browser.headless, slow_mo=cfg.browser.slow_mo_ms)
        context = browser.new_context(storage_state=args.storage)
        page = context.new_page()

        try:
            assist_all_pages(page, cfg, logger)
        except Exception:
            Path("logs/screenshots").mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            png = Path("logs/screenshots") / f"error_{ts}.png"
            page.screenshot(path=str(png), full_page=True)
            logger.exception("error; screenshot=%s", png)
            raise
        finally:
            context.close()
            browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
