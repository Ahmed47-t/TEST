/* ==========================================================
   محاسب DZ الذكي — منطق الواجهة (v3 - Gemini Vision)
   ========================================================== */
console.log("%c✅ app.js v3 loaded (Gemini Vision)", "color:#7c3aed;font-weight:bold;font-size:14px");

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let selectedFile = null;
let lastResult = null;

// ----------------------------------------------------------
// عناصر DOM
// ----------------------------------------------------------
const dropZone   = $("#drop-zone");
const fileInput  = $("#file-input");
const preview    = $("#preview");
const btnRun     = $("#btn-run");
const btnReset   = $("#btn-reset");
const loader     = $("#loader");
const loaderDetail = $("#loader-detail");
const toast      = $("#toast");
const jsonView   = $("#json-view");
const btnDownload = $("#btn-download");
const modelStatus = $("#model-status");
const msModel    = $("#ms-model");
const msTime     = $("#ms-time");
const msValidation = $("#ms-validation");

// ----------------------------------------------------------
// رفع الصورة (نقر + سحب/إفلات)
// ----------------------------------------------------------
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => handleFile(e.target.files[0]));

["dragenter", "dragover"].forEach(ev =>
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach(ev =>
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.remove("dragover");
  })
);
dropZone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files?.[0];
  if (file) handleFile(file);
});

function handleFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    showToast("يجب أن يكون الملف صورة (JPG, PNG, WEBP...)", "error");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast("حجم الصورة يتجاوز 10 ميغابايت.", "error");
    return;
  }
  selectedFile = file;
  preview.src = URL.createObjectURL(file);
  dropZone.classList.add("has-image");
  btnRun.disabled = false;
  btnReset.disabled = false;
  console.log("📁 صورة محدّدة:", file.name, `(${(file.size/1024).toFixed(1)} KB)`);
}

// ----------------------------------------------------------
// إعادة تعيين
// ----------------------------------------------------------
btnReset.addEventListener("click", () => {
  selectedFile = null;
  lastResult = null;
  fileInput.value = "";
  preview.src = "";
  dropZone.classList.remove("has-image");
  btnRun.disabled = true;
  btnReset.disabled = true;
  modelStatus.hidden = true;

  $$(".field-value").forEach(el => {
    el.textContent = "—";
    el.classList.remove("found", "missing");
  });
  $("#items-container").innerHTML = '<p class="empty-hint">ستظهر هنا قائمة المنتجات بعد التحليل.</p>';
  $("#notes-block").hidden = true;
  jsonView.textContent = "// سيظهر ناتج JSON هنا بعد التحليل";
  btnDownload.hidden = true;
});

// ----------------------------------------------------------
// زر التحليل
// ----------------------------------------------------------
// إخفاء الـ loader في بداية تحميل الصفحة (احتياط)
if (loader) loader.hidden = true;
if (toast)  toast.hidden = true;

btnRun.addEventListener("click", async () => {
  console.log("🖱️ زر التحليل ضُغط");

  if (btnRun.dataset.noKey !== undefined) {
    showToast("⚠️ أضف GEMINI_API_KEY في ملف .env أوّلاً", "warning");
    return;
  }
  if (!selectedFile) {
    showToast("اختر صورة أوّلاً", "error");
    return;
  }

  loader.hidden = false;
  if (loaderDetail) loaderDetail.textContent = "نجرّب Gemini 2.5 Pro أوّلاً (الأدق)...";
  btnRun.disabled = true;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3 * 60 * 1000);

  try {
    const fd = new FormData();
    fd.append("file", selectedFile);

    console.log("📤 إرسال POST /api/analyze ...");
    const res = await fetch("/api/analyze", {
      method: "POST",
      body: fd,
      signal: controller.signal,
    });

    console.log("📥 استجابة:", res.status, res.statusText);

    const contentType = res.headers.get("content-type") || "";
    let data;
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      const text = await res.text();
      throw new Error(`استجابة غير متوقّعة (${res.status}): ${text.slice(0, 300)}`);
    }

    if (!data.success) {
      throw new Error(data.error || `خطأ ${res.status}`);
    }

    lastResult = data;
    renderResults(data);

    const msg = `✅ تم التحليل بواسطة ${data.model_label} في ${data.elapsed_seconds}s`;
    showToast(msg, "success");

  } catch (err) {
    console.error("❌ خطأ:", err);
    let msg = err.message;
    if (err.name === "AbortError") {
      msg = "⏱️ انتهت المهلة (3 دقائق). حاول بصورة أصغر.";
    } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
      msg = "❌ انقطع الاتصال بالخادم. تحقّق من نافذة PowerShell.";
    }
    showToast(msg, "error");
  } finally {
    clearTimeout(timeoutId);
    loader.hidden = true;
    btnRun.disabled = false;
  }
});

// ----------------------------------------------------------
// عرض النتائج
// ----------------------------------------------------------
function renderResults(payload) {
  const data = payload.data || {};

  // 1) بيانات الفاتورة (المستوى الأعلى)
  ["invoice_number", "invoice_date", "due_date", "document_type",
   "payment_method", "payment_terms"].forEach(key => {
    setField(key, data[key]);
  });

  // ملاحظات
  if (data.notes) {
    $("#notes-block").hidden = false;
    $("#notes-content").textContent = data.notes;
  } else {
    $("#notes-block").hidden = true;
  }

  // 2) المورّد والزبون (nested)
  ["supplier", "customer"].forEach(party => {
    const partyData = data[party] || {};
    ["name", "address", "phone", "nif", "rc", "nis", "ai"].forEach(field => {
      setField(`${party}.${field}`, partyData[field]);
    });
  });

  // 3) المنتجات
  renderItems(data.items || []);

  // 3.5) قيد اليومية (SCF)
  renderJournal(data.journal_entry);

  // 4) المجاميع
  const totals = data.totals || {};
  ["total_ht", "tva_amount", "stamp_duty", "discount", "total_ttc"].forEach(k => {
    setField(`totals.${k}`, formatMoney(totals[k], totals.currency));
  });
  setField("totals.currency", totals.currency || "DZD");

  // 5) JSON
  jsonView.textContent = JSON.stringify(data, null, 2);
  btnDownload.hidden = false;

  // 6) معلومات النموذج
  modelStatus.hidden = false;
  msModel.textContent = payload.model_label || "—";
  msTime.textContent = `${payload.elapsed_seconds}s`;

  const validation = payload.validation || {};
  if (validation.passed) {
    msValidation.textContent = "✅ نجح";
    msValidation.className = "success";
  } else if (validation.warnings && validation.warnings.length > 0) {
    msValidation.textContent = `⚠️ ${validation.warnings.length} تنبيه`;
    msValidation.className = "warning";
    // اطبع التنبيهات في console للتشخيص
    validation.warnings.forEach(w => console.warn(w));
  } else {
    msValidation.textContent = "—";
    msValidation.className = "";
  }
}

function setField(key, value) {
  const el = document.querySelector(`.field-value[data-key="${key}"]`);
  if (!el) return;

  if (value === null || value === undefined || value === "" || value === "null") {
    el.textContent = "—";
    el.classList.add("missing");
    el.classList.remove("found");
  } else {
    el.textContent = value;
    el.classList.add("found");
    el.classList.remove("missing");
  }
}

function renderItems(items) {
  const container = $("#items-container");
  if (!items || items.length === 0) {
    container.innerHTML = '<p class="empty-hint">لا توجد منتجات مُستخرجة.</p>';
    return;
  }

  const rows = items.map((it, i) => `
    <tr>
      <td>${i + 1}</td>
      <td>${escapeHtml(it.description || "—")}</td>
      <td class="num">${it.quantity ?? "—"}</td>
      <td class="num">${formatNumber(it.unit_price)}</td>
      <td class="num">${it.tva_rate !== null && it.tva_rate !== undefined ? it.tva_rate + "%" : "—"}</td>
      <td class="num"><strong>${formatNumber(it.total_ht)}</strong></td>
      <td class="scf-cell">
        ${it.scf_account
          ? `<span class="scf-badge">${escapeHtml(it.scf_account)}</span>`
          : '<span class="scf-badge scf-badge-empty">—</span>'}
        ${it.category ? `<div class="scf-category">${escapeHtml(it.category)}</div>` : ''}
        ${it.scf_account_name ? `<div class="scf-name">${escapeHtml(it.scf_account_name)}</div>` : ''}
      </td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table class="items-table">
      <thead>
        <tr>
          <th>#</th>
          <th>الوصف</th>
          <th>الكمية</th>
          <th>سعر الوحدة</th>
          <th>TVA %</th>
          <th>الإجمالي HT</th>
          <th>🏦 حساب SCF</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ----------------------------------------------------------
// عرض قيد اليومية (SCF Journal Entry)
// ----------------------------------------------------------
function renderJournal(journal) {
  const container = $("#journal-container");
  if (!journal || !journal.entries || journal.entries.length === 0) {
    container.innerHTML = '<p class="empty-hint">قيد اليومية غير متاح.</p>';
    return;
  }

  const rows = journal.entries.map(e => `
    <tr>
      <td class="je-account"><strong>${escapeHtml(e.account)}</strong></td>
      <td class="je-name">${escapeHtml(e.name || "")}</td>
      <td class="je-libelle">${escapeHtml(e.libelle || "")}</td>
      <td class="je-debit num">${e.debit ? formatNumber(e.debit) : ""}</td>
      <td class="je-credit num">${e.credit ? formatNumber(e.credit) : ""}</td>
    </tr>
  `).join("");

  const badgeClass = journal.balanced ? "je-balanced" : "je-unbalanced";
  const badgeText  = journal.balanced ? "✅ القيد متوازن" : "⚠️ القيد غير متوازن";

  container.innerHTML = `
    <div class="journal-header">
      <div class="journal-info">
        <div><strong>📅 التاريخ:</strong> ${journal.date || "—"}</div>
        <div><strong>📝 البيان:</strong> ${escapeHtml(journal.libelle || "")}</div>
      </div>
      <div class="journal-badge ${badgeClass}">${badgeText}</div>
    </div>

    <table class="journal-table">
      <thead>
        <tr>
          <th>الحساب</th>
          <th>التسمية</th>
          <th>البيان</th>
          <th>مدين (Débit)</th>
          <th>دائن (Crédit)</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
      <tfoot>
        <tr>
          <td colspan="3"><strong>المجموع</strong></td>
          <td class="num"><strong>${formatNumber(journal.total_debit)}</strong></td>
          <td class="num"><strong>${formatNumber(journal.total_credit)}</strong></td>
        </tr>
      </tfoot>
    </table>

    <div class="journal-actions">
      <button class="btn btn-ghost" onclick="copyJournalToClipboard()">📋 نسخ القيد</button>
      <button class="btn btn-ghost" onclick="exportJournalCSV()">📥 تصدير CSV</button>
    </div>
  `;
}

// نسخ قيد اليومية إلى الحافظة (تنسيق نصّي)
window.copyJournalToClipboard = function() {
  if (!lastResult?.data?.journal_entry) return;
  const je = lastResult.data.journal_entry;
  let text = `Date: ${je.date}\nLibellé: ${je.libelle}\n\n`;
  text += "Compte  | Nom".padEnd(50) + " | Débit         | Crédit\n";
  text += "-".repeat(90) + "\n";
  je.entries.forEach(e => {
    const line = `${e.account.padEnd(7)} | ${(e.name || "").padEnd(40).slice(0, 40)} | ${
      (e.debit ? formatNumber(e.debit) : "").padStart(13)
    } | ${
      (e.credit ? formatNumber(e.credit) : "").padStart(13)
    }`;
    text += line + "\n";
  });
  text += "-".repeat(90) + "\n";
  text += `Total`.padEnd(50) + ` | ${formatNumber(je.total_debit).padStart(13)} | ${formatNumber(je.total_credit).padStart(13)}\n`;

  navigator.clipboard.writeText(text).then(() => {
    showToast("✅ تم نسخ القيد إلى الحافظة", "success");
  });
};

// تصدير قيد اليومية كـ CSV
window.exportJournalCSV = function() {
  if (!lastResult?.data?.journal_entry) return;
  const je = lastResult.data.journal_entry;
  let csv = "Date,Compte,Nom,Libellé,Débit,Crédit\n";
  je.entries.forEach(e => {
    const row = [
      je.date || "",
      e.account,
      `"${(e.name || "").replace(/"/g, '""')}"`,
      `"${(e.libelle || "").replace(/"/g, '""')}"`,
      e.debit || "",
      e.credit || "",
    ].join(",");
    csv += row + "\n";
  });

  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `journal_${je.date || "invoice"}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};

// ----------------------------------------------------------
// أدوات مساعدة
// ----------------------------------------------------------
function formatNumber(n) {
  if (n === null || n === undefined) return "—";
  if (typeof n !== "number") return String(n);
  return new Intl.NumberFormat("fr-DZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function formatMoney(n, currency) {
  if (n === null || n === undefined) return null;
  const num = formatNumber(n);
  return `${num} ${currency || "دج"}`;
}

function escapeHtml(s) {
  return (s || "").toString().replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function showToast(msg, type = "error") {
  // للرسائل الطويلة (متعدّدة الأسطر)، نستعمل modal بدل toast
  if (msg.includes("\n") && msg.length > 100) {
    showModal(msg, type);
    return;
  }
  toast.textContent = msg;
  toast.className = "toast " + (type === "success" ? "success" : type === "warning" ? "warning" : "");
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 5000);
}

function showModal(msg, type = "error") {
  // إنشاء modal بسيط للرسائل الطويلة
  const existing = document.getElementById("error-modal");
  if (existing) existing.remove();

  const modal = document.createElement("div");
  modal.id = "error-modal";
  modal.style.cssText = `
    position: fixed; inset: 0; background: rgba(15,23,42,0.7);
    display: grid; place-items: center; z-index: 1001;
    backdrop-filter: blur(6px);
  `;
  const bgColor = type === "error" ? "#dc2626" : type === "warning" ? "#d97706" : "#059669";
  modal.innerHTML = `
    <div style="background:#fff; padding:28px 32px; border-radius:12px;
                max-width:520px; box-shadow:0 20px 40px rgba(0,0,0,.3);
                direction:rtl; text-align:right; border-top:5px solid ${bgColor}">
      <pre style="white-space:pre-wrap; font-family:'Cairo',sans-serif;
                  font-size:14px; line-height:1.8; color:#1f2937; margin:0">${escapeHtml(msg)}</pre>
      <button onclick="document.getElementById('error-modal').remove()"
              style="margin-top:20px; padding:10px 20px; background:${bgColor};
                     color:#fff; border:none; border-radius:8px; cursor:pointer;
                     font-family:'Cairo',sans-serif; font-weight:700; width:100%">
        فهمت ✓
      </button>
    </div>
  `;
  document.body.appendChild(modal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.remove();
  });
}

// ----------------------------------------------------------
// التبويبات
// ----------------------------------------------------------
$$(".tab").forEach(t => {
  t.addEventListener("click", () => {
    const target = t.dataset.tab;
    $$(".tab").forEach(x => x.classList.toggle("active", x === t));
    $$(".tab-content").forEach(c => c.classList.toggle("active", c.dataset.tab === target));
  });
});

// ----------------------------------------------------------
// تحميل JSON
// ----------------------------------------------------------
btnDownload.addEventListener("click", () => {
  if (!lastResult) return;
  const blob = new Blob(
    [JSON.stringify(lastResult, null, 2)],
    { type: "application/json" }
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `invoice_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
});
