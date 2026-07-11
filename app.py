"""
app.py — واجهة ويب لمحاسب DZ الذكي (v3 - Multi-document)
============================================================
Flask app بواجهة عربية RTL أنيقة:
  • رفع صورة واحدة أو عدّة صور (batch)
  • دعم أنواع وثائق متعدّدة (فاتورة، BL، BC، شيك، Avoir...)
  • تحليل بـ Gemini Vision (Multi-provider fallback)
  • تصنيف SCF تلقائي + قيد يومية جاهز
  • دفتر يومية مُوحَّد (Grand Livre) لعدّة وثائق

Run:  python app.py     →  http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from ai_analyzer import DEFAULT_MODELS, InvoiceAnalyzer
from document_types import DOCUMENT_TYPES

# ---------------------------------------------------------
# تحميل متغيّرات البيئة
# ---------------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# ---------------------------------------------------------
# إعداد Flask
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
RESULT_DIR = BASE_DIR / "static" / "results"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
MAX_MB = 10
MAX_BATCH = 20  # حد أقصى للصور في دفعة واحدة

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * MAX_BATCH * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def _no_cache(response):
    if request.path.startswith("/static/") or request.path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


# ---------------------------------------------------------
# محلّل عام (يُنشأ مرّة واحدة)
# ---------------------------------------------------------
_analyzer: InvoiceAnalyzer | None = None


def get_analyzer() -> InvoiceAnalyzer | None:
    global _analyzer
    if _analyzer is None and GEMINI_API_KEY:
        _analyzer = InvoiceAnalyzer(api_key=GEMINI_API_KEY)
    return _analyzer


# ---------------------------------------------------------
# الصفحة الرئيسية
# ---------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        has_api_key=bool(GEMINI_API_KEY),
        models=DEFAULT_MODELS,
        doc_types=list(DOCUMENT_TYPES.values()),
        max_batch=MAX_BATCH,
    )


# ---------------------------------------------------------
# API: فحص الصحّة
# ---------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "has_api_key": bool(GEMINI_API_KEY),
        "models": [m["label"] for m in DEFAULT_MODELS],
        "doc_types": len(DOCUMENT_TYPES),
        "max_batch": MAX_BATCH,
    })


# ---------------------------------------------------------
# API: تحليل وثيقة واحدة (backward compatibility)
# ---------------------------------------------------------
@app.route("/api/analyze", methods=["POST"])
def api_analyze_single():
    """تحليل وثيقة واحدة (متوافق مع النسخة السابقة)."""
    return _analyze_files(request.files.getlist("file"), single_mode=True)


# ---------------------------------------------------------
# API: تحليل دفعة من الوثائق (Multi-document batch)
# ---------------------------------------------------------
@app.route("/api/analyze_batch", methods=["POST"])
def api_analyze_batch():
    """تحليل عدّة وثائق دفعة واحدة."""
    files = request.files.getlist("files")
    return _analyze_files(files, single_mode=False)


# ---------------------------------------------------------
# منطق مشترك للتحليل
# ---------------------------------------------------------
def _analyze_files(files, single_mode: bool = True):
    """يحلّل ملفاً واحداً أو عدّة ملفات."""

    if not GEMINI_API_KEY:
        return jsonify({
            "success": False,
            "error": (
                "GEMINI_API_KEY غير مضبوط. أنشئ ملف .env يحتوي:\n"
                "  GEMINI_API_KEY=مفتاحك_هنا\n"
                "احصل على المفتاح مجاناً: https://aistudio.google.com/app/apikey"
            ),
        }), 500

    if not files or all(not f.filename for f in files):
        return jsonify({"success": False, "error": "لم يُرسل أي ملف."}), 400

    if len(files) > MAX_BATCH:
        return jsonify({
            "success": False,
            "error": f"الحد الأقصى {MAX_BATCH} ملف/دفعة. لديك {len(files)}.",
        }), 400

    analyzer = get_analyzer()
    results: List[Dict[str, Any]] = []
    batch_id = uuid.uuid4().hex[:8]

    print(f"\n{'#'*60}", flush=True)
    print(f"# 📦 دفعة {batch_id}: {len(files)} ملف", flush=True)
    print(f"{'#'*60}", flush=True)

    for idx, f in enumerate(files, 1):
        if not f.filename:
            continue

        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            results.append({
                "success": False,
                "original_filename": f.filename,
                "error": f"صيغة غير مدعومة: {ext}",
            })
            continue

        # حفظ الصورة
        uid = f"{batch_id}_{idx:02d}_{uuid.uuid4().hex[:6]}"
        src_name = f"{uid}{ext}"
        src_path = UPLOAD_DIR / src_name
        f.save(src_path)

        print(f"\n[{idx}/{len(files)}] 💾 {src_name} ({src_path.stat().st_size // 1024} KB) "
              f"← {f.filename}", flush=True)

        try:
            result = analyzer.analyze(str(src_path))
            item_result = {
                "success": result.success,
                "index": idx,
                "original_filename": f.filename,
                "source_image": f"/static/uploads/{src_name}",
                "data": result.data,
                "error": result.error,
                "model_used": result.model_used,
                "model_label": result.model_label,
                "elapsed_seconds": round(result.elapsed_seconds, 2),
                "validation": result.validation,
                "attempts": result.attempts,
            }
            results.append(item_result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append({
                "success": False,
                "index": idx,
                "original_filename": f.filename,
                "source_image": f"/static/uploads/{src_name}",
                "error": f"{type(e).__name__}: {e}",
            })

    # حفظ نسخة JSON للدفعة
    batch_summary = _build_batch_summary(batch_id, results)
    with open(RESULT_DIR / f"{batch_id}_batch.json", "w", encoding="utf-8") as out:
        json.dump(batch_summary, out, ensure_ascii=False, indent=2)

    print(f"\n{'#'*60}", flush=True)
    print(f"# ✅ اكتملت الدفعة {batch_id}: "
          f"{batch_summary['stats']['success']}/{batch_summary['stats']['total']} نجحت", flush=True)
    print(f"{'#'*60}\n", flush=True)

    # في single_mode نُعيد أول نتيجة فقط (للتوافق مع الواجهة القديمة)
    if single_mode and len(results) == 1:
        r = results[0]
        r["success"] = r.get("success", False)
        status = 200 if r["success"] else 500
        return jsonify(r), status

    # في batch_mode نُعيد كل النتائج مع ملخّص
    status = 200 if batch_summary["stats"]["success"] > 0 else 500
    return jsonify(batch_summary), status


def _build_batch_summary(batch_id: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """يبني ملخّص الدفعة + دفتر اليومية المُوحَّد."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    # إحصائيات حسب نوع الوثيقة
    by_type: Dict[str, int] = {}
    total_ht = 0.0
    total_tva = 0.0
    total_ttc = 0.0

    # دفتر اليومية المُوحَّد (كل القيود في مكان واحد)
    consolidated_journal: List[Dict[str, Any]] = []

    for r in successful:
        data = r.get("data") or {}
        doc_type = data.get("document_type") or "unknown"
        by_type[doc_type] = by_type.get(doc_type, 0) + 1

        totals = data.get("totals") or {}
        total_ht  += float(totals.get("total_ht")  or 0)
        total_tva += float(totals.get("tva_amount") or 0)
        total_ttc += float(totals.get("total_ttc") or 0)

        # أضف القيد للدفتر المُوحَّد
        je = data.get("journal_entry")
        if je and je.get("entries"):
            consolidated_journal.append({
                "document_index": r["index"],
                "document_filename": r["original_filename"],
                "document_type": doc_type,
                "journal_entry": je,
            })

    return {
        "batch_id": batch_id,
        "success": len(successful) > 0,
        "stats": {
            "total": len(results),
            "success": len(successful),
            "failed": len(failed),
            "by_document_type": by_type,
            "totals_sum": {
                "total_ht": round(total_ht, 2),
                "tva_amount": round(total_tva, 2),
                "total_ttc": round(total_ttc, 2),
            },
        },
        "results": results,
        "consolidated_journal": consolidated_journal,
    }


# ---------------------------------------------------------
# التشغيل
# ---------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("🚀  محاسب DZ الذكي v3 - Multi-document Gemini Analyzer")
    print("=" * 60)

    if not GEMINI_API_KEY:
        print("\n⚠️  تحذير: GEMINI_API_KEY غير موجود!")
        print("   1. احصل على مفتاح مجاناً من:")
        print("      https://aistudio.google.com/app/apikey")
        print("   2. أنشئ ملف .env في مجلد المشروع بالمحتوى:")
        print("      GEMINI_API_KEY=مفتاحك_هنا")
        print("   3. أعد تشغيل التطبيق.\n")
    else:
        print(f"\n✅ GEMINI_API_KEY محمّل ({len(GEMINI_API_KEY)} حرف)")
        print(f"📊 النماذج المتاحة ({len(DEFAULT_MODELS)}):")
        for i, m in enumerate(DEFAULT_MODELS, 1):
            print(f"   {i}. {m['label']} — {m['accuracy']}")
        print(f"📄 أنواع الوثائق المدعومة ({len(DOCUMENT_TYPES)}):")
        for code, info in DOCUMENT_TYPES.items():
            if info["generates_journal"]:
                print(f"   {info['icon']}  {code:<20} — {info['label_ar']}")
        print(f"📦 حد أقصى للدفعة: {MAX_BATCH} ملف")

    print("\n" + "=" * 60)
    print("🌐 الواجهة تعمل على: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
