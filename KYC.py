#citeste fisierele, cheama verificarile si scrie logul

#importam modulele noastre
#importuri standard
import os                                   #pentru verificari de fisiere

from verificare_documente import(
        read_image, laplacian_variance, enhance_for_ocr, ocr_text,
        extract_pdf_text, parse_id_text, parse_invoice_text_native,
        validate_kyc
)
from log import write_log                   #functia de log simplu

#Config usor de modificat
CI_PATH = "ci.jpg"                          #cartea de identitate
PDF_PATH = "Factura.pdf"                    #factura
LOG_PATH = os.path.join("logs", "kyc_log.jsonl") #locatia logului simplu

def main():                 #rularea cap coada a fluxului KYC minimal
    #1. Verificare ca fisierele exista
    if not os.path.exists(CI_PATH):          #daca CI LIPSESTE
        print(f"Eroare: nu gasesc {CI_PATH}")#mesaj eroare
        return
    if not os.path.exists(PDF_PATH):         #DACA FACTURA LIPSESTE
        print(f"Eroare: nu gasesc {PDF_PATH}")#eroare
        return
    #2. citeste ci.jpg si calculeaza claritatea
    id_img = read_image(CI_PATH)        #INCARCA IMAGINEA
    if id_img is None:
        print("Eroare: nu pot citi imagineaza CI.")
        return
    lv = laplacian_variance(id_img) #scor claritate
    h, w = id_img.shape[:2]            #inaltime/latime
    print(f"CI: {w}x{h}, var(Laplacian)={lv:.1f}")      #afiseaza info utile

    #3. extrage info din factura
    inv_text = extract_pdf_text(PDF_PATH)           #extrage text (poate fi "")
    inv_fields = parse_invoice_text_native(inv_text) if inv_text.strip() else {} #parseaza campurile
    print("Invoice fields: ", inv_fields)           #afiseaza ce a gasit

    #4. OCR pe CI(chiar daca e putin blur incercam)
    id_gray = enhance_for_ocr(id_img)               #pregateste imaginea
    try:
        id_text = ocr_text(id_gray)                 #ruleaza Tesseract
    except Exception as e:                      #daca Tesseract nu e instalat
        print(f"Eroare OCR: {e}")               #mesaj
        return
    id_fields = parse_id_text(id_text)          #extrage campurile din textul OCR
    print("ID fields: ", id_fields)             #afiseaza ce a gasit

    #5 Valideaza KYC pe baza campurilor extrase
    status, failures = validate_kyc(            #apelam validatorul
        id_fields = id_fields,                  #campuri din CI
        inv_fields = inv_fields,                #campuri din factura
        ci_laplacian_var = lv                   #scor claritate CI
    )
    print("KYC verdict:", status, failures)     #afisam verdictul

    #6 Scrie un log simplu in JSON (FARA PII)
    write_log(                                  #apelam loggerul
        event="KYC_VERDICT",                    #numele evenimentului
        details= {
            "status": status,                   #verdictul
            "failures": failures,               #motive
            "id_fields_present":list(id_fields.keys()), #doar numele campurilor CI extrase
            "invoice_fields_present":list(inv_fields.keys())#Doar numele campurilor facturii
        },
        log_path=LOG_PATH                       #fisierul de log
    )
    print(f"Log scris in: {LOG_PATH}")          #CONFIRMA locul logului
    #ruleaza doar cand fisierul e executat direct (nu importat ca modul)
if __name__== "__main__":                       #entrypoint
    main()                                      #porneste fluxul















