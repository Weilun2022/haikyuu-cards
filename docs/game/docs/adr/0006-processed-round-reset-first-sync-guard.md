---
status: accepted
---

# `_processedRoundReset` 用 `_firstSync` 旗標對齊，不是進場就直接比對

`listenGame()` 內用一個閉包旗標 `_firstSync`（每次進場重建），第一次收到 Firebase 資料時把本機的 `_processedRoundReset` **直接對齊**成當下的 `data.roundReset` 值，之後才開始正常比對「值有沒有變化」來觸發 `handleRoundReset`。

## Considered Options

- **進場直接比對 `_processedRoundReset`（原本的 bug）**：進場路徑（`enterGame`/`create`/`join`/`start`）沒有初始化這個值，預設是 `0`。如果 Firebase 上已經有一個非 0 的舊 `roundReset` 時間戳（例如重新整理頁面重新進場），第一次收到資料就會因為「本機是 0，遠端不是 0」誤判成「發生了新的 round reset」，直接觸發 `handleRoundReset` 把手牌清空——玩家什麼都沒做，一進場手牌就被清掉。
- **`_firstSync` 對齊（現行）**：第一次同步只負責「記住目前值」，不觸發任何清空邏輯，之後才開始比對變化。

## Consequences

任何新增的「進場後第一次收到 Firebase 資料就要做什麼」的邏輯，都要考慮這個 `_firstSync` 模式——不能假設進場當下本機狀態是乾淨的初始值，Firebase 上可能已經有舊資料。這是一個根因修復（R13），如果之後重構 `listenGame()` 拿掉 `_firstSync` 這個閉包旗標，這個「一進場手牌被清空」的 bug 很可能會原封不動地復發。
