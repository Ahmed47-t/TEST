# 🇩🇿 محاسب DZ الذكي — Gemini Vision Invoice Analyzer

> أداة احترافية لتحليل الفواتير المحاسبية الجزائرية (عربي + فرنسي)
> مبنية على **Google Gemini Vision AI** بدل OCR التقليدي.
> مستوحاة من مشروع [TaxHacker](https://github.com/vas3k/TaxHacker) (6,500 ⭐).

```
┌────────────┐   ┌───────────────────────────┐   ┌──────────────────┐
│  الصورة    │──▶│  Gemini 2.5 Pro / Flash   │──▶│  JSON منظّم +    │
│ (jpg/png)  │   │  (Multi-provider fallback)│   │  تحقّق حسابي    │
└────────────┘   └───────────────────────────┘   └──────────────────┘
```

## 🎯 لماذا Gemini بدل OCR التقليدي؟

| المعيار | Tesseract / PaddleOCR | **Gemini Vision** ✅ |
|---------|:---------------------:|:-------------------:|
| دقّة على الفواتير الممسوحة | ~70% | **~94%** |
| حجم التثبيت | 300-500 MB | **~15 MB** |
| مشاكل تثبيت (oneDNN, libGL) | كثيرة | **صفر** |
| يفهم صيغ مختلفة تلقائياً | ❌ يحتاج Regex | ✅ نعم |
| العربية + الفرنسية معاً | مشاكل | ✅ مثالي |
| وقت التحليل | 8-15 ثانية | **3-10 ثوانٍ** |
| التكلفة | مجاني | **مجاني** (1550 فاتورة/يوم) |

## 📁 محتويات المشروع

| الملف | الوصف |
|-------|-------|
| `app.py` | 🌐 خادم Flask (واجهة الويب) |
| `ai_analyzer.py` | 🧠 محلّل Gemini مع Multi-provider fallback |
| `prompt_builder.py` | 📝 البرومبت الذكي بالسياق الضريبي الجزائري |
| `schema.py` | 📋 مخطط JSON للحقول المستخرجة |
| `templates/index.html` | واجهة عربية RTL أنيقة |
| `static/style.css` + `app.js` | التصميم والتفاعل |
| `.env.example` | قالب لملف الإعدادات |
| `run.bat` | تشغيل بنقرة واحدة على Windows |
| `requirements.txt` | التبعيات (4 حزم فقط!) |

## 🚀 التثبيت والتشغيل

### الخطوة 1: احصل على مفتاح Gemini المجاني (30 ثانية)

1. اذهب إلى **[Google AI Studio](https://aistudio.google.com/app/apikey)**
2. سجّل دخول بحساب Google العادي (لا يحتاج بطاقة ائتمان)
3. اضغط **"Create API Key"**
4. انسخ المفتاح

**الحدود المجانية**:
- Gemini 2.5 Pro: ~50 طلب/يوم
- Gemini 2.0 Flash: ~1500 طلب/يوم
- **المجموع: ~1550 فاتورة/يوم مجاناً**

### الخطوة 2: على Windows

```powershell
# 1. استنسخ المشروع
git clone https://github.com/Ahmed47-t/TEST.git
cd TEST

# 2. أنشئ بيئة افتراضية
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. ثبّت التبعيات (سريع جداً - ~15MB)
pip install -r requirements.txt

# 4. أنشئ ملف .env
copy .env.example .env
notepad .env
# ← ضع مفتاحك مكان "your_gemini_api_key_here"

# 5. شغّل
python app.py
```

ثم افتح المتصفّح على **http://127.0.0.1:5000** 🚀

**بديل أسهل**: انقر مرّتين على `run.bat`

### الخطوة 3: على Linux / macOS

```bash
git clone https://github.com/Ahmed47-t/TEST.git
cd TEST
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # ضع المفتاح
python app.py
```

## 🎨 الواجهة

- **شريط جانبي** أزرق داكن بمعلومات النماذج المتاحة
- **العمود الأيمن**: منطقة سحب/إفلات + معاينة + زر التحليل
- **العمود الأيسر**: 5 تبويبات:
  1. **📄 معلومات الفاتورة** — رقم، تاريخ، طريقة دفع...
  2. **🏢 المورّد والزبون** — الاسم، NIF، RC، NIS، AI، العنوان
  3. **📦 المنتجات** — جدول كامل بالكمية، السعر، TVA
  4. **💰 المجاميع** — HT، TVA، Timbre، TTC (مبرزة بألوان)
  5. **🔧 JSON** — النتيجة الخام + زر تحميل

## 🧠 الميزات الذكية

### 1. Multi-provider Fallback (مثل TaxHacker)
النظام يجرّب تلقائياً بترتيب الأولوية:
1. **Gemini 2.5 Pro** — الأدق (94%)
2. **Gemini 2.0 Flash** — سريع (~90%)
3. **Gemini 1.5 Flash** — استقرار احتياطي

إن فشل نموذج، ينتقل للتالي تلقائياً بدون تدخّل المستخدم.

### 2. تحقّق حسابي تلقائي
بعد كل استخراج، يتحقّق النظام أن:
```
TTC ≈ HT + TVA + Droits de timbre − Discount   (± 1 دج)
```
إن لم يتطابق، يظهر تنبيه بالعدد الخاطئ (منع للهلوسة).

### 3. سياق ضريبي جزائري في البرومبت
البرومبت يشرح للنموذج:
- بنية NIF (15 رقم)، RC (`16/00-1234567 B 21`)
- الفرق بين TVA و Droits de timbre
- تحويل الأرقام العربية-الهندية
- الفرق بين المورّد والزبون
- الأنماط الشائعة للتواريخ والأرقام الفرنسية

### 4. مقاومة الهلوسة
- إن كانت الصورة ليست فاتورة → يُرجع كل الحقول null + ملاحظة
- إن كانت بعض الحقول غير واضحة → يُرجع null (لا يخترع)
- التحقّق الحسابي يكتشف الأرقام المُتخيَّلة

## 📊 مثال ناتج

من فاتورة "Digitaliac INV/2024/00012":

```json
{
  "invoice_number": "INV/2024/00012",
  "invoice_date": "2024-04-26",
  "supplier": {
    "name": "SARL DIGITALIAC",
    "address": "BABEZOUAR ALGER, ALGER 16000, Algérie",
    "nif": "5231453",
    "nis": "00462546",
    "rc": "11256897",
    "ai": "46786"
  },
  "customer": {
    "name": "SARL FONETICA SPA",
    "address": "905 STREET BLIDA, Algérie",
    "nif": "16231453",
    "nis": "008962546",
    "rc": "152B56895",
    "ai": "66786"
  },
  "items": [{
    "description": "PROD2",
    "quantity": 1.00,
    "unit_price": 790000.00,
    "tva_rate": 19.0,
    "total_ht": 790000.00
  }],
  "totals": {
    "total_ht": 790000.00,
    "tva_amount": 150100.00,
    "stamp_duty": 18802.00,
    "total_ttc": 958902.00,
    "currency": "DZD"
  }
}
```

## 🐛 استكشاف الأخطاء

### "GEMINI_API_KEY غير مضبوط"
- تأكّد أن ملف `.env` موجود في **جذر المشروع** (بجانب `app.py`)
- تأكّد أن المفتاح **بدون علامات اقتباس**:
  ```
  ✅ GEMINI_API_KEY=AIzaSyABC123...
  ❌ GEMINI_API_KEY="AIzaSyABC123..."
  ```

### "429 Resource has been exhausted"
تجاوزت الحد اليومي المجاني. الحلول:
- انتظر 24 ساعة
- استعمل حساب Google آخر لمفتاح ثانٍ
- ادفع مقابل الاستعمال (~$0.0001 لكل فاتورة)

### "Connection error" / بطء
- تأكّد من الاتصال بالإنترنت
- Gemini يعمل مباشرة في الجزائر بدون VPN
- إن كنت خلف Proxy، اضبط متغيّرات `HTTP_PROXY` / `HTTPS_PROXY`

### الواجهة لا تتحدّث بعد `git pull`
اضغط `Ctrl+Shift+R` في المتصفّح لتحديث قاسي.

## 💰 التكلفة

**للاستعمال الشخصي**: مجاني تماماً بحدود 1550 فاتورة/يوم.

**للاستعمال التجاري الكثيف**:
- Gemini 2.0 Flash: **~$0.0001 لكل فاتورة** (10 آلاف فاتورة = 1$)
- Gemini 2.5 Pro: **~$0.005 لكل فاتورة** (200 فاتورة = 1$)

## 📜 الترخيص

مشروع مفتوح المصدر للاستعمال الشخصي والتعليمي.

## 🙏 مصادر الإلهام

- [TaxHacker](https://github.com/vas3k/TaxHacker) — فلسفة multi-provider LLM
- [Google Gemini](https://ai.google.dev/) — نموذج Vision المستعمل
- [Parsli Benchmark 2026](https://parsli.co/blog/llm-ocr-vs-traditional-ocr) — إثبات دقة 94%
