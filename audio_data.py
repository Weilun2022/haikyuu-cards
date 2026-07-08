"""
audio_data.py - 事件卡動畫語音對照表

card_no 對應音檔路徑，沒有音檔的卡不需要建條目（大多數事件卡目前都還沒有）。
音檔由使用者自行從動畫串流平台側錄後，用 ffmpeg 轉為小體積 .m4a 存放於 audio/。

status: ready（已上線）/ draft（片段還在測試，先不輸出到前端）

若同一張卡片重新剪輯音檔，檔名請加版本尾碼（如 -v2），不要覆蓋原檔名——
Service Worker 對 /audio/ 做 cache-first，覆蓋同檔名可能讓使用者長期吃到瀏覽器裡的舊快取。

card_no 本身已涵蓋同一張卡的所有稀有度印刷版本（如 N/NP 共用同一個 card_no），
不需要額外處理版本對應。若未來真的出現「不同 card_no 但共用同一段語音」的情況，
直接複製一筆條目、src 指向同一個檔案即可，不需要更複雜的結構。
"""

AUDIO_ENTRIES = [
    {
        "card_no": "HV-P02-097",
        "src": "audio/HV-P02-097.m4a",
        "mime": "audio/mp4",
        "status": "ready",
        "note": "使用者側錄串流平台片段，字幕原文即官方繁中翻譯",
    },
]
