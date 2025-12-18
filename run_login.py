from __future__ import annotations

import argparse
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pj_assistant.config import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--storage", default="storage_state.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    storage_path = Path(args.storage)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.browser.headless, slow_mo=cfg.browser.slow_mo_ms)
        context = browser.new_context()
        page = context.new_page()
        page.goto(cfg.login_url, wait_until="domcontentloaded")
        print("请在打开的页面中手动登录。登录完成后回到这里按回车保存登录态…")
        input()
        context.storage_state(path=str(storage_path))
        print(f"已保存登录态到 {storage_path}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
