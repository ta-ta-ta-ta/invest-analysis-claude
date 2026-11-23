"""yfinance で日経平均・TOPIX・個別銘柄の株価を取得する(非公式データ)。
需給診断(jp-market-supply-demand-analysis)用の一括取得・テクニカル計算モードもある。

準備:  pip install yfinance pandas

■ 単一銘柄モード(従来どおり)
  python yf_prices.py ^N225 2026-10-20 2026-11-20     # 日経平均
  python yf_prices.py 1306.T 2026-10-20 2026-11-20    # TOPIX(^TOPX は取得不可のため連動ETFで代替)
  python yf_prices.py 8697.T 2026-10-20 2026-11-20    # 個別銘柄(4桁コード + .T)
  python yf_prices.py ^N225                           # 期間省略: 直近1か月
  python yf_prices.py ^N225 2026-10-20 2026-11-20 out.csv   # CSV保存

■ 複数銘柄の終値一覧
  python yf_prices.py multi ^N225 ^GSPC JPY=X [--period 1mo] [--csv out.csv]

■ 需給診断モード(日経平均・TOPIXのテクニカル、NS/NT倍率、ドル建て日経RSI、
  VIXのMACD、クロスマーケット騰落、PER/PBRライン)
  python yf_prices.py diag
  python yf_prices.py diag --per-w 14.46 --per-i 17.43 --bps-w 33922 --bps-i 24289
  python yf_prices.py diag --end 2026-11-20 --md report_tables.md
    --per-w / --per-i : 日経平均プロフィルの予想PER(加重 / 指数ベース)。EPS は終値÷PER で逆算
    --bps-w / --bps-i : BPS(加重 / 指数ベース)。PBR2倍ラインを計算
    --end            : この日までのデータで計算(過去日の再現用。指定日を含む)
    --md             : 結果を Markdown で保存

注意: Yahoo!ファイナンスの非公式データ。仕様変更・取得制限・規約上の制約があり得る。
      閾値(±2σ、PER16倍など)の判定は仮説ベースの目安であり、投資助言ではない。
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
import yfinance as yf

# 需給診断で使うティッカー(表示名: Yahoo!ティッカー)
DIAG_TICKERS = {
    "日経平均": "^N225",
    "TOPIX(1306)": "1306.T",
    "日経レバ(1570)": "1570.T",
    "S&P500": "^GSPC",
    "NASDAQ総合": "^IXIC",
    "NYダウ": "^DJI",
    "SOX": "^SOX",
    "VIX": "^VIX",
    "ドル円": "JPY=X",
    "米10年金利": "^TNX",
    "米長期債(TLT)": "TLT",
    "米REIT(VNQ)": "VNQ",
    "KOSPI": "^KS11",
    "上海総合": "000001.SS",
    "DAX": "^GDAXI",
    "Nifty50": "^NSEI",
    "金": "GC=F",
    "銀": "SI=F",
    "銅": "HG=F",
    "BTC": "BTC-USD",
}


# ---------------------------------------------------------------- 取得
def fetch(ticker: str, start: str | None = None, end: str | None = None,
          period: str | None = None) -> pd.DataFrame:
    """日足 OHLCV を取得。index は tz なしの日付(Timestamp)。取得失敗時は空 DataFrame。"""
    try:
        if start:
            # yfinance の end は含まれないため、指定日を含めるよう1日足す
            end_incl = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if end else None
            df = yf.Ticker(ticker).history(start=start, end=end_incl, auto_adjust=False)
        else:
            df = yf.Ticker(ticker).history(period=period or "1mo", auto_adjust=False)
    except Exception as e:  # ネットワーク・ティッカー不正など
        print(f"[warn] {ticker}: {e}", file=sys.stderr)
        return pd.DataFrame()
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame()
    df.index = df.index.tz_localize(None).normalize()
    df.index.name = "Date"
    return df


def fetch_closes(tickers: dict[str, str], period: str = "2y",
                 end: str | None = None) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """複数銘柄の終値を1つの表に。OHLC も dict で返す。end 指定時はその日までに切る。"""
    closes, ohlc = {}, {}
    for name, t in tickers.items():
        df = fetch(t, period=period)
        if df.empty:
            print(f"[warn] 取得できませんでした: {name} ({t})", file=sys.stderr)
            continue
        if end:
            df = df.loc[: pd.Timestamp(end)]
        closes[name] = df["Close"]
        ohlc[name] = df
    return pd.DataFrame(closes), ohlc


# ---------------------------------------------------------------- 指標
def macd(s: pd.Series, fast=12, slow=26, sig=9) -> tuple[pd.Series, pd.Series]:
    m = s.ewm(span=fast, adjust=False).mean() - s.ewm(span=slow, adjust=False).mean()
    return m, m.ewm(span=sig, adjust=False).mean()


def rsi(s: pd.Series, p: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def parabolic_sar(high: pd.Series, low: pd.Series, af0=0.02, af_max=0.2) -> pd.DataFrame:
    """Wilder のパラボリック SAR。戻り値: SAR 値と上昇トレンドかどうか。"""
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


def technicals(close: pd.Series, ohlc: pd.DataFrame | None = None) -> pd.DataFrame:
    """ボリンジャー(25日±2σ)、移動平均、MACD、RSI、σ位置、パラボリック。"""
    s = close.dropna()
    ma25 = s.rolling(25).mean()
    sd = s.rolling(25).std(ddof=0)
    df = pd.DataFrame({"終値": s, "MA25": ma25, "+2σ": ma25 + 2 * sd, "-2σ": ma25 - 2 * sd})
    for k in (50, 75, 100, 200):
        df[f"MA{k}"] = s.rolling(k).mean()
    df["MACD"], df["シグナル"] = macd(s)
    df["RSI14"] = rsi(s)
    df["σ位置"] = (s - ma25) / sd
    if ohlc is not None and {"High", "Low"} <= set(ohlc.columns):
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


def pct(a: float, b: float) -> float:
    return (a / b - 1) * 100


# ---------------------------------------------------------------- 出力
def fmt_table(df: pd.DataFrame) -> str:
    """簡易 Markdown 表(tabulate 非依存)。"""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        idx_s = idx.strftime("%Y-%m-%d") if isinstance(idx, pd.Timestamp) else str(idx)
        cells = []
        for v in row:
            if isinstance(v, (bool, np.bool_)):
                cells.append("↑" if v else "↓")
            elif isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else f"{v:,.2f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join([idx_s] + cells) + " |")
    return "\n".join(lines)


def diag(args: argparse.Namespace) -> str:
    px, ohlc = fetch_closes(DIAG_TICKERS, period=args.period, end=args.end)
    out: list[str] = []
    p = out.append

    if "日経平均" not in px:
        sys.exit("日経平均が取得できませんでした(ネットワークを確認)")
    n225 = px["日経平均"].dropna()
    base = n225.index[-1]
    p(f"# 需給診断データ(yfinance) 基準日 {base:%Y-%m-%d}\n")

    # --- B. テクニカル
    for name in ("日経平均", "TOPIX(1306)"):
        if name not in px:
            p(f"## {name}: 未取得\n")
            continue
        t = technicals(px[name], ohlc.get(name) if name == "日経平均" else None)
        last = t.iloc[-1]
        s = t["終値"]
        hi_date = s[-250:].idxmax()
        p(f"## B. テクニカル: {name}")
        p(f"- 終値 {last['終値']:,.2f}(前日比 {pct(s.iloc[-1], s.iloc[-2]):+.2f}%)"
          f" / 1年高値 {s[-250:].max():,.2f}({hi_date:%Y-%m-%d})から {pct(s.iloc[-1], s[-250:].max()):+.2f}%")
        p(f"- σ位置 {last['σ位置']:+.2f}σ(-2σ={last['-2σ']:,.2f}、MA25={last['MA25']:,.2f})")
        p(f"- MA200 {last['MA200']:,.2f}(終値は {pct(last['終値'], last['MA200']):+.2f}%)")
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
        p(fmt_table(t[cols].tail(args.rows).round(2)))
        p("")

    # --- A/D. NS倍率・NT倍率・ドル建て日経・VIX
    p("## A/D. 比率・センチメント")
    if "S&P500" in px:
        ns = (px["日経平均"] / px["S&P500"]).dropna()
        p(f"- NS倍率(日経平均÷S&P500) {ns.iloc[-1]:.3f}:"
          f" 20営業日 {pct(ns.iloc[-1], ns.iloc[-21]):+.2f}% / 5営業日 {pct(ns.iloc[-1], ns.iloc[-6]):+.2f}%"
          f" → {'上昇(スイッチON寄り)' if ns.iloc[-1] > ns.iloc[-21] else '低下(スイッチOFF寄り)'}")
    if "TOPIX(1306)" in px:
        nt = (px["日経平均"] / px["TOPIX(1306)"]).dropna()
        p(f"- NT倍率(日経平均÷1306.T、代替) 20営業日 {pct(nt.iloc[-1], nt.iloc[-21]):+.2f}%"
          f" → {'日経平均優位' if nt.iloc[-1] > nt.iloc[-21] else 'TOPIX優位'}")
    if "ドル円" in px:
        fx = px["ドル円"].reindex(n225.index).ffill()
        usd = (n225 / fx).dropna()
        r = rsi(usd)
        p(f"- ドル建て日経平均 {usd.iloc[-1]:,.2f}、RSI14 {r.iloc[-1]:.1f}"
          f"(直近120日の最低 {r[-120:].min():.1f} @ {r[-120:].idxmin():%Y-%m-%d})")
    if "VIX" in px:
        v = px["VIX"].dropna()
        m, sg = macd(v)
        c = last_cross(m, sg)
        p(f"- VIX {v.iloc[-1]:.2f}(前日比 {pct(v.iloc[-1], v.iloc[-2]):+.1f}%)、"
          f"MACD-シグナル {m.iloc[-1] - sg.iloc[-1]:+.2f}"
          + (f"、最終クロス {c[1]} {c[0]:%Y-%m-%d}(GC=株安サイン / DC=株高サイン、仮説)" if c else ""))
    p("")

    # --- E. クロスマーケット
    p("## E. クロスマーケット")
    rows = {}
    for name in px.columns:
        s = px[name].dropna()
        if len(s) < 200:
            continue
        rows[name] = {
            "基準日": s.index[-1].strftime("%Y-%m-%d"),
            "終値": s.iloc[-1],
            "1日%": pct(s.iloc[-1], s.iloc[-2]),
            "5日%": pct(s.iloc[-1], s.iloc[-6]),
            "20日%": pct(s.iloc[-1], s.iloc[-21]),
            "1年高値比%": pct(s.iloc[-1], s[-250:].max()),
            "MA200上": "○" if s.iloc[-1] > s.rolling(200).mean().iloc[-1] else "×",
        }
    cm = pd.DataFrame(rows).T
    cm.index.name = "市場"
    for c in ("終値", "1日%", "5日%", "20日%", "1年高値比%"):
        cm[c] = cm[c].astype(float)
    p(fmt_table(cm))
    p("")

    # --- C. 理論値
    close = n225.iloc[-1]
    if any([args.per_w, args.per_i, args.bps_w, args.bps_i]):
        p(f"## C. 理論値(終値 {close:,.2f} 基準)")
        for label, per in (("加重", args.per_w), ("指数ベース", args.per_i)):
            if not per:
                continue
            eps = close / per
            p(f"- {label}: PER {per:.2f}倍 → EPS {eps:,.1f}円")
            for k in (14, 15, 16, 21):
                v = eps * k
                p(f"  - PER{k}倍: {v:,.0f}円({v - close:+,.0f}円 / {pct(v, close):+.1f}%)")
        for label, bps in (("加重", args.bps_w), ("指数ベース", args.bps_i)):
            if not bps:
                continue
            v = 2 * bps
            p(f"- {label} BPS {bps:,.0f}: 現在PBR {close / bps:.2f}倍、PBR2倍 {v:,.0f}円({pct(v, close):+.1f}%)")
        p("")
    else:
        p("## C. 理論値: --per-w/--per-i/--bps-w/--bps-i 未指定のため省略\n")

    p("※ yfinance(非公式)。TOPIXは1306.Tで代替。閾値判定は仮説ベースの目安で投資助言ではない。")
    return "\n".join(out)


def multi(args: argparse.Namespace) -> None:
    px, _ = fetch_closes({t: t for t in args.tickers}, period=args.period)
    if px.empty:
        sys.exit("データが取得できませんでした")
    px.index = px.index.strftime("%Y-%m-%d")
    pd.set_option("display.width", 200)
    print(px.round(2).to_string())
    if args.csv:
        px.to_csv(args.csv, encoding="utf-8-sig")
        print(f"\n保存しました: {args.csv}")


def single(argv: list[str]) -> None:
    """従来の単一銘柄モード: TICKER [start] [end] [out.csv]"""
    ticker = argv[0]
    start = argv[1] if len(argv) > 1 else None
    end = argv[2] if len(argv) > 2 else None
    out = argv[3] if len(argv) > 3 else None
    df = fetch(ticker, start=start, end=end)
    if df.empty:
        sys.exit(f"データが取得できませんでした: {ticker}(ティッカー・期間・ネットワークを確認)")
    df.index = df.index.strftime("%Y-%m-%d")
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[cols].round(2)
    pd.set_option("display.width", 200)
    print(df.to_string())
    if out:
        df.to_csv(out, encoding="utf-8-sig")
        print(f"\n保存しました: {out}")


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)

    if argv[0] == "diag":
        ap = argparse.ArgumentParser(prog="yf_prices.py diag")
        ap.add_argument("--period", default="2y", help="取得期間(MA200計算に1年以上必要)")
        ap.add_argument("--end", help="この日までで計算(YYYY-MM-DD)")
        ap.add_argument("--rows", type=int, default=15, help="テクニカル表の表示行数")
        ap.add_argument("--per-w", type=float, help="予想PER(加重)")
        ap.add_argument("--per-i", type=float, help="予想PER(指数ベース)")
        ap.add_argument("--bps-w", type=float, help="BPS(加重)")
        ap.add_argument("--bps-i", type=float, help="BPS(指数ベース)")
        ap.add_argument("--md", help="Markdown 保存先")
        args = ap.parse_args(argv[1:])
        text = diag(args)
        print(text)
        if args.md:
            with open(args.md, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"\n保存しました: {args.md}")
    elif argv[0] == "multi":
        ap = argparse.ArgumentParser(prog="yf_prices.py multi")
        ap.add_argument("tickers", nargs="+")
        ap.add_argument("--period", default="1mo")
        ap.add_argument("--csv")
        multi(ap.parse_args(argv[1:]))
    else:
        single(argv)


if __name__ == "__main__":
    main()
