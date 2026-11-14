"""Run `python -m app.seed` from backend/ to generate demo accounts/data. DEV ONLY."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import select
from reportlab.pdfgen import canvas
from .core import Base,engine,SessionLocal,hash_password,storage_dir,settings
from .models import *
from .extraction import validate
import hashlib

def main():
    if settings.app_env!='development':raise SystemExit('Demo seeding is disabled outside development')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            print('Database already contains users; seed skipped.');return
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
            for j in range(3):
                status='completed' if j<idx+1 else 'planned'
                db.add(Schedule(title=['Gặp đối tác','Khảo sát chi nhánh','Họp công tác'][j],destination=['Hà Nội','Đà Nẵng','Hồ Chí Minh'][j],starts_at=base+timedelta(days=j*6),ends_at=base+timedelta(days=j*6,hours=4),assigned_to=user.id,created_by=users[1].id,status=status,completed_at=base if status=='completed' else None))
        db.commit()
        print('Seeded:',len(users),'accounts,',len(samples),'sample invoices, schedules and notifications.')
        print('All demo accounts use password: Password@123 (DEVELOPMENT ONLY)')
        for _,email,_ in credentials:print(' -',email)
if __name__=='__main__':main()
