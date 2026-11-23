"""yfinance で日経平均・TOPIX・個別銘柄などの株価を取得する(非公式データ)。

準備:  pip install yfinance pandas

使い方(従来どおり・1銘柄):
  python yf_prices.py ^N225 2026-10-20 2026-11-20     # 日経平均
  python yf_prices.py 1306.T 2026-10-20 2026-11-20    # TOPIX連動ETF(^TOPXは取得不可のため代替)
  python yf_prices.py 8697.T 2026-10-20 2026-11-20    # 個別銘柄(4桁コード + .T)
  python yf_prices.py ^N225                           # 期間省略: 直近1か月
  python yf_prices.py ^N225 2026-10-20 2026-11-20 out.csv   # CSV保存

複数銘柄・期間指定:
  python yf_prices.py ^N225 ^GSPC USDJPY=X --period 2y --outdir data/
  python yf_prices.py ^N225 ^VIX --start 2025-01-01 --end 2026-11-20 --outdir data/
  python yf_prices.py --preset supply-demand --period 2y --outdir data/   # 需給診断用の一式

  --outdir を指定すると銘柄ごとに <outdir>/<ティッカー>.csv を保存し、画面には直近 --tail 行(既定5)だけ表示する。
  1銘柄で --outdir なしの場合は従来どおり全行を表示する。

Python から使う:
  from yf_prices import fetch, fetch_many, load_csv
  df = fetch("^N225", period="2y")
  data = fetch_many(["^N225", "^GSPC"], period="2y")   # {ticker: DataFrame}

注意: Yahoo!ファイナンスの非公式データ。仕様変更・取得制限・規約上の制約があり得る。
      ^TOPX(TOPIX指数)は現在データが返らないため、TOPIXは 1306.T(TOPIX連動ETF)で代替する。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

COLS = ["Open", "High", "Low", "Close", "Volume"]

# 需給診断(jp-market-supply-demand-analysis)で使う銘柄一式
PRESETS: dict[str, list[str]] = {
    "supply-demand": [
        "^N225", "1306.T", "^GSPC", "^DJI", "^IXIC", "^SOX", "^VIX", "USDJPY=X",
        "^TNX", "TLT", "GC=F", "SI=F", "HG=F", "BTC-USD",
        "000001.SS", "^KS11", "^STOXX50E", "^NSEI", "VNQ", "1570.T", "1343.T",
    ],
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch(ticker: str, start: str | None = None, end: str | None = None,
          period: str | None = None) -> pd.DataFrame:
    """1銘柄の日足を取得する。end は指定日を含む。start も period もなければ直近1か月。"""
    t = yf.Ticker(ticker)
    if start:
        # yfinance の end は含まれないため、指定日を含めるよう1日足す
        end_incl = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if end else None
        df = t.history(start=start, end=end_incl, auto_adjust=False)
    else:
        df = t.history(period=period or "1mo", auto_adjust=False)
    if df.empty:
        return df
    df.index = pd.DatetimeIndex(df.index.tz_localize(None).normalize(), name="Date")
    return df[[c for c in COLS if c in df.columns]]


def fetch_many(tickers: list[str], start: str | None = None, end: str | None = None,
               period: str | None = None) -> dict[str, pd.DataFrame]:
    """複数銘柄を取得する。取得できなかった銘柄は stderr に出して結果から除く。"""
    out: dict[str, pd.DataFrame] = {}
    for tk in tickers:
        try:
            df = fetch(tk, start, end, period)
        except Exception as e:  # ネットワーク・API 側のエラーは銘柄単位でスキップ
            print(f"取得エラー: {tk}: {e}", file=sys.stderr)
            continue
        if df.empty:
            print(f"データが取得できませんでした: {tk}", file=sys.stderr)
            continue
        out[tk] = df
    return out


def safe_name(ticker: str) -> str:
    """ファイル名に使えない/紛らわしい文字を置き換える(^N225 -> _N225, USDJPY=X -> USDJPY_X)。"""
    return re.sub(r"[^\w.\-]", "_", ticker)


def load_csv(path: str | Path) -> pd.DataFrame:
    """save した CSV を DatetimeIndex 付きで読み戻す。"""
    return pd.read_csv(path, index_col="Date", parse_dates=True, encoding="utf-8-sig")


def _for_display(df: pd.DataFrame) -> pd.DataFrame:
    d = df.round(2).copy()
    d.index = d.index.strftime("%Y-%m-%d")
    return d


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="yfinance で株価日足を取得する(非公式データ)",
        epilog="従来形式 'TICKER [START] [END] [OUT.csv]' もそのまま使える。",
    )
    p.add_argument("args", nargs="*", help="ティッカー(複数可)。YYYY-MM-DD は開始/終了日、*.csv は保存先として解釈")
    p.add_argument("--start", help="開始日 YYYY-MM-DD")
    p.add_argument("--end", help="終了日 YYYY-MM-DD(この日を含む)")
    p.add_argument("--period", help="期間(1mo, 6mo, 1y, 2y, 5y, max など)。--start 指定時は無視")
    p.add_argument("--out", help="CSV 保存先(1銘柄のとき)")
    p.add_argument("--outdir", help="銘柄ごとに CSV を保存するディレクトリ")
    p.add_argument("--preset", choices=sorted(PRESETS), help="銘柄一式を追加する")
    p.add_argument("--tail", type=int, default=5, help="--outdir または複数銘柄時に表示する直近行数")
    ns = p.parse_args(argv)

    # 従来の位置引数(日付・CSV)を振り分ける
    tickers, dates = [], []
    for a in ns.args:
        if _DATE_RE.match(a):
            dates.append(a)
        elif a.lower().endswith(".csv"):
            ns.out = ns.out or a
        else:
            tickers.append(a)
    if len(dates) > 2:
        p.error("日付は開始日・終了日の2つまでです")
    if dates:
        ns.start = ns.start or dates[0]
        if len(dates) > 1:
            ns.end = ns.end or dates[1]
    if ns.preset:
        tickers += [t for t in PRESETS[ns.preset] if t not in tickers]
    if not tickers:
        p.error("ティッカーを1つ以上指定してください")
    if ns.end and not ns.start:
        p.error("--end を使うときは開始日も指定してください")
    if ns.out and len(tickers) > 1:
        p.error("複数銘柄の保存には --outdir を使ってください")
    ns.tickers = tickers
    return ns


def main(argv: list[str] | None = None) -> None:
    ns = parse_args(sys.argv[1:] if argv is None else argv)
    data = fetch_many(ns.tickers, ns.start, ns.end, ns.period)
    if not data:
        sys.exit("データが取得できませんでした(ティッカー・期間・ネットワークを確認)")

    pd.set_option("display.width", 200)
    single_full = len(ns.tickers) == 1 and not ns.outdir
    if ns.outdir:
        Path(ns.outdir).mkdir(parents=True, exist_ok=True)

    for tk, df in data.items():
        if single_full:
            print(_for_display(df).to_string())
        else:
            last = df.index[-1].strftime("%Y-%m-%d")
            print(f"== {tk}  {len(df)}行  最終日 {last}  終値 {df['Close'].iloc[-1]:,.2f}")
            print(_for_display(df.tail(ns.tail)).to_string(), end="\n\n")
        if ns.outdir:
            path = Path(ns.outdir) / f"{safe_name(tk)}.csv"
            df.round(4).to_csv(path, encoding="utf-8-sig")
            print(f"保存しました: {path}")
        elif ns.out:
            df.round(2).to_csv(ns.out, encoding="utf-8-sig")
            print(f"\n保存しました: {ns.out}")

    missing = [t for t in ns.tickers if t not in data]
    if missing:
        print(f"\n取得できなかった銘柄: {', '.join(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
