#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

echo "== MultiNeiroCreator Codex 启动扫描 =="
echo
echo "== CLAUDE.md =="
sed -n '1,120p' CLAUDE.md
echo
echo "== unsolved.md 概览 =="
awk '
  /^## [A-H]\./ { sec=$2; gsub(/\./, "", sec); next }
  sec != "" && /\[[ \-!~]\]/ {
    count[sec]++
    if (!sample[sec]) sample[sec] = $0
  }
  END {
    for (sec in count) {
      printf "%s\t%d\t%s\n", sec, count[sec], sample[sec]
    }
  }
' unsolved.md | sort
echo
echo "== solved.md 最近条目 =="
rg '^### ' solved.md | tail -n 6
echo
echo "== 最近提交 =="
git log --oneline --date=short --pretty="%ad %h %s" -10
