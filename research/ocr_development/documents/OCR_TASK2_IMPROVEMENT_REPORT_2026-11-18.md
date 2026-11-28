# TASK 2 OCR improvement report — 2026-11-18

## Evaluation-set integrity

The seven-image set `HD-01`–`HD-07` is **no longer an untouched held-out set**. Its reviewed labels and scored failures were used to frame this improvement work. No image from that set was opened, rescored, or used to select a parser rule or preprocessing parameter during this change. Do not use its next score as an unbiased acceptance result; reserve a new held-out set for acceptance.

No independent real-document development set is present in the repository. The available OCR-related fixtures are synthetic text/XML and API fixtures. This change therefore uses synthetic unit tests and two synthetic local Tesseract smoke documents only. These are regression/development checks, not evidence of accuracy on unseen real invoices.

## Current pipeline findings

- The raster OCR engine is local Tesseract; the tested installation is Tesseract 5.5.3.20260724 with `eng`, `vie`, and `osd`. No document-understanding AI model is integrated.
- JPG/PNG use Tesseract `vie+eng`; PDF pages with embedded text use PyMuPDF text extraction; image-only PDF pages are rendered and passed to the raster pipeline.
- Before this change, image preparation applied EXIF orientation and enlargement but did not normalize contrast or estimate small skew. Page orientation detection was a later fallback when core fields were sparse.
- OCR selection is based on field completeness and text length, not calibrated OCR confidence. `confidence_score` is a required-field completeness ratio, not a measure of character or field recognition certainty.
- Invoice fields are extracted from flattened OCR text by conservative label patterns. Spatial OCR is used only for selected financial-row recovery. Different supplier layouts can still omit/misread labels or confuse seller blocks, invoice identifiers, totals, and tender/change amounts.
- Line items use delimited table parsing and a receipt fallback. Free text lacks reliable cell geometry, so wrapped descriptions, merged columns, and products without explicit row structure remain difficult. Unsupported/ambiguous values should remain null.

## Changes made

- `backend/app/extraction.py`: image preparation now normalizes grayscale contrast and attempts conservative deskew within ±5° using horizontal projection scoring. It rotates only when alignment improves by at least 6%; otherwise it leaves the image unchanged. This adds no new runtime dependency.
- `backend/app/extraction.py`: financial total extraction now ranks explicit payable-total labels ahead of generic `Total`, ignores subtotal/tax/tender/change rows, and leaves conflicting equally specific totals empty.
- `backend/app/extraction.py`: when a prominent e-invoice heading is missing from OCR text, classification now requires an explicit tax identifier, invoice number, issue date, and tax evidence together. A file suffix or single tax identifier remains insufficient.
- `backend/app/extraction.py`: receipt line-item filtering rejects additional generic metadata/contact/payment rows so they are not treated as products.
- `backend/tests/test_extraction.py`: added synthetic tests for VND formats, payable-total selection and ambiguity, non-product receipt rows, and skew/contrast preprocessing.
- `backend/tests/test_phase2_api.py`: added an actual Tesseract/API round-trip test using a generated synthetic receipt, in-memory SQLite, and temporary uploads. It checks field and line extraction, persistence/read-back, and original-file checksum.
- `web/src/InvoiceDetailPage.jsx` and `web/src/InvoiceDetailPage.css`: show a clear OCR-is-draft notice and mark empty extracted fields as “Chưa trích xuất”, while leaving populated values unlabelled as verified. Existing employee draft/rejected edit and save flow is retained.

No parser values are hardcoded for the seven held-out images. No database, migration, seed, upload, API contract, mobile or configuration files were changed.

## Verification evidence

- `backend/tests/test_extraction.py`: **32 passed**.
- Full backend test suite, run with its relative SQLite test database and uploads redirected to a fresh temporary working directory: **165 passed, 5 warnings**.
- After adding the API/Tesseract round-trip case, the full backend suite: **166 passed, 5 warnings**; the focused real-engine API case: **1 passed**.
- After adding the structural e-invoice classification regression, the full backend suite: **167 passed, 5 warnings**; extraction-focused tests: **33 passed**.
- Web `npm.cmd run build`: **PASS** (Vite 6.4.5; 2,221 modules). The package has no frontend test script. Vite emitted its existing large-chunk advisory.
- Local Tesseract smoke test on a generated synthetic English receipt page: extracted the explicit bill number, date, merchant, subtotal, total, and two structured item rows; ignored cash tender/change as total. This is one synthetic smoke test, not a real-invoice benchmark.
- Local Tesseract smoke test on a generated low-contrast, 2.5-degree-skewed Vietnamese e-invoice: OCR recovered the printed heading, seller, tax code, invoice number, date, subtotal, VAT, and total exactly. This is one synthetic example and does not establish real-document or held-out accuracy.
- Tesseract reports `eng`, `vie`, and `osd` available. An earlier Unicode smoke attempt was invalid because the shell altered its input before image generation; the later escaped-Unicode synthetic run above is the valid smoke evidence.
- No Browser UAT or PostgreSQL test was run. The upload persistence round-trip test used only in-memory SQLite and temporary files.
- The seven-image held-out set was **not rerun** after changes.

## Accuracy and remaining work

There is no post-change real-document accuracy result. The earlier baseline is retained only as a historical, now-contaminated development observation; it must not be compared with a new score as a fair held-out delta.

Next acceptance work requires a fresh, permitted set of at least 30–50 real documents, reviewed ground truth, and a split frozen before parser development. Include e-invoices and multiple retail/restaurant/supermarket/hotel/service layouts, distinct sellers, and images/PDFs at different quality levels. Development documents may guide rule/model changes; held-out documents must remain unseen until one final evaluation. Report field-level, line-level, document-level exact/normalized accuracy, abstentions, runtime, and upload/persistence separately.

For improved table recovery beyond rules, capture Tesseract word boxes/confidence or evaluate a locally deployable layout-aware OCR/document model on development data. Any new model requires a separate review of local resource needs, language support, licensing, privacy, and operational cost before adoption. No external API or paid service was added.

## Local document-model option assessed

PaddleOCR's PP-StructureV3 is the most relevant next experiment because it combines document layout parsing and table recognition and exposes local Python integration. Its official documentation says it supports CPU inference with lightweight configurations and gives an example of about 3.74 seconds per page on an Intel 8350C; this is an upstream example, not a measurement on this project hardware. The same documentation notes that the default configuration uses the largest model per module and recommends selecting configurations based on device capability. Therefore start with a separately installed development environment and lightweight CPU configuration, benchmark memory/latency, and compare on a fresh development set before deciding integration. Do not install/download model weights in the current backend environment until approved. [PP-StructureV3 overview and CPU FAQ](http<LOCAL_PATH>

**Task 2 is not complete and OCR is not accepted.**

## Follow-up Website integration attempt — 2026-11-18

- Re-ran the synthetic real-Tesseract API round-trip: **1 passed**. It writes only to the test's in-memory SQLite database and temporary upload directory.
- Rebuilt Web with `npm.cmd run build`: **PASS**; no Frontend test script is configured.
- Ports 8000, 8001, and 5173 had no listener when checked. No existing process was stopped.
- Browser UAT is **BLOCKED**: the Windows Computer Use native pipe failed to connect after retry and reinitialization (`The system cannot find the file specified`). No browser upload, login, or UI result is claimed. No PostgreSQL database was contacted or modified.
- The Website source has an Employee upload route and an authenticated original-file/detail/edit flow; this was source-reviewed and build-checked only in this follow-up.
