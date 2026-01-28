"""
Document verification utilities for a simple KYC pipeline.

- OCR on an identity document image (OpenCV + Tesseract)
- Native PDF text extraction for invoices (pdfminer)
- Field parsing via regex
- Rule-based validation (blur check, CNP checksum, expiry date, invoice age/amount)
"""

import os
import re
from datetime import datetime, timedelta, date
from typing import Dict, Tuple, List, Optional, Any

import cv2
import pytesseract
import dateparser
from pdfminer.high_level import extract_text


# (Windows) Set the path to tesseract.exe if it is not already in PATH
for guess in (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
):
    if os.path.exists(guess):
        pytesseract.pytesseract.tesseract_cmd = guess
        break


# Thresholds (can be overridden from kyc.py if you pass them into validate_kyc)
LAPLACIAN_THRESHOLD = 80.0     # below this, ID image is considered blurry
INVOICE_MAX_AGE_DAYS = 90      # invoices older than this are invalid


# -----------------------------
# Image / OCR / PDF extraction
# -----------------------------
def read_image(path: str):
    """Read an image from disk. Returns a BGR numpy array or None."""
    return cv2.imread(path)


def laplacian_variance(bgr) -> float:
    """
    Returns a simple sharpness metric (variance of Laplacian).
    Lower values usually mean blur.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def enhance_for_ocr(bgr):
    """Improve image for OCR using contrast enhancement and mild sharpening."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    g = clahe.apply(g)
    blur = cv2.GaussianBlur(g, (0, 0), 1.0)
    sharp = cv2.addWeighted(g, 1.0, blur, -0.5, 0)
    return sharp


def ocr_text(img_gray: "cv2.Mat") -> str:
    """Run Tesseract OCR and return extracted text."""
    return pytesseract.image_to_string(
        img_gray,
        lang="ron+eng",
        config="--psm 6",
    )


def extract_pdf_text(pdf_path: str) -> str:
    """Extract native text from a PDF (no OCR). Returns empty string on failure."""
    try:
        return extract_text(pdf_path) or ""
    except Exception:
        return ""


# -----------------------------
# Regex patterns for ID / invoice
# -----------------------------
RE_CNP = re.compile(r"\b(\d{13})\b")
RE_SERIE = re.compile(r"\bSERIA\s*([A-Z]{1,2})\b", re.I)
RE_NUMAR = re.compile(r"\bNR\.?\s*([0-9]{6})\b", re.I)
RE_EXP = re.compile(
    r"(EXPIRĂ|EXPIRARE|VALABIL|VALID UNTIL)[:\s]*([0-3]?\d[-./][0-1]?\d[-./]\d{2,4})",
    re.I,
)


def _parse_date_dmy(s: str) -> Optional[date]:
    """Parse a date string using DMY order. Returns date or None."""
    if not s:
        return None
    d = dateparser.parse(s, settings={"DATE_ORDER": "DMY"})
    return d.date() if d else None


def parse_id_text(text: str) -> Dict[str, Any]:
    """
    Parse fields from OCR text of a Romanian identity card.
    Returns a dict with any fields found.
    """
    out: Dict[str, Any] = {}

    if m := RE_CNP.search(text):
        out["cnp"] = m.group(1)

    if m := RE_SERIE.search(text):
        out["serie"] = m.group(1).upper()

    if m := RE_NUMAR.search(text):
        out["num"] = int(m.group(1))

    if m := RE_EXP.search(text):
        exp = _parse_date_dmy(m.group(2))
        if exp:
            out["expira"] = str(exp)  # YYYY-MM-DD

    # Try to capture labeled lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for i, ln in enumerate(lines):
        if re.search(r"\bNUME\b", ln, re.I):
            out["nume"] = ln.split(":")[-1].strip() if ":" in ln else (
                lines[i + 1].strip() if i + 1 < len(lines) else ""
            )

        if re.search(r"(DOMICILIU|ADRESA|ADDRESS)", ln, re.I):
            if ":" in ln:
                out["domiciliu"] = ln.split(":")[-1].strip()
            else:
                # join next 1-2 lines safely
                nxt = lines[i + 1: i + 3]
                out["domiciliu"] = " ".join([x.strip() for x in nxt]).strip()

    return out


def parse_invoice_text_native(txt: str) -> Dict[str, Any]:
    """
    Extract basic invoice fields from native PDF text.
    (For scanned PDFs, you'd need OCR.)
    """
    out: Dict[str, Any] = {}

    lines = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines() if l.strip()]
    joined = "\n".join(lines)

    # Invoice number
    m = re.search(
        r"(Factura(?:\s+fiscală)?|Invoice)\s*(?:nr\.?|no\.?|#)?\s*[:\-]?\s*([A-Z]{0,4}\s?\d{3,})",
        joined,
        re.I,
    )
    if m:
        out["factura_numar"] = m.group(2).replace(" ", "")

    # Invoice date
    m = re.search(
        r"(Data\s*(?:emiterii|facturii)?|Date)\s*[:\-]?\s*([0-3]?\d[-./][0-1]?\d[-./]\d{2,4})",
        joined,
        re.I,
    )
    if m:
        d = _parse_date_dmy(m.group(2))
        if d:
            out["factura_data"] = str(d)

    # Total amount
    m = re.search(
        r"(Total(?:\s+de\s+plată)?|Amount\s+Due)\s*[:\-]?\s*([0-9]+(?:[.,][0-9]{2})?)",
        joined,
        re.I,
    )
    if m:
        out["total"] = m.group(2).replace(",", ".")

    return out


# -----------------------------
# CNP validation + KYC rules
# -----------------------------
_CNP_CONST = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]


def valid_cnp(cnp: str) -> bool:
    """Validate Romanian CNP checksum (13 digits)."""
    if not cnp or not re.fullmatch(r"\d{13}", cnp):
        return False
    s = sum(int(cnp[i]) * _CNP_CONST[i] for i in range(12)) % 11
    ctrl = 1 if s == 10 else s
    return ctrl == int(cnp[12])


def validate_kyc(
    id_fields: Dict[str, Any],
    inv_fields: Dict[str, Any],
    *,
    ci_laplacian_var: float,
    today: Optional[date] = None,
    lap_threshold: float = LAPLACIAN_THRESHOLD,
    invoice_max_age_days: int = INVOICE_MAX_AGE_DAYS,
) -> Tuple[str, List[str]]:
    """
    Apply minimal KYC validation rules and return (status, failures).
    status is KYC_VALID if no failures, else KYC_INVALID.
    """
    failures: List[str] = []
    today = today or datetime.utcnow().date()

    # 1) ID photo quality
    if ci_laplacian_var < lap_threshold:
        failures.append("image_blurry")

    # 2) CNP validity
    cnp = id_fields.get("cnp")
    if not valid_cnp(str(cnp) if cnp else ""):
        failures.append("invalid_cnp")

    # 3) ID expiry date
    exp_str = id_fields.get("expira")
    exp_date = dateparser.parse(exp_str).date() if exp_str else None
    if (not exp_date) or (exp_date < today):
        failures.append("id_expired")

    # 4) Invoice age
    fdate_str = inv_fields.get("factura_data")
    fdate = dateparser.parse(fdate_str).date() if fdate_str else None
    if (not fdate) or ((today - fdate) > timedelta(days=invoice_max_age_days)):
        failures.append("invoice_too_old")

    # 5) Invoice total
    try:
        total = float(str(inv_fields.get("total", "0")).replace(",", "."))
        if total <= 0:
            failures.append("non_positive_total")
    except Exception:
        failures.append("non_positive_total")

    # 6) Required invoice fields
    for req in ("factura_numar", "factura_data", "total"):
        if req not in inv_fields:
            failures.append("missing_required_fields")
            break

    status = "KYC_INVALID" if failures else "KYC_VALID"
    return status, failures






















