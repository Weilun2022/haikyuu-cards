# Context Map

## Contexts

- [卡片目錄／牌組管理](./CONTEXT.md) — `index.html` 為主：卡片資料庫瀏覽、牌組構築、雲端同步、AI 牌組照片辨識
- [對戰遊戲引擎](./docs/game/CONTEXT.md) — `game.html`：即時連線對戰的回合制遊戲規則（發球/接球/舉球/攻擊/攔網、GUTS 資源、局數池），用獨立的 Firebase 專案做即時同步
- [卡牌翻譯 Pipeline](./docs/translation/CONTEXT.md) — `build_data.py`：建置期工具，把官方日文卡片資料轉成 `cards_zh.json`／`cards_data.js`，不是使用者互動的網站頁面

## Relationships

- **對戰遊戲引擎 → 卡片目錄**：`game.html` 讀同一份 `cards_data.js` 查卡片基本資料（名稱/數值/圖片），但不共用牌組管理或雲端同步——`game.html` 的即時對戰同步用使用者自貼的 `hv_firebase_config`，跟「卡片目錄／牌組管理」context 的雲端同步是完全獨立的 Firebase 專案。
- **⚠️ 撞名警告**：兩邊 context 都用到英文字 `set`，但語意完全不同——「卡片目錄／牌組管理」的 `COLOR_TAGS` 裡 `set` = 顏色標籤「舉球」；「對戰遊戲引擎」的 `zones.set`／SET tile = 比賽局數/分數（rally 輸贏）追蹤，跟舉球無關。看到 `set` 這個字時，一定要先確認在講哪個 context。
- **卡牌翻譯 Pipeline → 卡片目錄／對戰遊戲引擎**：翻譯 pipeline 的產出（`cards_zh.json`／`cards_data.js`）被另外兩個 context 讀取消費，但翻譯 pipeline 本身的詞彙（`MANUAL_OVERRIDES`／`ANNOTATION_ZH`／規則依序執行）純粹是建置期概念，另外兩個 context 完全不需要知道這些細節。
