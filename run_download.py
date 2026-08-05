"""非互動式執行下載 — 薄 wrapper，呼叫 haikyuu_downloader.main(interactive=False)。"""
import sys
sys.path.insert(0, '.')

from haikyuu_downloader import main

if __name__ == "__main__":
    main(interactive=False)
