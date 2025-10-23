# Automated PDF Text Extractor

## 📝 Overview
This tool extracts text from **specific pages** of a PDF and saves it into a clean UTF-8 text file.

## ⚙️ Requirements
- Python 3.8+
- Library: `pdfplumber`

Install dependencies:
```
pip install pdfplumber
```

## 🚀 Usage
```
python pdf_text_extractor.py input.pdf output.txt 1 3 5
```

## 💡 Example
Suppose you want text from pages 1 and 3 of `report.pdf`:
```
python pdf_text_extractor.py report.pdf clean_output.txt 1 3
```

### Output (`clean_output.txt`)
```
Quarterly Report
Q1 Sales - $10,000

Key Insights
- Revenue up 25%
```

## 🧪 Testing & QA
- Tested on Windows and macOS.
- Validated text integrity and UTF-8 encoding.
- Checked edge cases like empty or invalid pages.

## 🙋 Proposal Questions
**Q1: GitHub Profile**  
A: https://github.com/yourusername

**Q2: Frameworks Used**  
A: Django, Flask, FastAPI, Pandas, NumPy

**Q3: QA Approach**  
A: Unit testing, manual validation, cross-platform checks.
