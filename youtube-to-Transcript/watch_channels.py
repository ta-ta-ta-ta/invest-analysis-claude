"""登録チャンネルの新着動画を見つけて、文字起こしを保存する。

使い方:
  python youtube-to-Transcript/watch_channels.py            # 新着を取得
  python youtube-to-Transcript/watch_channels.py --dry-run  # 取得せず対象だけ表示
  python youtube-to-Transcript/watch_channels.py --since-days 7

チャンネルは youtube-to-Transcript/channels.json に書く:
  [{"name": "表示名", "handle": "@xxxx"}]   # channel_id (UC...) でも可
出力: transcripts/<name>/<公開日>_<動画ID>.md
すでにファイルがある動画は取得しない(ファイルの有無が既読管理)。
字幕がまだ無い動画(配信直後・プレミア前)は保存せず、次回の実行で再試行する。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import get_youtube_transcript  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CHANNELS_FILE = HERE / 'channels.json'
OUT_ROOT = REPO / 'transcripts'

_UA = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ja,en;q=0.8'}
_NS = {
    'a': 'http://www.w3.org/2005/Atom',
    'yt': 'http://www.youtube.com/xml/schemas/2015',
}
_CHANNEL_ID_RE = re.compile(r'UC[A-Za-z0-9_-]{22}')


def _get(url: str) -> str:
  req = urllib.request.Request(url, headers=_UA)
  with urllib.request.urlopen(req, timeout=30) as r:
    return r.read().decode('utf-8', errors='replace')


def resolve_channel_id(ch: dict) -> str:
  """channel_id が無ければハンドル(@xxx)のページから UC... を取り出す"""
  if ch.get('channel_id'):
    return ch['channel_id']
  handle = ch['handle'].lstrip('@')
  html = _get(f'https://www.youtube.com/@{urllib.parse.quote(handle)}')
  for pat in (
      r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
      r'"externalId":"(UC[\w-]{22})"',
      r'"channelId":"(UC[\w-]{22})"',
  ):
    m = re.search(pat, html)
    if m:
      return m.group(1)
  raise RuntimeError(f'channel_id を特定できません: @{handle}')


def latest_videos(channel_id: str) -> list[dict]:
  """RSS フィード(最新15本)から動画一覧を返す"""
  xml = _get(f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}')
  root = ET.fromstring(xml)
  videos = []
  for e in root.findall('a:entry', _NS):
    vid = e.findtext('yt:videoId', namespaces=_NS)
    link = e.find('a:link', _NS)
    videos.append({
        'id': vid,
        'title': e.findtext('a:title', namespaces=_NS) or '',
        'published': dt.datetime.fromisoformat(
            e.findtext('a:published', namespaces=_NS)
        ),
        'url': link.get('href') if link is not None else
               f'https://www.youtube.com/watch?v={vid}',
    })
  return videos


def safe_name(s: str) -> str:
  return re.sub(r'[\\/:*?"<>|\s]+', '_', s).strip('_') or 'channel'


def write_markdown(path: Path, ch_name: str, v: dict, items: list) -> None:
  jst = v['published'].astimezone(dt.timezone(dt.timedelta(hours=9)))
  lines = [
      f"# {v['title']}",
      '',
      f'- チャンネル: {ch_name}',
      f"- 公開: {jst:%Y-%m-%d %H:%M} JST",
      f"- URL: {v['url']}",
      '',
      '## 文字起こし',
      '',
  ]
  for it in items:
    start = float(it.get('start', 0.0))
    text = str(it.get('text', '')).replace('\n', ' ').strip()
    lines.append(f'[{int(start // 60):02d}:{int(start % 60):02d}] {text}')
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument('--since-days', type=float, default=3,
                  help='この日数より前に公開された動画は対象外 (既定: 3)')
  ap.add_argument('--dry-run', action='store_true')
  ap.add_argument('--channels', type=Path, default=CHANNELS_FILE)
  args = ap.parse_args()

  channels = json.loads(args.channels.read_text(encoding='utf-8'))
  cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.since_days)
  saved, pending, errors = [], [], []

  for ch in channels:
    name = ch.get('name') or ch.get('handle') or ch.get('channel_id')
    out_dir = OUT_ROOT / safe_name(name)
    try:
      cid = resolve_channel_id(ch)
      videos = latest_videos(cid)
    except Exception as e:  # チャンネル単位で失敗しても他は続ける
      errors.append(f'{name}: {e}')
      continue

    for v in videos:
      if v['published'] < cutoff:
        continue
      if any(out_dir.glob(f"*_{v['id']}.md")):
        continue
      if args.dry_run:
        print(f"[新着] {name} | {v['published']:%Y-%m-%d} | {v['title']} | {v['url']}")
        continue
      items = get_youtube_transcript(v['id'])
      if not items:
        pending.append(f"{name}: {v['title']} ({v['url']})")
        continue
      jst_date = v['published'].astimezone(
          dt.timezone(dt.timedelta(hours=9))).date()
      path = out_dir / f"{jst_date}_{v['id']}.md"
      write_markdown(path, name, v, items)
      saved.append(path)

  print(f'保存: {len(saved)} 件')
  for p in saved:
    print(f'  {p.relative_to(REPO)}')
  if pending:
    print(f'字幕未取得(次回再試行): {len(pending)} 件')
    for s in pending:
      print(f'  {s}')
  if errors:
    print(f'エラー: {len(errors)} 件')
    for s in errors:
      print(f'  {s}')
  return 1 if errors and not saved else 0


if __name__ == '__main__':
  sys.exit(main())
