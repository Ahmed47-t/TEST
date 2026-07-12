# 🇩🇿 محاسب DZ الذكي v4 — Multi-Company Accounting AI

> منصّة محاسبية ذكية للشركات الجزائرية.
> **جديد في v4**: دعم متعدّد الشركات (Multi-tenant) مثل PC Compta.

## 🏢 نظام متعدّد الشركات

كل شركة عندها:
- بياناتها الكاملة (اسم، NIF، RC، NIS، AI، عنوان...)
- شعار بلون مخصّص
- مجلد وثائق مستقل
- **دفتر يومية شامل** يتراكم تلقائياً مع كل تحليل
- إحصائيات فورية

## 📄 أنواع الوثائق المدعومة (10 أنواع)

| النوع | القيد المحاسبي |
|-------|:---:|
| 🧾 **Facture d'achat** | ✅ 6xx/2xx → 401/404 |
| 💼 **Facture de vente** | ✅ 411 → 7xx/44551 |
| ↩️ **Facture d'avoir** | ✅ عكسي |
| 📋 **Bon de commande** | ❌ خارج الميزانية |
| 🚚 **Bon de livraison** | ✅ 3x/408 |
| 📥 **Bon de réception** | ✅ 3x/408 |
| 💳 **Chèque bancaire** | ✅ 401/512 |
| 🧾 **Reçu de paiement** | ✅ 401/530 |
| 📝 **Devis** | ❌ إعلامي فقط |

## 📁 محتويات المشروع

| الملف | الوصف |
|-------|-------|
| `app.py` | 🌐 خادم Flask (Multi-tenant) |
| `companies.py` | 🏢 **إدارة الشركات (Multi-tenant)** |
| `ai_analyzer.py` | 🧠 محلّل ذكي + إثراء SCF |
| `document_types.py` | 📄 10 أنواع وثائق + مولّد قيود |
| `prompt_builder.py` | 📝 البرومبت الذكي |
| `schema.py` | 📋 مخطط JSON |
| `scf_accounts.py` | 🏦 SCF 2010 (49 حساب) |
| `templates/index.html` | واجهة عربية RTL |
| `static/style.css` + `app.js` | التصميم والتفاعل |

## 🚀 التثبيت والتشغيل

### 1) احصل على مفتاح API المجاني
1. اذهب إلى [Google AI Studio](https://aistudio.google.com/app/apikey)
2. اضغط **"Create API Key"** → انسخه

### 2) على Windows
```powershell
git clone https://github.com/Ahmed47-t/TEST.git
cd TEST
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
# ← ضع GEMINI_API_KEY=مفتاحك
python app.py
```

ثم افتح **http://127.0.0.1:5000**

## 🎯 دفق الاستعمال

1. **الشاشة الأولى**: قائمة شركاتك (فارغة أوّل مرّة)
2. اضغط **"➕ إضافة شركة جديدة"** واملأ البيانات
3. اضغط على بطاقة الشركة لدخولها
4. **رفع الوثائق** (حتى 20 صورة معاً)
5. اضغط **"تحليل الوثائق"** — انتظر **"جارٍ التحليل..."**
6. اطّلع على:
   - **📊 الملخّص السريع**: إحصائيات + مجاميع
   - **📋 نتائج آخر دفعة**: تفاصيل كل وثيقة
   - **📒 دفتر اليومية**: كل قيود الشركة منذ إنشائها

## 💾 التخزين

```
data/
├── companies.json              ← قائمة الشركات
├── <company_id_1>/
│   ├── uploads/                ← صور الوثائق
│   ├── results/                ← نتائج كل دفعة (JSON)
│   └── journal/                ← دفتر اليومية المتراكم
└── <company_id_2>/
    └── ...
```

بيانات كل شركة معزولة تماماً عن الأخرى.

## 🏦 التصنيف المحاسبي التلقائي (SCF)

النظام يستعمل **مخطط الحسابات المحاسبي الجزائري (SCF 2010)** كاملاً — 49 حساب.
لكل منتج في الفاتورة، النظام يختار تلقائياً رقم الحساب الصحيح، ويبني قيد اليومية المتوازن.

### مثال قيد يومية مُولَّد تلقائياً:

```
Date: 2024-04-26
Libellé: Facture INV/2024/00012 - SARL DIGITALIAC

Compte  | Nom                                    |    Débit  |   Crédit
--------|----------------------------------------|-----------|----------
2183    | Matériel de bureau et informatique     | 100,000.00|
607     | Achats non stockés - Fournitures       |   5,000.00|
44562   | TVA déductible sur immobilisations     |  19,950.00|
404     | Fournisseurs d'immobilisations - SARL..|           | 124,950.00
--------|----------------------------------------|-----------|----------
Total                                            | 124,950.00| 124,950.00
                                                 ✅ متوازن
```

## 📜 الترخيص

مشروع مفتوح المصدر للاستعمال الشخصي والتعليمي.

## 🔗 نقاط الحفظ

- `v1.0-gemini-stable` — النسخة الأساسية
- `v2.0-scf-integration` — + SCF + قيود يومية
- `v3.0-multi-document` — + رفع دفعات + 10 أنواع وثائق
- `v4.0-multi-company` — + إدارة شركات متعدّدة (الحالية)
