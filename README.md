# FINTECH OCR

**Internal Expense Invoice Digitization and Extraction System**

Capstone Project 1 (CMU-SE 450) · Team **C1SE.86** · International School, Duy Tan University

## About

Fintech OCR is a web-based system that automates the processing of electronic invoices. Users upload an invoice (PDF, JPG/PNG, or XML); the system extracts the data with OCR and AI, validates it, stores it, and lets users ask questions about their invoices through a chatbot.

```
Input → OCR → AI → Database → Validation → Chatbot → Output
```

## Key Features

- Upload invoices in PDF, image (JPG/PNG), or XML format
- OCR + LLM extraction into structured JSON (invoice number, date, seller/buyer, tax codes, line items, subtotal, VAT, total)
- Rule-based validation (tax code, date, subtotal/VAT/total calculation) with status (valid / needs review / error) and AI confidence score
- Review and correct extracted data side-by-side with the original invoice
- Dashboard with statistics and Excel (.xlsx) export
- Chatbot for natural-language Q&A over the invoice database (RAG as an extension)
- Role-based access: Admin, Employee, Viewer

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React.js, Tailwind CSS |
| Backend | Python FastAPI |
| Database | PostgreSQL / MySQL, vector DB (RAG) |
| AI / OCR | OpenCV, Tesseract / PaddleOCR, LLM (e.g. Google Gemini) |
| Storage | Cloudinary / Firebase Storage |
| Reporting | Openpyxl |

## Timeline

September 3, 2026 – December 15, 2026 (Scrum, 5 sprints + testing and final release)

## Team

| Name | Role |
| --- | --- |
| Tran Phuoc Hiep | Scrum Master |
| Tran Phuoc Nhan | Team Member |
| Tran Quang Thien | Team Member |
| Tran Quoc Huy | Team Member |

**Mentor:** MSc Dang Ngoc Trung

## Scope Note

Development and testing use simulated invoices. Focus is on Vietnamese e-invoices (VAT 0%, 5%, 8%, 10%). Legal authenticity checks, payment gateways, and handwritten invoices are out of scope for this phase.
