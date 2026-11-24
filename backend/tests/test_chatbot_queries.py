from datetime import date

import pytest

from app.chatbot_queries import parse_plan, period_bounds, render_fallback


@pytest.mark.parametrize(
    "question, metric, domain",
    [
        ("Có bao nhiêu hóa đơn?", "count", "invoice"),
        ("Tổng chi phí hóa đơn?", "amount", "invoice"),
        ("Tổng tiền trước thuế?", "amount", "invoice"),
        ("Tổng tiền thuế VAT?", "amount", "invoice"),
        ("Tổng tiền thanh toán?", "amount", "invoice"),
        ("Có bao nhiêu hóa đơn đã duyệt?", "count", "invoice"),
        ("Còn bao nhiêu hóa đơn đang chờ?", "count", "invoice"),
        ("Có bao nhiêu hóa đơn bị từ chối?", "count", "invoice"),
        ("Thống kê trạng thái hóa đơn", "status_distribution", "invoice"),
        ("Tỷ lệ hóa đơn đã duyệt là bao nhiêu?", "count", "invoice"),
        ("Tổng chi phí theo nhà cung cấp dạng bảng", "amount", "invoice"),
        ("Số hóa đơn theo nhân viên", "count", "invoice"),
        ("Thống kê hóa đơn theo ngày", "summary", "invoice"),
        ("Thống kê hóa đơn theo tháng", "summary", "invoice"),
        ("Thống kê hóa đơn theo quý", "summary", "invoice"),
        ("Thống kê hóa đơn theo năm", "summary", "invoice"),
        ("Lịch sử công tác tháng này", "schedule_stats", "schedule"),
        ("Lịch công tác của tôi", "schedule_stats", "schedule"),
        ("Có bao nhiêu nhân viên?", "employee_count", "employee"),
        ("Cho tôi biết thời tiết ngày mai", None, "unsupported"),
    ],
)
def test_vietnamese_intent_classification(question, metric, domain):
    plan = parse_plan(question, role="accountant")
    assert plan["domain"] == domain
    if metric is not None:
        assert plan["metric"] == metric


def test_conversation_followups_keep_domain_metric_and_apply_new_filters():
    first = parse_plan("Tổng chi phí hóa đơn tháng này", role="accountant")
    approved = parse_plan("Trong đó có bao nhiêu hóa đơn đã duyệt?", role="accountant", previous_context=first)
    assert approved["domain"] == "invoice"
    assert approved["metric"] == "count"
    assert approved["status_filter"] == "approved"
    last_month = parse_plan("Tháng trước thì sao?", role="accountant", previous_context=first)
    assert last_month["domain"] == "invoice"
    assert last_month["metric"] == "amount"
    assert last_month["period"] == "last_month"
    as_table = parse_plan("Hãy trình bày kết quả dưới dạng bảng", role="accountant", previous_context=first)
    assert as_table["format"] == "table"
    assert as_table["domain"] == "invoice"
    assert as_table["metric"] == "amount"


@pytest.mark.parametrize(
    "period, expected",
    [
        ("last_month", (date(2024, 2, 1), date(2024, 2, 29))),
        ("last_month", (date(2025, 2, 1), date(2025, 2, 28))),
        ("last_month", (date(2025, 6, 1), date(2025, 6, 30))),
        ("last_month", (date(2025, 7, 1), date(2025, 7, 31))),
        ("last_month", (date(2024, 12, 1), date(2024, 12, 31))),
    ],
)
def test_previous_month_ranges(period, expected):
    anchors = {
        (2024, 2): date(2024, 3, 31),
        (2025, 2): date(2025, 3, 31),
        (2025, 6): date(2025, 7, 31),
        (2025, 7): date(2025, 8, 31),
        (2024, 12): date(2025, 1, 31),
    }
    assert period_bounds(period, anchors[(expected[0].year, expected[0].month)]) == expected


def test_status_only_followup_and_user_requested_table_are_honored():
    previous = parse_plan("Có bao nhiêu hóa đơn?", role="admin")
    plan = parse_plan("Còn bao nhiêu đang chờ?", role="admin", previous_context=previous)
    assert plan["domain"] == "invoice" and plan["status_filter"] == "submitted"
    assert plan["metric"] == "count"
    table = render_fallback(
        {"domain": "invoice", "metric": "status_distribution", "group_by": "status", "format": "table"},
        {"rows": [{"label": "approved", "count": 2, "percentage": 100.0}]},
    )
    assert "|" in table and "Đã phê duyệt" in table and "100.0%" in table


def test_unsupported_question_is_not_sent_as_database_answer():
    plan = parse_plan("Viết giúp tôi một bài thơ", role="employee")
    assert plan["domain"] == "unsupported"
    assert "hỏi về" in render_fallback(plan, {})
