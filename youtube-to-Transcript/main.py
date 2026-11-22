from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse
from youtube_transcript_api import YouTubeTranscriptApi

_VIDEO_ID_RE = re.compile(r'[A-Za-z0-9_-]{11}')


def extract_video_id(arg: str) -> str | None:
  """動画ID・URL（watch / youtu.be / shorts / live / embed）から動画IDを取り出す"""
  raw = arg.strip().strip('"').strip("'")
  if _VIDEO_ID_RE.fullmatch(raw):
    return raw

  url = urlparse(raw if '://' in raw else f'https://{raw}')
  host = (url.hostname or '').removeprefix('www.').removeprefix('m.')
  parts = [p for p in url.path.split('/') if p]

  candidate = None
  if host == 'youtu.be' and parts:
    candidate = parts[0]
  elif host == 'youtube.com' or host.endswith('.youtube.com'):
    if url.path == '/watch':
      candidate = parse_qs(url.query).get('v', [None])[0]
    elif len(parts) >= 2 and parts[0] in ('shorts', 'live', 'embed'):
      candidate = parts[1]

  if candidate and _VIDEO_ID_RE.fullmatch(candidate):
    return candidate
  return None


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

  video_id = extract_video_id(sys.argv[1])
  if not video_id:
    print(f'動画IDを取り出せませんでした: {sys.argv[1]}')
    sys.exit(1)

  print(f'動画ID: {video_id} の字幕を取得中...')
  transcript = get_youtube_transcript(video_id)
  if transcript:
    save_transcript_to_file(transcript, video_id, Path.cwd())


if __name__ == '__main__':
  main()