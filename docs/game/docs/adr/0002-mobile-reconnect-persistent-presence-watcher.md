---
status: accepted
---

# 手機斷線重連改用持久 presence watcher，不用一次性 visibilitychange

改用 `_startPresenceWatch()`/`_stopPresenceWatch()` 持久監聽 Firebase 的 `.info/connected`，每次重新連線自動重設 `presence/${myRole}` 並重掛 `onDisconnect().remove()`；`visibilitychange` 只保留切到背景時的 `saveSession()`，移除原本所有 presence 重連邏輯。

## Considered Options

- **一次性 `visibilitychange` + 10 秒 listener**（舊版）：只在切回頁面那一刻檢查一次，手機背景很久或網路斷斷續續時容易漏掉重連時機。
- **持久 `.info/connected` watcher**（現行）：不管背景多久、斷線幾次，Firebase 重連當下就自動處理，不依賴使用者切回頁面的時間點。

## Consequences

雙離線判定計時器從 30 秒延長到 60 秒，避免手機正常切背景被誤判離線。`createRoom()` 移除了 `rooms/id` 和 `games/id` 的 `onDisconnect().remove()`，防止房主手機背景時房間被誤刪——這代表房間清除現在完全依賴另外 3 條路徑（主動離開、presence 60 秒計時器、大廳列表掃描、`listenGame` 偵測資料消失），如果之後要改房間生命週期管理，要記得這個 `onDisconnect` 移除是刻意的，不是遺漏。
