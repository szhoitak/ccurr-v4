
# ccurr 全自動加密貨幣量化交易系統 — 最終交付藍圖 v4

> **文件名稱** ：`CCURR_MASTER_BLUEPRINT.md`
> **版本** ：v4.0（最終版）
> **最後更新** ：2026-09-28
> **用途** ：完整的系統設計藍圖，可直接交付本地 AI 生成程式碼
> **狀態** ：所有容器與策略規格已定稿

---

## 交付說明

本文件是整個系統的 **單一真相來源（Single Source of Truth）**。

> **Final contract entrypoint**：完整的 Steps 1–7 整合契約、authority precedence、invariants、acceptance gates 與 release 狀態，以 [BLUEPRINT-MANIFEST.yaml](BLUEPRINT-MANIFEST.yaml) 為機器可讀來源，以 [BLUEPRINT-CONTRACT-INDEX.md](BLUEPRINT-CONTRACT-INDEX.md) 為人類可讀入口。本文件提供系統目錄，不得另行複製或覆寫契約內容。

> 策略引擎的介面契約由 [PART05 Chapter 9](BLUEPRINT-PART05-Chapter09-10-StrategyPluginInterface.md) `Strategy Plugin Contract v1` 唯一規範。Chapter 7 定義策略商業規則，Chapter 8 定義引擎編排，Chapter 10 定義回測實作；這些章節不得以重複摘錄覆寫 Chapter 9。

 **如何使用本文件** ：

| 使用者               | 用途                         |
| -------------------- | ---------------------------- |
| **本地 AI**    | 依章節逐個生成容器程式碼     |
| **多 AI 討論** | 提供完整上下文，討論特定設計 |
| **你自己**     | 查閱設計決策與規格           |
| **未來維護**   | 理解系統全貌，修改時參考     |

 **輸出方式** ：本文件將分多次輸出，每次輸出數個章節，直到完整交付。

---

## 完整目錄

* **第一部：系統總覽**
  * 第 0 章：系統概覽
  * 第 1 章：全域約定
  * 第 2 章：六大通用機制
* **第二部：資料層**
  * 第 3 章：資料庫 Schema
  * 第 4 章：Redis Key 總表
* **第三部：通訊層**
  * 第 5 章：Container 通訊總表
* **第四部：容器藍圖**
  * 第 6 章：各容器藍圖（16 個）
* **第五部：策略引擎**
  * 第 7 章：`ccurr-strategy` Step 1~9
  * 第 8 章：引擎架構
  * 第 9 章：策略插件介面
  * 第 10 章：回測接口
* **第六部：附錄**
  * 第 11 章：AI 生成順序
  * 第 12 章：待辦與開放問題
