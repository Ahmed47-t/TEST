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

from prompt_builder import SYSTEM_PROMPT, build_user_prompt
from schema import INVOICE_SCHEMA
from scf_accounts import (
    determine_tva_account,
    get_account_info,
    suggest_account_for_item,
)


# =========================================================
# إعدادات المزوّدين (Multi-provider fallback مثل TaxHacker)
# =========================================================
DEFAULT_MODELS = [
    {
        "name": "gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "accuracy": "94% على الفواتير الممسوحة",
        "free_tier": "~50 طلب/يوم",
    },
    {
        "name": "gemini-2.5-flash",
        "label": "Gemini 2.5 Flash",
        "accuracy": "~91% مع سرعة عالية",
        "free_tier": "~1500 طلب/يوم",
    },
    {
        "name": "gemini-2.0-flash",
        "label": "Gemini 2.0 Flash",
        "accuracy": "~89% - Fallback مستقر",
        "free_tier": "~1500 طلب/يوم",
    },
    {
        "name": "gemini-flash-latest",
        "label": "Gemini Flash Latest",
        "accuracy": "~88% - alias مستقر",
        "free_tier": "متغيّرة",
    },
    {
        "name": "gemini-2.0-flash-lite",
        "label": "Gemini 2.0 Flash Lite",
        "accuracy": "~85% - أخفّ نسخة",
        "free_tier": "أعلى حصّة",
    },
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

        # 2) بناء قيد اليومية
        journal_entry = InvoiceAnalyzer._build_journal_entry(data)
        data["journal_entry"] = journal_entry

        return data

    @staticmethod
    def _build_journal_entry(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        يبني قيد اليومية المحاسبي (Écriture comptable) من الفاتورة.

        قيد شراء نموذجي:
          Débit  6xx  ... Charges (المصاريف)          HT
          Débit  44566 ou 44562 ... TVA déductible    TVA
          Débit  6414 ... Droits de timbre            (إن وُجد)
          Crédit 401 ... Fournisseur                  TTC
        """
        entries = []
        items = data.get("items") or []
        totals = data.get("totals") or {}
        supplier = data.get("supplier") or {}
        invoice_date = data.get("invoice_date")
        invoice_number = data.get("invoice_number")

        supplier_name = supplier.get("name", "المورد")
        libelle = f"Facture {invoice_number or ''} - {supplier_name}".strip(" -")

        # تجميع المبالغ حسب الحساب (لو عدّة منتجات لنفس الحساب)
        charges_by_account: Dict[str, Dict[str, Any]] = {}
        has_immobilisation = False

        for item in items:
            code = item.get("scf_account") or "607"
            ht = item.get("total_ht") or 0
            if not ht:
                # احسب من quantity * unit_price إن كان total_ht مفقوداً
                qty = item.get("quantity") or 0
                pu = item.get("unit_price") or 0
                ht = qty * pu

            if code not in charges_by_account:
                info = get_account_info(code)
                charges_by_account[code] = {
                    "account": code,
                    "name": info["name_fr"] if info else item.get("scf_account_name", ""),
                    "amount": 0,
                }
            charges_by_account[code]["amount"] += float(ht)

            # هل هذا حساب من الطبقة 2 (تثبيتات)؟
            if str(code).startswith("2"):
                has_immobilisation = True

        # 1) سطور الديْن (Débit) — المصاريف/التثبيتات
        for code, info in charges_by_account.items():
            entries.append({
                "account": code,
                "name": info["name"],
                "libelle": libelle,
                "debit": round(info["amount"], 2),
                "credit": 0,
            })

        # 2) سطر TVA (Débit) إن كانت > 0
        tva_amount = totals.get("tva_amount") or 0
        if tva_amount:
            tva_account = determine_tva_account(has_immobilisation)
            tva_info = get_account_info(tva_account)
            entries.append({
                "account": tva_account,
                "name": tva_info["name_fr"] if tva_info else "TVA déductible",
                "libelle": libelle,
                "debit": round(float(tva_amount), 2),
                "credit": 0,
            })

        # 3) حقوق الطابع (Débit) إن وُجدت
        stamp = totals.get("stamp_duty") or 0
        if stamp:
            entries.append({
                "account": "6414",
                "name": "Droits de timbre",
                "libelle": libelle,
                "debit": round(float(stamp), 2),
                "credit": 0,
            })

        # 4) سطر المورد (Crédit) — المجموع الإجمالي TTC
        ttc = totals.get("total_ttc") or 0
        supplier_account = "404" if has_immobilisation else "401"
        supplier_name_full = supplier.get("name", "Fournisseur")
        supplier_label = "Fournisseurs d'immobilisations" if has_immobilisation else "Fournisseurs"
        entries.append({
            "account": supplier_account,
            "name": f"{supplier_label} - {supplier_name_full}",
            "libelle": libelle,
            "debit": 0,
            "credit": round(float(ttc), 2),
        })

        total_debit = sum(e["debit"] for e in entries)
        total_credit = sum(e["credit"] for e in entries)

        return {
            "date": invoice_date,
            "libelle": libelle,
            "entries": entries,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "balanced": abs(total_debit - total_credit) < 0.01,
        }

    # ---------------------------------------------------------
    # التحقّق الحسابي (منع الهلوسة)
    # ---------------------------------------------------------
    @staticmethod
    def _validate(data: Dict[str, Any]) -> Dict[str, Any]:
        """يتحقّق من اتساق الأرقام: TTC ≈ HT + TVA + Timbre."""
        checks: Dict[str, Any] = {"passed": True, "warnings": []}
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

        # جرّب النماذج بالترتيب
        for model_config in self.models:
            model_name = model_config["name"]
            model_label = model_config["label"]

            print(f"\n🧠 محاولة: {model_label} ({model_name})", flush=True)
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
                print(f"✅ {model_label} نجح في {elapsed:.1f}s", flush=True)
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

                # طباعة ملخّص قيد اليومية
                je = output.get("journal_entry", {})
                if je.get("entries"):
                    print(f"   📒 قيد اليومية: {len(je['entries'])} سطر، "
                          f"{'متوازن ✓' if je.get('balanced') else 'غير متوازن ✗'}",
                          flush=True)
                break
            else:
                print(f"❌ {model_label} فشل ({elapsed:.1f}s): {output}", flush=True)
                attempt["error"] = str(output)
                result.attempts.append(attempt)
                continue

        if not result.success:
            # حلّل نوع الخطأ الأكثر شيوعاً وأعطِ نصيحة للمستخدم
            all_errors = " ".join(a.get("error", "") for a in result.attempts)

            if "RESOURCE_EXHAUSTED" in all_errors or "429" in all_errors:
                result.error = (
                    "🚫 تجاوزت الحصّة اليومية المجانية لكل نماذج Gemini.\n\n"
                    "الحلول:\n"
                    "1. انتظر 24 ساعة (الحصّة تتجدّد يومياً)\n"
                    "2. أنشئ مفتاح API جديد في مشروع Google Cloud جديد:\n"
                    "   → https://aistudio.google.com/app/apikey\n"
                    "   → اضغط 'Create API key in NEW project'\n"
                    "3. أو ادفع مقابل الاستعمال (~$0.0001/فاتورة)"
                )
            elif "PERMISSION_DENIED" in all_errors or "403" in all_errors:
                result.error = (
                    "🔒 مشروعك على Google Cloud مرفوض من الوصول للنموذج.\n\n"
                    "الحل: أنشئ مفتاح API جديد في مشروع جديد:\n"
                    "→ https://aistudio.google.com/app/apikey\n"
                    "→ اضغط 'Create API key in NEW project'"
                )
            elif "API_KEY_INVALID" in all_errors or "401" in all_errors:
                result.error = (
                    "🔑 مفتاح GEMINI_API_KEY غير صحيح.\n\n"
                    "تحقّق من ملف .env — يجب أن يكون بهذا الشكل:\n"
                    "GEMINI_API_KEY=AIzaSy...\n"
                    "(بدون علامات اقتباس، بدون مسافات)"
                )
            else:
                result.error = "فشلت جميع النماذج. راجع رسائل الخطأ في PowerShell."
            print(f"\n❌ فشل التحليل بعد {len(result.attempts)} محاولات", flush=True)

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
