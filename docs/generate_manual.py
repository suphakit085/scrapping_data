#!/usr/bin/env python3
"""
Generator for ai_web_scrpping Project Manual (Thai language PDF)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
import datetime
import os

# ─── Register Fonts ───────────────────────────────────────────────────────────
font_path = "C:/Windows/Fonts/tahoma.ttf"
font_bold_path = "C:/Windows/Fonts/tahomabd.ttf"
if not os.path.exists(font_path):
    font_path = "C:/Windows/Fonts/arial.ttf"
    font_bold_path = "C:/Windows/Fonts/arialbd.ttf"
try:
    pdfmetrics.registerFont(TTFont('Thai', font_path))
    pdfmetrics.registerFont(TTFont('ThaiBold', font_bold_path))
    pdfmetrics.registerFont(TTFont('ThaiItalic', font_path))
    pdfmetrics.registerFont(TTFont('Mono', 'C:/Windows/Fonts/cour.ttf'))
    pdfmetrics.registerFont(TTFont('MonoBold', 'C:/Windows/Fonts/courbd.ttf'))
except Exception:
    pass
pdfmetrics.registerFontFamily('Thai', normal='Thai', bold='ThaiBold', italic='ThaiItalic')

# ─── Color Palette ────────────────────────────────────────────────────────────
NAVY       = colors.HexColor('#1B2A4A')
TEAL       = colors.HexColor('#0D7377')
TEAL_LIGHT = colors.HexColor('#14A085')
TEAL_BG    = colors.HexColor('#E8F8F5')
GRAY_DARK  = colors.HexColor('#2C3E50')
GRAY_MID   = colors.HexColor('#5D6D7E')
GRAY_LIGHT = colors.HexColor('#ECF0F1')
GRAY_RULE  = colors.HexColor('#BDC3C7')
WHITE      = colors.white
ORANGE     = colors.HexColor('#E67E22')
ORANGE_BG  = colors.HexColor('#FEF9E7')
RED        = colors.HexColor('#C0392B')
RED_BG     = colors.HexColor('#FDEDEC')
GREEN      = colors.HexColor('#1E8449')
GREEN_BG   = colors.HexColor('#EAFAF1')
BLUE       = colors.HexColor('#1565C0')
BLUE_BG    = colors.HexColor('#E3F2FD')
CODE_BG    = colors.HexColor('#F4F6F8')
CODE_BORDER= colors.HexColor('#CAD3DC')

PAGE_W, PAGE_H = A4  # 210 x 297 mm

# ─── Styles ───────────────────────────────────────────────────────────────────
def make_styles():
    s = {}
    s['body'] = ParagraphStyle('body', fontName='Thai', fontSize=10.5, leading=17, textColor=GRAY_DARK, spaceAfter=6, spaceBefore=2)
    s['h1'] = ParagraphStyle('h1', fontName='ThaiBold', fontSize=20, leading=26, textColor=NAVY, spaceBefore=18, spaceAfter=10, borderPad=(0, 0, 4, 0))
    s['h2'] = ParagraphStyle('h2', fontName='ThaiBold', fontSize=14, leading=20, textColor=TEAL, spaceBefore=14, spaceAfter=6)
    s['h4'] = ParagraphStyle('h4', fontName='ThaiBold', fontSize=10.5, leading=15, textColor=GRAY_DARK, spaceBefore=8, spaceAfter=3)
    s['code'] = ParagraphStyle('code', fontName='Mono', fontSize=9.5, leading=14, textColor=colors.HexColor('#1A252F'), backColor=CODE_BG, borderColor=CODE_BORDER, borderWidth=1, borderPad=8, spaceBefore=4, spaceAfter=6)
    s['bullet'] = ParagraphStyle('bullet', fontName='Thai', fontSize=10.5, leading=17, leftIndent=16, bulletIndent=0, textColor=GRAY_DARK, spaceAfter=3)
    s['table_header'] = ParagraphStyle('table_header', fontName='ThaiBold', fontSize=9.5, leading=13, textColor=WHITE)
    s['table_cell'] = ParagraphStyle('table_cell', fontName='Thai', fontSize=9.5, leading=14, textColor=GRAY_DARK)
    return s

ST = make_styles()

# ─── Helper Flowables ─────────────────────────────────────────────────────────
def hline(color=GRAY_RULE, thickness=0.8, spB=4, spA=8):
    return HRFlowable(width='100%', thickness=thickness, color=color, spaceAfter=spA, spaceBefore=spB)

def vspace(h=6):
    return Spacer(1, h)

def code_block(lines):
    text = '\n'.join(lines)
    return Paragraph(text.replace('\n', '<br/>').replace(' ', '&nbsp;'), ST['code'])

def bullet_item(text):
    return Paragraph(f'<bullet>&bull;</bullet>{text}', ST['bullet'])

def callout(kind, title, body_items):
    cfg = {
        'note':    (BLUE,   BLUE_BG,   BLUE,   'ℹ หมายเหตุ'),
        'warning': (ORANGE, ORANGE_BG, ORANGE, '⚠ ข้อควรระวัง'),
        'tip':     (GREEN,  GREEN_BG,  GREEN,  '✓ เคล็ดลับ'),
        'error':   (RED,    RED_BG,    RED,    '✕ ข้อผิดพลาด'),
    }
    border_c, bg_c, text_c, default_title = cfg.get(kind, cfg['note'])
    label = title or default_title

    title_style = ParagraphStyle(f'ct_{kind}', fontName='ThaiBold', fontSize=10, leading=14, textColor=text_c)
    body_style = ParagraphStyle(f'cb_{kind}', fontName='Thai', fontSize=10, leading=15, textColor=GRAY_DARK, spaceAfter=2)

    content = [[Paragraph(label, title_style)]]
    for item in body_items:
        content.append([Paragraph(item, body_style)])

    t = Table(content, colWidths=[PAGE_W - 2*2.5*cm - 2*12])
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), bg_c),
        ('LINEAFTER',   (0,0), (0,-1), 3, border_c),
        ('LINEBEFORE',  (0,0), (0,-1), 3, border_c),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING',(0,0), (-1,-1), 10),
        ('TOPPADDING',  (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('BOX', (0,0),(-1,-1), 1, border_c),
    ]))
    return t

# ─── Page Templates ───────────────────────────────────────────────────────────
def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    page_num = doc.page

    if page_num > 2:
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 18*mm, w, 10*mm, fill=1, stroke=0)
        canvas.setFont('ThaiBold', 9)
        canvas.setFillColor(WHITE)
        canvas.drawString(2.5*cm, h - 13*mm, 'คู่มือการใช้งาน ai_web_scrpping')
        canvas.setFont('Thai', 9)
        canvas.drawRightString(w - 2.5*cm, h - 13*mm, 'ระบบรวบรวมข้อมูลเชิงพื้นที่ (Location Intelligence)')

        canvas.setFillColor(GRAY_LIGHT)
        canvas.rect(0, 0, w, 12*mm, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, 11.5*mm, w, 0.8*mm, fill=1, stroke=0)

        canvas.setFont('Thai', 8.5)
        canvas.setFillColor(GRAY_MID)
        canvas.drawString(2.5*cm, 4*mm, f'เวอร์ชัน 2.0  |  จัดทำ: {datetime.date.today().strftime("%d %B %Y")}')
        canvas.setFont('ThaiBold', 9)
        canvas.setFillColor(NAVY)
        canvas.drawRightString(w - 2.5*cm, 4*mm, f'หน้า {page_num - 2}')

    canvas.restoreState()

# ─── COVER PAGE ───────────────────────────────────────────────────────────────
def build_cover():
    elements = []
    w, h = A4

    class CoverCanvas(Flowable):
        def wrap(self, availWidth, availHeight):
            return (availWidth, h - 4*cm)
        def draw(self):
            c = self.canv
            cw = self.width
            ch = h - 4*cm

            c.setFillColor(NAVY)
            c.rect(0, 0, cw, ch, fill=1, stroke=0)
            c.setFillColor(TEAL)
            c.rect(0, ch * 0.42, cw, ch * 0.58, fill=1, stroke=0)

            c.setFillColor(colors.HexColor('#FFFFFF18'))
            c.circle(cw * 0.85, ch * 0.75, 80, fill=1, stroke=0)
            c.circle(cw * 0.12, ch * 0.85, 50, fill=1, stroke=0)
            
            c.setFillColor(NAVY)
            c.rect(0, 0, cw, ch * 0.42, fill=1, stroke=0)
            c.setFillColor(TEAL_LIGHT)
            c.rect(0.1*cw, ch*0.42, 0.8*cw, 3, fill=1, stroke=0)

            c.setFillColor(WHITE)
            c.setFont('ThaiBold', 26)
            c.drawCentredString(cw*0.5, ch*0.70, 'คู่มือการใช้งานอย่างละเอียด')
            c.setFont('ThaiBold', 32)
            c.setFillColor(colors.HexColor('#7DD8D0'))
            c.drawCentredString(cw*0.5, ch*0.62, 'ai_web_scrpping')

            c.setFont('Thai', 12)
            c.setFillColor(colors.HexColor('#D5E8F0'))
            c.drawCentredString(cw*0.5, ch*0.54, 'ระบบรวบรวมและวิเคราะห์ข้อมูลเชิงพื้นที่ (Location Intelligence)')
            c.drawCentredString(cw*0.5, ch*0.50, 'ข้อมูลจุดสำคัญ โครงข่ายถนน และบริบทแวดล้อม')

            c.setFont('Thai', 9)
            c.setFillColor(colors.HexColor('#8AABBB'))
            c.drawCentredString(cw*0.5, ch*0.24, 'Python Data Pipeline  •  Playwright  •  OSM  •  Google Maps')

    elements.append(CoverCanvas())
    elements.append(PageBreak())
    return elements

# ─── TABLE OF CONTENTS ────────────────────────────────────────────────────────
def build_toc():
    elements = []
    class TocCanvas(Flowable):
        def wrap(self, aw, ah):
            return (aw, 14*mm)
        def draw(self):
            c = self.canv
            c.setFillColor(NAVY)
            c.rect(0, 0, self.width, 14*mm, fill=1, stroke=0)
            c.setFillColor(TEAL_LIGHT)
            c.rect(0, 0, 5, 14*mm, fill=1, stroke=0)
            c.setFont('ThaiBold', 16)
            c.setFillColor(WHITE)
            c.drawString(16, 4.5*mm, 'สารบัญ')

    elements.append(TocCanvas())
    elements.append(vspace(12))

    chapters = [
        ('1', 'ภาพรวมโปรเจกต์', ''),
        ('2', 'โครงสร้างโฟลเดอร์', ''),
        ('3', 'สิ่งที่ต้องเตรียมก่อนใช้งาน', ''),
        ('4', 'วิธีรัน Pipeline หลัก (main.py)', ''),
        ('5', 'คำสั่งย่อยที่ใช้งานบ่อย', ''),
        ('6', 'Data Flow และสถาปัตยกรรมระบบ', ''),
        ('7', 'Output และ Data Contract', ''),
        ('8', 'Quality Gate', ''),
        ('9', 'Troubleshooting', ''),
        ('10', 'Best Practices', ''),
        ('11', 'ภาคผนวก', ''),
    ]

    for num, title, page in chapters:
        row = Table([[
            Paragraph(f'บทที่ {num}', ParagraphStyle('toc_n', fontName='ThaiBold', fontSize=10, textColor=TEAL, leading=15)),
            Paragraph(title, ParagraphStyle('toc_t', fontName='Thai', fontSize=10.5, textColor=NAVY, leading=15)),
            Paragraph(page, ParagraphStyle('toc_p', fontName='Thai', fontSize=10, textColor=GRAY_MID, leading=15, alignment=TA_RIGHT)),
        ]], colWidths=[60, None, 30])
        row.setStyle(TableStyle([
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('TOPPADDING', (0,0),(-1,-1), 5),
            ('LINEBELOW', (0,0), (-1,-1), 0.3, GRAY_RULE),
        ]))
        elements.append(row)

    elements.append(PageBreak())
    return elements

# ─── CHAPTERS ─────────────────────────────────────────────────────────────────
def chapter_header(num, title):
    el = []
    el.append(Paragraph(f'บทที่ {num}', ParagraphStyle('ch_tag', fontName='ThaiBold', fontSize=10, textColor=TEAL_LIGHT, leading=14)))
    el.append(Paragraph(title, ST['h1']))
    el.append(hline(TEAL, 1.5, 0, 10))
    return el

def ch1():
    el = chapter_header(1, 'ภาพรวมโปรเจกต์')
    el.append(Paragraph('โปรเจกต์ ai_web_scrpping เป็นระบบ Data Pipeline อัตโนมัติสำหรับการรวบรวมข้อมูลเชิงพื้นที่ (Location Intelligence) เพื่อวิเคราะห์ศักยภาพของพื้นที่ต่างๆ ในประเทศไทย โดยดึงข้อมูลจากหลายแหล่ง เช่น OpenStreetMap, Google Maps และข้อมูลภาครัฐ', ST['body']))
    el.append(Paragraph('เป้าหมายหลักคือการสร้างชุดข้อมูลมาตรฐานที่สะอาด (Canonical Outputs) เช่น ตำแหน่งสถานที่สำคัญ (Landmarks), สิ่งอำนวยความสะดวก (Amenities) และโครงข่ายเส้นทางจราจร (Road Networks) ที่พร้อมใช้งานสำหรับงาน BI หรือนำไปวิเคราะห์ต่อ', ST['body']))
    return el

def ch2():
    el = chapter_header(2, 'โครงสร้างโฟลเดอร์')
    el.append(code_block([
        'ai_web_scrpping/',
        '├── data/ ',
        '│   ├── raw/          # ข้อมูลดิบที่ Scraper ดึงมา (มักเป็น JSON)',
        '│   └── processed/    # ข้อมูลที่ Clean แล้ว พร้อมใช้งาน (มักเป็น CSV)',
        '├── scrapers/         # Script สำหรับดึงข้อมูลจากแหล่งต่างๆ (OSM, DOPA, Google)',
        '├── utils/            # Logic วิเคราะห์ข้อมูล, ทำความสะอาด และ Quality Gate',
        '├── docs/             # เอกสารคู่มือและการตั้งค่า',
        '├── main.py           # Entry point หลัก (Full Pipeline)',
        '└── run_*.py          # สคริปต์แยกสำหรับรันเฉพาะเรื่อง เช่น ถนน หรือ landmark'
    ]))
    el.append(vspace(6))
    el.append(callout('tip', 'กฎเหล็ก', ['อย่ารันไฟล์ใน scrapers/ หรือ utils/ โดยตรง ให้ใช้ entrypoint ที่ root (ไฟล์ run_*.py) เพื่อป้องกันปัญหา Path หาย']))
    return el

def ch3():
    el = chapter_header(3, 'สิ่งที่ต้องเตรียมก่อนใช้งาน')
    el.append(Paragraph('1. **Python Environment**: ใช้ Python 3.13 ขึ้นไป และรันใน Virtual Environment (venv)', ST['body']))
    el.append(Paragraph('2. **ติดตั้ง Playwright**: สำหรับให้บอทเปิดหน้าเว็บเบราว์เซอร์', ST['body']))
    el.append(code_block(['python -m playwright install chromium']))
    el.append(Paragraph('3. **ตั้งค่า .env**: ต้องมีไฟล์ .env ที่โฟลเดอร์หลัก ระบุ Key ดังนี้:', ST['body']))
    el.append(code_block(['BOT_API_KEY=your_key_here']))
    el.append(Paragraph('ถ้าต้องการใช้งานอัปโหลด S3 ต้องตรวจสอบและแก้ชื่อ Bucket ในโค้ดด้วย', ST['body']))
    el.append(PageBreak())
    return el

def ch4():
    el = chapter_header(4, 'วิธีรัน Pipeline หลัก (main.py)')
    el.append(Paragraph('ไฟล์ main.py คือศูนย์รวมคำสั่ง สามารถรันเพื่ออัปเดตข้อมูลทั้งหมดได้ในคราวเดียว', ST['body']))
    el.append(code_block(['python main.py']))
    el.append(Paragraph('ระบบจะแสดงเมนูหลัก (Interactive Menu):', ST['body']))
    el.append(code_block([
        '[1] รันทุกอย่าง (Full Pipeline)',
        '[2] ดึงเฉพาะ Landmarks (OSM + Google Maps Sync)',
        '[3] ดึงเฉพาะ Restaurants',
        '[4] เลือกเองทีละรายการ (Custom)'
    ]))
    el.append(Paragraph('การทำงานของ Full Pipeline ครอบคลุมถึง:', ST['body']))
    el.append(bullet_item('ดึงข้อมูลสินเชื่อธนาคาร'))
    el.append(bullet_item('ดึงสถานที่สำคัญและเติมเต็มด้วย Google Maps'))
    el.append(bullet_item('ตรวจสอบความสมบูรณ์ (Quality Gate) และบันทึกลงโฟลเดอร์ processed/'))
    return el

def ch5():
    el = chapter_header(5, 'คำสั่งย่อยที่ใช้งานบ่อย')
    el.append(Paragraph('ถ้าต้องการอัปเดตข้อมูลบางประเภท สามารถใช้สคริปต์แยก (Modular Scripts) ได้เลย:', ST['body']))
    el.append(bullet_item('<b>python run_landmarks_only.py</b>: โหลดเฉพาะ Landmarks สำคัญในเขตจังหวัดเป้าหมาย'))
    el.append(bullet_item('<b>python run_roads_only.py</b>: โหลดและวิเคราะห์โครงข่ายถนน (Road Network) จาก OSM'))
    el.append(bullet_item('<b>python run_restaurants_only.py</b>: ดึงเฉพาะร้านอาหาร'))
    el.append(bullet_item('<b>python run_property_road_access.py</b>: คำนวณระยะการเชื่อมต่อของที่ดิน/อสังหาฯ ออกสู่ถนนสายหลัก'))
    el.append(bullet_item('<b>python run_google_road_enrichment.py</b>: ดึงชื่อถนนจาก Google มาเติมเต็ม OSM'))
    el.append(PageBreak())
    return el

def ch6():
    el = chapter_header(6, 'Data Flow และสถาปัตยกรรมระบบ')
    el.append(Paragraph('1. <b>Ingestion (รวบรวม)</b>: Scraper ดึงข้อมูลจาก OSM, ทศท. และ Google Maps แล้วเก็บใน data/raw/ (สกุล .json)', ST['body']))
    el.append(Paragraph('2. <b>Processing (ประมวลผลและคลีน)</b>: Utils นำ JSON มาลบรายการซ้ำ, เติมข้อมูลให้เต็ม, และฟอร์แมตใหม่', ST['body']))
    el.append(Paragraph('3. <b>Enrichment (เสริมข้อมูล)</b>: ในส่วนของสถานที่และถนน จะใช้ Playwright ยิงไปหา Google Maps เพื่อเอาชื่อจริง พิกัดจริง และเรตติ้ง', ST['body']))
    el.append(Paragraph('4. <b>Export (ส่งออก)</b>: สร้างเป็นไฟล์ CSV ลงใน data/processed/ เพื่อให้นำไปทำ Report ได้ง่าย', ST['body']))
    return el

def ch7():
    el = chapter_header(7, 'Output และ Data Contract')
    el.append(Paragraph('ข้อมูลที่พร้อมนำไปใช้งานจริง (Canonical Outputs) ในโฟลเดอร์ data/processed/ ได้แก่:', ST['body']))
    el.append(Paragraph('<b>1. landmarks_clean.csv</b>', ST['h2']))
    el.append(bullet_item('คอลัมน์สำคัญ: province, name, category, layer, lat, lon'))
    el.append(Paragraph('<b>2. roads_final.csv</b>', ST['h2']))
    el.append(bullet_item('คอลัมน์สำคัญ: road_name, road_display_name, highway_type, length_km'))
    el.append(Paragraph('<b>3. bank_loans_clean.csv</b>', ST['h2']))
    el.append(bullet_item('คอลัมน์สำคัญ: bank_name, interest_rate, updated_at'))
    el.append(vspace(6))
    el.append(callout('note', 'คำแนะนำ', ['ไม่ควรหยิบไฟล์ใน data/raw/ ไปใช้วิเคราะห์ เนื่องจากข้อมูลยังไม่เสถียรและอาจซ้ำซ้อน']))
    el.append(PageBreak())
    return el

def ch8():
    el = chapter_header(8, 'Quality Gate')
    el.append(Paragraph('Quality Gate เป็นขั้นตอนตรวจสอบว่าการดึงและแปลงข้อมูลสมบูรณ์หรือไม่ ทำงานอยู่ใน utils/pipeline_quality.py', ST['body']))
    el.append(Paragraph('สิ่งที่ตรวจสอบ:', ST['body']))
    el.append(bullet_item('ข้อมูลสถานที่ (Landmarks) ต้องมีครบตามจังหวัดเป้าหมาย'))
    el.append(bullet_item('ไฟล์ Output ที่จำเป็นต้องถูกสร้างอย่างถูกต้อง ไม่ใช่ไฟล์ว่าง'))
    el.append(Paragraph('หากไม่ผ่าน Quality Gate ระบบจะแจ้ง Error เพื่อป้องกันการเอาข้อมูลขยะไปใช้งาน', ST['body']))
    return el

def ch9():
    el = chapter_header(9, 'Troubleshooting')
    el.append(Paragraph('ปัญหาที่พบบ่อยและวิธีแก้:', ST['body']))
    el.append(Paragraph('<b>1. เปิดเบราว์เซอร์ไม่ได้ (Playwright Error)</b>', ST['h4']))
    el.append(Paragraph('ให้รัน `python -m playwright install chromium` เพื่อติดตั้งเบราว์เซอร์ใหม่', ST['body']))
    el.append(Paragraph('<b>2. หาไฟล์ data/raw/... ไม่เจอ</b>', ST['h4']))
    el.append(Paragraph('ตรวจสอบว่ารันสคริปต์จากตำแหน่ง C:\\ai_web_scrpping (Root) หรือไม่ หากรันจากในโฟลเดอร์ย่อยจะหาไฟล์ไม่เจอ', ST['body']))
    el.append(Paragraph('<b>3. ได้ข้อมูลน้อยผิดปกติ</b>', ST['h4']))
    el.append(Paragraph('อาจติด Limit ของ API แนะนำให้รอสักพัก หรือใช้ฟีเจอร์ Cache (ไม่ต้องดึงใหม่ทั้งหมด)', ST['body']))
    el.append(PageBreak())
    return el

def ch10():
    el = chapter_header(10, 'Best Practices')
    el.append(bullet_item('<b>จัดการ Cache อย่างระมัดระวัง</b>: ไฟล์เช่น geocode_cache.json ช่วยให้ไม่ต้องยิง Google บ่อยๆ หากพบข้อมูลไม่อัปเดต ค่อยพิจารณาลบ'))
    el.append(bullet_item('<b>ใช้ road_display_name เสมอ</b>: เวลาใช้งานข้อมูลถนน ให้ใช้คอลัมน์นี้แทน road_name เพียวๆ เพื่อป้องกันชื่อติด Tag ที่อ่านไม่รู้เรื่อง'))
    el.append(bullet_item('<b>ระวังการ Push ไฟล์ Data</b>: คอยเช็ก .gitignore เพื่อไม่ให้ดันไฟล์ CSV/JSON หนักๆ ขึ้น Git Repository'))
    return el

def ch11():
    el = chapter_header(11, 'ภาคผนวก')
    el.append(Paragraph('<b>การจัดเรียงความสำคัญของถนน (Highway Type Priority)</b>', ST['h4']))
    el.append(Paragraph('ตามโครงสร้าง OpenStreetMap โปรเจกต์จัดลำดับความสำคัญของถนน (Major Priority) โดยตัวเลขน้อยหมายถึงมีความสำคัญสูงสุดในการใช้หาทางเชื่อมต่อออกถนนใหญ่:', ST['body']))
    el.append(bullet_item('0: trunk (ทางหลวงสายประธาน)'))
    el.append(bullet_item('1: primary (ทางหลวงสายหลัก)'))
    el.append(bullet_item('2: secondary (ทางหลวงสายรอง)'))
    el.append(bullet_item('3: tertiary (ทางหลวงท้องถิ่น)'))
    el.append(Paragraph('*หมายเหตุ: motorway จะจัดเป็น Major เช่นกัน แต่ด้วยธรรมชาติของมอเตอร์เวย์มักจะเข้าถึงจากอสังหาฯ ตรงๆ ไม่ได้ จึงมีการแยกวิเคราะห์*', ST['body']))
    return el

def build_pdf(output_path):
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.4*cm, bottomMargin=2.0*cm,
        title='คู่มือการใช้งาน ai_web_scrpping',
    )
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    cover_template = PageTemplate(id='cover', frames=[cover_frame])
    content_frame = Frame(2.5*cm, 1.6*cm, PAGE_W - 5*cm, PAGE_H - 4.2*cm, leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=4)
    content_template = PageTemplate(id='content', frames=[content_frame], onPage=_header_footer)
    doc.addPageTemplates([cover_template, content_template])

    story = []
    story += build_cover()
    
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate('content'))
    
    story += build_toc()
    story += ch1()
    story += ch2()
    story += ch3()
    story += ch4()
    story += ch5()
    story += ch6()
    story += ch7()
    story += ch8()
    story += ch9()
    story += ch10()
    story += ch11()

    doc.build(story)
    print(f"PDF generated: {output_path}")

if __name__ == '__main__':
    output_file = os.path.join(os.path.dirname(__file__), 'ai_web_scrpping_COMPREHENSIVE_MANUAL.pdf')
    build_pdf(output_file)
