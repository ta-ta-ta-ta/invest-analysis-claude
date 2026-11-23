# invest-analysis-claude

## 日本株 需給診断(jp-market-supply-demand-analysis スキル)の実行ルール

価格とテクニカルは、スキルの「データ収集」表にある yfinance の個別取得の代わりに、必ずこのリポジトリのスクリプトで取得する。

```bash
pip install -q yfinance pandas
python get_market_info/yf_prices.py diag --md <スクラッチパッド>/diag.md
# 日経平均のPER・BPSが手に入ったら、引数で渡して理論値ラインも計算する
python get_market_info/yf_prices.py diag --per-w <加重PER> --per-i <指数PER> --bps-w <加重BPS> --bps-i <指数BPS> --md <スクラッチパッド>/diag.md
# 過去日を再現するとき
python get_market_info/yf_prices.py diag --end YYYY-MM-DD
```

- `diag` が出すもの: 日経平均・TOPIX(1306.Tで代替)の±2σ・移動平均クロス・MACD・RSI・パラボリック、NS/NT倍率、ドル建て日経RSI、VIXのMACD、20市場の騰落、PER14/15/16/21倍・PBR2倍ライン。
- `diag` で取れないもの(信用残、1570信用倍率、投資主体別売買、空売り比率、騰落レシオ、日経平均のPER・BPS)は、これまでどおり WebSearch で集める。取れなければ「未取得」と書く。
- `^TOPX` は yfinance で取れないため、TOPIXは常に 1306.T で代替し、レポートにその旨を書く。
- レポートは `reports/YYYY-MM-DD_jp-supply-demand.md` に保存する。
