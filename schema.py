"""
schema.py
=========
مخطط JSON للحقول المطلوب استخراجها من الفواتير الجزائرية.

مبني على النظام الضريبي الجزائري:
  - NIF (الرقم الجبائي)  — عادة 15 رقم
  - RC  (السجل التجاري) — مثال: 16/00-1234567 B 21
  - NIS (الرقم الإحصائي) — عادة 15 رقم
  - AI  (المادة/Article d'imposition)
  - TVA — 19% أو 9% أو 0%
  - Droits de timbre — عادة 1% من TTC للدفع النقدي
"""

# مخطط الاستخراج — يمرَّر إلى Gemini كـ response_schema
INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_number": {
            "type": "string",
            "description": (
                "رقم الفاتورة كما هو مكتوب. أمثلة: "
                "'FA-2025/00123', 'INV/2024/00012', 'FC/2026/0589', '00456'. "
                "التقط الرقم الكامل بأي صيغة (Facture N°, N° Facture, "
                "Facture INV, رقم الفاتورة، فاتورة رقم)."
            ),
            "nullable": True,
        },
        "invoice_date": {
            "type": "string",
            "description": (
                "تاريخ إصدار الفاتورة بصيغة ISO YYYY-MM-DD. "
                "حوّل من dd/mm/yyyy → yyyy-mm-dd. "
                "ابحث عن: Date, Date de la facture, التاريخ, بتاريخ, Le."
            ),
            "nullable": True,
        },
        "due_date": {
            "type": "string",
            "description": (
                "تاريخ الاستحقاق بصيغة YYYY-MM-DD. "
                "ابحث عن: Date d'échéance, تاريخ الاستحقاق."
            ),
            "nullable": True,
        },
        "supplier": {
            "type": "object",
            "description": "بيانات المورّد (البائع/Fournisseur/الشركة المُصدرة للفاتورة)",
            "properties": {
                "name": {"type": "string", "nullable": True,
                         "description": "الاسم الكامل (SARL/EURL/SPA...)"},
                "address": {"type": "string", "nullable": True,
                            "description": "العنوان الكامل"},
                "phone": {"type": "string", "nullable": True},
                "email": {"type": "string", "nullable": True},
                "nif": {"type": "string", "nullable": True,
                        "description": "الرقم الجبائي (NIF) — أرقام فقط بدون رموز"},
                "rc": {"type": "string", "nullable": True,
                       "description": "السجل التجاري (RC) بصيغته الأصلية مثل '16/00-1234567 B 21'"},
                "nis": {"type": "string", "nullable": True,
                        "description": "الرقم الإحصائي (NIS) — أرقام فقط"},
                "ai": {"type": "string", "nullable": True,
                       "description": "رقم المادة (Article d'imposition)"},
            },
        },
        "customer": {
            "type": "object",
            "description": "بيانات الزبون (Client/المُشتري)",
            "properties": {
                "name": {"type": "string", "nullable": True},
                "address": {"type": "string", "nullable": True},
                "nif": {"type": "string", "nullable": True},
                "rc": {"type": "string", "nullable": True},
                "nis": {"type": "string", "nullable": True},
                "ai": {"type": "string", "nullable": True},
            },
        },
        "items": {
            "type": "array",
            "description": "قائمة المنتجات/الخدمات المفوترة (كل صف من جدول الفاتورة)",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "nullable": True,
                                    "description": "اسم المنتج/الخدمة"},
                    "quantity": {"type": "number", "nullable": True,
                                 "description": "الكمية (رقم عشري)"},
                    "unit_price": {"type": "number", "nullable": True,
                                   "description": "سعر الوحدة (بدون TVA) — رقم عشري بدون رموز"},
                    "tva_rate": {"type": "number", "nullable": True,
                                 "description": "نسبة الضريبة كنسبة مئوية (19، 9، 0)"},
                    "total_ht": {"type": "number", "nullable": True,
                                 "description": "الإجمالي بدون ضريبة لهذا السطر"},
                },
            },
        },
        "totals": {
            "type": "object",
            "description": "المجاميع النهائية للفاتورة (كلّها أرقام عشرية بدون رموز عملة)",
            "properties": {
                "total_ht": {"type": "number", "nullable": True,
                             "description": "المبلغ الصافي HT (Montant HT / Total HT)"},
                "tva_amount": {"type": "number", "nullable": True,
                               "description": "مبلغ الضريبة TVA (Taxes / TVA)"},
                "stamp_duty": {"type": "number", "nullable": True,
                               "description": "حقوق الطابع (Droits de timbre) — قد لا توجد"},
                "discount": {"type": "number", "nullable": True,
                             "description": "الخصم (Remise) إن وُجد"},
                "total_ttc": {"type": "number", "nullable": True,
                              "description": "المبلغ الإجمالي TTC (Total / Total TTC / Net à payer)"},
                "currency": {"type": "string", "nullable": True,
                             "description": "العملة (DZD/DA/دج افتراضياً)"},
            },
        },
        "payment_terms": {"type": "string", "nullable": True,
                          "description": "شروط الدفع (Conditions de paiement) إن وُجدت"},
        "payment_method": {"type": "string", "nullable": True,
                           "description": "طريقة الدفع (نقداً، شيك، تحويل...) إن ذُكرت"},
        "notes": {"type": "string", "nullable": True,
                  "description": "أي ملاحظات إضافية مهمّة (مثل 'Arrêtée la présente facture...')"},
        "document_type": {"type": "string", "nullable": True,
                          "description": "نوع الوثيقة: facture, devis, bon_livraison, recu, avoir"},
        "confidence_notes": {"type": "string", "nullable": True,
                             "description": (
                                 "ملاحظات عن ثقة القراءة: إن كانت الصورة غير واضحة "
                                 "أو بعض الحقول غير مقروءة، اذكر ذلك هنا. "
                                 "إن كانت الصورة ممتازة، اترك null."
                             )},
    },
    "required": ["invoice_number", "invoice_date", "totals"],
}


# قائمة الحقول للعرض في الواجهة (بالعربية)
FIELD_LABELS_AR = {
    "invoice_number": "رقم الفاتورة",
    "invoice_date": "تاريخ الفاتورة",
    "due_date": "تاريخ الاستحقاق",
    "document_type": "نوع الوثيقة",
    "payment_method": "طريقة الدفع",
    "payment_terms": "شروط الدفع",
    "notes": "ملاحظات",
    # supplier / customer
    "name": "الاسم",
    "address": "العنوان",
    "phone": "الهاتف",
    "email": "البريد الإلكتروني",
    "nif": "الرقم الجبائي (NIF)",
    "rc": "السجل التجاري (RC)",
    "nis": "الرقم الإحصائي (NIS)",
    "ai": "رقم المادة (AI)",
    # items
    "description": "الوصف",
    "quantity": "الكمية",
    "unit_price": "سعر الوحدة",
    "tva_rate": "نسبة TVA",
    "total_ht": "الإجمالي HT",
    # totals
    "tva_amount": "مبلغ TVA",
    "stamp_duty": "حقوق الطابع",
    "discount": "الخصم",
    "total_ttc": "الإجمالي TTC",
    "currency": "العملة",
}
