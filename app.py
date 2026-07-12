"""
app.py — واجهة ويب لمحاسب DZ الذكي (v4 - Multi-Company)
============================================================
Flask app بواجهة عربية RTL أنيقة:
  • إدارة الشركات (Multi-tenant مثل PC Compta)
  • رفع صورة واحدة أو عدّة صور (batch)
  • دعم أنواع وثائق متعدّدة
  • تحليل ذكي + تصنيف SCF تلقائي + قيود يومية جاهزة
  • دفتر يومية مستقل لكل شركة

Run:  python app.py     →  http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

from ai_analyzer import DEFAULT_MODELS, InvoiceAnalyzer
from document_types import DOCUMENT_TYPES
import companies as companies_mgr

# ---------------------------------------------------------
# تحميل متغيّرات البيئة
# ---------------------------------------------------------
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# ---------------------------------------------------------
# إعداد Flask
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
MAX_MB = 10
MAX_BATCH = 20

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
# محلّل ذكي (يُنشأ مرّة واحدة)
# ---------------------------------------------------------
_analyzer: InvoiceAnalyzer | None = None


def get_analyzer() -> InvoiceAnalyzer | None:
    global _analyzer
    if _analyzer is None and API_KEY:
        _analyzer = InvoiceAnalyzer(api_key=API_KEY)
    return _analyzer


# ---------------------------------------------------------
# الصفحة الرئيسية
# ---------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        has_api_key=bool(API_KEY),
        doc_types=list(DOCUMENT_TYPES.values()),
        max_batch=MAX_BATCH,
    )


# ---------------------------------------------------------
# API: صحّة
# ---------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "has_api_key": bool(API_KEY),
        "doc_types": len(DOCUMENT_TYPES),
        "max_batch": MAX_BATCH,
        "companies_count": len(companies_mgr.list_companies()),
    })


# =========================================================
# API: إدارة الشركات
# =========================================================
@app.route("/api/companies", methods=["GET"])
def api_list_companies():
    return jsonify({
        "success": True,
        "companies": companies_mgr.list_companies(),
    })


@app.route("/api/companies", methods=["POST"])
def api_create_company():
    try:
        payload = request.get_json() or {}
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "اسم الشركة مطلوب"}), 400

        company = companies_mgr.create_company(
            name=name,
            activity=payload.get("activity", ""),
            nif=payload.get("nif", ""),
            rc=payload.get("rc", ""),
            nis=payload.get("nis", ""),
            ai=payload.get("ai", ""),
            address=payload.get("address", ""),
            phone=payload.get("phone", ""),
            email=payload.get("email", ""),
            logo_color=payload.get("logo_color", "#2563eb"),
        )
        return jsonify({"success": True, "company": company}), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/companies/<company_id>", methods=["GET"])
def api_get_company(company_id):
    company = companies_mgr.get_company(company_id)
    if not company:
        return jsonify({"success": False, "error": "شركة غير موجودة"}), 404
    return jsonify({"success": True, "company": company})


@app.route("/api/companies/<company_id>", methods=["PUT", "PATCH"])
def api_update_company(company_id):
    updates = request.get_json() or {}
    updated = companies_mgr.update_company(company_id, updates)
    if not updated:
        return jsonify({"success": False, "error": "شركة غير موجودة"}), 404
    return jsonify({"success": True, "company": updated})


@app.route("/api/companies/<company_id>", methods=["DELETE"])
def api_delete_company(company_id):
    delete_data = request.args.get("delete_data", "0") in ("1", "true", "yes")
    ok = companies_mgr.delete_company(company_id, delete_data=delete_data)
    if not ok:
        return jsonify({"success": False, "error": "شركة غير موجودة"}), 404
    return jsonify({"success": True, "deleted_data": delete_data})


@app.route("/api/companies/<company_id>/select", methods=["POST"])
def api_select_company(company_id):
    """يُحدّث last_used_at (يُستدعى عند دخول شركة)."""
    company = companies_mgr.get_company(company_id)
    if not company:
        return jsonify({"success": False, "error": "شركة غير موجودة"}), 404
    companies_mgr.touch_company(company_id)
    return jsonify({"success": True, "company": company})


# =========================================================
# API: دفتر يومية الشركة (المتراكم)
# =========================================================
@app.route("/api/companies/<company_id>/journal", methods=["GET"])
def api_company_journal(company_id):
    company = companies_mgr.get_company(company_id)
    if not company:
        return jsonify({"success": False, "error": "شركة غير موجودة"}), 404

    entries = companies_mgr.get_company_journal(company_id)
    # حساب الإجمالي الكلّي
    grand_debit = sum(e.get("total_debit") or 0 for e in entries)
    grand_credit = sum(e.get("total_credit") or 0 for e in entries)

    return jsonify({
        "success": True,
        "company": company,
        "entries": entries,
        "totals": {
            "count": len(entries),
            "grand_debit": round(grand_debit, 2),
            "grand_credit": round(grand_credit, 2),
        },
    })


# =========================================================
# خدمة صور الشركات (خارج static/)
# =========================================================
@app.route("/company_files/<company_id>/uploads/<filename>")
def serve_company_upload(company_id, filename):
    paths = companies_mgr.get_company_paths(company_id)
    return send_from_directory(paths["uploads"], filename)


# =========================================================
# API: تحليل دفعة وثائق لشركة معيّنة
# =========================================================
@app.route("/api/companies/<company_id>/analyze", methods=["POST"])
def api_analyze_for_company(company_id):
    """تحليل دفعة وثائق لشركة معيّنة."""

    if not API_KEY:
        return jsonify({
            "success": False,
            "error": "المفتاح غير مضبوط. الرجاء إعداد ملف .env",
        }), 500

    company = companies_mgr.get_company(company_id)
    if not company:
        return jsonify({"success": False, "error": "شركة غير موجودة"}), 404

    files = request.files.getlist("files")
    if not files or all(not f.filename for f in files):
        return jsonify({"success": False, "error": "لم يُرسل أي ملف."}), 400

    if len(files) > MAX_BATCH:
        return jsonify({
            "success": False,
            "error": f"الحد الأقصى {MAX_BATCH} ملف/دفعة. لديك {len(files)}.",
        }), 400

    paths = companies_mgr.get_company_paths(company_id)
    paths["uploads"].mkdir(parents=True, exist_ok=True)
    paths["results"].mkdir(parents=True, exist_ok=True)

    analyzer = get_analyzer()
    results: List[Dict[str, Any]] = []
    batch_id = uuid.uuid4().hex[:8]

    print(f"\n{'#'*60}", flush=True)
    print(f"# 🏢 الشركة: {company['name']}", flush=True)
    print(f"# 📦 دفعة {batch_id}: {len(files)} ملف", flush=True)
    print(f"{'#'*60}", flush=True)

    for idx, f in enumerate(files, 1):
        if not f.filename:
            continue

        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            results.append({
                "success": False,
                "index": idx,
                "original_filename": f.filename,
                "error": f"صيغة غير مدعومة: {ext}",
            })
            continue

        uid = f"{batch_id}_{idx:02d}_{uuid.uuid4().hex[:6]}"
        src_name = f"{uid}{ext}"
        src_path = paths["uploads"] / src_name
        f.save(src_path)

        print(f"\n[{idx}/{len(files)}] 💾 {src_name} "
              f"({src_path.stat().st_size // 1024} KB) ← {f.filename}", flush=True)

        try:
            result = analyzer.analyze(str(src_path))
            item_result = {
                "success": result.success,
                "index": idx,
                "original_filename": f.filename,
                "source_image": f"/company_files/{company_id}/uploads/{src_name}",
                "data": result.data,
                "error": result.error,
                "elapsed_seconds": round(result.elapsed_seconds, 2),
                "validation": result.validation,
                # ملاحظة: لا نُرسل model_used/model_label للواجهة
                # (نُخفي تفاصيل مزوّد الـ AI عن المستخدم)
            }
            results.append(item_result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append({
                "success": False,
                "index": idx,
                "original_filename": f.filename,
                "source_image": f"/company_files/{company_id}/uploads/{src_name}",
                "error": f"{type(e).__name__}: {e}",
            })

    # بناء الملخّص
    batch_summary = _build_batch_summary(batch_id, results, company)

    # حفظ نتيجة الدفعة في مجلد الشركة
    with open(paths["results"] / f"{batch_id}_batch.json", "w", encoding="utf-8") as out:
        json.dump(batch_summary, out, ensure_ascii=False, indent=2)

    # حفظ في دفتر اليومية المتراكم للشركة
    companies_mgr.append_to_company_journal(company_id, batch_summary)

    print(f"\n{'#'*60}", flush=True)
    print(f"# ✅ اكتملت الدفعة {batch_id}: "
          f"{batch_summary['stats']['success']}/{batch_summary['stats']['total']}", flush=True)
    print(f"{'#'*60}\n", flush=True)

    status = 200 if batch_summary["stats"]["success"] > 0 else 500
    return jsonify(batch_summary), status


def _build_batch_summary(batch_id: str, results: List[Dict[str, Any]],
                         company: Dict[str, Any]) -> Dict[str, Any]:
    """يبني ملخّص الدفعة + دفتر اليومية المُوحَّد للدفعة."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    by_type: Dict[str, int] = {}
    total_ht = total_tva = total_ttc = 0.0
    consolidated_journal: List[Dict[str, Any]] = []

    for r in successful:
        data = r.get("data") or {}
        doc_type = data.get("document_type") or "unknown"
        by_type[doc_type] = by_type.get(doc_type, 0) + 1

        totals = data.get("totals") or {}
        total_ht  += float(totals.get("total_ht")  or 0)
        total_tva += float(totals.get("tva_amount") or 0)
        total_ttc += float(totals.get("total_ttc") or 0)

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
        "company_id": company["id"],
        "company_name": company["name"],
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
    print("🚀  محاسب DZ الذكي v4 - Multi-Company Accounting AI")
    print("=" * 60)

    if not API_KEY:
        print("\n⚠️  تحذير: مفتاح الـ AI غير مضبوط!")
        print("   أنشئ ملف .env في مجلد المشروع بالمحتوى:")
        print("      GEMINI_API_KEY=مفتاحك_هنا\n")
    else:
        print(f"\n✅ مفتاح AI محمّل ({len(API_KEY)} حرف)")
        print(f"📄 أنواع الوثائق المدعومة: {len(DOCUMENT_TYPES)}")
        print(f"🏢 الشركات المسجّلة: {len(companies_mgr.list_companies())}")
        print(f"📦 حد أقصى للدفعة: {MAX_BATCH} ملف")

    print("\n" + "=" * 60)
    print("🌐 الواجهة تعمل على: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
