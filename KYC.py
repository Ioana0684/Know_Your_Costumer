"""
KYC demo runner.

Reads an ID image + an invoice PDF, extracts fields, validates basic KYC rules,
and writes a JSONL log entry (without storing PII).
"""

import os
import argparse
from typing import Optional

from verificare_documente import (
    read_image,
    laplacian_variance,
    enhance_for_ocr,
    ocr_text,
    extract_pdf_text,
    parse_id_text,
    parse_invoice_text_native,
    validate_kyc,
)
from log import write_log


DEFAULT_CI_PATH = "ci.jpg"
DEFAULT_PDF_PATH = "Factura.pdf"
DEFAULT_LOG_PATH = os.path.join("logs", "kyc_log.jsonl")


def ensure_parent_dir(path: str) -> None:
    """Create parent folder if it does not exist."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple OCR-based KYC pipeline.")
    parser.add_argument("--id-image", default=DEFAULT_CI_PATH, help="Path to ID image (e.g. ci.jpg)")
    parser.add_argument("--invoice-pdf", default=DEFAULT_PDF_PATH, help="Path to invoice PDF (e.g. Factura.pdf)")
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH, help="Path to output JSONL log file")
    parser.add_argument("--lap-threshold", type=float, default=None, help="Override blur threshold (variance of Laplacian)")
    parser.add_argument("--invoice-max-age-days", type=int, default=None, help="Override max invoice age (days)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    id_path: str = args.id_image
    pdf_path: str = args.invoice_pdf
    log_path: str = args.log_path

    # 1) Check inputs exist
    if not os.path.exists(id_path):
        print(f"[ERROR] ID image not found: {id_path}")
        return 2
    if not os.path.exists(pdf_path):
        print(f"[ERROR] Invoice PDF not found: {pdf_path}")
        return 2

    # 2) Load ID image + compute sharpness
    id_img = read_image(id_path)
    if id_img is None:
        print("[ERROR] Could not read ID image (invalid format or unreadable file).")
        return 3

    lv = laplacian_variance(id_img)
    h, w = id_img.shape[:2]
    print(f"[INFO] ID image: {w}x{h}, Laplacian variance={lv:.1f}")

    # 3) Extract invoice fields from native PDF text
    inv_text = extract_pdf_text(pdf_path)
    inv_fields = parse_invoice_text_native(inv_text) if inv_text.strip() else {}
    print(f"[INFO] Invoice fields extracted: {list(inv_fields.keys())}")

    # 4) OCR on ID image
    id_gray = enhance_for_ocr(id_img)
    try:
        id_text = ocr_text(id_gray)
    except Exception as e:
        print(f"[ERROR] OCR failed: {e}")
        return 4

    id_fields = parse_id_text(id_text)
    print(f"[INFO] ID fields extracted: {list(id_fields.keys())}")

    # 5) Validate KYC rules
    validate_kwargs = {}
    if args.lap_threshold is not None:
        validate_kwargs["lap_threshold"] = args.lap_threshold
    if args.invoice_max_age_days is not None:
        validate_kwargs["invoice_max_age_days"] = args.invoice_max_age_days

    status, failures = validate_kyc(
        id_fields=id_fields,
        inv_fields=inv_fields,
        ci_laplacian_var=lv,
        **validate_kwargs,
    )

    print(f"[RESULT] {status} | failures={failures}")

    # 6) Write JSONL log entry (avoid PII)
    ensure_parent_dir(log_path)
    write_log(
        event="KYC_VERDICT",
        details={
            "status": status,
            "failures": failures,
            "id_fields_present": list(id_fields.keys()),
            "invoice_fields_present": list(inv_fields.keys()),
            "metrics": {"laplacian_variance": lv, "image_width": w, "image_height": h},
        },
        log_path=log_path,
    )
    print(f"[INFO] Log written to: {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())














