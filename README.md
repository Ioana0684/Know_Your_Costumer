# Know Your Customer (KYC) – OCR-based Document Verification

This project is a simple KYC (Know Your Customer) pipeline that extracts and validates information from identity documents and invoices using OCR and rule-based checks.

## 🔍 What the project does
- Reads an image of an identity card and a PDF invoice
- Uses OCR (Tesseract + OpenCV) to extract text from ID documents
- Extracts structured fields from native PDF invoices (without OCR)
- Performs KYC validation checks:
  - Personal identification number (CNP)
  - ID expiration date
  - Invoice age and total amount
- Outputs a final decision: `KYC_VALID` or `KYC_INVALID`, with reasons
- Writes a simple JSON log of each verification

## 🧠 Why this matters
Automated KYC pipelines are widely used in fintech and compliance systems to reduce manual verification effort and detect invalid or expired documents early in the process.

This project focuses on the **document processing and validation logic**, rather than deep learning models.

## 🛠️ Technologies used
- Python
- OpenCV
- Tesseract OCR
- PDF text parsing
- Basic image preprocessing
- Rule-based validation logic

## 📂 Project structure
