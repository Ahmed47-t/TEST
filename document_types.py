"""
document_types.py
=================
تعريف أنواع الوثائق المحاسبية الجزائرية المدعومة، مع منطق توليد
القيود المحاسبية المناسبة لكل نوع.

الأنواع المدعومة:
  1. facture               — فاتورة شراء/بيع
  2. facture_avoir         — فاتورة إرجاع/تخفيض (Avoir)
  3. bon_commande          — طلبية (Bon de commande) — التزام فقط
  4. bon_livraison         — وصل تسليم (Bon de livraison)
  5. bon_reception         — وصل استلام (Bon de réception)
  6. cheque_bancaire       — شيك بنكي
  7. recu_paiement         — وصل دفع/إيصال
"""

from typing import Any, Dict, List, Optional


# =========================================================
# قاموس أنواع الوثائق (ميتاداتا)
# =========================================================
DOCUMENT_TYPES = {
    "facture": {
        "code": "facture",
        "label_ar": "فاتورة شراء",
        "label_fr": "Facture d'achat",
        "icon": "🧾",
        "generates_journal": True,
        "affects_stock": False,
        "description": "فاتورة شراء عادية تُسجَّل قيد شراء كامل",
    },
    "facture_vente": {
        "code": "facture_vente",
        "label_ar": "فاتورة بيع",
        "label_fr": "Facture de vente",
        "icon": "💼",
        "generates_journal": True,
        "affects_stock": False,
        "description": "فاتورة صادرة للزبون — قيد بيع",
    },
    "facture_avoir": {
        "code": "facture_avoir",
        "label_ar": "فاتورة إرجاع",
        "label_fr": "Facture d'avoir",
        "icon": "↩️",
        "generates_journal": True,
        "affects_stock": False,
        "description": "فاتورة إرجاع/تخفيض — قيد عكسي",
    },
    "bon_commande": {
        "code": "bon_commande",
        "label_ar": "طلبية",
        "label_fr": "Bon de commande",
        "icon": "📋",
        "generates_journal": False,
        "affects_stock": False,
        "description": "طلبية شراء — التزام تعاقدي فقط، لا قيد محاسبي (خارج الميزانية)",
    },
    "bon_livraison": {
        "code": "bon_livraison",
        "label_ar": "وصل تسليم",
        "label_fr": "Bon de livraison",
        "icon": "🚚",
        "generates_journal": True,
        "affects_stock": True,
        "description": "وصل تسليم — يُسجَّل دخول المخزون (37 / 408)",
    },
    "bon_reception": {
        "code": "bon_reception",
        "label_ar": "وصل استلام",
        "label_fr": "Bon de réception",
        "icon": "📥",
        "generates_journal": True,
        "affects_stock": True,
        "description": "وصل استلام مماثل لوصل التسليم — دخول مخزون",
    },
    "cheque_bancaire": {
        "code": "cheque_bancaire",
        "label_ar": "شيك بنكي",
        "label_fr": "Chèque bancaire",
        "icon": "💳",
        "generates_journal": True,
        "affects_stock": False,
        "description": "شيك — قيد تسوية دفع من البنك (401 / 512)",
    },
    "recu_paiement": {
        "code": "recu_paiement",
        "label_ar": "وصل دفع",
        "label_fr": "Reçu de paiement",
        "icon": "🧾",
        "generates_journal": True,
        "affects_stock": False,
        "description": "وصل دفع نقدي — تسوية من الصندوق (401 / 530)",
    },
    "devis": {
        "code": "devis",
        "label_ar": "عرض سعر",
        "label_fr": "Devis",
        "icon": "📝",
        "generates_journal": False,
        "affects_stock": False,
        "description": "عرض سعر — لا قيد محاسبي",
    },
    "unknown": {
        "code": "unknown",
        "label_ar": "غير محدّد",
        "label_fr": "Non identifié",
        "icon": "❓",
        "generates_journal": False,
        "affects_stock": False,
        "description": "نوع الوثيقة غير معروف",
    },
}


def get_doc_type(code: str) -> Dict[str, Any]:
    """يعيد ميتاداتا نوع الوثيقة، مع fallback على 'unknown'."""
    return DOCUMENT_TYPES.get(code, DOCUMENT_TYPES["unknown"])


# =========================================================
# قواعد كشف نوع الوثيقة (heuristics للـ Gemini)
# =========================================================
DETECTION_HINTS_PROMPT = """
تحديد نوع الوثيقة:

قواعد الاكتشاف (اختر الأكثر تطابقاً):

  • "facture" — إذا رأيت "FACTURE", "Facture N°", "فاتورة", "فاتورة رقم"
    مع جدول منتجات + مبالغ (HT، TVA، TTC).

  • "facture_vente" — إذا كانت الفاتورة صادرة **من** شركة المستخدم إلى زبون
    (اسم المستخدم في خانة "Vendeur/Émetteur"، وبيانات "Client" في الأسفل).
    الافتراضي هو "facture" (شراء) إن لم تكن متأكداً.

  • "facture_avoir" — إذا رأيت "AVOIR", "Facture d'avoir", "فاتورة إرجاع",
    "Note de crédit", أو إذا كانت المبالغ سالبة.

  • "bon_commande" — إذا رأيت "BON DE COMMANDE", "Commande N°", "طلبية",
    "طلب شراء" — عادةً لا يحتوي على TVA أو TTC نهائي (فقط الالتزام).

  • "bon_livraison" — إذا رأيت "BON DE LIVRAISON", "BL N°", "وصل تسليم"،
    مع كميات مسلَّمة (بدون بالضرورة أسعار).

  • "bon_reception" — إذا رأيت "BON DE RÉCEPTION", "BR N°", "وصل استلام".

  • "cheque_bancaire" — إذا رأيت شيكاً (تصميم يشبه الشيك المصرفي)،
    مع كلمات "PAYEZ CONTRE CE CHÈQUE", "المبلغ بالحروف",
    اسم البنك (BNA, CPA, BEA...), رقم الشيك.

  • "recu_paiement" — إذا رأيت "REÇU", "REÇU DE PAIEMENT",
    "وصل استلام مبلغ", "إيصال قبض" مع مبلغ نقدي واحد.

  • "devis" — إذا رأيت "DEVIS", "PROFORMA", "عرض سعر" — عادةً مذكور
    "Ce devis est valable X jours".

  • "unknown" — إذا لم تنطبق أي قاعدة.
"""


# =========================================================
# مولّد القيود لكل نوع
# =========================================================
def build_journal_entry(
    data: Dict[str, Any],
    doc_type_code: str,
    get_account_info,
    determine_tva_account,
    suggest_account_for_item,
) -> Optional[Dict[str, Any]]:
    """
    يبني قيد اليومية المناسب حسب نوع الوثيقة.

    Returns None إذا كان النوع لا يولّد قيداً (bon_commande, devis).
    """
    doc_info = get_doc_type(doc_type_code)
    if not doc_info["generates_journal"]:
        return None

    # مُوجّه لكل نوع
    if doc_type_code == "facture" or doc_type_code == "unknown":
        return _journal_facture_achat(data, get_account_info, determine_tva_account,
                                       suggest_account_for_item)
    elif doc_type_code == "facture_vente":
        return _journal_facture_vente(data, get_account_info, determine_tva_account,
                                       suggest_account_for_item)
    elif doc_type_code == "facture_avoir":
        return _journal_facture_avoir(data, get_account_info, determine_tva_account,
                                       suggest_account_for_item)
    elif doc_type_code in ("bon_livraison", "bon_reception"):
        return _journal_bon_livraison(data, get_account_info, suggest_account_for_item)
    elif doc_type_code == "cheque_bancaire":
        return _journal_cheque(data)
    elif doc_type_code == "recu_paiement":
        return _journal_recu(data)
    return None


# =========================================================
# 1) قيد فاتورة شراء (Facture d'achat)
# =========================================================
def _journal_facture_achat(
    data: Dict[str, Any],
    get_account_info,
    determine_tva_account,
    suggest_account_for_item,
) -> Dict[str, Any]:
    """
    قيد شراء نموذجي:
      Débit  6xx / 2xx     Charges/Immo         HT
      Débit  44566 / 44562 TVA déductible       TVA
      Débit  6414          Droits de timbre     Timbre
      Crédit 401 / 404     Fournisseur          TTC
    """
    entries = []
    items = data.get("items") or []
    totals = data.get("totals") or {}
    supplier = data.get("supplier") or {}
    libelle = _make_libelle(data, "Achat")

    charges_by_account: Dict[str, Dict[str, Any]] = {}
    has_immobilisation = False

    for item in items:
        code = item.get("scf_account") or suggest_account_for_item(item.get("description", "")) or "607"
        ht = item.get("total_ht") or (item.get("quantity", 0) * item.get("unit_price", 0)) or 0

        if code not in charges_by_account:
            info = get_account_info(code)
            charges_by_account[code] = {
                "account": code,
                "name": info["name_fr"] if info else item.get("scf_account_name", ""),
                "amount": 0,
            }
        charges_by_account[code]["amount"] += float(ht)
        if str(code).startswith("2"):
            has_immobilisation = True

    # Débit charges/immo
    for code, info in charges_by_account.items():
        entries.append(_entry(code, info["name"], libelle, debit=info["amount"]))

    # Débit TVA
    tva = totals.get("tva_amount") or 0
    if tva:
        tva_acc = determine_tva_account(has_immobilisation)
        tva_info = get_account_info(tva_acc)
        entries.append(_entry(tva_acc, tva_info["name_fr"] if tva_info else "TVA déductible",
                              libelle, debit=float(tva)))

    # Débit timbre
    stamp = totals.get("stamp_duty") or 0
    if stamp:
        entries.append(_entry("6414", "Droits de timbre", libelle, debit=float(stamp)))

    # Crédit fournisseur
    ttc = totals.get("total_ttc") or 0
    supplier_acc = "404" if has_immobilisation else "401"
    supplier_label = "Fournisseurs d'immobilisations" if has_immobilisation else "Fournisseurs"
    supplier_name = supplier.get("name") or "Fournisseur"
    entries.append(_entry(supplier_acc, f"{supplier_label} - {supplier_name}",
                          libelle, credit=float(ttc)))

    return _wrap_journal(data, "🧾 قيد شراء", libelle, entries)


# =========================================================
# 2) قيد فاتورة بيع (Facture de vente)
# =========================================================
def _journal_facture_vente(
    data: Dict[str, Any],
    get_account_info,
    determine_tva_account,
    suggest_account_for_item,
) -> Dict[str, Any]:
    """
    قيد بيع نموذجي:
      Débit  411            Client                    TTC
      Crédit 700 / 701 / 706 Ventes (marchandises/produits/services) HT
      Crédit 44551          TVA collectée             TVA
      Crédit 445...         Droits de timbre collectés Timbre
    """
    entries = []
    items = data.get("items") or []
    totals = data.get("totals") or {}
    customer = data.get("customer") or {}
    libelle = _make_libelle(data, "Vente")

    # Débit client
    ttc = totals.get("total_ttc") or 0
    customer_name = customer.get("name") or "Client"
    entries.append(_entry("411", f"Clients - {customer_name}", libelle, debit=float(ttc)))

    # Crédit ventes (نجمع حسب نوع البيع)
    # المبيعات عادة تُسجَّل في:
    #   700 - Ventes de marchandises (بضائع)
    #   701 - Ventes de produits finis (منتجات مصنّعة)
    #   706 - Prestations de services (خدمات)
    ventes_by_account: Dict[str, float] = {}
    for item in items:
        # نستنتج حساب البيع من فئة المنتج
        cat = (item.get("category") or "").lower()
        desc = (item.get("description") or "").lower()
        if any(k in cat + desc for k in ["service", "prestation", "خدمة", "استشارة"]):
            acc = "706"; name = "Prestations de services"
        elif any(k in cat + desc for k in ["produit fini", "منتج مصنوع"]):
            acc = "701"; name = "Ventes de produits finis"
        else:
            acc = "700"; name = "Ventes de marchandises"

        ht = item.get("total_ht") or 0
        ventes_by_account[acc] = ventes_by_account.get(acc, 0) + float(ht)

    for acc, amount in ventes_by_account.items():
        name = {"700": "Ventes de marchandises",
                "701": "Ventes de produits finis",
                "706": "Prestations de services"}.get(acc, "Ventes")
        entries.append(_entry(acc, name, libelle, credit=amount))

    # Crédit TVA collectée
    tva = totals.get("tva_amount") or 0
    if tva:
        entries.append(_entry("44551", "TVA collectée", libelle, credit=float(tva)))

    # Crédit timbre
    stamp = totals.get("stamp_duty") or 0
    if stamp:
        entries.append(_entry("44571", "Droits de timbre collectés", libelle, credit=float(stamp)))

    return _wrap_journal(data, "💼 قيد بيع", libelle, entries)


# =========================================================
# 3) قيد فاتورة إرجاع (Avoir) — عكس قيد الشراء
# =========================================================
def _journal_facture_avoir(
    data: Dict[str, Any],
    get_account_info,
    determine_tva_account,
    suggest_account_for_item,
) -> Dict[str, Any]:
    """
    قيد Avoir (فاتورة إرجاع من مورد) — عكس الشراء:
      Débit  401 / 404       Fournisseur (نخفض دينه)   TTC
      Crédit 6xx / 2xx      Charges/Immo (نلغي المصروف) HT
      Crédit 44566          TVA déductible (نلغي)      TVA
    """
    # نفس منطق الشراء لكن معكوس
    entries = []
    items = data.get("items") or []
    totals = data.get("totals") or {}
    supplier = data.get("supplier") or {}
    libelle = _make_libelle(data, "Avoir")

    charges_by_account: Dict[str, Dict[str, Any]] = {}
    has_immo = False

    for item in items:
        code = item.get("scf_account") or suggest_account_for_item(item.get("description", "")) or "607"
        ht = abs(item.get("total_ht") or 0)  # نأخذ القيمة المطلقة
        if code not in charges_by_account:
            info = get_account_info(code)
            charges_by_account[code] = {"account": code,
                                        "name": info["name_fr"] if info else "",
                                        "amount": 0}
        charges_by_account[code]["amount"] += float(ht)
        if str(code).startswith("2"):
            has_immo = True

    # Débit fournisseur (نخفض دينه)
    ttc = abs(totals.get("total_ttc") or 0)
    supplier_acc = "404" if has_immo else "401"
    supplier_name = supplier.get("name") or "Fournisseur"
    entries.append(_entry(supplier_acc, f"Fournisseur (avoir) - {supplier_name}",
                          libelle, debit=float(ttc)))

    # Crédit charges (نلغي المصروف)
    for code, info in charges_by_account.items():
        entries.append(_entry(code, info["name"], libelle, credit=info["amount"]))

    # Crédit TVA (نلغي TVA المدفوع)
    tva = abs(totals.get("tva_amount") or 0)
    if tva:
        tva_acc = determine_tva_account(has_immo)
        tva_info = get_account_info(tva_acc)
        entries.append(_entry(tva_acc, tva_info["name_fr"] if tva_info else "TVA",
                              libelle, credit=float(tva)))

    return _wrap_journal(data, "↩️ قيد إرجاع (Avoir)", libelle, entries)


# =========================================================
# 4) قيد وصل تسليم / استلام (Bon de livraison / réception)
# =========================================================
def _journal_bon_livraison(
    data: Dict[str, Any],
    get_account_info,
    suggest_account_for_item,
) -> Dict[str, Any]:
    """
    قيد BL/BR — دخول مخزون مع فاتورة لم تصل بعد:
      Débit  38 / 31 / 30     Stock                  HT
      Crédit 408              Fournisseurs - Factures non parvenues  TTC (تقديري)

    ملاحظة: القيد النهائي يُعدَّل عند وصول الفاتورة.
    """
    entries = []
    items = data.get("items") or []
    totals = data.get("totals") or {}
    supplier = data.get("supplier") or {}
    libelle = _make_libelle(data, "BL/BR")

    # نجمع المخزون حسب النوع
    stocks_by_account: Dict[str, Dict[str, Any]] = {}
    for item in items:
        # حدّد نوع المخزون
        code = item.get("scf_account", "")
        if code == "600":       stock_acc = "30"; stock_name = "Stocks de marchandises"
        elif code == "601":     stock_acc = "31"; stock_name = "Matières premières"
        elif code == "602":     stock_acc = "32"; stock_name = "Autres approvisionnements"
        else:                   stock_acc = "38"; stock_name = "Achats stockés en transit"

        ht = item.get("total_ht") or (item.get("quantity", 0) * item.get("unit_price", 0)) or 0
        key = stock_acc
        if key not in stocks_by_account:
            stocks_by_account[key] = {"account": key, "name": stock_name, "amount": 0}
        stocks_by_account[key]["amount"] += float(ht)

    # Débit stocks
    for _, info in stocks_by_account.items():
        entries.append(_entry(info["account"], info["name"], libelle, debit=info["amount"]))

    # Crédit fournisseur (facture non parvenue) — بالمبلغ HT إن TTC غير معروف
    total = totals.get("total_ttc") or totals.get("total_ht") or sum(
        s["amount"] for s in stocks_by_account.values()
    )
    supplier_name = supplier.get("name") or "Fournisseur"
    entries.append(_entry("408", f"Factures non parvenues - {supplier_name}",
                          libelle, credit=float(total)))

    return _wrap_journal(data, "🚚 قيد استلام بضاعة", libelle, entries,
                         note="قيد مؤقت — يُعدَّل عند وصول الفاتورة النهائية")


# =========================================================
# 5) قيد شيك بنكي (تسوية دفع بالشيك)
# =========================================================
def _journal_cheque(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    قيد شيك مُسلَّم لمورد:
      Débit  401       Fournisseur (نلغي الدين)   Montant
      Crédit 512       Banque                     Montant

    أو شيك مُستلَم من زبون:
      Débit  512       Banque                     Montant
      Crédit 411       Client                     Montant
    """
    entries = []
    totals = data.get("totals") or {}
    supplier = data.get("supplier") or {}
    customer = data.get("customer") or {}
    libelle = _make_libelle(data, "Chèque")

    # نحاول تحديد الاتجاه من البيانات (بيانات المستفيد)
    amount = totals.get("total_ttc") or 0

    # افتراض: الشيك مُسلَّم لمورد (الحالة الأكثر شيوعاً)
    # إن كانت هناك بيانات customer وليس supplier، فهو مُستلَم من زبون
    if customer.get("name") and not supplier.get("name"):
        # شيك مُستلَم من زبون
        client_name = customer.get("name") or "Client"
        entries.append(_entry("512", "Banque (encaissement chèque)", libelle, debit=float(amount)))
        entries.append(_entry("411", f"Clients - {client_name}", libelle, credit=float(amount)))
    else:
        # شيك مُسلَّم لمورد
        supplier_name = supplier.get("name") or customer.get("name") or "Bénéficiaire"
        entries.append(_entry("401", f"Fournisseurs - {supplier_name}", libelle, debit=float(amount)))
        entries.append(_entry("512", "Banque (émission chèque)", libelle, credit=float(amount)))

    return _wrap_journal(data, "💳 قيد شيك بنكي", libelle, entries)


# =========================================================
# 6) قيد وصل دفع نقدي (Reçu de paiement)
# =========================================================
def _journal_recu(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    قيد وصل دفع نقدي:
      Débit  401       Fournisseur (نلغي الدين)   Montant
      Crédit 530       Caisse                     Montant

    أو استلام نقدي من زبون:
      Débit  530       Caisse                     Montant
      Crédit 411       Client                     Montant
    """
    entries = []
    totals = data.get("totals") or {}
    supplier = data.get("supplier") or {}
    customer = data.get("customer") or {}
    libelle = _make_libelle(data, "Reçu")

    amount = totals.get("total_ttc") or 0

    if customer.get("name") and not supplier.get("name"):
        # استلام من زبون
        client_name = customer.get("name") or "Client"
        entries.append(_entry("530", "Caisse (encaissement)", libelle, debit=float(amount)))
        entries.append(_entry("411", f"Clients - {client_name}", libelle, credit=float(amount)))
    else:
        # دفع لمورد
        supplier_name = supplier.get("name") or customer.get("name") or "Bénéficiaire"
        entries.append(_entry("401", f"Fournisseurs - {supplier_name}", libelle, debit=float(amount)))
        entries.append(_entry("530", "Caisse (paiement)", libelle, credit=float(amount)))

    return _wrap_journal(data, "🧾 قيد وصل دفع", libelle, entries)


# =========================================================
# مساعدات داخلية
# =========================================================
def _make_libelle(data: Dict[str, Any], doc_prefix: str) -> str:
    num = data.get("invoice_number") or data.get("document_number") or ""
    party = (data.get("supplier") or {}).get("name") or \
            (data.get("customer") or {}).get("name") or ""
    parts = [doc_prefix]
    if num:   parts.append(f"N° {num}")
    if party: parts.append(f"- {party}")
    return " ".join(parts).strip()


def _entry(account: str, name: str, libelle: str,
           debit: float = 0, credit: float = 0) -> Dict[str, Any]:
    return {
        "account": account,
        "name": name,
        "libelle": libelle,
        "debit": round(float(debit), 2),
        "credit": round(float(credit), 2),
    }


def _wrap_journal(data: Dict[str, Any], journal_type: str, libelle: str,
                  entries: List[Dict[str, Any]],
                  note: Optional[str] = None) -> Dict[str, Any]:
    total_debit = sum(e["debit"] for e in entries)
    total_credit = sum(e["credit"] for e in entries)
    result = {
        "journal_type": journal_type,
        "date": data.get("invoice_date") or data.get("document_date"),
        "libelle": libelle,
        "entries": entries,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balanced": abs(total_debit - total_credit) < 0.01,
    }
    if note:
        result["note"] = note
    return result


if __name__ == "__main__":
    # اختبار سريع
    print("أنواع الوثائق المدعومة:")
    for code, info in DOCUMENT_TYPES.items():
        journal = "✅" if info["generates_journal"] else "❌"
        stock = "📦" if info["affects_stock"] else "  "
        print(f"  {info['icon']} {code:<20} {journal} قيد  {stock}  {info['label_ar']}")
