# 新着動画の文字起こしを取得して yt-transcripts ブランチへ push する(Windows 用)。
# タスクスケジューラから 18:00 / 20:00 に呼ぶ。登録方法は README.md の「7. 新着の自動取得」。
$ErrorActionPreference = 'Continue'  # git の stderr 出力で止まらないように
$Branch = 'yt-transcripts'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$Log = Join-Path $PSScriptRoot 'run_watch.log'
Start-Transcript -Path $Log -Append | Out-Null

try {
  git fetch origin
  # 専用ブランチの作業ツリーを repo 直下の .yt-transcripts に置き、普段の作業ブランチを汚さない
  $Wt = Join-Path $Repo '.yt-transcripts'
  if (-not (Test-Path $Wt)) {
    git ls-remote --exit-code --heads origin $Branch | Out-Null
    if ($LASTEXITCODE -eq 0) { git worktree add $Wt $Branch }
    else { git worktree add -b $Branch $Wt origin/main }
  }
  Set-Location $Wt
  git pull --ff-only origin $Branch 2>$null

  # スクリプトとチャンネル一覧は普段の作業ツリーのものを使い、保存先だけ専用ブランチ側にする
  Push-Location (Join-Path $Repo 'youtube-to-Transcript')
  uv run watch_channels.py --out (Join-Path $Wt 'transcripts')
  Pop-Location

  git add transcripts
  git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) {
    git commit -m "transcripts: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    git push -u origin $Branch
  } else {
    Write-Output '新着なし'
  }
} finally {
  Stop-Transcript | Out-Null
}
