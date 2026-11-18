#!/usr/bin/env python3
"""Host-only checks for the public T736 media CMA default.

This test inspects source/config artifacts only. It does not access a board,
build a kernel, or claim that a 512 MiB pool has passed HEVC playback.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "512"


def config_value(path):
    matches = re.findall(r"^CONFIG_CMA_SIZE_MBYTES=(\d+)$", path.read_text(), re.MULTILINE)
    assert matches == [EXPECTED], f"{path}: expected one CMA_SIZE_MBYTES={EXPECTED}, got {matches!r}"


def main():
    config_value(ROOT / "userpatches/linux-t736-mainline-current.config")
    patch_text = (ROOT / "patches/t736-armbian-open-source.patch").read_text()
    assert "+CONFIG_CMA_SIZE_MBYTES=512\n" in patch_text
    assert "+CONFIG_CMA_SIZE_MBYTES=256\n" not in patch_text

    builder = (ROOT / "tools/build_media_v29_candidate.py").read_text()
    assert "'--set-val', 'CMA_SIZE_MBYTES', '512'" in builder
    assert "CONFIG_CMA_SIZE_MBYTES=256" in builder
    assert "CONFIG_CMA_SIZE_MBYTES=512" in builder

    updater = (ROOT / "tools/validation/update_t736_media_v29.py").read_text()
    assert "CONFIG_CMA_SIZE_MBYTES=512" in updater
    assert "CONFIG_CMA_SIZE_MBYTES=256" not in updater
    print("PASS_HOST_ONLY: public patch and media-v29 path require CMA_SIZE_MBYTES=512")


if __name__ == "__main__":
    main()
