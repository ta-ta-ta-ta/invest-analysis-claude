# invest-analysis-claude

## 株価データの取得

株価・指数・為替などの日足は、独自スクリプトを書かずに `get_market_info/yf_prices.py` を使う。

- 需給診断(jp-market-supply-demand-analysis)のテクニカル・比率・クロスマーケット・理論値ライン:
  `python get_market_info/yf_prices.py diag --md <scratchpad>/diag.md`
  日経平均のPER・BPSが分かったら `--per-w/--per-i/--bps-w/--bps-i` を付けて再実行する。過去日の再現は `--end YYYY-MM-DD`。
- 生データ(CSV)が必要なとき:
  `python get_market_info/yf_prices.py --preset supply-demand --period 2y --outdir <scratchpad>/data`
  銘柄ごとに `<outdir>/<ティッカー>.csv` が保存される(`^N225` → `_N225.csv`、`USDJPY=X` → `USDJPY_X.csv`)。
- 指標計算で読み込むとき: `from yf_prices import load_csv, technicals, macd, rsi`(`sys.path` に `get_market_info` を追加)。
- `^TOPX` は yfinance でデータが返らないため、TOPIX は `1306.T` で代替し、レポートにその旨を書く。
- yfinance が入っていなければ `pip install yfinance pandas`。

## 日本株 需給診断

手順は `.claude/skills/jp-market-supply-demand-analysis/SKILL.md`(このリポジトリ版)に従う。アカウント側に同名のスキルがあっても、こちらを優先する。

## レポート

需給診断などのレポートは `reports/YYYY-MM-DD_<名前>.md` に保存する。同じ日のファイルがすでにあれば上書きせず、`_v2` などを付ける。
