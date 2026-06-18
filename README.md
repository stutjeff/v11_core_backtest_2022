# V11-Core 2022 Event Backtest R5-fixed

這是 V11-Core 的 2022 升息殺估值回測版。

R5 = R3 主體 + R4 快速回攻通道，但 R4 通道必須先通過「急殺型危機辨識」。

目的：
- 保留 R3 在 2022 慢熊中的防守能力。
- 避免 R4 把 2022 熊市反彈誤判成 2020 式 V 型反攻。

R5 快速通道只在以下急殺條件成立後才允許：
- 近 45 日 VIX 曾 >= 50；或
- 近 45 日 VIX 曾 >= 40，且總分曾 > 85，且 QQQ 20 日跌幅曾 <= -18%，SOXX 20 日跌幅曾 <= -25%。

執行：

```bash
pip install -r requirements.txt
python v11_core_2022_backtest.py
```

輸出：
- output/v11_core_2022_weekly_modes.csv
- output/v11_core_2022_switch_log.csv
- output/v11_core_2022_summary.md


## R5-fixed 修正

這版修正快速回攻通道：`fast_release_confirm` 與 `fast_r_confirm` 必須同時滿足 `fast_panic_regime == True`，避免 2022 慢熊反彈被誤判成 2020 類型 V 型急殺反彈。
