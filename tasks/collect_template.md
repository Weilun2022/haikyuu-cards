# 收尾任務：整合第 [批次號] 批子 Chat 輸出

## 背景
本批次共 N 個子 Chat 已完成開發，輸出存在：
- tasks/output_01.md
- tasks/output_02.md
- tasks/output_NN.md

需整合進 index.html，並回報結果給中樞。

## 目標
所有 output 的程式碼正確插入 index.html 指定位置，無衝突，專案可正常執行。

## 操作範圍
- 讀：tasks/output_01.md ... tasks/output_NN.md
- 改：index.html（唯一可直接修改的檔案）
- 寫：tasks/collect_result.md（整合結果回報）

## 步驟
1. 讀所有 output 檔，確認各插入位置不衝突
2. 如有衝突 → 停止，在 collect_result.md 記錄衝突後等中樞決策，不修改 index.html
3. 無衝突 → 依 output 序號順序插入
4. 完成後寫回報至 tasks/collect_result.md

## 禁止事項
- 不能 git commit / push
- 衝突時不能自行決策，只能回報

## 回報格式（tasks/collect_result.md）

### 【完成項目】
[哪幾個 task 的程式碼已整合，各自插入位置]

### 【結果】
[成功 / 失敗 / 部分完成]

### 【遺留問題】
[衝突、異常、插入失敗的細節，沒有則填「無」]

### 【待中樞決策】
[需要拍板的事項，沒有則填「無」]
