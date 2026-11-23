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
  # 要約はクラウドだけが書くので、PC側は毎回 origin に合わせる。
  # 前回 push できずに残ったコミット(未 push の文字起こし)があれば、その上に載せ直す。
  git rebase origin/$Branch 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) {
    git rebase --abort 2>&1 | Out-Host
    Write-Output "エラー: origin/$Branch に合わせられませんでした。手作業で確認してください。"
    exit 1
  }

  # チャンネル一覧は origin/main のものを使う(GitHub でマージすれば PC で pull しなくても反映される)。
  # PowerShell 5.1 の > は UTF-16 で書くので、cmd のリダイレクトでバイトのまま書き出す。
  # 取り出せなければ普段の作業ツリーの channels.json を使う。
  $Channels = Join-Path $env:TEMP 'yt_watch_channels.json'
  cmd /c "git -C `"$Repo`" show origin/main:youtube-to-Transcript/channels.json > `"$Channels`""
  if ($LASTEXITCODE -ne 0 -or (Get-Item $Channels -ErrorAction SilentlyContinue).Length -eq 0) {
    Write-Output '注意: origin/main の channels.json を取り出せないため、作業ツリーのものを使います'
    $Channels = Join-Path $Repo 'youtube-to-Transcript\channels.json'
  }

  # スクリプトは普段の作業ツリーのものを使い、保存先だけ専用ブランチ側にする
  Push-Location (Join-Path $Repo 'youtube-to-Transcript')
  # Python の出力を PowerShell のパイプに通してからログへ書く。
  # 直接コンソールに書かせると Start-Transcript が一部しか拾わず、文字の間に空白が入って文字化けもする。
  # そのため Python は UTF-8 で出力させ、PowerShell 側も UTF-8 で読む。stderr も一緒に記録する。
  $env:PYTHONIOENCODING = 'utf-8'
  $env:PYTHONUNBUFFERED = '1'
  $prevEnc = [Console]::OutputEncoding
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
  uv run watch_channels.py --channels $Channels --out (Join-Path $Wt 'transcripts') 2>&1 |
    ForEach-Object { "$_" } | Out-Host
  [Console]::OutputEncoding = $prevEnc
  Pop-Location

  git add transcripts
  git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) {
    git commit -m "transcripts: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
  } else {
    Write-Output '新着なし'
  }

  # 未 push のコミットがあれば push(失敗したら pull --rebase して1回だけ再試行)
  $ahead = git rev-list --count "origin/$Branch..HEAD"
  if ([int]$ahead -gt 0) {
    git push -u origin $Branch 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
      git pull --rebase origin $Branch 2>&1 | Out-Host
      git push -u origin $Branch 2>&1 | Out-Host
    }
    if ($LASTEXITCODE -ne 0) { Write-Output 'エラー: push に失敗しました(次回の実行で再試行)'; exit 1 }
    Write-Output "push 完了: $ahead コミット"
  }
} finally {
  Stop-Transcript | Out-Null
}
