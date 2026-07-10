"""
scf_accounts.py
================
مخطط الحسابات المحاسبي الجزائري (SCF - Système Comptable Financier 2010)

يستعمل لـ:
  1. تزويد Gemini بقائمة الحسابات ليصنّف كل منتج تلقائياً
  2. عرض قيد اليومية جاهزاً بعد كل تحليل فاتورة
  3. التحقق من صحّة أرقام الحسابات المُعادة

المصادر:
  • adesk.dz/plan_comptable_scf
  • مدونة SCF الجزائرية الرسمية 2010
"""

# =========================================================
# الطبقة 6 - حسابات الأعباء (Charges) — الأكثر استعمالاً في الفواتير
# =========================================================
CHARGES_ACCOUNTS = [
    # 60 - المشتريات المستهلكة
    {"code": "600", "name_fr": "Achats de marchandises vendues",
     "name_ar": "مشتريات البضائع المبيعة",
     "keywords": ["marchandise", "revente", "produit fini", "بضاعة", "منتج جاهز"],
     "description": "مشتريات بضائع للبيع بدون تحويل (تجار الجملة/التجزئة)"},

    {"code": "601", "name_fr": "Matières premières",
     "name_ar": "المواد الأولية",
     "keywords": ["matière première", "matiere premiere", "brut", "مواد أولية", "خام"],
     "description": "مواد أولية تدخل في تصنيع منتج نهائي"},

    {"code": "602", "name_fr": "Autres approvisionnements",
     "name_ar": "التموينات الأخرى",
     "keywords": ["approvisionnement", "consommable", "emballage", "تموين", "استهلاكي", "تغليف"],
     "description": "لوازم استهلاكية، تعبئة وتغليف، قطع غيار صغيرة"},

    {"code": "604", "name_fr": "Achats d'études et de prestations de services",
     "name_ar": "مشتريات الدراسات والخدمات",
     "keywords": ["étude", "prestation", "service", "consulting", "دراسة", "خدمة", "استشارة"],
     "description": "دراسات وخدمات مشتراة تدمج في منتج/خدمة الشركة"},

    {"code": "605", "name_fr": "Achats de matériels, équipements et travaux",
     "name_ar": "مشتريات المعدات والتجهيزات والأشغال",
     "keywords": ["matériel", "équipement", "travaux", "معدات", "تجهيزات", "أشغال"],
     "description": "معدات وتجهيزات بقيمة صغيرة (غير مثبتة كأصول)"},

    {"code": "6061", "name_fr": "Fournitures non stockables - Eau",
     "name_ar": "توريدات غير مخزّنة - الماء",
     "keywords": ["eau", "SEAAL", "ADE", "ماء", "مياه"],
     "description": "فواتير الماء"},

    {"code": "6062", "name_fr": "Fournitures non stockables - Électricité, gaz",
     "name_ar": "توريدات غير مخزّنة - كهرباء وغاز",
     "keywords": ["électricité", "electricite", "gaz", "sonelgaz", "energie", "كهرباء", "غاز", "سونلغاز"],
     "description": "فواتير الكهرباء والغاز"},

    {"code": "607", "name_fr": "Achats non stockés de matières et fournitures",
     "name_ar": "المشتريات غير المخزنة من المواد والتوريدات",
     "keywords": ["fourniture bureau", "papeterie", "لوازم مكتبية", "قرطاسية"],
     "description": "لوازم مكتبية صغيرة، مواد استهلاكية غير مخزّنة"},

    {"code": "608", "name_fr": "Frais accessoires d'achat",
     "name_ar": "مصاريف الشراء التبعية",
     "keywords": ["transport achat", "frais port", "مصاريف نقل", "شحن"],
     "description": "مصاريف نقل الشراء، تأمين النقل، جمارك"},

    # 61 - الخدمات الخارجية
    {"code": "611", "name_fr": "Sous-traitance générale",
     "name_ar": "المقاولة العامة",
     "keywords": ["sous-traitance", "sous traitance", "مقاولة من الباطن"],
     "description": "أعمال مقاولة من الباطن"},

    {"code": "613", "name_fr": "Locations",
     "name_ar": "الإيجارات",
     "keywords": ["location", "loyer", "bail", "إيجار", "كراء"],
     "description": "إيجار محلات، معدات، سيارات"},

    {"code": "615", "name_fr": "Entretien, réparations et maintenance",
     "name_ar": "الصيانة والإصلاح والصيانة",
     "keywords": ["entretien", "réparation", "reparation", "maintenance", "صيانة", "إصلاح", "تصليح"],
     "description": "صيانة وإصلاح المعدات، السيارات، المباني"},

    {"code": "616", "name_fr": "Primes d'assurances",
     "name_ar": "أقساط التأمين",
     "keywords": ["assurance", "prime", "SAA", "CAAT", "تأمين", "قسط"],
     "description": "تأمينات (مبنى، سيارة، مسؤولية...)"},

    {"code": "617", "name_fr": "Études et recherches",
     "name_ar": "الدراسات والبحوث",
     "keywords": ["étude", "recherche", "audit", "دراسة", "بحث", "تدقيق"],
     "description": "دراسات وبحوث خارجية"},

    {"code": "618", "name_fr": "Documentation et divers",
     "name_ar": "الوثائق والمتنوعات",
     "keywords": ["documentation", "livre", "abonnement", "وثائق", "كتب", "اشتراك"],
     "description": "كتب، اشتراكات مهنية، وثائق"},

    # 62 - خدمات خارجية أخرى
    {"code": "621", "name_fr": "Personnel extérieur à l'entreprise",
     "name_ar": "العمالة الخارجية",
     "keywords": ["intérim", "interim", "personnel extérieur", "عمالة مؤقتة"],
     "description": "عمالة مؤقتة من وكالات"},

    {"code": "622", "name_fr": "Rémunérations d'intermédiaires et honoraires",
     "name_ar": "أتعاب الوسطاء والمستشارين",
     "keywords": ["honoraire", "avocat", "notaire", "expert comptable", "أتعاب", "محامي", "موثق", "خبير محاسب"],
     "description": "أتعاب المحامين، الموثقين، الخبراء المحاسبين"},

    {"code": "623", "name_fr": "Publicité, publication, relations publiques",
     "name_ar": "الإعلانات والنشر والعلاقات العامة",
     "keywords": ["publicité", "publicite", "marketing", "pub", "communication", "إعلان", "إشهار", "تسويق"],
     "description": "إعلانات، تسويق، طباعة كتيّبات"},

    {"code": "624", "name_fr": "Transports de biens et transport collectif du personnel",
     "name_ar": "نقل البضائع ونقل العمّال",
     "keywords": ["transport", "livraison", "expédition", "expedition", "نقل", "شحن", "توصيل"],
     "description": "نقل البضائع، نقل العمّال جماعياً"},

    {"code": "625", "name_fr": "Déplacements, missions et réceptions",
     "name_ar": "التنقلات والمهام والاستقبال",
     "keywords": ["déplacement", "deplacement", "mission", "hôtel", "hotel", "restaurant", "voyage", "تنقل", "مهمة", "فندق", "مطعم", "سفر"],
     "description": "فنادق، مطاعم، تذاكر سفر، مصاريف مهام"},

    {"code": "6261", "name_fr": "Frais postaux",
     "name_ar": "مصاريف بريدية",
     "keywords": ["poste", "timbre", "courrier", "بريد", "طوابع"],
     "description": "بريد وطوابع"},

    {"code": "6262", "name_fr": "Frais de télécommunications",
     "name_ar": "مصاريف الاتصالات",
     "keywords": ["télécom", "telecom", "internet", "téléphone", "telephone", "algerie telecom", "djezzy", "ooredoo", "mobilis", "اتصالات", "إنترنت", "هاتف"],
     "description": "هاتف، إنترنت، فاكس، اشتراكات اتصالات"},

    {"code": "627", "name_fr": "Services bancaires et assimilés",
     "name_ar": "الخدمات المصرفية",
     "keywords": ["banque", "frais bancaire", "commission bancaire", "بنك", "مصاريف بنكية", "عمولة"],
     "description": "عمولات بنكية، مصاريف حسابات"},

    {"code": "628", "name_fr": "Cotisations et divers",
     "name_ar": "الاشتراكات والمتنوعات",
     "keywords": ["cotisation", "adhésion", "adhesion", "اشتراك", "انتساب"],
     "description": "اشتراكات مهنية، انتسابات لغرف"},

    # 63 - أعباء المستخدمين
    {"code": "631", "name_fr": "Rémunérations du personnel",
     "name_ar": "أجور المستخدمين",
     "keywords": ["salaire", "rémunération", "remuneration", "paie", "أجر", "راتب"],
     "description": "أجور ورواتب العمّال"},

    {"code": "635", "name_fr": "Cotisations aux organismes sociaux (CNAS, CASNOS)",
     "name_ar": "اشتراكات الضمان الاجتماعي",
     "keywords": ["cnas", "casnos", "sécurité sociale", "securite sociale", "ضمان اجتماعي"],
     "description": "اشتراكات CNAS/CASNOS"},

    # 64 - الضرائب والرسوم
    {"code": "6411", "name_fr": "Taxe sur l'activité professionnelle (TAP)",
     "name_ar": "الرسم على النشاط المهني",
     "keywords": ["tap", "taxe activité", "رسم النشاط المهني"],
     "description": "الرسم على النشاط المهني"},

    {"code": "6412", "name_fr": "Impôt Forfaitaire Unique (IFU)",
     "name_ar": "الضريبة الجزافية الوحيدة",
     "keywords": ["ifu", "impot forfaitaire", "ضريبة جزافية"],
     "description": "IFU للمكلفين بالنظام الجزافي"},

    {"code": "6414", "name_fr": "Droits de timbre",
     "name_ar": "حقوق الطابع",
     "keywords": ["timbre", "droit timbre", "حقوق الطابع", "طابع"],
     "description": "حقوق الطابع على الفواتير النقدية (1%)"},

    # 68 - المخصصات
    {"code": "681", "name_fr": "Dotations aux amortissements",
     "name_ar": "مخصصات الاهتلاك",
     "keywords": ["amortissement", "اهتلاك"],
     "description": "اهتلاك الأصول الثابتة"},
]


# =========================================================
# الطبقة 2 - التثبيتات (Immobilisations) — الأصول الثابتة
# =========================================================
IMMOBILISATIONS_ACCOUNTS = [
    {"code": "204", "name_fr": "Logiciels informatiques et assimilés",
     "name_ar": "برامج معلوماتية",
     "keywords": ["logiciel", "software", "licence", "برنامج", "رخصة", "software", "SAP", "office"],
     "description": "برامج معلوماتية بقيمة كبيرة (>60,000 DA)"},

    {"code": "211", "name_fr": "Terrains",
     "name_ar": "الأراضي",
     "keywords": ["terrain", "أرض"],
     "description": "شراء أراضي"},

    {"code": "213", "name_fr": "Constructions",
     "name_ar": "البنايات",
     "keywords": ["construction", "bâtiment", "batiment", "immeuble", "بناية", "مبنى", "عقار"],
     "description": "بنايات ومحلات"},

    {"code": "2151", "name_fr": "Installations techniques",
     "name_ar": "التركيبات التقنية",
     "keywords": ["installation", "تركيبات"],
     "description": "تركيبات تقنية صناعية"},

    {"code": "2154", "name_fr": "Matériel industriel",
     "name_ar": "المعدات الصناعية",
     "keywords": ["machine", "outillage industriel", "آلة", "معدات صناعية"],
     "description": "آلات ومعدات صناعية"},

    {"code": "2182", "name_fr": "Matériel de transport",
     "name_ar": "معدات النقل",
     "keywords": ["véhicule", "vehicule", "voiture", "camion", "utilitaire", "سيارة", "شاحنة", "مركبة"],
     "description": "سيارات، شاحنات، مركبات"},

    {"code": "2183", "name_fr": "Matériel de bureau et informatique",
     "name_ar": "معدات المكتب والإعلام الآلي",
     "keywords": ["ordinateur", "pc", "laptop", "portable", "imprimante", "scanner", "serveur",
                  "moniteur", "écran", "ecran", "clavier", "souris", "smartphone",
                  "حاسوب", "كمبيوتر", "طابعة", "شاشة", "خادم"],
     "description": "أجهزة كمبيوتر، طابعات، خوادم (>60,000 DA)"},

    {"code": "2184", "name_fr": "Mobilier de bureau",
     "name_ar": "أثاث المكتب",
     "keywords": ["mobilier", "bureau", "chaise", "table", "armoire", "أثاث", "طاولة", "كرسي", "خزانة"],
     "description": "أثاث ومفروشات المكتب"},
]


# =========================================================
# الطبقة 3 - المخزونات (Stocks)
# =========================================================
STOCKS_ACCOUNTS = [
    {"code": "30", "name_fr": "Stocks de marchandises",
     "name_ar": "مخزون البضائع",
     "keywords": [], "description": "بضائع للبيع"},
    {"code": "31", "name_fr": "Matières premières et fournitures",
     "name_ar": "مواد أولية وتموينات",
     "keywords": [], "description": "مواد أولية مخزّنة"},
    {"code": "35", "name_fr": "Stocks de produits",
     "name_ar": "مخزون المنتجات",
     "keywords": [], "description": "منتجات نصف مصنّعة/تامة"},
]


# =========================================================
# الطبقة 4 - الأطراف الثالثة (Tiers)
# =========================================================
TIERS_ACCOUNTS = [
    {"code": "401", "name_fr": "Fournisseurs de biens et services",
     "name_ar": "الموردون",
     "keywords": [], "description": "الموردون (دين على الشركة)"},
    {"code": "404", "name_fr": "Fournisseurs d'immobilisations",
     "name_ar": "موردو التثبيتات",
     "keywords": [], "description": "موردون لشراء أصول ثابتة"},
    {"code": "411", "name_fr": "Clients",
     "name_ar": "الزبائن",
     "keywords": [], "description": "الزبائن (دين لصالح الشركة)"},
    {"code": "44551", "name_fr": "TVA collectée",
     "name_ar": "TVA محصّلة",
     "keywords": [], "description": "TVA على المبيعات"},
    {"code": "44566", "name_fr": "TVA déductible sur autres biens et services",
     "name_ar": "TVA قابلة للخصم على السلع والخدمات",
     "keywords": [], "description": "TVA على المشتريات — قابلة للاسترجاع"},
    {"code": "44562", "name_fr": "TVA déductible sur immobilisations",
     "name_ar": "TVA قابلة للخصم على التثبيتات",
     "keywords": [], "description": "TVA على شراء الأصول الثابتة"},
]


# =========================================================
# الطبقة 5 - الحسابات المالية
# =========================================================
FINANCIAL_ACCOUNTS = [
    {"code": "512", "name_fr": "Banques comptes courants",
     "name_ar": "البنك حسابات جارية",
     "keywords": [], "description": "الحساب البنكي"},
    {"code": "530", "name_fr": "Caisse",
     "name_ar": "الصندوق",
     "keywords": [], "description": "الصندوق النقدي"},
]


# =========================================================
# الجميع في قاموس واحد للبحث السريع
# =========================================================
ALL_ACCOUNTS = (
    CHARGES_ACCOUNTS
    + IMMOBILISATIONS_ACCOUNTS
    + STOCKS_ACCOUNTS
    + TIERS_ACCOUNTS
    + FINANCIAL_ACCOUNTS
)

ACCOUNT_BY_CODE = {a["code"]: a for a in ALL_ACCOUNTS}


def get_account_info(code: str) -> dict | None:
    """يعيد بيانات حساب حسب رقمه، أو None."""
    if not code:
        return None
    return ACCOUNT_BY_CODE.get(str(code).strip())


def build_llm_accounts_context() -> str:
    """
    يبني نصّاً يُدرج في البرومبت ليعرف Gemini كل الحسابات المتاحة.
    يعرض فقط حسابات المصاريف والتثبيتات (الأكثر استعمالاً في فواتير الشراء).
    """
    lines = ["حسابات المصاريف (Charges - Classe 6):"]
    for acc in CHARGES_ACCOUNTS:
        kw = ", ".join(acc["keywords"][:5]) if acc["keywords"] else "—"
        lines.append(f"  • {acc['code']} - {acc['name_fr']} ({acc['name_ar']}) — كلمات: {kw}")

    lines.append("\nحسابات التثبيتات (Immobilisations - Classe 2 - للأصول >60,000 DA):")
    for acc in IMMOBILISATIONS_ACCOUNTS:
        kw = ", ".join(acc["keywords"][:5]) if acc["keywords"] else "—"
        lines.append(f"  • {acc['code']} - {acc['name_fr']} ({acc['name_ar']}) — كلمات: {kw}")

    return "\n".join(lines)


def suggest_account_for_item(description: str) -> str | None:
    """
    اقتراح رقم حساب بناءً على وصف المنتج (backup إن لم يعطِ Gemini رقماً).
    يبحث في الكلمات المفتاحية.
    """
    if not description:
        return None
    desc_lower = description.lower()
    for acc in ALL_ACCOUNTS:
        for kw in acc.get("keywords", []):
            if kw.lower() in desc_lower:
                return acc["code"]
    return None


def determine_tva_account(is_immobilisation: bool = False) -> str:
    """يحدّد حساب TVA الصحيح حسب نوع الشراء."""
    return "44562" if is_immobilisation else "44566"


if __name__ == "__main__":
    # اختبار
    print(f"إجمالي الحسابات: {len(ALL_ACCOUNTS)}")
    print(f"\nاختبار suggest_account_for_item:")
    tests = [
        "Ordinateur portable HP",
        "Facture d'électricité SONELGAZ",
        "Papier A4 ramette",
        "Voiture Renault Clio",
        "Consultation avocat",
        "Frais de téléphone Ooredoo",
    ]
    for t in tests:
        suggested = suggest_account_for_item(t)
        info = get_account_info(suggested)
        name = info["name_fr"] if info else "—"
        print(f"  '{t}' → {suggested} ({name})")
