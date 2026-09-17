"""Reproducible extraction from the user-supplied official source files.
No approximate logos. Text/contained sample-logo paths only are removed from covers.
"""
from pathlib import Path
import hashlib
import json
import shutil
import pymupdf

ROOT = Path(__file__).resolve().parents[1] / 'app/templates/infath/assets'
SOURCE = Path('/Users/mohammad/Downloads')
ROOT.mkdir(parents=True, exist_ok=True)
manifest = {}
for n in range(1,7):
    source = SOURCE / f'اغلفة-الكتيف/Ai/{n}.ai'
    doc = pymupdf.open(source)
    p = doc[0]
    # Remove the sample auction title, date, auction mark and selling-agent mark.
    # Do not erase the background image or large background vector shapes.
    title = (175,350,390,453) if n in (2,3) else (290,350,500,453) if n in (4,5) else (360,730,570,819)
    footer = (18,775,577,823)
    for box in (title,footer): p.add_redact_annot(box,fill=False)
    p.apply_redactions(images=0,graphics=1,text=0)
    p.get_pixmap(matrix=pymupdf.Matrix(2,2)).save(ROOT / f'cover-{n}.png')
    p.get_pixmap(matrix=pymupdf.Matrix(.45,.45)).save(ROOT / f'thumb-{n}.png')
    manifest[f'cover-{n}']={'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'removed_dynamic_regions':[title,footer]}
pymupdf.open(SOURCE/'اغلفة-الكتيف/Ai/2.ai')[0].get_pixmap(matrix=pymupdf.Matrix(4,4),clip=pymupdf.Rect(488,22,577,85),alpha=True).save(ROOT/'infath-white.png')
book = pymupdf.open(SOURCE/'كتيب-حضوري-الكتروني-مفتوح.pdf')
book[1].get_pixmap(matrix=pymupdf.Matrix(2,2)).save(ROOT/'introduction.png')
# Extract the actual Infath vector mark, retaining its exact appearance.
book[18].get_pixmap(matrix=pymupdf.Matrix(4,4),clip=pymupdf.Rect(525,770,595,824),alpha=True).save(ROOT/'infath-logo.png')
guide = pymupdf.open(SOURCE/'دليل-التسويق-والهوية-البصرية-للمزادات-V2.pdf')
# Immutable terms, one distinct variant per auction type (guide page 24).
for kind,box in [('physical',(111,222,251,390)),('hybrid',(331,214,464,411)),('electronic',(525,234,670,400))]:
    guide[23].get_pixmap(matrix=pymupdf.Matrix(5,5),clip=pymupdf.Rect(box)).save(ROOT/f'terms-{kind}.png')
for name in ['LamaSans-Bold.otf','LamaSans-Light.otf','LamaSans-Medium.otf','LamaSans-Regular.otf','RuaqArabic-Bold.ttf','RuaqArabic-Light.ttf','RuaqArabic-Medium.ttf']:
    shutil.copyfile(SOURCE/'خطوط-انفاذ'/name,ROOT/name)
manifest['fixed']={'introduction':'supplied booklet page 2, unchanged','terms':'guide page 24; immutable crops by auction type','font':'guide page 9: Ruaq Arabic','logos':'original artwork only'}
(ROOT/'provenance.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
