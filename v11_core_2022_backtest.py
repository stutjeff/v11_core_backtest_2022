#!/usr/bin/env python3
"""
V11-Core 2022 Event Backtest R4

Goal:
- Test whether V11 can switch from 452 to 514 after capital starts leaving risk assets.
- Test whether V11 can later switch from 514 to 433 when recovery / R-mode conditions are confirmed.

Period default:
- 2021-11-01 to 2023-03-31

Outputs:
- output/v11_core_2022_weekly_modes.csv
- output/v11_core_2022_switch_log.csv
- output/v11_core_2022_summary.md

Run:
    pip install -r requirements.txt
    python v11_core_2022_backtest.py
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf


TICKERS = [
    "QQQ",   # 00662 proxy / Nasdaq 100
    "SOXX",  # semiconductor proxy
    "HYG",   # high yield bond ETF
    "LQD",   # investment grade bond ETF
    "SPY",   # S&P 500
    "RSP",   # equal-weight S&P 500
    "IWM",   # Russell 2000
    "SHY",   # short-term Treasuries / 00865B proxy
    "^VIX",  # VIX index
]

DEFAULT_START = "2021-11-01"
DEFAULT_END = "2023-03-31"


@dataclass(frozen=True)
class ModeConfig:
    """V11 final allocation definitions."""
    mode_452: Tuple[int, int, int] = (45, 25, 30)  # normal operating / neutral-offensive base
    mode_514: Tuple[int, int, int] = (50, 10, 40)  # defensive shock absorber
    mode_433: Tuple[int, int, int] = (40, 30, 30)  # confirmed rebound / counterattack


def safe_pct_change(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods=periods).replace([np.inf, -np.inf], np.nan)


def ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=max(5, window // 4)).mean()


def download_prices(start: str, end: str) -> pd.DataFrame:
    # Add buffer before start so 200D moving averages are usable near the beginning.
    download_start = (pd.Timestamp(start) - pd.Timedelta(days=420)).strftime("%Y-%m-%d")
    raw = yf.download(
        TICKERS,
        start=download_start,
        end=(pd.Timestamp(end) + pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if raw.empty:
        raise RuntimeError("yfinance returned no data. Check internet access or ticker availability.")

    # yfinance may return MultiIndex columns. Prefer adjusted/auto-adjusted Close.
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].copy()
        elif "Adj Close" in raw.columns.get_level_values(0):
            close = raw["Adj Close"].copy()
        else:
            raise RuntimeError(f"Could not find Close columns in yfinance data: {raw.columns}")
    else:
        # Single ticker fallback, unlikely here.
        close = raw[["Close"]].copy()

    close = close.sort_index().ffill().dropna(how="all")
    missing = [t for t in TICKERS if t not in close.columns]
    if missing:
        raise RuntimeError(f"Missing tickers from download: {missing}")
    return close


def score_market_momentum(df: pd.DataFrame) -> pd.Series:
    score = pd.Series(0.0, index=df.index)
    for ticker in ["QQQ", "SOXX"]:
        s = df[ticker]
        score += np.where(s < ma(s, 20), 5, 0)
        score += np.where(s < ma(s, 60), 8, 0)
        score += np.where(s < ma(s, 200), 12, 0)
    return score.clip(upper=25)


def score_credit_proxy(df: pd.DataFrame) -> pd.Series:
    ratio = df["HYG"] / df["LQD"]
    score = pd.Series(0.0, index=df.index)
    score += np.where(ratio < ma(ratio, 20), 5, 0)
    score += np.where(ratio < ma(ratio, 60), 8, 0)
    score += np.where(ratio < ma(ratio, 200), 12, 0)
    score += np.where(safe_pct_change(ratio, 20) < -0.03, 8, 0)
    return pd.Series(score, index=df.index).clip(upper=20)


def score_breadth(df: pd.DataFrame) -> pd.Series:
    rsp_spy = df["RSP"] / df["SPY"]
    iwm_spy = df["IWM"] / df["SPY"]
    qqq_rsp = df["QQQ"] / df["RSP"]

    qqq_rsp_ma20 = ma(qqq_rsp, 20)
    qqq_rsp_ma60 = ma(qqq_rsp, 60)
    qqq_rsp_std60 = qqq_rsp.rolling(60, min_periods=20).std()
    was_overheated = (qqq_rsp > (qqq_rsp_ma60 + 1.5 * qqq_rsp_std60)).rolling(60, min_periods=10).max().fillna(False).astype(bool)
    qqq_rsp_turning_weak = (qqq_rsp < qqq_rsp_ma20) | (safe_pct_change(qqq_rsp, 20) < 0)

    score = pd.Series(0.0, index=df.index)
    score += np.where(rsp_spy < ma(rsp_spy, 60), 6, 0)
    score += np.where(iwm_spy < ma(iwm_spy, 60), 6, 0)
    score += np.where(was_overheated & qqq_rsp_turning_weak, 8, 0)
    return pd.Series(score, index=df.index).clip(upper=20)


def score_vix(df: pd.DataFrame) -> pd.Series:
    v = df["^VIX"]
    score = pd.Series(0.0, index=df.index)
    score = pd.Series(np.select(
        [v > 40, v > 30, v > 25, v > 20],
        [20, 12, 8, 5],
        default=0,
    ), index=df.index).astype(float)
    return score.clip(upper=20)


def score_defensive_strength(df: pd.DataFrame) -> pd.Series:
    ratio = df["SHY"] / df["SPY"]
    score = pd.Series(0.0, index=df.index)
    score += np.where(ratio > ma(ratio, 20), 5, 0)
    score += np.where(ratio > ma(ratio, 60), 8, 0)
    score += np.where(ratio > ma(ratio, 200), 12, 0)
    return pd.Series(score, index=df.index).clip(upper=15)


def compute_r_mode(df: pd.DataFrame, components: pd.DataFrame) -> pd.DataFrame:
    """
    Stricter V11 R-mode rules plus R4 V-shaped rebound fast lane.

    R2 fixed:
    - 433 triggered too early during bear-market rallies.

    R3 adds:
    - 514 -> 452 release also needs confirmation.
    - In a bear market, simply cooling from 60 score to 35 score is not enough.
      QQQ/SOXX/credit must regain trend before leaving 514.

    R4 adds:
    - V-shaped rebound fast lane after a true panic regime.
    - If VIX and total score spiked to panic levels, then VIX cools sharply and QQQ/SOXX/credit regain 20D trends, allow 514 -> 452 earlier.
    """
    qqq = df["QQQ"]
    soxx = df["SOXX"]
    credit = df["HYG"] / df["LQD"]
    vix = df["^VIX"]

    conds = pd.DataFrame(index=df.index)
    conds["r_qqq_above_ma20"] = qqq > ma(qqq, 20)
    conds["r_soxx_above_ma20"] = soxx > ma(soxx, 20)
    conds["r_credit_above_ma20"] = credit > ma(credit, 20)
    conds["r_vix_below_25"] = vix < 25
    conds["r_qqq_20d_return_positive"] = safe_pct_change(qqq, 20) > 0
    conds["r_count"] = conds[[
        "r_qqq_above_ma20",
        "r_soxx_above_ma20",
        "r_credit_above_ma20",
        "r_vix_below_25",
        "r_qqq_20d_return_positive",
    ]].sum(axis=1)

    conds["r_credit_veto"] = components["credit_proxy_score"] >= 12
    conds["r_momentum_veto"] = components["market_momentum_score"] >= 20
    conds["r_score_veto"] = components["total_score"] > 35

    conds["r_watch"] = (conds["r_count"] >= 3) & (~conds["r_credit_veto"])
    conds["r_confirm"] = (
        (conds["r_count"] >= 4)
        & (~conds["r_credit_veto"])
        & (~conds["r_momentum_veto"])
        & (~conds["r_score_veto"])
    )

    # R3: leaving 514 is not the same as launching 433.
    # It still requires capital to show real stabilization, not just a short bounce.
    conds["release_qqq_above_ma60"] = qqq > ma(qqq, 60)
    conds["release_soxx_above_ma60"] = soxx > ma(soxx, 60)
    conds["release_credit_above_ma60"] = credit > ma(credit, 60)
    conds["release_score_ok"] = components["total_score"] <= 35
    conds["release_momentum_ok"] = components["market_momentum_score"] < 20
    conds["release_credit_ok"] = components["credit_proxy_score"] < 12
    conds["release_vix_ok"] = vix < 25
    conds["release_confirm"] = (
        conds["release_score_ok"]
        & conds["release_momentum_ok"]
        & conds["release_credit_ok"]
        & conds["release_vix_ok"]
        & conds["release_qqq_above_ma60"]
        & conds["release_soxx_above_ma60"]
        & conds["release_credit_above_ma60"]
    )

    # R4: V-shaped rebound fast lane.
    # This is only armed after a true panic regime, so ordinary bear-market rallies should not pass it easily.
    recent_vix_peak_90d = vix.rolling(90, min_periods=10).max()
    recent_score_peak_90d = components["total_score"].rolling(90, min_periods=10).max()
    conds["fast_panic_regime"] = (recent_vix_peak_90d > 40) & (recent_score_peak_90d > 85)
    conds["fast_vix_cooldown"] = (vix / recent_vix_peak_90d - 1.0) <= -0.40
    conds["fast_qqq_above_ma20"] = qqq > ma(qqq, 20)
    conds["fast_soxx_above_ma20"] = soxx > ma(soxx, 20)
    conds["fast_credit_above_ma20"] = credit > ma(credit, 20)
    conds["fast_qqq_20d_return_positive"] = safe_pct_change(qqq, 20) > 0
    conds["fast_vix_below_35"] = vix < 35
    conds["fast_count"] = conds[[
        "fast_panic_regime",
        "fast_vix_cooldown",
        "fast_qqq_above_ma20",
        "fast_soxx_above_ma20",
        "fast_credit_above_ma20",
        "fast_qqq_20d_return_positive",
        "fast_vix_below_35",
    ]].sum(axis=1)
    conds["fast_release_confirm"] = conds["fast_count"] >= 5
    conds["fast_r_confirm"] = (conds["fast_count"] >= 6) & (components["credit_proxy_score"] < 12)
    return conds


def raw_mode_from_score(score: float) -> str:
    if score <= 55:
        return "452"
    return "514"


def apply_cooldown(weekly: pd.DataFrame, cooldown_weeks: int = 3) -> pd.DataFrame:
    """
    Stabilize mode changes:
    - Emergency de-risk to 514 if score >= 75: immediate.
    - 452 -> 514 requires repeated risk signal unless emergency.
    - 514 -> 452 requires release_confirm repeated; raw score cooling alone is not enough.
    - 514 -> 433 requires stricter R-confirmation repeated.
    """
    out = weekly.copy()
    final_modes: List[str] = []
    reasons: List[str] = []

    current = "452"
    pending = None
    pending_count = 0
    r_pending_count = 0
    release_pending_count = 0
    fast_release_pending_count = 0
    fast_r_pending_count = 0

    for _, row in out.iterrows():
        raw = row["raw_mode"]
        score = float(row["total_score"])
        r_confirm = bool(row.get("r_confirm", False))
        release_confirm = bool(row.get("release_confirm", False))
        fast_release_confirm = bool(row.get("fast_release_confirm", False))
        fast_r_confirm = bool(row.get("fast_r_confirm", False))

        reason = "維持原模式"

        if score >= 75 and current != "514":
            current = "514"
            pending = None
            pending_count = 0
            r_pending_count = 0
            release_pending_count = 0
            fast_release_pending_count = 0
            fast_r_pending_count = 0
            reason = "風險分數>=75，立即切514防守"

        elif current == "514" and fast_release_confirm:
            # R4 fast lane: after a true panic regime, allow earlier release from 514 to 452.
            pending = None
            pending_count = 0
            r_pending_count = 0
            fast_release_pending_count += 1
            if fast_release_pending_count >= 1:
                current = "452"
                release_pending_count = 0
                reason = "V型急殺後快速回攻通道成立，514→452"
            else:
                reason = f"快速回攻第{fast_release_pending_count}週觀察，暫維持514"

        elif current == "514" and r_confirm:
            release_pending_count = 0
            r_pending_count += 1
            if r_pending_count >= cooldown_weeks:
                current = "433"
                pending = None
                pending_count = 0
                fast_release_pending_count = 0
                fast_r_pending_count = 0
                reason = f"R模式連續{cooldown_weeks}週成立，切433反攻"
            else:
                reason = f"R模式第{r_pending_count}週觀察，暫維持514"

        else:
            r_pending_count = 0
            target = raw

            if current == "452" and fast_r_confirm:
                fast_r_pending_count += 1
                if fast_r_pending_count >= 2:
                    current = "433"
                    pending = None
                    pending_count = 0
                    release_pending_count = 0
                    reason = "V型急殺後反攻確認連續2週成立，452→433"
                else:
                    reason = f"V型反攻第{fast_r_pending_count}週觀察，暫維持452"

            elif current == "514" and target == "452":
                pending = None
                pending_count = 0
                if release_confirm:
                    release_pending_count += 1
                    if release_pending_count >= cooldown_weeks:
                        current = "452"
                        release_pending_count = 0
                        fast_release_pending_count = 0
                        reason = f"解除防守條件連續{cooldown_weeks}週成立，514→452"
                    else:
                        reason = f"解除防守條件第{release_pending_count}週觀察，暫維持514"
                else:
                    release_pending_count = 0
                    reason = "分數降溫但解除防守條件不足，暫維持514"

            # Once in 433, if risk rises again, go back to 514 immediately above 56.
            elif current == "433" and target == "514":
                current = "514"
                pending = None
                pending_count = 0
                release_pending_count = 0
                fast_release_pending_count = 0
                fast_r_pending_count = 0
                reason = "反攻後風險再升，切回514"

            elif target != current:
                release_pending_count = 0
                if pending == target:
                    pending_count += 1
                else:
                    pending = target
                    pending_count = 1

                if pending_count >= cooldown_weeks:
                    current = target
                    reason = f"{target}訊號連續{cooldown_weeks}週成立，正式切換"
                    pending = None
                    pending_count = 0
                else:
                    reason = f"{target}訊號第{pending_count}週觀察，尚未切換"
            else:
                pending = None
                pending_count = 0
                release_pending_count = 0
                reason = "分數與目前模式一致"

        final_modes.append(current)
        reasons.append(reason)

    out["final_mode"] = final_modes
    out["mode_reason"] = reasons
    return out


def build_backtest(start: str, end: str, cooldown_weeks: int) -> pd.DataFrame:
    daily = download_prices(start, end)

    components = pd.DataFrame(index=daily.index)
    components["market_momentum_score"] = score_market_momentum(daily)
    components["credit_proxy_score"] = score_credit_proxy(daily)
    components["breadth_score"] = score_breadth(daily)
    components["vix_score"] = score_vix(daily)
    components["defensive_strength_score"] = score_defensive_strength(daily)
    components["total_score"] = components.sum(axis=1).clip(upper=100)

    r = compute_r_mode(daily, components)
    full = pd.concat([daily, components, r], axis=1)

    # Weekly Friday snapshot. If Friday is holiday, use the last available trading day in that week.
    weekly = full.resample("W-FRI").last()
    weekly = weekly.loc[(weekly.index >= pd.Timestamp(start)) & (weekly.index <= pd.Timestamp(end))].copy()

    weekly["raw_mode"] = weekly["total_score"].apply(raw_mode_from_score)
    weekly["raw_comment"] = np.select(
        [
            weekly["total_score"] <= 30,
            weekly["total_score"].between(31, 55, inclusive="both"),
            weekly["total_score"].between(56, 70, inclusive="both"),
            weekly["total_score"].between(71, 85, inclusive="both"),
            weekly["total_score"] > 85,
        ],
        [
            "正常偏多 → 452",
            "過熱觀察 → 452，但停止追高",
            "危機升溫 → 514",
            "高風險防守 → 514",
            "恐慌/流動性危機 → 514，等待R模式",
        ],
        default="未分類",
    )

    weekly = apply_cooldown(weekly, cooldown_weeks=cooldown_weeks)
    return weekly


def make_switch_log(weekly: pd.DataFrame) -> pd.DataFrame:
    changes = weekly[weekly["final_mode"].ne(weekly["final_mode"].shift(1))].copy()
    cols = [
        "total_score", "final_mode", "raw_mode", "r_count", "r_watch", "r_confirm",
        "r_credit_veto", "r_momentum_veto", "r_score_veto", "release_confirm",
        "fast_count", "fast_release_confirm", "fast_r_confirm",
        "release_qqq_above_ma60", "release_soxx_above_ma60", "release_credit_above_ma60",
        "market_momentum_score", "credit_proxy_score", "breadth_score", "vix_score",
        "defensive_strength_score", "mode_reason",
    ]
    return changes[cols]


def make_summary(weekly: pd.DataFrame, switch_log: pd.DataFrame, start: str, end: str) -> str:
    mode_counts = weekly["final_mode"].value_counts().sort_index()
    first_514 = weekly[weekly["final_mode"] == "514"].index.min()
    first_433 = weekly[weekly["final_mode"] == "433"].index.min()
    max_score_date = weekly["total_score"].idxmax()
    max_score = weekly["total_score"].max()

    def fmt_date(x) -> str:
        if pd.isna(x):
            return "無"
        return pd.Timestamp(x).strftime("%Y-%m-%d")

    lines = []
    lines.append("# V11-Core 2022 Event Backtest R4 Summary")
    lines.append("")
    lines.append(f"Period: {start} to {end}")
    lines.append("")
    lines.append("## Mode Definitions")
    lines.append("- 452 = 平常作戰 / 中性偏進攻底盤 = 45:25:30")
    lines.append("- 514 = 危機升溫 / 防守避震 = 50:10:40")
    lines.append("- 433 = R模式確認 / 防守反擊 = 40:30:30")
    lines.append("")
    lines.append("## Quick Stats")
    for mode in ["452", "514", "433"]:
        lines.append(f"- {mode} weeks: {int(mode_counts.get(mode, 0))}")
    lines.append(f"- First 514 week: {fmt_date(first_514)}")
    lines.append(f"- First 433 week: {fmt_date(first_433)}")
    lines.append(f"- Highest risk score: {max_score:.1f} on {fmt_date(max_score_date)}")
    lines.append(f"- Number of mode switches: {max(0, len(switch_log) - 1)}")
    lines.append("")
    lines.append("## Switch Log")
    if switch_log.empty:
        lines.append("No mode switches detected.")
    else:
        for date, row in switch_log.iterrows():
            lines.append(
                f"- {date.strftime('%Y-%m-%d')}: mode={row['final_mode']}, "
                f"score={row['total_score']:.1f}, R={int(row['r_count'])}/5, reason={row['mode_reason']}"
            )
    lines.append("")
    lines.append("## How to judge this backtest")
    lines.append("- Good: 2022 risk expansion shifts to 514 before or during the main drawdown, not after the entire bear market is over.")
    lines.append("- Good: R/433 does not trigger on every short bear-market bounce.")
    lines.append("- Revised R filter: 433 requires R>=4/5, total_score<=35, credit_proxy_score<12, market_momentum_score<20, and 3 consecutive weekly confirmations by default.")
    lines.append("- R4 fast lane: after a true panic regime, if VIX cools sharply and QQQ/SOXX/credit regain 20D trends, 514 can release to 452 earlier; 433 still needs extra confirmation.")
    lines.append("- Good: Once capital returns, the model can leave 514 instead of staying permanently defensive.")
    lines.append("- Bad: Model stays 452 through the main drawdown.")
    lines.append("- Bad: Model flips between 452/514/433 too often.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run V11-Core 2022 event backtest R4.")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    # Revised after first backtest: 433 should require more confirmation.
    parser.add_argument("--cooldown-weeks", type=int, default=3)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    weekly = build_backtest(args.start, args.end, args.cooldown_weeks)
    switch_log = make_switch_log(weekly)
    summary = make_summary(weekly, switch_log, args.start, args.end)

    weekly_csv = out_dir / "v11_core_2022_weekly_modes.csv"
    switch_csv = out_dir / "v11_core_2022_switch_log.csv"
    summary_md = out_dir / "v11_core_2022_summary.md"

    weekly.to_csv(weekly_csv, encoding="utf-8-sig")
    switch_log.to_csv(switch_csv, encoding="utf-8-sig")
    summary_md.write_text(summary, encoding="utf-8")

    print(summary)
    print("")
    print(f"Saved: {weekly_csv}")
    print(f"Saved: {switch_csv}")
    print(f"Saved: {summary_md}")


if __name__ == "__main__":
    main()
