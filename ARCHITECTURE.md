# 排球少年!! バボカ!! BREAK — 架構手冊

> 用途：與 Claude 討論修改時，直接引用區塊代號（如「改 DB-3 的篩選器」）

---

## 概覽：三大系統

```
[DATA]  卡牌資料系統   →  cards_zh.json（主資料）
[WEB]   網頁前端       →  index.html（卡牌庫）、game.html（對戰模擬）
[OPT]   牌組優化器     →  deck_optimizer/（Python CLI）
```

---

## DB — 卡牌資料庫前端（index.html）

| 代號 | 名稱 | 描述 |
|------|------|------|
| **DB-1** | 頂部導覽列 | 黏頂 header，含搜尋欄、卡片計數顯示 |
| **DB-2** | 篩選面板 | 系列 / 學校 / 類型 / 位置 / 稀有度 六維篩選；桌機展開、手機可收合 |
| **DB-3** | 卡片網格 | 主要卡片列表，3 欄式排列；卡片縮圖、名稱、稀有度、數值顯示 |
| **DB-4** | 卡片詳情 Modal | 點卡片彈出：大圖、完整數值、技能文字、Q&A |
| **DB-5** | 牌組托盤 | 右下角黏底浮動按鈕，顯示目前牌組數量，點擊展開牌組面板 |
| **DB-6** | 牌組面板 | 右側滑入式 Overlay：選擇牌組、卡片清單 +/−、統計（張數/事件/學校比例）、匯出匯入、QR 碼產生 |
| **DB-7** | 庫存分析 Overlay | 統計持有/缺少的卡片數量，依學校分布 |
| **DB-8** | 資料載入層 | fetch `cards_zh.json` → 解析 → 渲染 DB-3；無伺服器端，純前端 |

---

## GM — 對戰模擬器（game.html）

| 代號 | 名稱 | 描述 |
|------|------|------|
| **GM-1** | 設定畫面 | Firebase 連線設定輸入 |
| **GM-2** | 大廳畫面 | 建立/加入房間、QR 碼邀請 |
| **GM-3** | 對戰場地 | 主遊戲介面（見下方 GM-3 子區塊） |
| **GM-3A** | 對手區域 | 上半場：對手 6 個功能格（srv/blk/rcv/tos/atk/evt） |
| **GM-3B** | 中線 / NET | 場地分隔線，顯示回合資訊 |
| **GM-3C** | 我方區域 | 下半場：己方 6 個功能格 + 手牌列 |
| **GM-4** | 技能解決 Modal | 技能啟動流程彈窗（選擇目標、計算 OP/DP） |
| **GM-5** | Guts 管理 | 資源（ガッツ）追蹤、消耗與補充 |
| **GM-6** | 回合流程控制 | 摸牌 → 出牌 → OP/DP → 結束 四階段按鈕 |
| **GM-7** | 聊天側欄 | Firebase 同步的即時文字聊天 |
| **GM-8** | Firebase 同步層 | Realtime Database 雙向同步，所有遊戲狀態存在 Firebase |

---

## DP — 牌組優化器（deck_optimizer/）

| 代號 | 名稱 | 檔案 | 描述 |
|------|------|------|------|
| **DP-1** | 進入點 CLI | `analyze.py` | `py analyze.py --school 稲荷崎 --avg-dp 7.0` |
| **DP-2** | 卡片評分引擎 | `scorer.py` | 4 維度評分：A（攻擊）/ D（防守）/ R（資源）/ S（協同） |
| **DP-3** | 牌組建構器 | `builder.py` | 從評分結果選出最優 40 張（含 8 事件上限） |
| **DP-4** | 報告產生器 | `report.py` | 輸出 Markdown 牌組清單 + 分析說明 |
| **DP-5** | 技能解析器 | `skill_parser.py` | 從技能文字萃取 OP/DP 數值、抽牌數、連鎖條件 |
| **DP-6** | 評分參數設定 | `config.py` | 權重調整：`DIM_WEIGHTS {A:0.33, D:0.28, R:0.14, S:0.25}` |
| **DP-7** | 輸出報告目錄 | `output/` | 儲存 `學校_YYYYMMDD.md` 結果檔 |

---

## DAT — 資料系統

| 代號 | 名稱 | 檔案 | 描述 |
|------|------|------|------|
| **DAT-1** | 主資料檔 | `cards_zh.json` | 最終主資料，1000+ 張卡，含中文技能文字 |
| **DAT-2** | 原始資料 | `all_cards.json` | 從官方 API 爬下的原始日文資料 |
| **DAT-3** | 翻譯引擎 | `build_data.py` | 日→繁中翻譯管道；140+ 規則，7 大問題類型文件化 |
| **DAT-4** | Q&A 翻譯器 | `translate_qa.py` | 官方 Q&A 文件翻譯 |
| **DAT-5** | 批次翻譯器 | `translate_outputjson.py` | JSON 批次翻譯處理器 |
| **DAT-6** | 翻譯 QA 工具 | `check_translations.js` | 驗證翻譯一致性 |
| **DAT-7** | 圖片資源 | `images/` | 1000+ 張 WebP 卡圖；命名規則：`HV-P01-001-H.webp` |
| **DAT-8** | 爬蟲 | `haikyuu_downloader.py` | 從 Takara Tomy API 抓資料 + 下載圖片 |

---

## WF — 任務工作流程（tasks/）

| 代號 | 名稱 | 描述 |
|------|------|------|
| **WF-1** | 任務發包檔 | `task_01~09.md`：中樞 Chat 派發給子 Chat 的工作規格 |
| **WF-2** | 子 Chat 輸出 | `output_01~09.md`：子 Chat 回傳的程式碼（不直接改主檔） |
| **WF-3** | 整合任務 | `collect_01.md`：整合 Chat 把 output 合併進 index.html / game.html |
| **WF-4** | 整合結果 | `collect_result.md`：整合報告 |

---

## 資料流向圖

```
Takara Tomy API
    ↓ DAT-8（爬蟲）
DAT-2（all_cards.json）
    ↓ DAT-3（翻譯引擎）
DAT-1（cards_zh.json）← 所有系統的單一資料來源
    ├─→ DB-8（前端載入）→ DB-3（卡片網格）
    ├─→ GM-8（Firebase 同步）→ GM-3（對戰場地）
    └─→ DP-1（CLI）→ DP-2 → DP-3 → DP-4 → DP-7（報告）
```

---

## 技術棧快查

| 層級 | 技術 |
|------|------|
| 前端 | HTML5 + CSS3（Custom Properties）+ Vanilla JS |
| 同步 | Firebase Realtime Database |
| 分析 | Python 3.8+（本機執行） |
| 資料格式 | JSON（cards_zh.json ~672 KB） |
| 外部套件 | Firebase SDK、QRCode.js、LZ-String（URL 壓縮） |
| 圖片 | WebP（~400+ 張） |

---

## 常用討論句型

- 「改 **DB-3** 的卡片顯示格式」
- 「**DB-6** 牌組面板要加新功能」
- 「**GM-3C** 我方區域的 UI 調整」
- 「**DP-2** 評分權重修改」
- 「**DAT-3** 翻譯規則新增」
- 「**WF-1** 發新任務給子 Chat」
