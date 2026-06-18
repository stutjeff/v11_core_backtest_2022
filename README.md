# V11-Core 2022 Event Backtest

這是「全球市場雷達 V11」的第一段事件型回測：2022 升息殺估值。

目標不是預測第一擊，而是驗證：

1. 第一擊後，資金撤退是否能讓 V11 從 452 切到 514。
2. 危機中，是否能避開主要下跌段。
3. 資金回流後，是否能透過 R 模式從 514 切到 433。

## 模式定義

- `452`：平常作戰 / 中性偏進攻底盤 = 45:25:30
- `514`：危機升溫 / 防守避震 = 50:10:40
- `433`：R 模式確認 / 防守反擊 = 40:30:30

## 使用 proxy

- 00662 proxy：QQQ
- 半導體：SOXX
- 信用利差 proxy：HYG/LQD
- 市場廣度：RSP/SPY、IWM/SPY、QQQ/RSP
- 防禦資產：SHY/SPY
- 波動：^VIX

## 執行方式

```bash
pip install -r requirements.txt
python v11_core_2022_backtest.py
```

自訂期間：

```bash
python v11_core_2022_backtest.py --start 2021-11-01 --end 2023-03-31
```

## 輸出

執行後會產生：

- `output/v11_core_2022_weekly_modes.csv`
- `output/v11_core_2022_switch_log.csv`
- `output/v11_core_2022_summary.md`

## 判斷標準

成功：

- 2022 風險擴散時，能切到 514。
- 主要下跌段大部分時間維持 514。
- 熊市短反彈不會太早切 433。
- 2023 資金回流時，不會永遠卡在 514。

失敗：

- 2022 大跌時長期維持 452。
- 一跌就亂切，模式頻繁跳動。
- 每次短反彈都誤判成 433。
- 2023 回升後仍長期不解除防守。
