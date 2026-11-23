# invest-analysis-claude

## 株価データの取得

株価・指数・為替などの日足は、独自スクリプトを書かずに `get_market_info/yf_prices.py` を使う。

- 需給診断(jp-market-supply-demand-analysis)の価格データ一式:
  `python get_market_info/yf_prices.py --preset supply-demand --period 2y --outdir <scratchpad>/data`
  銘柄ごとに `<outdir>/<ティッカー>.csv` が保存される(`^N225` → `_N225.csv`、`USDJPY=X` → `USDJPY_X.csv`)。
- 指標計算で読み込むとき: `from yf_prices import load_csv`(`sys.path` に `get_market_info` を追加)。
- `^TOPX` は yfinance でデータが返らないため、TOPIX は `1306.T` で代替し、レポートにその旨を書く。
- yfinance が入っていなければ `pip install yfinance pandas`。

## レポート

需給診断などのレポートは `reports/YYYY-MM-DD_<名前>.md` に保存する。
