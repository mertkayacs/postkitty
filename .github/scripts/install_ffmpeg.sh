#!/usr/bin/env bash
# Install ffmpeg and ffprobe on an Ubuntu runner without letting a stalled package mirror stall the job.
# The workflow step runs this file as root. apt goes first, with short network timeouts. When it fails or
# stalls, a static build is fetched from a pinned GitHub release and checked by SHA-256. The tests need ffprobe,
# libx264 with 10-bit output, the ass filter (libass, for captions) and zscale (zimg, for HDR video). Both
# sources have them; the last lines make sure.
set -euo pipefail

# FFmpeg 6.1.3, the release branch Ubuntu 24.04 packages. Monthly builds stay online for two years.
STATIC_URL=https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/autobuild-2025-08-31-13-00/ffmpeg-n6.1.3-linux64-gpl-6.1.tar.xz
STATIC_SHA256=400f9ca9d8ea3f812660cf7a00b9bfed944175cd9d6bd0c9b6257cf99376a75c
APT_NETWORK=(-o Acquire::Retries=3 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20)

apt_install() {
  DEBIAN_FRONTEND=noninteractive timeout --kill-after=10 150 apt-get install -y "${APT_NETWORK[@]}" ffmpeg
}

from_apt() {
  local status=0
  # The runner image ships a package index, so the refresh is only for an index that is missing or out of date.
  if apt-cache show ffmpeg >/dev/null 2>&1; then
    apt_install && return 0 || status=$?
    # 124 and 137 mean the time limit ended it: the mirror is not answering, so do not wait for it again.
    if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
      return 1
    fi
  fi
  timeout --kill-after=10 60 apt-get update "${APT_NETWORK[@]}" && apt_install
}

from_static_build() {
  local dir=${RUNNER_TEMP:-/tmp}/ffmpeg-static
  mkdir -p "$dir"
  curl -fsSL --retry 3 --retry-max-time 240 --connect-timeout 20 --max-time 120 -o "$dir/ffmpeg.tar.xz" "$STATIC_URL"
  echo "$STATIC_SHA256  $dir/ffmpeg.tar.xz" | sha256sum -c -
  tar -xJf "$dir/ffmpeg.tar.xz" -C "$dir" --strip-components=2 --wildcards '*/bin/ffmpeg' '*/bin/ffprobe'
  rm "$dir/ffmpeg.tar.xz"
  echo "$dir" >> "$GITHUB_PATH"
  export PATH="$dir:$PATH"
}

if from_apt; then
  echo "ffmpeg comes from apt"
else
  echo "::warning::apt could not install ffmpeg; using the pinned static build instead"
  from_static_build
fi

# sed reads to the end, so ffmpeg never writes into a closed pipe the way it can with head.
ffmpeg -hide_banner -version | sed -n 1p
ffprobe -hide_banner -version | sed -n 1p
filters=$(ffmpeg -hide_banner -filters)
for filter in ass zscale; do
  if ! grep -qE "^ \S+ +$filter " <<< "$filters"; then
    echo "::error::this ffmpeg build has no $filter filter"
    exit 1
  fi
done
