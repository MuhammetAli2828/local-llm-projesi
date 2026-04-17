from __future__ import annotations

import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROCESSED = BASE / "data" / "processed"


def main():
    source = PROCESSED / "train_data.jsonl"
    if not source.exists():
        raise FileNotFoundError(f"Bulunamadı: {source}")

    lines = source.read_text(encoding="utf-8").splitlines()
    random.shuffle(lines)

    split_idx = int(len(lines) * 0.9)

    train_lines = lines[:split_idx]
    val_lines = lines[split_idx:]

    train_out = PROCESSED / "train_data_split.jsonl"
    val_out = PROCESSED / "val_data.jsonl"

    train_out.write_text("\n".join(train_lines), encoding="utf-8")
    val_out.write_text("\n".join(val_lines), encoding="utf-8")

    print("Train örnek:", len(train_lines))
    print("Validation örnek:", len(val_lines))
    print("Yazıldı:", train_out)
    print("Yazıldı:", val_out)


if __name__ == "__main__":
    main()