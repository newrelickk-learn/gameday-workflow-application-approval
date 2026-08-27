import argparse
import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="出力ファイル名の元になる識別子（例: chapter2_answer, chapter2_options）")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="暗号化する単一のテキスト")
    group.add_argument("--json-file", help="暗号化するJSON配列を含むファイルのパス")

    parser.add_argument(
        "--key",
        help="既存の復号鍵（base64）。指定しない場合は新しい鍵を生成する（鍵のローテーションになる点に注意）",
    )
    args = parser.parse_args()

    if args.key:
        key = base64.b64decode(args.key)
        if len(key) != 32:
            print("エラー: --keyは32バイト（base64で44文字程度）のAES-256鍵である必要があります", file=sys.stderr)
            sys.exit(1)
    else:
        key = AESGCM.generate_key(bit_length=256)

    if args.text is not None:
        plaintext = args.text.encode("utf-8")
    else:
        with open(args.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    out_path = DATA_DIR / f"{args.name}.enc.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "_comment": (
                    "GameDay演習の正解/選択肢データをAES-256-GCMで暗号化したもの。復号鍵は"
                    "GitHub Secret経由でk8s Secretに注入され、コンテナ内にのみ存在する。"
                ),
                "algorithm": "AES-256-GCM",
                "nonce_base64": base64.b64encode(nonce).decode(),
                "ciphertext_base64": base64.b64encode(ciphertext).decode(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")

    print(f"暗号文を書き込みました（コミットしてよい）: {out_path}")
    print()
    print("復号鍵（base64）。コミットしない。GitHub Secretに設定してください:")
    print(base64.b64encode(key).decode())


if __name__ == "__main__":
    main()
