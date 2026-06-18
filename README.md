# V11-Core 2022 Event Backtest R7

測試 R7 在 2022 升息殺估值慢熊環境中，是否會被熊市反彈騙出去。

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

Go to **Actions → Run V11-Core 2022 Backtest R7 → Run workflow**.

Outputs:

- `output/v11_core_2022_weekly_modes.csv`
- `output/v11_core_2022_switch_log.csv`
- `output/v11_core_2022_summary.md`

## R7 logic

R7 = R5-fixed + medium repair lane.

- Slow bear / valuation compression: keep R3-style defensive confirmation.
- True panic: allow R4-style fast release only when fast panic regime is confirmed.
- Medium correction: allow 514 → 452 only after medium repair confirmation, not direct 433.


## R7 update

R7 tightens the medium repair lane. In R6, a 7/9 count could release 514 to 452 even when market momentum was still weak. R7 requires momentum repair, QQQ/SOXX 60D repair, credit 60D repair, VIX cooling, score cooling, and positive QQQ 20D return. The goal is to keep the 2018 repair benefit while blocking 2022-style bear-market rallies.
