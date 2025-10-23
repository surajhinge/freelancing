"""
pdf_text_extractor.py
---------------------
A lightweight script that extracts text from specific pages of a PDF and saves it as a UTF-8 .txt file.
Supports PyPDF2 or pdfplumber and runs on both Windows and macOS.

Usage:
    python pdf_text_extractor.py input.pdf output.txt 1 3 5
    python pdf_text_extractor.py sample.pdf extracted.txt 2 3
"""

import sys
import pdfplumber # This is external dependency; ensure it's installed via pip (pip install pdfplumber)


def extract_text_from_pages(pdf_path, output_path, pages):
    extracted_text = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages in PDF: {total_pages}")

        for p in pages:
            if p < 1 or p > total_pages:
                print(f"⚠️ Skipping invalid page number: {p}")
                continue
            page = pdf.pages[p - 1]
            text = page.extract_text()
            if text:
                extracted_text.append(text.strip())
            else:
                print(f"⚠️ No text found on page {p}")

    combined_text = "\n\n".join(extracted_text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined_text)

    print(f"✅ Extraction complete! Saved to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python pdf_text_extractor.py input.pdf output.txt 1 2 3")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_txt = sys.argv[2]
    page_numbers = list(map(int, sys.argv[3:]))

    extract_text_from_pages(input_pdf, output_txt, page_numbers)
