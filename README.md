# Know your Customer (KYC) - OCR CI + Factura (Python + OpenCv + Tesseract)

Proiect demo care:

-citeste o poza de carte de Identitate (CI) si o factura PDF,
- face OCR pe CI, extrage campuri din PDF nativ (fara OCR),
- ruleaza validari KYC (CNP, expirare CI, vechime factura, total),
- emite un verdict KYC_VALID/ KYC_INVALID (cu motive),
- scrie un log simplu in logs/kyc_log.jsonl

> In acest MVP, facturile PDF cu text nativ se parseaza direct (fara OCR).Pentru PDF-uri scanate se poate adauga pdfimage + OCR.
 ---

##Structura proiectului 