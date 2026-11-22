from pathlib import Path
import sys
from youtube_transcript_api import YouTubeTranscriptApi


def get_youtube_transcript(video_id: str):
  """指定したYouTube動画の字幕（文字起こし）を取得する"""
  try:
    ytt_api = YouTubeTranscriptApi()
    fetched_transcript = ytt_api.fetch(video_id, languages=['ja', 'en'])
    return fetched_transcript.to_raw_data()
  except Exception as e:
    print(f'字幕の取得に失敗しました: {e}')
    return None


def save_transcript_to_file(
    transcript_items, video_id: str, output_dir: Path
):
  """取得した文字起こしデータをテキストファイルに保存する"""
  output_dir.mkdir(parents=True, exist_ok=True)
  output_path = output_dir / f'transcript_{video_id}.txt'

  with output_path.open('w', encoding='utf-8') as f:
    f.write(f'# YouTube 動画文字起こし (ID: {video_id})\n\n')
    for item in transcript_items:
      text_val = (
          item.get('text', '') if isinstance(item, dict) else str(item)
      ).strip()
      start_val = (
          float(item.get('start', 0.0)) if isinstance(item, dict) else 0.0
      )
      minutes = int(start_val // 60)
      seconds = int(start_val % 60)
      f.write(f'[{minutes:02d}:{seconds:02d}] {text_val}\n')

  print(f'文字起こしファイルを保存しました: {output_path}')


def main():
  if len(sys.argv) < 2:
    print('使い方: uv run main.py <YouTube動画ID>')
    sys.exit(1)

  # '&' 以降やクエリパラメータが混ざった場合に備えて動画ID部分を抽出
  raw_arg = sys.argv[1].strip().strip('"').strip("'")
  video_id = raw_arg.split('&', 1)[0].split('?', 1)[0]

  print(f'動画ID: {video_id} の字幕を取得中...')
  transcript = get_youtube_transcript(video_id)
  if transcript:
    save_transcript_to_file(transcript, video_id, Path.cwd())


if __name__ == '__main__':
  main()