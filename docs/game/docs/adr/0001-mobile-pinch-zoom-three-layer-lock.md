---
status: accepted
---

# 手機 pinch zoom 鎖定用三層防護，缺一不可

`viewport` meta 宣告 + CSS `touch-action: pan-x pan-y`（全站，保留 scroll）+ JS 攔截 iOS Safari 的 `gesturestart`/`gesturechange`（`capture:true, passive:false`），三層同時存在才真正擋住手機雙指縮放。

## Considered Options

- 只用 `viewport` 的 `maximum-scale=1.0`：iOS Safari 可繞過，不夠。
- **`touch-action: manipulation`**：容易被誤以為等同禁止縮放，實際上 `manipulation` = `pan-x + pan-y` **+ 允許 pinch-zoom**（只禁雙擊縮放），是錯的選項，之前有審查員建議過這個做法，已確認是陷阱。
- **現行三層方案**：`gesturestart`/`gesturechange` 是 iOS Safari 雙指縮放的真正入口，`capture:true` 確保不被子元素 `stopPropagation` 繞過；CSS `pan-x pan-y` 對 Android/現代瀏覽器有效。

## Consequences

刻意不加 `user-scalable=no`，保留無障礙性，靠 CSS+JS 防護即可。已知不覆蓋：桌機 Ctrl+滾輪縮放、系統級輔助功能縮放（可接受，非目標場景）。之後如果有人「簡化」把 `touch-action` 改回 `manipulation`，會重新打開 pinch-zoom 這個洞，要特別小心這個字面上看起來更合理但實際錯誤的選項。
