"""
ai_analyzer.py
==============
محلّل الفواتير باستعمال Gemini Vision API (SDK الحديث google-genai).

استراتيجية Multi-provider (مُستوحاة من TaxHacker):
  1. المحاولة الأولى: Gemini 2.5 Pro (الأعلى دقة - 94%)
  2. Fallback أوّل:   Gemini 2.5 Flash (~90% سرعة عالية)
  3. Fallback ثانٍ:   Gemini 2.0 Flash (استقرار قصوى)

بعد الاستخراج: تحقّق حسابي تلقائي (TTC ≈ HT + TVA + Timbre).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types
from PIL import Image

from document_types import (
    DOCUMENT_TYPES,
    build_journal_entry as build_je_for_doc,
    get_doc_type,
)
from prompt_builder import SYSTEM_PROMPT, build_user_prompt
from schema import INVOICE_SCHEMA
from scf_accounts import (
    determine_tva_account,
    get_account_info,
    suggest_account_for_item,
)


# =========================================================
# إعدادات المزوّدين (Multi-provider fallback)
# ⚠️ ملاحظة داخلية: الأسماء الفنية للنماذج تبقى في الكود لأنّها
# مطلوبة للاستدعاء البرمجي، لكن لا يُعرَض أي منها للمستخدم في الواجهة.
# =========================================================
DEFAULT_MODELS = [
    {"name": "gemini-2.5-pro",        "label": "AI Model 1"},
    {"name": "gemini-2.5-flash",      "label": "AI Model 2"},
    {"name": "gemini-2.0-flash",      "label": "AI Model 3"},
    {"name": "gemini-flash-latest",   "label": "AI Model 4"},
    {"name": "gemini-2.0-flash-lite", "label": "AI Model 5"},
]


@dataclass
class AnalysisResult:
    """نتيجة التحليل مع بيانات وصفية عن المزوّد المستعمل."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    model_used: Optional[str] = None
    model_label: Optional[str] = None
    elapsed_seconds: float = 0.0
    validation: Dict[str, Any] = field(default_factory=dict)
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "model_used": self.model_used,
            "model_label": self.model_label,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "validation": self.validation,
            "attempts": self.attempts,
        }


class InvoiceAnalyzer:
    """
    محلّل الفواتير الجزائرية بالذكاء الاصطناعي.

    Usage:
        analyzer = InvoiceAnalyzer(api_key="...")
        result = analyzer.analyze("invoice.jpg")
        print(result.data)
    """

    def __init__(
        self,
        api_key: str,
        models: Optional[List[Dict[str, str]]] = None,
        timeout: int = 90,
    ) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY مطلوب. احصل عليه مجاناً من:\n"
                "  https://aistudio.google.com/app/apikey"
            )
        self.client = genai.Client(api_key=api_key)
        self.models = models or DEFAULT_MODELS
        self.timeout = timeout

    # ---------------------------------------------------------
    # تحضير الصورة
    # ---------------------------------------------------------
    @staticmethod
    def _prepare_image(image_path: str) -> Image.Image:
        """تحميل الصورة + تحسين خفيف للجودة."""
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"لم يتم العثور على الصورة: {image_path}")

        img = Image.open(image_path)

        # تحويل RGBA/P إلى RGB
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # تكبير الصور الصغيرة لجودة قراءة أفضل
        max_side = max(img.size)
        if max_side < 1024:
            scale = 1024.0 / max_side
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

        # تصغير الصور الضخمة لتوفير tokens
        if max_side > 3072:
            scale = 3072.0 / max_side
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

        return img

    # ---------------------------------------------------------
    # استدعاء نموذج واحد
    # ---------------------------------------------------------
    def _call_model(
        self, model_config: Dict[str, str], img: Image.Image
    ) -> Tuple[bool, Any]:
        """استدعاء نموذج Gemini واحد. يعيد (success, result_or_error)."""
        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,   # حتمي (مثل TaxHacker)
                response_mime_type="application/json",
                response_schema=INVOICE_SCHEMA,
            )

            response = self.client.models.generate_content(
                model=model_config["name"],
                contents=[build_user_prompt(), img],
                config=config,
            )

            if not response.text:
                return False, "استجابة فارغة من النموذج (قد تكون الصورة رُفضت لسبب أمني)"

            data = json.loads(response.text)
            return True, data

        except json.JSONDecodeError as e:
            return False, f"فشل تحليل JSON: {e}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    # ---------------------------------------------------------
    # إثراء SCF: يكمل التصنيف إن لم يعطِه Gemini + يبني قيد اليومية
    # ---------------------------------------------------------
    @staticmethod
    def _enrich_scf(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        يُثري البيانات بمعلومات SCF:
          1. يكمل scf_account لأي منتج ينقصه (fallback على الكلمات المفتاحية)
          2. يتحقّق من أن رقم الحساب موجود في مخطط SCF
          3. يبني قيد اليومية الجاهز (journal entry)
        """
        items = data.get("items") or []

        # 1) إكمال scf_account الناقص
        for item in items:
            code = item.get("scf_account")
            if not code:
                # جرّب استنتاج من الوصف
                suggested = suggest_account_for_item(item.get("description", ""))
                if suggested:
                    item["scf_account"] = suggested
                    info = get_account_info(suggested)
                    if info and not item.get("scf_account_name"):
                        item["scf_account_name"] = info["name_fr"]
                    if not item.get("category"):
                        item["category"] = info["name_ar"] if info else "أخرى"

            # تحقّق أن الحساب موجود، وإلا استعمل 607 (استهلاكيات) كافتراضي
            if code and not get_account_info(code):
                # الحساب المُعاد غير موجود في SCF — احتفظ به لكن أضف حساباً افتراضياً
                item["scf_account_original"] = code
                item["scf_account"] = "607"  # استهلاكيات
                item["scf_account_name"] = "Achats non stockés de matières et fournitures"

        # 2) بناء قيد اليومية حسب نوع الوثيقة
        doc_type_code = data.get("document_type") or "facture"
        doc_info = get_doc_type(doc_type_code)
        data["document_type_info"] = {
            "code": doc_info["code"],
            "label_ar": doc_info["label_ar"],
            "label_fr": doc_info["label_fr"],
            "icon": doc_info["icon"],
            "generates_journal": doc_info["generates_journal"],
        }

        if doc_info["generates_journal"]:
            journal_entry = build_je_for_doc(
                data, doc_type_code,
                get_account_info=get_account_info,
                determine_tva_account=determine_tva_account,
                suggest_account_for_item=suggest_account_for_item,
            )
            data["journal_entry"] = journal_entry
        else:
            data["journal_entry"] = None
            data["journal_note"] = (
                f"لا يوجد قيد محاسبي لهذا النوع ({doc_info['label_ar']}). "
                "هذه وثيقة إعلامية أو التزامية فقط."
            )

        return data

    # ---------------------------------------------------------
    # التحقّق الحسابي (منع الهلوسة)
    # ---------------------------------------------------------
    @staticmethod
    def _validate(data: Dict[str, Any]) -> Dict[str, Any]:
        """يتحقّق من اتساق الأرقام: TTC ≈ HT + TVA + Timbre."""
        checks: Dict[str, Any] = {"passed": True, "warnings": []}

        doc_type = (data.get("document_type") or "facture").lower()

        # التحقّق الحسابي ينطبق فقط على الفواتير
        if doc_type in ("facture", "facture_vente", "facture_avoir", "devis"):
            totals = data.get("totals") or {}
            ht = totals.get("total_ht")
            tva = totals.get("tva_amount") or 0
            timbre = totals.get("stamp_duty") or 0
            discount = totals.get("discount") or 0
            ttc = totals.get("total_ttc")

            if ht is not None and ttc is not None:
                try:
                    expected = float(ht) + float(tva) + float(timbre) - float(discount)
                    diff = abs(expected - float(ttc))
                    if diff > 1.0:
                        checks["passed"] = False
                        checks["warnings"].append(
                            f"⚠️ عدم اتساق حسابي: HT ({ht}) + TVA ({tva}) "
                            f"+ Timbre ({timbre}) − Discount ({discount}) = {expected:.2f}، "
                            f"لكن TTC المُستخرج = {ttc}. الفرق = {diff:.2f}"
                        )
                except (ValueError, TypeError):
                    pass

        # التحقّق من صيغة NIF (أرقام فقط)
        for party in ("supplier", "customer"):
            party_data = data.get(party) or {}
            nif = party_data.get("nif")
            if nif and not str(nif).replace(" ", "").replace("-", "").isdigit():
                checks["warnings"].append(
                    f"⚠️ {party}.nif يحتوي أحرف غير رقمية: '{nif}'"
                )

        return checks

    # ---------------------------------------------------------
    # الواجهة العامّة
    # ---------------------------------------------------------
    def analyze(self, image_path: str) -> AnalysisResult:
        """يُحلّل صورة فاتورة عبر سلسلة النماذج (fallback تلقائي)."""
        t_total = time.time()
        result = AnalysisResult(success=False)

        print(f"\n{'='*60}", flush=True)
        print(f"🔍 تحليل: {image_path}", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            img = self._prepare_image(image_path)
            print(f"🖼️  الصورة جاهزة ({img.width}×{img.height})", flush=True)
        except Exception as e:
            result.error = f"فشل تحضير الصورة: {e}"
            result.elapsed_seconds = time.time() - t_total
            return result

        # جرّب النماذج بالترتيب (بدون كشف أسمائها في السجل)
        for attempt_idx, model_config in enumerate(self.models, 1):
            model_name = model_config["name"]
            model_label = model_config["label"]

            print(f"\n🔎 المحاولة {attempt_idx}/{len(self.models)} ...", flush=True)
            t = time.time()
            success, output = self._call_model(model_config, img)
            elapsed = time.time() - t

            attempt = {
                "model": model_name,
                "label": model_label,
                "success": success,
                "elapsed_seconds": round(elapsed, 2),
            }

            if success:
                print(f"✅ نجحت المعالجة في {elapsed:.1f}s", flush=True)
                # إثراء بـ SCF + بناء قيد اليومية
                output = self._enrich_scf(output)
                result.success = True
                result.data = output
                result.model_used = model_name
                result.model_label = model_label
                result.validation = self._validate(output)
                attempt["result"] = "success"
                result.attempts.append(attempt)

                if result.validation.get("warnings"):
                    for w in result.validation["warnings"]:
                        print(f"   {w}", flush=True)
                else:
                    print(f"   ✔️ التحقّق الحسابي: نجح", flush=True)

                # طباعة نوع الوثيقة + قيد اليومية
                doc_info = output.get("document_type_info", {})
                if doc_info:
                    print(f"   📄 نوع الوثيقة: {doc_info.get('icon', '')} "
                          f"{doc_info.get('label_ar', '')}", flush=True)

                je = output.get("journal_entry") or {}
                if je.get("entries"):
                    print(f"   📒 قيد اليومية ({je.get('journal_type', '')}): "
                          f"{len(je['entries'])} سطر، "
                          f"{'متوازن ✓' if je.get('balanced') else 'غير متوازن ✗'}",
                          flush=True)
                elif output.get("journal_note"):
                    print(f"   ℹ️  {output['journal_note']}", flush=True)
                break
            else:
                # نُقصر رسالة الخطأ في السجل (لا نكشف اسم المزوّد)
                err_short = str(output)[:120]
                print(f"❌ فشلت المحاولة {attempt_idx} ({elapsed:.1f}s): {err_short}", flush=True)
                attempt["error"] = str(output)
                result.attempts.append(attempt)
                continue

        if not result.success:
            # حلّل نوع الخطأ الأكثر شيوعاً وأعطِ نصيحة للمستخدم
            # (بدون ذكر اسم مزوّد الـ AI)
            all_errors = " ".join(a.get("error", "") for a in result.attempts)

            if "RESOURCE_EXHAUSTED" in all_errors or "429" in all_errors:
                result.error = (
                    "🚫 تجاوزت الحصّة اليومية المجانية.\n\n"
                    "الحلول الممكنة:\n"
                    "1. انتظر 24 ساعة (الحصّة تتجدّد يومياً)\n"
                    "2. اطلب من مسؤول النظام تحديث المفتاح\n"
                    "3. اطلب ترقية للاستعمال المدفوع (~$0.0001/وثيقة)"
                )
            elif "PERMISSION_DENIED" in all_errors or "403" in all_errors:
                result.error = (
                    "🔒 مفتاح النظام مرفوض من الوصول لهذا النموذج.\n\n"
                    "الحل: اطلب من مسؤول النظام إعادة إعداد المفتاح."
                )
            elif "API_KEY_INVALID" in all_errors or "401" in all_errors:
                result.error = (
                    "🔑 المفتاح غير صحيح.\n\n"
                    "الحل: تحقّق من ملف .env في مجلد المشروع."
                )
            else:
                result.error = "تعذّرت معالجة الوثيقة. راجع سجل النظام."
            print(f"\n❌ فشلت المعالجة بعد {len(result.attempts)} محاولات", flush=True)

        result.elapsed_seconds = time.time() - t_total
        print(f"⏱️  الوقت الإجمالي: {result.elapsed_seconds:.1f}s", flush=True)
        print(f"{'='*60}\n", flush=True)
        return result


# =========================================================
# تشغيل مباشر للاختبار
# =========================================================
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ ضع GEMINI_API_KEY في ملف .env")
        print("   احصل عليه من: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python ai_analyzer.py <image_path>")
        sys.exit(1)

    analyzer = InvoiceAnalyzer(api_key=api_key)
    result = analyzer.analyze(sys.argv[1])
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
