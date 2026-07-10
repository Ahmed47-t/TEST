"""
app.py — واجهة ويب لمحاسب DZ الذكي
====================================
Flask app بواجهة عربية RTL أنيقة:
  • رفع صورة فاتورة (drag & drop)
  • تحليل بـ Gemini Vision (Multi-provider fallback)
  • عرض الحقول المستخرجة + التحقّق الحسابي
  • تصدير JSON

Run:
    python app.py     →  http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from ai_analyzer import DEFAULT_MODELS, InvoiceAnalyzer

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

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def _no_cache(response):
    """يمنع المتصفح من تخزين الملفّات (يتفادى مشاكل التحديث)."""
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
    })


# ---------------------------------------------------------
# API: التحليل
# ---------------------------------------------------------
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    print(f"\n📥 [POST /api/analyze] استقبال طلب...", flush=True)

    if not GEMINI_API_KEY:
        return jsonify({
            "success": False,
            "error": (
                "GEMINI_API_KEY غير مضبوط. أنشئ ملف .env يحتوي:\n"
                "  GEMINI_API_KEY=مفتاحك_هنا\n"
                "احصل على المفتاح مجاناً: https://aistudio.google.com/app/apikey"
            ),
        }), 500

    if "file" not in request.files:
        return jsonify({"success": False, "error": "لم يُرسل أي ملف."}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"success": False, "error": "اسم الملف فارغ."}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return jsonify({
            "success": False,
            "error": f"صيغة غير مدعومة. المسموح: {', '.join(sorted(ALLOWED_EXT))}",
        }), 400

    # حفظ الصورة بمعرّف فريد
    uid = uuid.uuid4().hex[:12]
    src_name = f"{uid}{ext}"
    src_path = UPLOAD_DIR / src_name
    f.save(src_path)
    print(f"💾 حُفظت الصورة: {src_path.name} ({src_path.stat().st_size // 1024} KB)", flush=True)

    try:
        analyzer = get_analyzer()
        result = analyzer.analyze(str(src_path))

        payload = {
            "success": result.success,
            "source_image": f"/static/uploads/{src_name}",
            "data": result.data,
            "error": result.error,
            "model_used": result.model_used,
            "model_label": result.model_label,
            "elapsed_seconds": round(result.elapsed_seconds, 2),
            "validation": result.validation,
            "attempts": result.attempts,
        }

        # حفظ نسخة JSON للتحميل لاحقاً
        with open(RESULT_DIR / f"{uid}_result.json", "w", encoding="utf-8") as out:
            json.dump(payload, out, ensure_ascii=False, indent=2)

        status = 200 if result.success else 500
        return jsonify(payload), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"{type(e).__name__}: {e}",
        }), 500


# ---------------------------------------------------------
# التشغيل
# ---------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("🚀  محاسب DZ الذكي - Gemini Vision Invoice Analyzer")
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
        print(f"📊 النماذج المتاحة (بترتيب الأولوية):")
        for i, m in enumerate(DEFAULT_MODELS, 1):
            print(f"   {i}. {m['label']} — {m['accuracy']} — {m['free_tier']}")

    print("\n" + "=" * 60)
    print("🌐 الواجهة تعمل على: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
