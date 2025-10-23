"""
pdf_text_extractor_builtin.py
-----------------------------
A lightweight script that extracts text from specific pages of a PDF file
and saves it as a UTF-8 text file, using only built-in Python modules.

Usage:
    python pdf_text_extractor_builtin.py input.pdf output.txt 1 3 5
"""

import sys
import subprocess
import tempfile
import os


def check_pdftotext():
    """Check if pdftotext (part of poppler-utils) is available."""
    try:
        subprocess.run(["pdftotext", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False


def extract_with_pdftotext(pdf_path, output_path, pages):
    """Extract text using the system 'pdftotext' command."""
    extracted_text = []
    for page in pages:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp_path = tmp.name

        # Run pdftotext for a single page
        cmd = ["pdftotext", "-f", str(page), "-l", str(page), pdf_path, tmp_path]
        subprocess.run(cmd, check=True)

        # Read the extracted text
        with open(tmp_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
            if text:
                extracted_text.append(text)
            else:
                print(f"⚠️ No text found on page {page}")

        os.remove(tmp_path)

    combined_text = "\n\n".join(extracted_text)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(combined_text)

    print(f"✅ Extraction complete! Saved to: {output_path}")


def extract_basic(pdf_path, output_path):
    """Fallback: crude text extraction for very simple PDFs (no formatting)."""
    with open(pdf_path, "rb") as f:
        content = f.read()

    text = content.decode(errors="ignore")
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(text)
    print("⚠️ Used basic extraction (no page control).")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python pdf_text_extractor_builtin.py input.pdf output.txt 1 2 3")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_txt = sys.argv[2]
    pages = list(map(int, sys.argv[3:]))

    if check_pdftotext():
        extract_with_pdftotext(input_pdf, output_txt, pages)
    else:
        print("⚠️ 'pdftotext' not found. Using basic fallback (less accurate).")
        extract_basic(input_pdf, output_txt)
