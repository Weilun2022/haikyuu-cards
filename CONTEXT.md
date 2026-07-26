# 排球少年!! バボカ!!BREAK 卡牌資料庫

卡片目錄／牌組管理 context（`index.html` 為主）：官方卡牌 TCG「ハイキュー!! バボカ!! BREAK」的卡片資料庫網站，含牌組構築、雲端同步、AI 牌組照片辨識。多 context 結構見根目錄 `CONTEXT-MAP.md`。

## Language

**牌組（Deck）**：
使用者組出來、要拿去比賽或管理庫存用的一副套牌，資料結構是 `{id, name, cards, owned}`。
_Avoid_: 不包含「快速查詢」——那是每個裝置自動建立、名字固定的偽牌組，只是實作上借用同一份資料結構，語意上不算「牌組」。

**持有（Owned）**：
某張卡有沒有補進「這一副牌組」的實體收藏檢查清單，範圍是單一牌組（`deck.owned`），同一張卡在不同牌組裡持有狀態彼此獨立。
_Avoid_: 不要跟「我的最愛」混用——「持有」是牌組範疇內的概念，不是全站盤點。

**我的最愛（Favorites）**：
全站共用、跟牌組系統完全獨立的單卡收藏清單（`window.HVFavorites`），不因你在哪個牌組而不同。
_Avoid_: 不要跟「持有」混用——範圍是 global，不是 deck-scoped。

**快速查詢**：
每個裝置自動建立、固定排在第一位、名字固定的預設牌組（`QUICK_DECK_ID`），供使用者臨時勾選/查詢用，不算「牌組」概念下的正式套牌。歷史上是「我的最愛」功能推出前的舊機制（舊版用星號標記等同於把卡加進這副牌），現在單純當預設空白牌組保留。

**顏色標籤（Color Tags）**：
使用者在「上色」模式手動幫牌組裡的卡片標記的策略分類（自由/接球/舉球/攻擊四色，`COLOR_TAGS`），使用者主動指定、跟卡片本身的稀有度或學校無關。
_Avoid_: 不要單獨用「顏色」兩個字指稱它——容易跟「稀有度色票」「學校色票」搞混。也不要跟已持有狀態色（`--an-owned`，深綠）混淆，兩者刻意選了不同色系。

**卡片版本**：
同一個角色/卡名底下，因插畫、印刷批次或稀有度不同而產生的每一個獨立 `card_no`＋`image_file` 組合，例如及川徹有 10 種卡片版本。
_Avoid_: 不要跟「稀有度」混用——稀有度只是版本底下的一個屬性欄位（`rarity_code`），不是版本本身。

**稀有度色票**：
卡片稀有度對應的裝飾色票（`--r-*`），純視覺呈現，跟稀有度綁定，使用者不能更改。

**學校色票**：
卡片所屬學校對應的識別色票（`--s-*`），跟卡片的 `school`/`school_tags` 綁定，使用者不能更改。

## docs/adr/

- [0001](docs/adr/0001-cloud-sync-last-write-wins.md) — 雲端同步用 last-write-wins，不做欄位級 3-way merge
- [0002](docs/adr/0002-theme-colors-from-live-official-ui.md) — 視覺主題色票讀官方頁面 UI 元件 computed style，不用圖片採樣
- [0003](docs/adr/0003-deck-scan-gemini-key-via-env-not-secret-manager.md) — 牌組照片辨識的 Gemini key 存 `.env`，不用 Secret Manager（避免強制升級 Blaze）
- [0004](docs/adr/0004-node-test-runner-for-functions.md) — `functions/` 的測試框架用 Node 內建 `node:test`，不裝 Jest/Vitest
