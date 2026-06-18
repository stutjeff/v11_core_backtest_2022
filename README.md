# V11-Core 2022 Event Backtest R4

這是「全球市場雷達 V11」的 2022 升息殺估值事件型回測 R4 版。

R4 目的：把 2020 回測驗證有效的「V 型急殺後快速回攻通道」放回 2022，檢查它會不會在慢熊裡被熊市反彈騙出去。

## 核心邏輯

- 452：平常作戰 / 中性偏進攻底盤
- 514：危機升溫 / 防守避震
- 433：R 模式確認 / 防守反擊

## R4 新增

在 R3 的嚴格防守解除與 R 模式之上，新增快速回攻條件：

- 近 90 日曾 VIX > 40
- 近 90 日總風險分數曾 > 85
- VIX 從高點回落超過 40%
- QQQ 站回 20 日線
- SOXX 站回 20 日線
- HYG/LQD 站回 20 日線
- QQQ 20 日報酬轉正

若快速條件符合 5 項以上，可讓 514 → 452；若後續條件繼續成立，連續 2 週後才允許 452 → 433。

## 執行

```bash
pip install -r requirements.txt
python v11_core_2022_backtest.py
```

## 輸出

- output/v11_core_2022_weekly_modes.csv
- output/v11_core_2022_switch_log.csv
- output/v11_core_2022_summary.md
