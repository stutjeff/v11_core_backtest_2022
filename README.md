# V11-Core 2022 Event Backtest R6

測試 R6 在 2022 升息殺估值慢熊環境中，是否會被熊市反彈騙出去。

## Files

- `v11_core_2022_backtest.py`
- `requirements.txt`
- `.github/workflows/run-v11-core-2022-backtest.yml`

## Run locally

```bash
pip install -r requirements.txt
python v11_core_2022_backtest.py
```

## GitHub Actions

Go to **Actions → Run V11-Core 2022 Backtest R6 → Run workflow**.

Outputs:

- `output/v11_core_2022_weekly_modes.csv`
- `output/v11_core_2022_switch_log.csv`
- `output/v11_core_2022_summary.md`

## R6 logic

R6 = R5-fixed + medium repair lane.

- Slow bear / valuation compression: keep R3-style defensive confirmation.
- True panic: allow R4-style fast release only when fast panic regime is confirmed.
- Medium correction: allow 514 → 452 only after medium repair confirmation, not direct 433.
