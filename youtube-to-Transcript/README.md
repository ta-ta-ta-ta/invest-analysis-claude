# YouTube動画 文字起こし（スクリプト）取得手順書

本手順書では、`uv` を使用してPython環境を構築し、YouTube動画の字幕（タイムスタンプ付きテキスト）を自動取得してテキスト保存するまでの手順を解説します。

---

## 1. プロジェクトの初期化

ターミナル（PowerShell等）を開き、作業用プロジェクトを作成・初期化します。

```powershell
# 作業フォルダを作成して移動
mkdir C:\Users\takahiro2\youtube-to-transcript
cd C:\Users\takahiro2\youtube-to-transcript

# uvプロジェクトの初期化
uv init
```

---

## 2. 必要なライブラリのインストール

YouTubeから字幕データを取得するためのパッケージをインストールします。

```powershell
uv add youtube-transcript-api
```

---

## 3. スクリプトファイルの作成 (`main.py`)

プロジェクトフォルダ内に `main.py` を作成し、以下のコードを記述します。

### PowerShellから自動生成する場合：
以下のコマンドを実行すると、`main.py` が直接作成されます。

```powershell
Set-Content -Path "main.py" -Value 'import sys
from youtube_transcript_api import YouTubeTranscriptApi

def get_youtube_transcript(video_id):
    """指定したYouTube動画の字幕（文字起こし）を取得する"""
    try:
        ytt_api = YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id, languages=["ja", "en"])
        return fetched_transcript.to_raw_data()
    except Exception as e:
        print(f"字幕の取得に失敗しました: {e}")
        return None

def save_transcript_to_file(transcript_items, video_id):
    """取得した文字起こしデータをテキストファイルに保存する"""
    output_filename = f"transcript_{video_id}.txt"
    
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(f"# YouTube 動画文字起こし (ID: {video_id})\n\n")
        
        for item in transcript_items:
            text_val = item.get("text", "") if isinstance(item, dict) else str(item)
            start_val = item.get("start", 0.0) if isinstance(item, dict) else 0.0
            
            # 分:秒 形式に変換
            minutes = int(start_val // 60)
            seconds = int(start_val % 60)
            f.write(f"[{minutes:02d}:{seconds:02d}] {text_val}\n")
            
    print(f"文字起こしファイルを保存しました: {output_filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: uv run main.py <YouTube動画ID>")
        sys.exit(1)
        
    video_id = sys.argv[1]
    print(f"動画ID: {video_id} の字幕を取得中...")
    
    transcript = get_youtube_transcript(video_id)
    if transcript:
        save_transcript_to_file(transcript, video_id)
' -Encoding UTF8
```

---

## 4. スクリプトの実行

YouTube動画のURLから **動画ID（`v=` の後の文字列）** を確認し、引数として渡して実行します。

例: URLが `https://www.youtube.com/watch?v=rxFjizFYh8g` の場合、動画IDは `rxFjizFYh8g` です。

```powershell
# プロジェクトフォルダ内で実行
uv run main.py rxFjizFYh8g
```

動画IDの代わりにURLをそのまま渡すこともできます（`watch?v=`・`youtu.be/`・`shorts/`・`live/`・`embed/` 形式に対応）。

```powershell
uv run main.py "https://www.youtube.com/watch?v=rxFjizFYh8g&t=120s"
uv run main.py "https://youtu.be/rxFjizFYh8g"
```

---

## 5. 出力結果の確認

実行が完了すると、カレントフォルダ内に `transcript_rxFjizFYh8g.txt` が生成されます。

### 出力ファイルの例：
```text
# YouTube 動画文字起こし (ID: rxFjizFYh8g)

[00:00] こんにちは
[00:03] 今回は働きすぎの管理職についてお話しします
[00:08] 忙しいリーダーに必要なのは心がけではありません...
```

---

## 6. トラブルシューティング

| 症状 / エラーメッセージ | 原因 | 解決策 |
| :--- | :--- | :--- |
| `ModuleNotFoundError` | 仮想環境外（グローバルなPython）で実行している | `python main.py` ではなく **`uv run main.py`** で実行してください |
| `type object ... has no attribute 'get_transcript'` | `youtube-transcript-api` v1.0.0以降の仕様変更 | 本手順書の `main.py`（`YouTubeTranscriptApi().fetch()` を使うコード）に更新してください |
| `字幕の取得に失敗しました` | 動画に日本語・英語の字幕が提供されていない | 対象動画の設定（自動生成字幕の有無）を確認してください |
---

## 7. 新着の自動取得(登録チャンネル)

`channels.json` に登録したチャンネルの新着動画を見つけ、文字起こしを `yt-transcripts` ブランチの `transcripts/<チャンネル>/<公開日>_<動画ID>.md` に保存する。

- 字幕の取得は **自分のPCで行う**。クラウド(Claude Code のクラウドセッション等)から字幕を取ろうとすると、YouTube がクラウド事業者のIPを拒否するため失敗する(新着の検知はクラウドでもできる)。
- 要約は、PCで push された後にクラウドの定期タスク(毎日 18:10 / 20:10)が各ファイル冒頭に `## 要約` として追記する。

### 手動で試す

```powershell
cd <リポジトリ>\youtube-to-Transcript
uv run watch_channels.py --dry-run   # 対象の新着を表示するだけ
powershell -ExecutionPolicy Bypass -File .\run_watch.ps1   # 取得して yt-transcripts へ push
```

対象は **チャンネルごとに、公開から24時間以内の最新1本だけ**。同じチャンネルが続けて投稿した場合、古いほうは取得しない。`--since-hours N` で期間を、`--all` で「期間内をすべて取得」に変えられる(`--since-days N` も可)。取得済みかどうかはファイルの有無で判断し、最新の動画に字幕がまだ無い場合(配信直後など)は次回再試行する(古い動画には戻らない)。

### 要約のまとめ

同じルール(チャンネルごとに最新1本・24時間以内)で、各ファイルの `## 要約` を1つの Markdown にまとめる。

```powershell
python youtube-to-Transcript\latest_summaries.py --root .yt-transcripts\transcripts --out latest.md
```

`--since-hours N` で期間を、`--all` で「最新1本に絞らない」に変えられる。要約がまだ無い動画は「(要約なし)」と出る。

### タスクスケジューラに登録(18:00 と 20:00)

```powershell
$ps1 = (Resolve-Path .\run_watch.ps1).Path
schtasks /create /tn "YT Transcripts 1800" /sc daily /st 18:00 /tr "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ps1`""
schtasks /create /tn "YT Transcripts 2000" /sc daily /st 20:00 /tr "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ps1`""
```

PCが起動していて、git が GitHub に push できる状態(ログイン済み)である必要がある。実行ログは `run_watch.log`。

### チャンネルの追加・削除

`channels.json` を編集する。`handle`(@xxxx)か `channel_id`(UC...)のどちらかがあればよい。
