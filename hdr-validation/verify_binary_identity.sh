#!/bin/bash
# Re-encode one CRF point per arm with the CURRENT binary and compare against
# the stored encode. Proves whether the arms of the three-way report are
# reproducible with one binary, rather than relying on "the default path was
# verified bit-identical". whale10 CRF34 is the cheapest point.
#
# 2026-08-08 CORRECTION -- compare DECODED PIXELS, not bitstream bytes.
# The raw-byte comparison this script used to do is misleading: x265 emits the
# version-string SEI once per KEYFRAME, so on a 300-frame clip at keyint 250
# there are two copies, the second one hundreds of kilobytes into the file. The
# old heuristic ("differences confined to the first ~400 bytes are the SEI and
# cosmetic; deeper differences are real") therefore mislabelled the second SEI
# copy as coded data, which is what produced the bogus "11 bytes of coded data
# differ, so the binary must have been built from uncommitted work" conclusion.
# Measured: the archived 4.2+119 pre-rebuild binary, 4.2+128-fb6839767 and
# 4.2+131-96275df9c all decode whale10 prodstack CRF34 to the SAME pixels
# (MD5 66746bc96f163ab24aed7ee14aacd42a); only the two SEI regions differ.
# `ffmpeg -f md5` over the decode is the ground truth -- it ignores metadata
# entirely and answers the only question that matters: is the coded video the
# same? (Bitstream MD5s are still printed, for information.)
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
    local a b da db
    a=$(md5sum "$ref" | cut -d' ' -f1)
    b=$(md5sum "$new" | cut -d' ' -f1)
    # decoded-pixel MD5: ignores the version SEI and every other metadata
    # difference, so it answers "is the coded video identical?" directly
    da=$(ffmpeg -v error -i "$ref" -f md5 - 2>/dev/null)
    db=$(ffmpeg -v error -i "$new" -f md5 - 2>/dev/null)
    if [ "$da" = "$db" ]; then
        echo "SAME VIDEO   $cfg  decoded $da"
        [ "$a" = "$b" ] || echo "             (bitstreams differ in metadata only: stored=$a current=$b)"
    else
        echo "DIFFERS      $cfg  decoded stored=$da current=$db  <-- real coding difference"
    fi
}

echo "=== coding identity vs current binary ($($X265 --version 2>&1 | head -1)) ==="
run anchor    "${ANCHOR[@]}"
run hdr10opt  "${ANCHOR[@]}" --hdr10-opt
run prodstack "${PRODSTACK[@]}"
echo VERIFY_DONE
} > verify_identity.out 2>&1 && touch verify_identity.marker
