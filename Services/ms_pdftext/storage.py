import os, re

PDF_DIR = "/data/pdf"
TXT_DIR = "/data/txt"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(TXT_DIR, exist_ok=True)

def safe_name(s: str) -> str:
    s = re.sub(r"[^\w\-\.]", "_", s)
    return s[:180]

def pdf_path(event):
    return f"{PDF_DIR}/{safe_name(event['dosar'])}.pdf"

def txt_path(event):
    return f"{TXT_DIR}/{safe_name(event['dosar'])}.txt"
