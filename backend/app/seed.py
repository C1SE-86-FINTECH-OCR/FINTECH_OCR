"""Run `python -m app.seed` from backend/ to generate demo accounts/data. DEV ONLY."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import select
from reportlab.pdfgen import canvas
from .core import Base,engine,SessionLocal,hash_password,storage_dir,settings
from .models import *
from .extraction import validate
import hashlib

ACCOUNTANT_DEMO_TRIPS = (
        ('Kiểm toán chi nhánh miền Trung', 'Đà Nẵng', datetime(2026, 12, 7, 8, 30, tzinfo=timezone.utc), datetime(2026, 12, 9, 17, 30, tzinfo=timezone.utc), 'planned'),
        ('Quyết toán thuế và đối soát tài chính cuối năm', 'Hà Nội', datetime(2026, 12, 14, 8, 0, tzinfo=timezone.utc), datetime(2026, 12, 16, 17, 0, tzinfo=timezone.utc), 'planned'),
        ('Tập huấn chuẩn mực kế toán tài chính mới', 'TP. Hồ Chí Minh', datetime(2026, 12, 21, 9, 0, tzinfo=timezone.utc), datetime(2026, 12, 23, 16, 0, tzinfo=timezone.utc), 'in_progress'),
 )

EMPLOYEE_DEMO_TRIPS = (
    ('Gặp đối tác', 'Hà Nội'),
    ('Khảo sát chi nhánh', 'Đà Nẵng'),
    ('Họp công tác', 'Hồ Chí Minh'),
)
EMPLOYEE_DEMO_EMAILS = ('employee@fintech.local', 'duy@fintech.local', 'ha@fintech.local')


def add_demo_schedule(db, **values):
    schedule = Schedule(**values)
    db.add(schedule)
    db.flush()
    db.add(AuditLog(action='schedule.demo_seeded', entity_type='schedule',
                    entity_id=schedule.id, actor_id=schedule.created_by))


def seed_accountant_schedules(db):
    accountant = db.scalar(select(User).where(User.email == 'accountant@fintech.local'))
    admin = db.scalar(select(User).where(User.email == 'admin@fintech.local'))
    if not accountant or not admin:
        return 0
    added = 0
    for title, dest, starts_at, ends_at, status in ACCOUNTANT_DEMO_TRIPS:
        exists = db.scalar(select(Schedule.id).where(Schedule.assigned_to == accountant.id, Schedule.title == title, Schedule.starts_at == starts_at).limit(1))
        if not exists:
            add_demo_schedule(db, title=title, destination=dest, starts_at=starts_at, ends_at=ends_at, assigned_to=accountant.id, created_by=admin.id, status=status)
            added += 1
    if added:
        db.commit()
    return added

def main():
    if settings.app_env!='development':raise SystemExit('Demo seeding is disabled outside development')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            added = seed_accountant_schedules(db)
            if added:
                print(f'Database already contains users. Seeded {added} missing accountant schedules for Dec 2026.')
            else:
                print('Database already contains users; demo data and accountant schedules already up to date.')
            return
        credentials=[('Quang Tú','admin@fintech.local','admin'),('Minh Anh','accountant@fintech.local','accountant'),('Trần Lan Hương','employee@fintech.local','employee'),('Ngô Đức Duy','duy@fintech.local','employee'),('Phạm Thu Hà','ha@fintech.local','employee')]
        users=[]
        for name,email,role in credentials:
            u=User(full_name=name,email=email,role=role,password_hash=hash_password('Password@123'))
            db.add(u);users.append(u)
        db.flush()
        samples=[('0000248','Khach san Song May',3472500,'pending','einvoice',users[2]),('0000234','Van tai An Phuc',865000,'approved','einvoice',users[2]),('0000219','Nha hang Bep Viet',1248000,'approved','bill',users[2]),('0000201','Luu tru Binh Minh',2156000,'rejected','einvoice',users[3]),('B-0246','Quan ca phe Ha Noi',196000,'draft','bill',users[3]),('0000290','Dich vu Hoa Sen',3420000,'pending','einvoice',users[4]),('0000321','Van phong pham Nam Son',760000,'approved','bill',users[4])]
        for idx,(number,seller,amount,approval,dtype,owner) in enumerate(samples):
            name=f'demo_invoice_{idx+1}.pdf';path=storage_dir()/name
            p=canvas.Canvas(str(path),pagesize=(595,842))
            p.setFont('Helvetica-Bold',18);p.drawString(55,760,'FINTECH OCR - DEMO INVOICE')
            p.setFont('Helvetica',12)
            for n,text in enumerate([f'Invoice No: {number}',f'Supplier: {seller}',f'Date: 23/10/2026',f'Tax code: 0108463921',f'Total amount: {amount} VND','SAMPLE DATA - NOT A LEGAL INVOICE']):p.drawString(55,700-n*36,text)
            p.save();raw=path.read_bytes()
            file=InvoiceFile(uploaded_by=owner.id,original_filename=name,file_type='pdf',mime_type='application/pdf',file_size_bytes=len(raw),storage_key=name,checksum_sha256=hashlib.sha256(raw).hexdigest())
            db.add(file);db.flush()
            inv=Invoice(file_id=file.id,invoice_number=number,invoice_date=datetime(2026,10,23).date(),seller_name=seller,seller_tax_code='0108463921',subtotal=round(amount/1.08,2),vat_rate=8,vat_amount=round(amount-(amount/1.08),2),total_amount=amount,confidence_score=.98,validation_status='valid',approval_status=approval,lookup_status='not_applicable' if dtype=='bill' else 'not_checked',document_type=dtype)
            db.add(inv);db.flush()
            db.add(ExtractionRun(invoice_id=inv.id,method='seed',status='completed',confidence_score=.98,extracted_json={'sample':True}))
            if approval=='pending':db.add(InvoiceApproval(invoice_id=inv.id,action_by=owner.id,action='submitted'))
            elif approval in ('approved','rejected'):
                db.add(InvoiceApproval(invoice_id=inv.id,action_by=owner.id,action='submitted'))
                db.add(InvoiceApproval(invoice_id=inv.id,action_by=users[1].id,action=approval,reason='Cần kiểm tra mã số thuế' if approval=='rejected' else None))
            if approval=='pending':db.add(Notification(user_id=users[1].id,invoice_id=inv.id,title='Hóa đơn chờ duyệt',message=f'{seller} đang chờ phê duyệt'))
        base=datetime.now(timezone.utc)
        for idx,user in enumerate(users[2:]):
            for j, (title, destination) in enumerate(EMPLOYEE_DEMO_TRIPS):
                status='completed' if j<idx+1 else 'planned'
                add_demo_schedule(db, title=title, destination=destination,
                                  starts_at=base+timedelta(days=j*6), ends_at=base+timedelta(days=j*6,hours=4),
                                  assigned_to=user.id, created_by=users[1].id, status=status,
                                  completed_at=base if status=='completed' else None)
        seed_accountant_schedules(db)
        db.commit()
        print('Seeded:',len(users),'accounts,',len(samples),'sample invoices, schedules and notifications.')
        print('All demo accounts use password: Password@123 (DEVELOPMENT ONLY)')
        for _,email,_ in credentials:print(' -',email)
if __name__=='__main__':main()
