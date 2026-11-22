"""yfinance で日経平均・TOPIX・個別銘柄の株価を取得する(非公式データ)。

準備:  pip install yfinance pandas
使い方:
  python yf_prices.py ^N225 2026-10-20 2026-11-20     # 日経平均
  python yf_prices.py ^TOPX 2026-10-20 2026-11-20     # TOPIX
  python yf_prices.py 8697.T 2026-10-20 2026-11-20    # 個別銘柄(4桁コード + .T)
  python yf_prices.py ^N225                           # 期間省略: 直近1か月
  python yf_prices.py ^N225 2026-10-20 2026-11-20 out.csv   # CSV保存
注意: Yahoo!ファイナンスの非公式データ。仕様変更・取得制限・規約上の制約があり得る。
"""
import sys

import pandas as pd
import yfinance as yf


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ticker = sys.argv[1]
    start = sys.argv[2] if len(sys.argv) > 2 else None
    end = sys.argv[3] if len(sys.argv) > 3 else None
    out = sys.argv[4] if len(sys.argv) > 4 else None

    if start:
        # yfinance の end は含まれないため、指定日を含めるよう1日足す
        end_incl = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if end else None
        df = yf.Ticker(ticker).history(start=start, end=end_incl, auto_adjust=False)
    else:
        df = yf.Ticker(ticker).history(period="1mo", auto_adjust=False)

    if df.empty:
        sys.exit(f"データが取得できませんでした: {ticker}(ティッカー・期間・ネットワークを確認)")

    df.index = df.index.tz_localize(None).strftime("%Y-%m-%d")
    df.index.name = "Date"
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[cols].round(2)
    pd.set_option("display.width", 200)
    print(df.to_string())
    if out:
        df.to_csv(out, encoding="utf-8-sig")
        print(f"\n保存しました: {out}")


if __name__ == "__main__":
    main()
