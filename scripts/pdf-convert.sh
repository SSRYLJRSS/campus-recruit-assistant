#!/usr/bin/env bash
# MD → PDF（跨平台：Windows(MSYS/Cygwin) / macOS / Linux）
# 用法: pdf-convert.sh <input.md> [output.pdf]
# 依赖: pandoc + 一个 Chromium 内核浏览器（Edge/Chrome/Chromium；可用 EDGE_BIN 指定）
# 输出: PDF + 验证（<100KB 判为错误页并报警）
set -euo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

MD="${1:?用法: pdf-convert.sh <input.md> [output.pdf]}"
[ -f "$MD" ] || { echo "输入不存在: $MD" >&2; exit 1; }

# 取“真实”绝对路径：MSYS/Cygwin 下 pwd -W 给 Windows 路径；其他系统退回 pwd。
winpath() {
  # $1 = 目录
  ( cd "$1" && { pwd -W 2>/dev/null || pwd; } )
}
WORKDIR="$(winpath "$(dirname "$MD")")"
BASE="$(basename "$MD" .md)"

case "${2:-}" in
  "") OUT="$WORKDIR/$BASE.pdf" ;;
  /*|[A-Za-z]:/*) OUT="${2}" ;;
  *) OUT="$(winpath "$(pwd)")/${2}" ;;
esac
HTML="$WORKDIR/$BASE.html"

pandoc "$MD" -s -o "$HTML"

# ---- 自动探测 Chromium 内核浏览器（Edge 优先）；EDGE_BIN 优先 ----
find_browser() {
  if [ -n "${EDGE_BIN:-}" ] && [ -x "${EDGE_BIN}" ]; then echo "$EDGE_BIN"; return 0; fi
  for c in msedge msedge.exe google-chrome google-chrome-stable chrome chromium chromium-browser; do
    p="$(command -v "$c" 2>/dev/null || true)"
    [ -n "$p" ] && { echo "$p"; return 0; }
  done
  # Windows 常见安装目录（从环境拼接，不写死盘符/用户名）
  for root in "${ProgramFiles:-}" "$(printenv 'ProgramFiles(x86)' 2>/dev/null || true)" "${LOCALAPPDATA:-}"; do
    [ -n "$root" ] || continue
    for rel in "Microsoft/Edge/Application/msedge.exe" "Google/Chrome/Application/chrome.exe"; do
      f="$root/$rel"
      [ -x "$f" ] && { echo "$f"; return 0; }
    done
  done
  # macOS
  for app in \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    [ -x "$app" ] && { echo "$app"; return 0; }
  done
  return 1
}
BROWSER="$(find_browser || true)"
[ -n "$BROWSER" ] || { echo "未找到 Chromium 内核浏览器(Edge/Chrome)；可设 EDGE_BIN 指定路径" >&2; exit 1; }

# file:// URL：Windows 盘符路径用 file:///C:/...，unix 绝对路径用 file:///home/...
case "$HTML" in
  [A-Za-z]:/*) URL="file:///$HTML" ;;
  *) URL="file://$HTML" ;;
esac

# --user-data-dir 用独立临时目录，避免与已开实例冲突导致 headless 被忽略
rm -rf "$WORKDIR/.edgetmp"
"$BROWSER" --headless=new --disable-gpu --no-sandbox \
  --user-data-dir="$WORKDIR/.edgetmp" \
  --print-to-pdf="$OUT" --no-pdf-header-footer \
  "$URL" 2>/dev/null || true
sleep 4
rm -rf "$WORKDIR/.edgetmp" "$HTML"

# ---- 跨平台取文件大小（GNU / BSD-macOS / wc 兜底）----
filesize() {
  stat -c%s "$1" 2>/dev/null \
    || stat -f%z "$1" 2>/dev/null \
    || wc -c < "$1" 2>/dev/null \
    || echo 0
}
SIZE="$(filesize "$OUT")"
SIZE="${SIZE//[!0-9]/}"   # 只保留数字
[ -n "$SIZE" ] || SIZE=0
if [ "$SIZE" -lt 100000 ]; then
  echo "警告: PDF 仅 ${SIZE}B，疑似渲染了错误页 — 检查 file:// URL 是否为真实绝对路径、浏览器是否可用" >&2
  exit 1
fi
echo "OK: $OUT (${SIZE}B)"
