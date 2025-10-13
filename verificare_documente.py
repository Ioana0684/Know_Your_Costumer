#verificare documente

import os, re           #lucram cu fisiere           #regex
from datetime import datetime, timedelta #comparatii de date

#Biblioteci externe
import cv2          #OpenCv pentru procesare imagini
import pytesseract  #OCR
import dateparser   #parseaza stringuri de tip data
from dateparser_data.settings import settings
from pdfminer.high_level import extract_text #extrage text din PDF nativ fara OCR


# (Windows) setează calea către tesseract.exe dacă nu e în PATH
for guess in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
    if os.path.exists(guess):
        pytesseract.pytesseract.tesseract_cmd = guess
        break


#praguri ce pot fi schimbate din kyc.py, optional
LAPLACIAN_THRESHOLD = 80.0          #sub 80 poza CI BLURATA
INVOICE_MAX_AGE_DAYS = 90           #FACTURA MAI VECHE DE 90 DE ZILE => INVALID

#FUNCTII IMAGINE/OCR/PARSARE
def read_image(path: str): #citeste imagine de la path si intoarce obiectul OpenCv sau none
    return cv2.imread(path)#intoarce numpy array (BGR) sau None

def laplacian_variance(bgr) -> float:  #alculeaza varianta laplacianului(masura simpla de claritate)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)  # conversie la gri
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())  #varianta gradient -> claritate

def enhance_for_ocr(bgr):  #imbunatateste imaginea pentru OCR: contrast + local
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)   #gri
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) #contrast
    g = clahe.apply(g)
    blur = cv2.GaussianBlur(g, (0, 0), 1.0)     #netezire usoara
    sharp = cv2.addWeighted(g, 1.0, blur, -0.5, 0) #unsharp mask
    return sharp                                                #imaginea pregatita

def ocr_text(img_gray: 'cv2.Mat') -> str: #Ruleaza OCR cu Tesseract pe imaginea gri si intoarce textul
    return pytesseract.image_to_string(         #apeleaza motorul OCR(OPTICAL CHARACTER RECOGNITION)
        img_gray,                               #imaginea de intrare
        lang = "ron+eng",                       #ro + en
        config="--psm 6",                       #impartire paragrafe simple
    )

def extract_pdf_text(pdf_path: str) -> str: #extragem textul din PDF
    try:
        return extract_text(pdf_path) or "" #incearca sa extraga text
    except Exception:
        return ""                           #eroare se intoarce gol

#Regex pentru CI
RE_CNP  = re.compile(r"\b(\d{13})\b")  #13 cifre
RE_SERIE = re.compile(r"\bSERIA\s*([A-Z]{1,2})\b", re.I) #seria XX
RE_NUMAR = re.compile(r"\bNR\.?\s*([0-9]{6})\b", re.I) #"Numar 12345"
RE_EXP   = re.compile(r"(EXPIRĂ|EXPIRARE|VALABIL|VALID UNTIL)[:\s]*([0-3]?\d[-./][0-1]?\d[-./]\d{2,4})", re.I)

def parse_id_text(text: str) -> dict:  #extrage campuri din textul OCR al CI
    out = {}
    if m := RE_CNP.search(text): out["cnp"] = m.group(1)    #cnp
    if m := RE_SERIE.search(text): out["serie"] = m.group(1).upper()#seria
    if m := RE_NUMAR.search(text): out["num"] = int(m.group(1))   #numar
    if m := RE_EXP.search(text):                                  #expirare
        d = dateparser.parse(m.group(2), settings={"DATE_ORDER":"DMY"})
        if d: out["expira"] = str(d.date())         #YYYY-MM-DD

    #CAUTAM ETICHETE
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()] #linii curate
    for i, ln in enumerate(lines):
        if re.search(r"\bNUME\b", ln, re.I): #line cu "Nume"
            out["nume"] = ln.split(":")[-1].strip() if ":" in ln else (lines[i+1].strip() if i+1 < len(lines) else "")
        if re.search(r"(DOMICILIU|ADRESA|ADDRESS)", ln, re.I): # linie cu Domiciliu adresa
            out["domiciliu"] = ln.split(":")[-1].strip() if ":" in ln else " ".join(lines[i+1:i+3].strip())
        return out                                                     #intoarce campurile gasite
def parse_invoice_text_native(txt: str) -> dict: #extrage campuri din factura
    out = {}            #REZULTAT
    lines = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines() if l.strip()] #normalizeaza spatiile
    joined = "\n" .join(lines)

    #nr. factura
    m = re.search(r"(Factura(?:\s+fiscală)?|Invoice)\s*(?:nr\.?|no\.?|#)?\s*[:\-]?\s*([A-Z]{0,4}\s?\d{3,})", joined, re.I)
    if m: out["factura_numar"] = m.group(2).replace(" ", "") #scoate spatiile

    #data facturii
    m = re.search(r"(Data\s*(?:emiterii|facturii)?|Date)\s*[:\-]?\s*([0-3]?\d[-./][0-1]?\d[-./]\d{2,4})", joined, re.I)
    if m:
        d = dateparser.parse(m.group(2), settings={"DATE_ORDER":"DMY"})
        if d: out["factura_data"]  = str(d.date())          #YYYY-MM -DD

    #total de plata
    m = re.search(r"(Total(?:\s+de\s+plată)?|Amount\s+Due)\s*[:\-]?\s*([0-9]+(?:[.,][0-9]{2})?)", joined, re.I)
    if m: out ["total"] = m.group(1).replace(", ", ".") #inlocuieste virgula cu punt
    return out
#Validari CNP si reguli KYC

_CNP_CONST = [2,7,9,1,4,6,3,5,8,2,7,9]              #PONDERI CIFRE CNP

def valid_cnp(cnp: str) -> bool: #verifica cifra CNP ului
    if not cnp or not re.fullmatch(r"\d{13}", cnp):
        return False
    s = sum(int(cnp[i]) * _CNP_CONST[i] for i in range(12)) % 11 #suma ponderata mod 11
    ctrl = 1 if s == 10 else s
    return ctrl == int(cnp[12])  #compara cu cifra a 13 a

def validate_kyc(id_fields: dict, inv_fields: dict, *,          #aplica regulile de KYC minim
                 ci_laplacian_var: float,
                 today: 'date' = None,
                 lap_threshold: float = LAPLACIAN_THRESHOLD,
                 invoice_max_age_days: int = INVOICE_MAX_AGE_DAYS) -> tuple[str, list]:
    failures = []                                       #lista motivelor
    today = today or datetime.utcnow().date()          #data de azi (UTC)

    #1. calitatea pozei CI
    if ci_laplacian_var < lap_threshold:                #sub prag - blur
        failures.append("image_blurry")                 #adauga motiv

    #2.CNP valid
    cnp = id_fields.get("cnp")                          #ia cnp
    if not valid_cnp(cnp):                              #verifica
        failures.append("invalid cnp")                  #marcheaza invalid

    #3. CI expirata
    exp_str = id_fields.get("expira")                   #ia data expirarii
    exp_date = dateparser.parse(exp_str).date() if exp_str else None #parseaza
    if (not exp_date) or (exp_date < today):            #lipsa sau in trecut
        failures.append("id_expired")                   #marcheaza invalid

    #4.Factura: vechime si total
    fdate_str = id_fields.get("factura_data")           #data facturii
    fdate = dateparser.parse(fdate_str).date() if fdate_str else None #parseaza
    if(not fdate) or ((today - fdate) > timedelta(days=invoice_max_age_days)): #prea veche
        failures.append("Factura_veche")                                        #marcheaza invalid
    try:
        total = float(str(inv_fields.get("total", 0)).replace(",", "."))#converteteste total
        if total <= 0: #<= zero?
            failures.append("non_positive_total")           #invalid
    except Exception:
        failures.append("non_positive_total") #conversie esuata

    #5 campuri minime pe factura
    for req in ("factura_numar", "factura_data", "total"):  #3 campuri esentiale
        if req not in inv_fields:  #daca lipsesc
            failures.append("missing_requiered")  #invalid
            break               # nu continuam

    status = "KYC_INVALID" if failures else "KYC_VALID"     #VERDICT FINAL
    return status, failures                                 #intoarce rezultatul






















