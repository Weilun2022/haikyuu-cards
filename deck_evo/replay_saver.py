"""
deck_evo/replay_saver.py — Showcase Replay 管理
每代 evolution 結束後為最佳 genome 儲存精選展示局。
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SHOWCASE_PREFIX = "visual_replay_evo_"


def init_run(replays_dir: Path) -> str:
    """
    產生 run_id（時間戳格式）並確保 replays_dir 存在。

    Args:
        replays_dir: replays 目錄路徑

    Returns:
        run_id 字串（格式：YYYYMMDD_HHMMSS）
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    replays_dir = Path(replays_dir)
    replays_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Initialized run with ID: {run_id}")
    return run_id


def showcase_path(
    replays_dir: Path, run_id: str, generation: int, idx: int = 0
) -> Path:
    """
    計算 showcase replay 檔案路徑。

    Args:
        replays_dir: replays 目錄路徑
        run_id: evolution run ID
        generation: 代數
        idx: 同代內索引（預設 0）

    Returns:
        展示局檔案 Path
    """
    filename = f"{SHOWCASE_PREFIX}{run_id}_gen{generation:04d}_{idx:02d}.html"
    return Path(replays_dir) / filename


def save_showcase(
    html_content: str,
    replays_dir: Path,
    run_id: str,
    generation: int,
    idx: int = 0,
) -> Path:
    """
    原子寫入 showcase replay HTML。
    先寫 .tmp 暫存檔，成功後 rename 成正式檔名。

    Args:
        html_content: 展示局 HTML 內容
        replays_dir: replays 目錄路徑
        run_id: evolution run ID
        generation: 代數
        idx: 同代內索引（預設 0）

    Returns:
        最終存檔 Path
    """
    target_path = showcase_path(replays_dir, run_id, generation, idx)
    tmp_path = Path(str(target_path) + ".tmp")

    # 先寫入暫存檔
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(html_content, encoding="utf-8")

    # 原子 rename 到正式檔名
    tmp_path.replace(target_path)
    logger.info(f"Saved showcase replay: {target_path}")

    return target_path


def cleanup_old_showcases(replays_dir: Path, keep_latest: int = 50):
    """
    自動清理舊的 evo showcase 檔案。
    只掃 visual_replay_evo_*.html 檔案，保留最新 keep_latest 個。

    Args:
        replays_dir: replays 目錄路徑
        keep_latest: 保留最新檔案個數（預設 50）
    """
    replays_dir = Path(replays_dir)
    if not replays_dir.exists():
        logger.debug(f"Replays directory does not exist: {replays_dir}")
        return

    # 找出所有 showcase 檔案
    showcase_files = sorted(replays_dir.glob(f"{SHOWCASE_PREFIX}*.html"))

    if len(showcase_files) <= keep_latest:
        logger.debug(f"Found {len(showcase_files)} showcases, no cleanup needed")
        return

    # 計算要刪除的檔案（舊的在前，新的在後）
    to_delete = showcase_files[: len(showcase_files) - keep_latest]

    for file_path in to_delete:
        try:
            file_path.unlink()
            logger.info(f"Deleted old showcase: {file_path.name}")
        except OSError as e:
            logger.warning(f"Failed to delete {file_path}: {e}")


def latest_showcase_url(replays_dir: Path, run_id: str) -> str | None:
    """
    找該 run_id 最新一個 showcase 檔。

    Args:
        replays_dir: replays 目錄路徑
        run_id: evolution run ID

    Returns:
        相對 URL（replays/visual_replay_evo_...html），找不到回傳 None
    """
    replays_dir = Path(replays_dir)
    if not replays_dir.exists():
        logger.debug(f"Replays directory does not exist: {replays_dir}")
        return None

    # 找該 run_id 的所有 showcase 檔
    pattern = f"{SHOWCASE_PREFIX}{run_id}_gen*.html"
    files = sorted(replays_dir.glob(pattern))

    if not files:
        logger.debug(f"No showcases found for run_id: {run_id}")
        return None

    # 回傳最新檔（排序後最後一個）的相對 URL
    latest_file = files[-1]
    relative_url = f"replays/{latest_file.name}"
    logger.debug(f"Latest showcase URL: {relative_url}")

    return relative_url
