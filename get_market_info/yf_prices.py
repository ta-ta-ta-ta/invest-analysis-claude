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

需給診断(テクニカル・比率・クロスマーケット・理論値ラインを計算して表示):
  python yf_prices.py diag
  python yf_prices.py diag --per-w 14.46 --per-i 17.43 --bps-w 33922 --bps-i 24289 --md out.md
  python yf_prices.py diag --end 2026-11-20          # 過去日の再現(指定日を含む)
    --per-w / --per-i : 日経平均プロフィルの予想PER(加重 / 指数ベース)。EPS は終値÷PER で逆算
    --bps-w / --bps-i : BPS(加重 / 指数ベース)。PBR2倍ラインを計算
    --md              : 結果を Markdown で保存

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

import numpy as np
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



# ---------------------------------------------------------------- 需給診断(diag)
# 表示名: ティッカー。PRESETS["supply-demand"] と同じ銘柄
DIAG_NAMES: dict[str, str] = {
    "日経平均": "^N225", "TOPIX(1306)": "1306.T", "日経レバ(1570)": "1570.T",
    "S&P500": "^GSPC", "NASDAQ総合": "^IXIC", "NYダウ": "^DJI", "SOX": "^SOX", "VIX": "^VIX",
    "ドル円": "USDJPY=X", "米10年金利": "^TNX", "米長期債(TLT)": "TLT", "米REIT(VNQ)": "VNQ",
    "東証REIT(1343)": "1343.T", "KOSPI": "^KS11", "上海総合": "000001.SS",
    "ユーロストックス50": "^STOXX50E", "Nifty50": "^NSEI",
    "金": "GC=F", "銀": "SI=F", "銅": "HG=F", "BTC": "BTC-USD",
}


def macd(s: pd.Series, fast=12, slow=26, sig=9) -> tuple[pd.Series, pd.Series]:
    m = s.ewm(span=fast, adjust=False).mean() - s.ewm(span=slow, adjust=False).mean()
    return m, m.ewm(span=sig, adjust=False).mean()


def rsi(s: pd.Series, p: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def parabolic_sar(high: pd.Series, low: pd.Series, af0=0.02, af_max=0.2) -> pd.DataFrame:
    """Wilder のパラボリック SAR。SAR 値と上昇トレンドかどうかを返す。"""
    h, lo = high.values, low.values
    n = len(h)
    sar, up_arr = np.zeros(n), np.ones(n, dtype=bool)
    up, af, ep = True, af0, h[0]
    sar[0] = lo[0]
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if up:
            sar[i] = min(sar[i], lo[i - 1], lo[i - 2] if i > 1 else lo[i - 1])
            if lo[i] < sar[i]:
                up, sar[i], ep, af = False, ep, lo[i], af0
            elif h[i] > ep:
                ep, af = h[i], min(af + af0, af_max)
        else:
            sar[i] = max(sar[i], h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > sar[i]:
                up, sar[i], ep, af = True, ep, h[i], af0
            elif lo[i] < ep:
                ep, af = lo[i], min(af + af0, af_max)
        up_arr[i] = up
    return pd.DataFrame({"SAR": sar, "SAR上昇": up_arr}, index=high.index)


def technicals(ohlc: pd.DataFrame, with_sar: bool = False) -> pd.DataFrame:
    """ボリンジャー(25日±2σ)、移動平均、MACD、RSI、σ位置、(任意で)パラボリック。"""
    s = ohlc["Close"].dropna()
    ma25 = s.rolling(25).mean()
    sd = s.rolling(25).std(ddof=0)
    df = pd.DataFrame({"終値": s, "MA25": ma25, "+2σ": ma25 + 2 * sd, "-2σ": ma25 - 2 * sd})
    for k in (50, 75, 100, 200):
        df[f"MA{k}"] = s.rolling(k).mean()
    df["MACD"], df["シグナル"] = macd(s)
    df["RSI14"] = rsi(s)
    df["σ位置"] = (s - ma25) / sd
    if with_sar:
        hl = ohlc.loc[s.index]
        df = df.join(parabolic_sar(hl["High"], hl["Low"]))
    return df


def last_cross(a: pd.Series, b: pd.Series) -> tuple[pd.Timestamp, str] | None:
    """a が b を最後にクロスした日と種類(GC/DC)。"""
    above = (a > b)[a.notna() & b.notna()].astype(int)
    d = above.diff()
    d = d[d != 0].dropna()
    if d.empty:
        return None
    return d.index[-1], ("GC" if d.iloc[-1] > 0 else "DC")


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100


def _md_table(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        cells = [idx.strftime("%Y-%m-%d") if isinstance(idx, pd.Timestamp) else str(idx)]
        for v in row:
            if isinstance(v, (bool, np.bool_)):
                cells.append("↑" if v else "↓")
            elif isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else f"{v:,.2f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def diag(ns: argparse.Namespace) -> str:
    raw = fetch_many(list(DIAG_NAMES.values()), period=ns.period)
    data = {name: raw[t] for name, t in DIAG_NAMES.items() if t in raw}
    if ns.end:
        data = {k: v.loc[: pd.Timestamp(ns.end)] for k, v in data.items()}
    if "日経平均" not in data:
        sys.exit("日経平均が取得できませんでした(ネットワークを確認)")
    px = pd.DataFrame({k: v["Close"] for k, v in data.items()})
    n225 = px["日経平均"].dropna()
    out: list[str] = []
    p = out.append
    p(f"# 需給診断データ(yfinance) 基準日 {n225.index[-1]:%Y-%m-%d}\n")
    missing = [f"{k}({t})" for k, t in DIAG_NAMES.items() if k not in data]
    if missing:
        p(f"未取得: {', '.join(missing)}\n")

    # B. テクニカル
    for name in ("日経平均", "TOPIX(1306)"):
        if name not in data:
            p(f"## B. テクニカル: {name}: 未取得\n")
            continue
        t = technicals(data[name], with_sar=(name == "日経平均"))
        last, s = t.iloc[-1], t["終値"]
        hi = s[-250:]
        p(f"## B. テクニカル: {name}")
        p(f"- 終値 {last['終値']:,.2f}(前日比 {_pct(s.iloc[-1], s.iloc[-2]):+.2f}%)"
          f" / 1年高値 {hi.max():,.2f}({hi.idxmax():%Y-%m-%d})から {_pct(s.iloc[-1], hi.max()):+.2f}%")
        p(f"- σ位置 {last['σ位置']:+.2f}σ(-2σ={last['-2σ']:,.2f}、MA25={last['MA25']:,.2f})")
        p(f"- MA200 {last['MA200']:,.2f}(終値は {_pct(last['終値'], last['MA200']):+.2f}%)")
        for k in (25, 50, 75, 100):
            c = last_cross(t[f"MA{k}"], t["MA200"])
            if c:
                p(f"- MA{k} × MA200: 最終クロス {c[1]} {c[0]:%Y-%m-%d}(現在 MA{k}={last[f'MA{k}']:,.2f})")
        c = last_cross(t["MACD"], t["シグナル"])
        if c:
            p(f"- MACD {last['MACD']:,.2f} / シグナル {last['シグナル']:,.2f}: 最終クロス {c[1]} {c[0]:%Y-%m-%d}")
        p(f"- RSI14 {last['RSI14']:.1f}")
        if "SAR上昇" in t:
            flips = t["SAR上昇"].astype(int).diff()
            flips = flips[flips != 0].dropna()
            if not flips.empty:
                p(f"- パラボリック: {'上昇' if last['SAR上昇'] else '下降'}トレンド"
                  f"(最終転換 {flips.index[-1]:%Y-%m-%d}、SAR={last['SAR']:,.2f})")
        p("")
        cols = ["終値", "MA25", "-2σ", "σ位置", "MA200", "MACD", "シグナル", "RSI14"]
        if "SAR上昇" in t:
            cols.append("SAR上昇")
        p(_md_table(t[cols].tail(ns.rows).round(2)))
        p("")

    # A/D. 比率・センチメント
    p("## A/D. 比率・センチメント")
    if "S&P500" in px:
        r = (px["日経平均"] / px["S&P500"]).dropna()
        p(f"- NS倍率(日経平均÷S&P500) {r.iloc[-1]:.3f}: 20営業日 {_pct(r.iloc[-1], r.iloc[-21]):+.2f}%"
          f" / 5営業日 {_pct(r.iloc[-1], r.iloc[-6]):+.2f}%"
          f" → {'上昇(スイッチON寄り)' if r.iloc[-1] > r.iloc[-21] else '低下(スイッチOFF寄り)'}")
    if "TOPIX(1306)" in px:
        r = (px["日経平均"] / px["TOPIX(1306)"]).dropna()
        p(f"- NT倍率(日経平均÷1306.T、代替) 20営業日 {_pct(r.iloc[-1], r.iloc[-21]):+.2f}%"
          f" → {'日経平均優位' if r.iloc[-1] > r.iloc[-21] else 'TOPIX優位'}")
    if "ドル円" in px:
        usd = (n225 / px["ドル円"].reindex(n225.index).ffill()).dropna()
        r = rsi(usd)
        p(f"- ドル建て日経平均 {usd.iloc[-1]:,.2f}、RSI14 {r.iloc[-1]:.1f}"
          f"(直近120日の最低 {r[-120:].min():.1f} @ {r[-120:].idxmin():%Y-%m-%d})")
    if "VIX" in px:
        v = px["VIX"].dropna()
        m, sg = macd(v)
        c = last_cross(m, sg)
        p(f"- VIX {v.iloc[-1]:.2f}(前日比 {_pct(v.iloc[-1], v.iloc[-2]):+.1f}%)、MACD-シグナル {m.iloc[-1] - sg.iloc[-1]:+.2f}"
          + (f"、最終クロス {c[1]} {c[0]:%Y-%m-%d}(GC=株安サイン / DC=株高サイン、仮説)" if c else ""))
    p("")

    # E. クロスマーケット
    p("## E. クロスマーケット")
    rows = {}
    for name in px.columns:
        s = px[name].dropna()
        if len(s) < 200:
            continue
        rows[name] = {
            "基準日": s.index[-1].strftime("%Y-%m-%d"), "終値": s.iloc[-1],
            "1日%": _pct(s.iloc[-1], s.iloc[-2]), "5日%": _pct(s.iloc[-1], s.iloc[-6]),
            "20日%": _pct(s.iloc[-1], s.iloc[-21]), "1年高値比%": _pct(s.iloc[-1], s[-250:].max()),
            "MA200上": "○" if s.iloc[-1] > s.rolling(200).mean().iloc[-1] else "×",
        }
    cm = pd.DataFrame(rows).T
    cm.index.name = "市場"
    for c in ("終値", "1日%", "5日%", "20日%", "1年高値比%"):
        cm[c] = cm[c].astype(float)
    p(_md_table(cm))
    p("")

    # C. 理論値
    close = n225.iloc[-1]
    if any([ns.per_w, ns.per_i, ns.bps_w, ns.bps_i]):
        p(f"## C. 理論値(終値 {close:,.2f} 基準)")
        for label, per in (("加重", ns.per_w), ("指数ベース", ns.per_i)):
            if per:
                eps = close / per
                p(f"- {label}: PER {per:.2f}倍 → EPS {eps:,.1f}円")
                for k in (14, 15, 16, 21):
                    v = eps * k
                    p(f"  - PER{k}倍: {v:,.0f}円({v - close:+,.0f}円 / {_pct(v, close):+.1f}%)")
        for label, bps in (("加重", ns.bps_w), ("指数ベース", ns.bps_i)):
            if bps:
                p(f"- {label} BPS {bps:,.0f}: 現在PBR {close / bps:.2f}倍、"
                  f"PBR2倍 {2 * bps:,.0f}円({_pct(2 * bps, close):+.1f}%)")
        p("")
    else:
        p("## C. 理論値: --per-w/--per-i/--bps-w/--bps-i 未指定のため省略\n")

    p("※ yfinance(非公式)。TOPIXは1306.Tで代替。閾値判定は仮説ベースの目安で投資助言ではない。")
    return "\n".join(out)


def diag_main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(prog="yf_prices.py diag", description="需給診断用のテクニカル・比率・理論値を計算する")
    ap.add_argument("--period", default="2y", help="取得期間(MA200 の計算に1年以上必要)")
    ap.add_argument("--end", help="この日までで計算(YYYY-MM-DD、指定日を含む)")
    ap.add_argument("--rows", type=int, default=15, help="テクニカル表の表示行数")
    ap.add_argument("--per-w", type=float, help="予想PER(加重)")
    ap.add_argument("--per-i", type=float, help="予想PER(指数ベース)")
    ap.add_argument("--bps-w", type=float, help="BPS(加重)")
    ap.add_argument("--bps-i", type=float, help="BPS(指数ベース)")
    ap.add_argument("--md", help="Markdown 保存先")
    ns = ap.parse_args(argv)
    text = diag(ns)
    print(text)
    if ns.md:
        Path(ns.md).write_text(text + "\n", encoding="utf-8")
        print(f"\n保存しました: {ns.md}")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "diag":
        diag_main(argv[1:])
        return
    ns = parse_args(argv)
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
