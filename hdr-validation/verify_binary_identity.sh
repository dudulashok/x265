#!/bin/bash
# Re-encode one CRF point per arm with the CURRENT binary and compare the
# bitstream MD5 against the stored encode. Proves whether the three arms of the
# three-way report are all reproducible with one post-rebase binary, rather
# than relying on "the default path was verified bit-identical".
# whale10 CRF34 is the cheapest point (300 frames, smallest output).
cd "$(dirname "$0")"
rm -f verify_identity.marker
{
X265=/c/x265_github/x265/build/vc17-x86_64/Release/x265.exe
ANCHOR=(--colorprim bt2020 --transfer smpte2084 --colormatrix bt2020nc --range limited)
PRODSTACK=(--hdr-pq --hdr-chroma-adapt 1.0 --hdr-luma-qp 0.5 --hdr-scene-qp 1.0)

run() { # $1 cfg-name; rest: args
    local cfg=$1; shift
    local ref="whale10_${cfg}_crf34.hevc" new="verify_${cfg}.hevc"
    "$X265" --input whale10.yuv --input-res 3840x2160 --fps 60 --input-depth 10 \
        --preset medium --crf 34 "$@" -o "$new" 2>"verify_${cfg}.enclog"
    local a b
    a=$(md5sum "$ref" | cut -d' ' -f1)
    b=$(md5sum "$new" | cut -d' ' -f1)
    if [ "$a" = "$b" ]; then echo "IDENTICAL  $cfg  $a"
    else echo "DIFFERS    $cfg  stored=$a current=$b  (sizes: $(stat -c%s "$ref") vs $(stat -c%s "$new"))"; fi
}

echo "=== bit-identity vs current binary ($($X265 --version 2>&1 | head -1)) ==="
run anchor    "${ANCHOR[@]}"
run hdr10opt  "${ANCHOR[@]}" --hdr10-opt
run prodstack "${PRODSTACK[@]}"
echo VERIFY_DONE
} > verify_identity.out 2>&1 && touch verify_identity.marker
