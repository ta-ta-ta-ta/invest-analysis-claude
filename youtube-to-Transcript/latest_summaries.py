"""文字起こしファイルの「## 要約」を、チャンネルごとの最新1本・公開から24時間以内に絞って1つの Markdown にまとめる。

使い方:
  python youtube-to-Transcript/latest_summaries.py --root .yt-transcripts/transcripts
  python youtube-to-Transcript/latest_summaries.py --root <...> --since-hours 48 --out digest.md
  python youtube-to-Transcript/latest_summaries.py --root <...> --all   # 最新1本に絞らない

要約がまだ無いファイルは「(要約なし)」と表示する。--out を省くと標準出力へ書く。
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import re
import sys
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))


def parse(path: Path) -> dict | None:
  t = path.read_text(encoding='utf-8')
  pub = re.search(r'^- 公開: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})', t, re.M)
  if not pub:
    return None
  ch = re.search(r'^- チャンネル: (.*)$', t, re.M)
  url = re.search(r'^- URL: (.*)$', t, re.M)
  summary = ''
  if '## 要約' in t:
    summary = t.split('## 要約', 1)[1].split('## 文字起こし', 1)[0].strip()
  return {
      'path': path,
      'title': t.splitlines()[0].lstrip('# ').strip(),
      'channel': ch.group(1).strip() if ch else path.parent.name,
      'published': dt.datetime.strptime(pub.group(1), '%Y-%m-%d %H:%M').replace(tzinfo=JST),
      'url': url.group(1).strip() if url else '',
      'summary': summary,
  }


def select(items: list[dict], since_hours: float, latest_only: bool, now: dt.datetime) -> list[dict]:
  cutoff = now - dt.timedelta(hours=since_hours)
  items = [x for x in items if x['published'] >= cutoff]
  if latest_only:
    best: dict[str, dict] = {}
    for x in items:
      if x['channel'] not in best or x['published'] > best[x['channel']]['published']:
        best[x['channel']] = x
    items = list(best.values())
  return sorted(items, key=lambda x: x['published'], reverse=True)


def render(items: list[dict], since_hours: float, latest_only: bool, now: dt.datetime) -> str:
  rule = 'チャンネルごとに最新1本' if latest_only else '全動画'
  out = [f'# YouTube 要約({rule}・{since_hours:g}時間以内)\n',
         f'\n基準時刻: {now:%Y-%m-%d %H:%M} JST ・ {len(items)} 本\n']
  for x in items:
    out.append(f"\n---\n\n## {x['title']}\n\n"
               f"{x['channel']} ・ {x['published']:%Y-%m-%d %H:%M} ・ [動画]({x['url']})\n\n"
               f"{x['summary'] or '(要約なし)'}\n")
  return ''.join(out)


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument('--root', type=Path, required=True, help='transcripts フォルダ')
  ap.add_argument('--since-hours', type=float, default=24)
  ap.add_argument('--all', action='store_true', help='最新1本に絞らない')
  ap.add_argument('--out', type=Path, help='出力先 .md (省略時は標準出力)')
  args = ap.parse_args()

  now = dt.datetime.now(JST)
  items = [x for p in sorted(args.root.glob('*/*.md')) if (x := parse(p))]
  text = render(select(items, args.since_hours, not args.all, now),
                args.since_hours, not args.all, now)
  if args.out:
    args.out.write_text(text, encoding='utf-8')
    print(f'保存: {args.out}')
  else:
    io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8').write(text)
  return 0


if __name__ == '__main__':
  sys.exit(main())
