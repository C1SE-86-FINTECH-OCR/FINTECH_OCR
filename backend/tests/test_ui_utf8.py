from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_profile_report_schedule_sources_are_valid_utf8_vietnamese():
    sources = {
        "web/src/App.jsx": ("Hồ sơ cá nhân", "Mật khẩu hiện tại", "Lịch sử xuất báo cáo", "Tổng tiền trước thuế"),
        "web/src/SchedulePage.jsx": ("Lịch công tác", "Bảng chú thích màu trên lịch", "Ngày bắt đầu", "Ngày kết thúc"),
        "backend/app/main.py": ("Mật khẩu hiện tại không đúng", "Nhân viên đã có lịch công tác trùng thời gian"),
    }
    for relative_path, phrases in sources.items():
        content = (ROOT / relative_path).read_bytes().decode("utf-8")
        assert "\ufffd" not in content
        for phrase in phrases:
            assert phrase in content


def test_profile_report_schedule_ui_strings_have_no_common_mojibake_markers():
    app = (ROOT / "web/src/App.jsx").read_bytes().decode("utf-8")
    backend = (ROOT / "backend/app/main.py").read_bytes().decode("utf-8")
    schedule = (ROOT / "web/src/SchedulePage.jsx").read_bytes().decode("utf-8")
    relevant = (
        app[app.index("function ReportsPage("):app.index("function UsersPage(")],
        app[app.index("function ProfileAvatar("):app.index("function InvoiceThumbnail(")],
        backend[backend.index("def login("):backend.index("@app.get('/api/v1/invoices')")],
        backend[backend.index("@app.get('/api/v1/schedules')"):backend.index("@app.get('/api/v1/ranking')")],
        backend[backend.index("def _report_invoice_query("):backend.index("@app.get('/api/v1/audit-logs')")],
        schedule,
    )
    for section in relevant:
        assert all(marker not in section for marker in ("Ã", "Ä", "\ufffd"))
