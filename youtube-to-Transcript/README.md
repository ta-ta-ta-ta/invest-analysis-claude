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