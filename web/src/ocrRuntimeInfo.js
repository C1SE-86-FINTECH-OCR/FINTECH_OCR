const hasValue = value => value != null && (typeof value !== 'string' || value.trim() !== '');

export function invoiceProcessingState(invoice) {
  if (!hasValue(invoice?.id)) return { label: 'Chưa có kết quả', tone: 'gray' };
  if (invoice?.validation_status === 'error' || invoice?.ocr?.reason === 'extraction_failed') {
    return { label: 'Xử lý thất bại', tone: 'red' };
  }
  if (invoice?.validation_status === 'needs_review' || invoice?.ocr?.requires_review || aiProcessingState(invoice?.ocr)?.fallback
      || invoice?.warnings?.some(warning => warning.passed !== true)) {
    return { label: 'Cần kiểm tra', tone: 'orange' };
  }
  return { label: 'Đã xử lý', tone: 'green' };
}

export function aiProcessingState(ocr) {
  const llm = ocr?.llm;
  if (llm?.status === 'failed') {
    const rejected = ['schema_error', 'invalid_json', 'invalid_response'].includes(llm.error_kind);
    return { label: rejected ? 'AI chưa có kết quả phù hợp' : 'AI tạm thời không khả dụng', tone: 'orange', fallback: true };
  }
  if (llm?.status === 'grounded_proposal' && llm.merge_status === 'accepted') {
    return { label: 'AI đã hỗ trợ trích xuất', tone: 'green', fallback: false };
  }
  if (llm?.status === 'grounded_proposal' && llm.merge_status === 'no_supported_proposal') {
    return { label: 'Đề xuất AI chưa đủ bằng chứng', tone: 'orange', fallback: true };
  }
  return null; // No success/failure claim when AI did not participate.
}

export function invoiceStatusNotes(invoice) {
  const notes = [];
  const assessment = invoice?.ocr?.confidence;
  if (!hasValue(assessment?.score) || !assessment?.policy || !assessment?.approval_reference
      || !Number.isFinite(Number(assessment.score)) || Number(assessment.score) < 0 || Number(assessment.score) > 1) {
    notes.push({ key: 'confidence', label: 'Độ tin cậy chưa xác định', tone: 'gray' });
  } else {
    notes.push({ key: 'confidence', label: assessment.status === 'low' ? 'Độ tin cậy thấp'
      : `Điểm tin cậy ${Math.round(Number(assessment.score) * 100)}%`, tone: assessment.status === 'low' ? 'orange' : 'gray' });
  }
  const ai = aiProcessingState(invoice?.ocr);
  if (ai) notes.push({ ...ai, key: 'ai', label: ai.fallback ? `${ai.label} · Đã dùng kết quả tại máy` : ai.label });
  const informationOnly = invoice?.ocr?.findings?.some(finding => finding.code === 'NON_FINANCIAL_ADJUSTMENT');
  const fields = ['invoice_number', 'invoice_date', 'seller_name'];
  if (!informationOnly) fields.push('total_amount');
  if (invoice?.document_type === 'einvoice') fields.push('seller_tax_code');
  if (fields.some(key => !hasValue(invoice?.[key]))
      || (!informationOnly && Array.isArray(invoice?.items) && invoice.items.length === 0)) {
    notes.push({ key: 'missing', label: 'Một số trường chưa đủ dữ liệu', tone: 'orange' });
  }
  if (invoice?.ocr?.truncated || invoice?.warnings?.some(warning => warning.rule === 'EXTRACTION-COVERAGE')) {
    notes.push({ key: 'coverage', label: 'Kết quả chưa bao phủ toàn bộ chứng từ', tone: 'orange' });
  }
  return notes;
}

export function ocrRuntimeNotice(ocr) {
  if (!ocr) return null;
  const preview = ocr.findings?.some(finding => finding?.code === 'LOCAL_DEVELOPMENT_PREVIEW_UNVERIFIED');
  const used = ({ current: 'current (OCR cục bộ)', hybrid_v8_final: 'Hybrid V8 Final', hybrid_v8: 'Hybrid V8', hybrid_v7: 'Hybrid V7', hybrid_v6: 'Hybrid V6', none: 'chưa có kết quả' })[ocr.used_pipeline] || ocr.used_pipeline || 'chưa xác định';
  const prefix = `${preview ? 'UNVERIFIED / DEVELOPMENT PREVIEW · ' : ''}Pipeline thực tế: ${used}. `;
  if (!['hybrid_v6', 'hybrid_v7', 'hybrid_v8', 'hybrid_v8_final'].includes(ocr.requested_pipeline)) return prefix.trim();
  const name = ocr.requested_pipeline === 'hybrid_v8_final' ? 'Hybrid V8 — bản hoàn thiện kỹ thuật' : ocr.requested_pipeline === 'hybrid_v8' ? 'Hybrid V8' : ocr.requested_pipeline === 'hybrid_v7' ? 'Hybrid V7' : 'Hybrid V6';
  if (ocr.reason === 'extraction_failed') return `${prefix}Trích xuất trong chế độ ${name} thất bại. Tệp gốc được giữ lại; hãy kiểm tra lỗi và dữ liệu trước khi tiếp tục.`;
  if (ocr.fallback) return `${prefix}${name} gặp lỗi; hóa đơn này đã dùng pipeline OCR hiện tại. Hãy kiểm tra thủ công.`;
  if (ocr.reason === 'v8_baseline_retained') return `${prefix}Bước hoàn thiện của ${name} chưa cung cấp được kết quả sử dụng được. Hóa đơn giữ kết quả Hybrid V8 và cần được đối chiếu với chứng từ gốc.`;
  if (ocr.reason === 'xml_uses_existing_parser') return `${prefix}XML được xử lý bằng parser hiện có. Cấu hình thử nghiệm ${name} chỉ áp dụng cho ảnh/PDF.`;
  return `${prefix}${name} · Chế độ thử nghiệm, chưa nghiệm thu. Kết quả cần người dùng đối chiếu.${ocr.truncated ? ' Tài liệu vượt giới hạn số trang; kết quả chưa bao phủ toàn bộ file.' : ''}`;
}

export function completenessLabel(value) {
  if (value == null || !Number.isFinite(Number(value))) return 'Chưa đo độ đầy đủ';
  return `Trường đã có dữ liệu · ${Math.round(Number(value) * 100)}%`;
}

export function confidenceLabel(ocr, legacyValue) {
  const assessment = ocr?.confidence;
  if (!assessment) return completenessLabel(legacyValue);
  if (assessment.score == null || !Number.isFinite(Number(assessment.score))) return 'Điểm tin cậy chưa xác định';
  return `Điểm theo chính sách · ${Math.round(Number(assessment.score) * 100)}%`;
}

export function llmRuntimeNotice(ocr) {
  const policy = ocr?.findings?.find(finding => finding?.code === 'GEMINI_ADMIN_POLICY_STATUS');
  if (policy && policy.status !== 'approved') return policy.reason;
  const consent = ocr?.findings?.find(finding => finding?.code === 'GEMINI_WEB_CONSENT_STATUS');
  if (consent && consent.status !== 'approved') return consent.reason;
  const llm = ocr?.llm;
  if (!llm) return null;
  if (llm.status === 'unconfigured') return 'Lớp hỗ trợ Gemini chưa được kích hoạt hoặc chưa đủ cấu hình/quyền truyền dữ liệu. Hóa đơn giữ kết quả OCR.';
  if (llm.status === 'local_only') return 'Chứng từ này được giữ tại máy; không thuộc phạm vi chính sách cho phép gửi tới Gemini Free Tier hoặc quyền đã được thu hồi.';
  if (llm.status === 'deferred' && llm.quota_limit) return 'Gemini không được gọi: đã đạt giới hạn số lần thử cục bộ theo phút/ngày. Hệ thống giữ kết quả OCR/Hybrid, không chuyển sang dịch vụ trả phí.';
  if (llm.status === 'deferred') return ocr.findings?.some(finding => finding.code === 'LLM_FALLBACK_TO_OCR' && finding.reason === 'rate_limit')
    ? 'Gemini không được gọi: đang chờ sau khi chạm hạn mức Free Tier. Hệ thống giữ kết quả tại máy, không gửi lại liên tục.'
    : 'Gemini không được gọi: đang xử lý yêu cầu khác. Hệ thống giữ kết quả trích xuất tại máy.';
  if (llm.status === 'input_unavailable') return 'Gemini không xử lý vì văn bản OCR không có hoặc vượt giới hạn. Hóa đơn giữ kết quả OCR.';
  if (llm.status === 'failed') {
    if (llm.http_status === 503) {
      const attempts = Number.isInteger(llm.attempts) && llm.attempts > 0 ? ` sau ${llm.attempts} lần thử` : '';
      const stopped = llm.retry_stop_reason === 'local_request_limit' ? ' Đã dừng retry do giới hạn số lần gọi cục bộ.'
        : llm.retry_stop_reason === 'time_budget' ? ' Đã dừng retry do hết thời gian cho phép.' : '';
      return `Gemini trả HTTP 503 UNAVAILABLE${attempts}: dịch vụ hiện không khả dụng.${stopped} Hệ thống giữ kết quả OCR/Hybrid tại máy; chưa có kết quả Gemini được chấp nhận.`;
    }
    if (llm.error_kind === 'schema_error' || llm.error_kind === 'invalid_json') return 'Gemini đã phản hồi nhưng JSON hoặc cấu trúc dữ liệu không đáp ứng yêu cầu. Hệ thống giữ kết quả OCR/Hybrid tại máy.';
    if (ocr.findings?.some(finding => finding.code === 'LLM_FALLBACK_TO_OCR' && finding.reason === 'rate_limit')) return 'Gemini Free Tier đã chạm hạn mức hoặc bị giới hạn tần suất. Hệ thống giữ kết quả OCR tại máy, không chuyển sang dịch vụ trả phí.';
    return 'Lớp hỗ trợ trích xuất không khả dụng hoặc phản hồi không đáp ứng yêu cầu. Hệ thống đã giữ kết quả OCR dự phòng; không tự đổi model, khóa, project hoặc chuyển sang dịch vụ trả phí.';
  }
  if (llm.status === 'grounded_proposal') {
    if (llm.merge_status === 'no_supported_proposal') return 'Gemini đã trả JSON hợp lệ nhưng chưa có đề xuất nào đủ bằng chứng và ngữ cảnh để hợp nhất. Hệ thống giữ kết quả OCR/Hybrid.';
    return `${llm.provider === 'google-gemini' ? 'Gemini đã phản hồi' : 'Lớp AI đã phản hồi'}; đề xuất đã được đối chiếu với văn bản OCR. Các giá trị mâu thuẫn không tự ghi đè; kết quả vẫn cần xem xét và không đồng nghĩa với đã xác minh chính xác.`;
  }
  return null;
}

export function ocrFindingLabel(finding) {
  const labels = {
    GEMINI_ADMIN_POLICY_STATUS: 'Quyết định tự động theo chính sách Gemini',
    GEMINI_WEB_CONSENT_STATUS: 'Quyền chia sẻ Gemini cho lần tải này',
    LLM_OCR_FIELD_CONFLICT: 'Dữ liệu OCR và đề xuất AI khác nhau; giữ giá trị OCR',
    LLM_FIELD_EVIDENCE_REJECTED: 'Đề xuất chưa khớp bằng chứng OCR',
    LLM_FIELD_CONTEXT_CONFLICT: 'Nhãn hoặc vai trò của trường không khớp',
    LLM_FIELD_CONTEXT_UNRESOLVED: 'Chưa đủ ngữ cảnh để bổ sung trường còn thiếu',
    LLM_FIELD_CONFLICT_UNRESOLVED: 'OCR còn nhiều giá trị hoặc nhiều mức VAT; AI không tự chọn một giá trị chung',
    LLM_ITEM_ALIGNMENT_UNRESOLVED: 'Chưa xác định được dòng hàng tương ứng duy nhất',
    LLM_OCR_ITEM_CONFLICT: 'Ô dữ liệu dòng hàng có mâu thuẫn; giữ dữ liệu OCR',
    LLM_ITEM_COUNT_CONFLICT: 'Số dòng hàng OCR và đề xuất AI khác nhau',
    LLM_ITEMS_EVIDENCE_REJECTED: 'Đề xuất dòng hàng chưa đủ bằng chứng về dòng hoặc cột',
    LLM_ITEM_EVIDENCE_REJECTED: 'Một dòng đề xuất chưa đủ bằng chứng; giữ các dòng đã nhận diện được',
    LLM_PARTIAL_TABLE_PROPOSAL: 'Chỉ một phần bảng đề xuất đủ bằng chứng; bảng còn cần xem xét',
    LLM_FIELD_CONTEXT_UNAVAILABLE: 'Chưa xác định được vùng nguồn của trường; giữ trống thay vì đoán',
    XML_NUMERIC_PRECISION_UNSUPPORTED: 'Số liệu XML vượt độ chính xác cột hiện có; giữ tệp nguồn và cần xem xét',
    DOCUMENT_RELATIONSHIP: 'Loại chứng từ và thông tin hóa đơn được tham chiếu',
    CURRENT_DOCUMENT_REFERENCE_EXCLUDED: 'Đã tách thông tin hóa đơn gốc khỏi trường của hóa đơn hiện tại',
    NON_FINANCIAL_ADJUSTMENT: 'Điều chỉnh thông tin phi tài chính; không tự điền cột tiền hoặc VAT',
    PRINTED_ZERO_RETAINED: 'Đã giữ giá trị 0 có trên chứng từ',
    LLM_FALLBACK_TO_OCR: 'Lớp hỗ trợ trích xuất gặp lỗi; đã giữ kết quả OCR',
    LLM_UNCONFIGURED: 'Lớp hỗ trợ trích xuất chưa được kích hoạt',
    LLM_FREE_TIER_LOCAL_ONLY: 'Chứng từ được giữ tại máy; không thuộc phạm vi được phép gửi tới Gemini Free Tier',
    LLM_INPUT_UNAVAILABLE: 'Văn bản OCR không đủ điều kiện gửi tới lớp hỗ trợ',
    LLM_RESULT_REQUIRES_REVIEW: 'Đề xuất AI vẫn cần được xem xét',
    ROW_ARITHMETIC_CONFLICT: 'Số lượng nhân đơn giá chưa khớp thành tiền; số liệu được giữ nguyên',
    ITEM_SUBTOTAL_CONFLICT: 'Tổng dòng hàng chưa khớp tiền trước thuế; cần đối chiếu giảm giá hoặc phạm vi tính',
  };
  return labels[finding?.code] || finding?.code || 'Ghi nhận OCR';
}
