"""
companies.py
============
إدارة الشركات (Multi-tenant) — مثل PC Compta.

كل شركة لها:
  • معرّف فريد (uuid)
  • بياناتها (اسم، NIF، RC، ...)
  • مجلد نتائج خاص بها
  • دفتر يومية مستقل

التخزين:
  data/
  ├── companies.json           ← قائمة كل الشركات
  ├── <company_id>/
  │   ├── uploads/             ← صور الوثائق
  │   ├── results/             ← نتائج JSON
  │   └── journal/             ← دفتر اليومية المُتراكم
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
COMPANIES_FILE = DATA_DIR / "companies.json"


# =========================================================
# التهيئة
# =========================================================
def _ensure_data_dir() -> None:
    """يتأكّد من وجود المجلد + الملف الأساسي (بدون استدعاء _save_all)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not COMPANIES_FILE.exists():
        with open(COMPANIES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def _load_all() -> List[Dict[str, Any]]:
    _ensure_data_dir()
    try:
        with open(COMPANIES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(companies: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(COMPANIES_FILE, "w", encoding="utf-8") as f:
        json.dump(companies, f, ensure_ascii=False, indent=2)


# =========================================================
# العمليات
# =========================================================
def list_companies() -> List[Dict[str, Any]]:
    """قائمة كل الشركات مع إحصائيات لكل واحدة."""
    companies = _load_all()
    for c in companies:
        c["stats"] = _company_stats(c["id"])
    # ترتيب حسب آخر استعمال
    companies.sort(key=lambda c: c.get("last_used_at") or c.get("created_at") or "",
                   reverse=True)
    return companies


def get_company(company_id: str) -> Optional[Dict[str, Any]]:
    """يجلب شركة واحدة بمعرّفها."""
    for c in _load_all():
        if c["id"] == company_id:
            c["stats"] = _company_stats(company_id)
            return c
    return None


def create_company(
    name: str,
    activity: str = "",
    nif: str = "",
    rc: str = "",
    nis: str = "",
    ai: str = "",
    address: str = "",
    phone: str = "",
    email: str = "",
    logo_color: str = "#2563eb",
) -> Dict[str, Any]:
    """إنشاء شركة جديدة."""
    if not name or not name.strip():
        raise ValueError("اسم الشركة مطلوب")

    companies = _load_all()

    # منع التكرار على الاسم
    for c in companies:
        if c["name"].strip().lower() == name.strip().lower():
            raise ValueError(f"يوجد شركة مسجّلة بنفس الاسم: {name}")

    company_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat(timespec="seconds")

    company = {
        "id": company_id,
        "name": name.strip(),
        "activity": activity.strip(),
        "nif": nif.strip(),
        "rc": rc.strip(),
        "nis": nis.strip(),
        "ai": ai.strip(),
        "address": address.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "logo_color": logo_color,
        "created_at": now,
        "last_used_at": now,
    }
    companies.append(company)
    _save_all(companies)

    # إنشاء مجلدات الشركة
    (DATA_DIR / company_id / "uploads").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / company_id / "results").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / company_id / "journal").mkdir(parents=True, exist_ok=True)

    company["stats"] = _company_stats(company_id)
    return company


def update_company(company_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """تحديث بيانات شركة."""
    companies = _load_all()
    for c in companies:
        if c["id"] == company_id:
            # الحقول المسموح تعديلها فقط
            allowed = {"name", "activity", "nif", "rc", "nis", "ai",
                       "address", "phone", "email", "logo_color"}
            for k, v in updates.items():
                if k in allowed and v is not None:
                    c[k] = str(v).strip()
            _save_all(companies)
            c["stats"] = _company_stats(company_id)
            return c
    return None


def touch_company(company_id: str) -> None:
    """يُحدّث last_used_at (يُستدعى عند اختيار الشركة)."""
    companies = _load_all()
    for c in companies:
        if c["id"] == company_id:
            c["last_used_at"] = datetime.now().isoformat(timespec="seconds")
            _save_all(companies)
            return


def delete_company(company_id: str, delete_data: bool = False) -> bool:
    """
    حذف شركة.
    إن delete_data=True، يحذف كل ملفاتها من disk أيضاً.
    """
    companies = _load_all()
    new_list = [c for c in companies if c["id"] != company_id]
    if len(new_list) == len(companies):
        return False
    _save_all(new_list)

    if delete_data:
        company_dir = DATA_DIR / company_id
        if company_dir.exists() and company_dir.is_dir():
            shutil.rmtree(company_dir, ignore_errors=True)
    return True


def get_company_paths(company_id: str) -> Dict[str, Path]:
    """يعيد مسارات مجلدات شركة معيّنة."""
    base = DATA_DIR / company_id
    return {
        "base": base,
        "uploads": base / "uploads",
        "results": base / "results",
        "journal": base / "journal",
    }


# =========================================================
# إحصائيات الشركة
# =========================================================
def _company_stats(company_id: str) -> Dict[str, Any]:
    """إحصائيات عن ملفّات ونتائج الشركة."""
    paths = get_company_paths(company_id)
    stats = {
        "uploads_count": 0,
        "results_count": 0,
        "journal_entries_count": 0,
        "total_size_mb": 0.0,
    }

    if paths["uploads"].exists():
        uploads = list(paths["uploads"].glob("*"))
        stats["uploads_count"] = len([u for u in uploads if u.is_file()])
        stats["total_size_mb"] = round(
            sum(u.stat().st_size for u in uploads if u.is_file()) / (1024 * 1024), 2
        )

    if paths["results"].exists():
        stats["results_count"] = len(list(paths["results"].glob("*.json")))

    if paths["journal"].exists():
        stats["journal_entries_count"] = len(list(paths["journal"].glob("*.json")))

    return stats


# =========================================================
# دفتر اليومية المتراكم للشركة
# =========================================================
def append_to_company_journal(company_id: str, batch_summary: Dict[str, Any]) -> str:
    """
    يُضيف دفعة قيود إلى دفتر يومية الشركة الدائم.
    يعيد اسم الملف المحفوظ.
    """
    paths = get_company_paths(company_id)
    paths["journal"].mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_{timestamp}_{batch_summary.get('batch_id', 'unknown')}.json"

    with open(paths["journal"] / filename, "w", encoding="utf-8") as f:
        json.dump({
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "batch_summary": batch_summary,
        }, f, ensure_ascii=False, indent=2)
    return filename


def get_company_journal(company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """يعيد كل قيود الشركة المتراكمة (مرتّبة زمنياً - الأحدث أوّلاً)."""
    paths = get_company_paths(company_id)
    if not paths["journal"].exists():
        return []

    all_entries = []
    files = sorted(paths["journal"].glob("*.json"), reverse=True)[:limit]
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                batch = data.get("batch_summary", {})
                for j in batch.get("consolidated_journal", []):
                    entry = j.get("journal_entry", {})
                    all_entries.append({
                        "batch_file": f.name,
                        "saved_at": data.get("saved_at"),
                        "batch_id": batch.get("batch_id"),
                        "document_filename": j.get("document_filename"),
                        "document_type": j.get("document_type"),
                        "date": entry.get("date"),
                        "libelle": entry.get("libelle"),
                        "journal_type": entry.get("journal_type"),
                        "total_debit": entry.get("total_debit"),
                        "total_credit": entry.get("total_credit"),
                        "balanced": entry.get("balanced"),
                        "entries": entry.get("entries", []),
                    })
        except (json.JSONDecodeError, OSError):
            continue
    return all_entries


# =========================================================
# اختبار سريع
# =========================================================
if __name__ == "__main__":
    print("قائمة الشركات الحالية:", list_companies())

    if not list_companies():
        c = create_company(
            name="SARL Test Company",
            activity="تجارة عامة",
            nif="000216001234567",
            rc="16/00-1234567 B 21",
        )
        print("تم إنشاء شركة اختبار:", c["name"], "id:", c["id"])
