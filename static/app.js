/* ==========================================================
   محاسب DZ الذكي v3 — Multi-document analyzer
   ========================================================== */
console.log("%c✅ app.js v5 loaded (Multi-Document)", "color:#7c3aed;font-weight:bold;font-size:14px");

const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let selectedFiles = [];   // ملفات المستخدم المختارة
let batchResult   = null; // ناتج آخر تحليل دفعة
let selectedDocIdx = -1;  // مؤشر الوثيقة المعروضة تفصيلياً

// ==========================================================
// DOM refs
// ==========================================================
const dropZone   = $("#drop-zone");
const fileInput  = $("#file-input");
const previewGrid = $("#preview-grid");
const btnRun     = $("#btn-run");
const btnRunText = $("#btn-run-text");
const btnReset   = $("#btn-reset");
const toast      = $("#toast");
const progressBox  = $("#progress-box");
const progressBar  = $("#progress-bar");
const progressText = $("#progress-text");
const progressCurrent = $("#progress-current");
const resultsCountBadge = $("#results-count");

// إخفاء العناصر عند البداية
if (progressBox) progressBox.hidden = true;
if (toast) toast.hidden = true;

// ==========================================================
// اختيار الملفات (نقر + سحب)
// ==========================================================
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => addFiles(Array.from(e.target.files)));

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
  const files = Array.from(e.dataTransfer.files || []);
  if (files.length) addFiles(files);
});

function addFiles(newFiles) {
  const imageFiles = newFiles.filter(f => f.type.startsWith("image/"));
  if (imageFiles.length !== newFiles.length) {
    showToast("⚠️ بعض الملفات ليست صوراً وتم تجاهلها", "warning");
  }

  const oversized = imageFiles.filter(f => f.size > 10 * 1024 * 1024);
  if (oversized.length) {
    showToast(`⚠️ ${oversized.length} ملف تجاوز 10MB وتم تجاهله`, "warning");
  }

  const valid = imageFiles.filter(f => f.size <= 10 * 1024 * 1024);
  selectedFiles = [...selectedFiles, ...valid].slice(0, 20);

  renderPreviews();
  updateButtons();
}

function renderPreviews() {
  if (selectedFiles.length === 0) {
    previewGrid.innerHTML = "";
    dropZone.classList.remove("has-images");
    return;
  }
  dropZone.classList.add("has-images");
  previewGrid.innerHTML = selectedFiles.map((f, i) => `
    <div class="preview-item" data-idx="${i}">
      <img src="${URL.createObjectURL(f)}" alt="">
      <div class="preview-name">${escapeHtml(f.name)}</div>
      <div class="preview-size">${(f.size / 1024).toFixed(0)} KB</div>
      <button class="preview-remove" onclick="removeFile(${i})">✕</button>
    </div>
  `).join("");
}

window.removeFile = function(idx) {
  selectedFiles.splice(idx, 1);
  renderPreviews();
  updateButtons();
};

function updateButtons() {
  const n = selectedFiles.length;
  btnRun.disabled = (n === 0);
  btnReset.disabled = (n === 0);
  btnRunText.textContent = n === 0
    ? "تحليل الوثائق"
    : (n === 1 ? "تحليل الوثيقة" : `تحليل ${n} وثائق`);
}

// ==========================================================
// إعادة تعيين
// ==========================================================
btnReset.addEventListener("click", () => {
  selectedFiles = [];
  fileInput.value = "";
  renderPreviews();
  updateButtons();
});

// ==========================================================
// زر التحليل — يستدعي /api/analyze_batch
// ==========================================================
btnRun.addEventListener("click", async () => {
  console.log("🖱️ زر التحليل ضُغط، عدد الملفات:", selectedFiles.length);

  if (btnRun.dataset.noKey !== undefined) {
    showToast("⚠️ أضف GEMINI_API_KEY في ملف .env أوّلاً", "warning");
    return;
  }
  if (selectedFiles.length === 0) return;

  btnRun.disabled = true;
  btnReset.disabled = true;
  progressBox.hidden = false;
  updateProgress(0, selectedFiles.length, "بدء المعالجة...");

  const controller = new AbortController();
  // 3 دقائق لكل ملف (تقدير)
  const timeoutMs = Math.max(180000, selectedFiles.length * 90000);
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // شريط تقدّم تقديري (Gemini لا يعطينا progress حقيقي)
  let fakeProgress = 0;
  const fakeInterval = setInterval(() => {
    fakeProgress = Math.min(fakeProgress + 1, selectedFiles.length - 0.3);
    updateProgress(fakeProgress, selectedFiles.length,
      `معالجة الملف ${Math.ceil(fakeProgress)} من ${selectedFiles.length}...`);
  }, 3500);

  try {
    const fd = new FormData();
    selectedFiles.forEach(f => fd.append("files", f));

    console.log(`📤 إرسال ${selectedFiles.length} ملف إلى /api/analyze_batch ...`);
    const res = await fetch("/api/analyze_batch", {
      method: "POST",
      body: fd,
      signal: controller.signal,
    });

    clearInterval(fakeInterval);
    console.log("📥 استجابة:", res.status, res.statusText);

    const contentType = res.headers.get("content-type") || "";
    let data;
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      const text = await res.text();
      throw new Error(`استجابة غير متوقّعة (${res.status}): ${text.slice(0, 300)}`);
    }

    if (!res.ok && !data.stats) {
      throw new Error(data.error || `خطأ ${res.status}`);
    }

    batchResult = data;
    updateProgress(selectedFiles.length, selectedFiles.length, "اكتمل ✓");

    // عرض النتائج
    renderSummary(data);
    renderResultsList(data);
    renderConsolidatedJournal(data);

    const msg = `✅ تمت معالجة ${data.stats.success}/${data.stats.total} وثيقة`;
    showToast(msg, data.stats.failed > 0 ? "warning" : "success");

    // تحديث badge القائمة
    resultsCountBadge.textContent = data.stats.total;
    resultsCountBadge.hidden = false;

    // انتقل مباشرة لعرض النتائج
    setTimeout(() => progressBox.hidden = true, 1200);

  } catch (err) {
    clearInterval(fakeInterval);
    console.error("❌ خطأ:", err);
    let msg = err.message;
    if (err.name === "AbortError") {
      msg = "⏱️ انتهت المهلة. حاول بعدد أقل من الملفات.";
    }
    showToast(msg, "error");
    progressBox.hidden = true;
  } finally {
    clearTimeout(timeoutId);
    btnRun.disabled = false;
    btnReset.disabled = false;
  }
});

function updateProgress(done, total, msg) {
  const pct = total > 0 ? (done / total) * 100 : 0;
  progressBar.style.width = pct + "%";
  progressText.textContent = `${Math.round(done)} / ${total}`;
  if (msg) progressCurrent.textContent = msg;
}

// ==========================================================
// عرض الملخّص السريع
// ==========================================================
function renderSummary(data) {
  $("#empty-summary").hidden = true;
  $("#summary-content").hidden = false;

  const stats = data.stats;
  $("#stat-total").textContent = stats.total;
  $("#stat-success").textContent = stats.success;
  $("#stat-failed").textContent = stats.failed;
  $("#stat-entries").textContent = data.consolidated_journal.length;

  const sums = stats.totals_sum;
  $("#sum-ht").textContent = formatMoney(sums.total_ht);
  $("#sum-tva").textContent = formatMoney(sums.tva_amount);
  $("#sum-ttc").textContent = formatMoney(sums.total_ttc);

  // كشف الأنواع
  const typeList = $("#type-list");
  const types = stats.by_document_type;
  if (Object.keys(types).length === 0) {
    typeList.innerHTML = '<p class="empty-hint">لا توجد بيانات</p>';
  } else {
    typeList.innerHTML = Object.entries(types).map(([code, count]) => {
      const label = getDocTypeLabel(code);
      return `<div class="type-row"><span>${label.icon} ${label.name_ar}</span> <strong>${count}</strong></div>`;
    }).join("");
  }
}

// ==========================================================
// عرض قائمة الوثائق (View: Results)
// ==========================================================
function renderResultsList(data) {
  const listEl = $("#docs-list");
  const results = data.results || [];

  if (results.length === 0) {
    listEl.innerHTML = '<p class="empty-hint">لا توجد وثائق.</p>';
    return;
  }

  listEl.innerHTML = results.map((r, i) => {
    const status = r.success ? "✅" : "❌";
    const docTypeInfo = r.data ? (r.data.document_type_info || {}) : {};
    const icon = docTypeInfo.icon || "❓";
    const typeName = docTypeInfo.label_ar || getDocTypeLabel(r.data?.document_type).name_ar;
    const invoiceNum = r.data?.invoice_number || r.data?.document_number || "—";
    const totalTtc = r.data?.totals?.total_ttc;
    return `
      <div class="doc-item ${r.success ? '' : 'doc-item-failed'}" data-idx="${i}" onclick="selectDoc(${i})">
        <div class="doc-item-header">
          <span class="doc-item-status">${status}</span>
          <span class="doc-item-index">#${r.index}</span>
          <span class="doc-item-icon">${icon}</span>
        </div>
        <div class="doc-item-type">${typeName}</div>
        <div class="doc-item-num">${escapeHtml(invoiceNum)}</div>
        ${totalTtc ? `<div class="doc-item-amount">${formatMoney(totalTtc)}</div>` : ''}
        <div class="doc-item-file">${escapeHtml(r.original_filename)}</div>
      </div>
    `;
  }).join("");

  // اختر الأول تلقائياً
  if (results.length > 0) selectDoc(0);
}

window.selectDoc = function(idx) {
  selectedDocIdx = idx;
  $$(".doc-item").forEach((el, i) => el.classList.toggle("active", i === idx));
  const r = batchResult?.results?.[idx];
  if (r) renderDocDetail(r);
};

// ==========================================================
// عرض تفاصيل وثيقة واحدة
// ==========================================================
function renderDocDetail(r) {
  const detail = $("#doc-detail");
  if (!r.success) {
    detail.innerHTML = `
      <div class="doc-detail-header">
        <h3>❌ فشل التحليل</h3>
        <p>${escapeHtml(r.original_filename)}</p>
      </div>
      <div class="error-block">${escapeHtml(r.error || "خطأ غير معروف")}</div>
    `;
    return;
  }

  const d = r.data || {};
  const dti = d.document_type_info || {};
  const supplier = d.supplier || {};
  const customer = d.customer || {};
  const totals = d.totals || {};
  const items = d.items || [];
  const je = d.journal_entry;
  const bank = d.bank_info || {};

  let html = `
    <div class="doc-detail-header">
      <div>
        <h3>${dti.icon || '📄'} ${dti.label_ar || 'وثيقة'} · ${escapeHtml(d.invoice_number || d.document_number || '—')}</h3>
        <p>${escapeHtml(r.original_filename)} · ${r.model_label} · ${r.elapsed_seconds}s</p>
      </div>
      <div class="detail-actions">
        <a href="${r.source_image}" target="_blank" class="btn btn-ghost">🖼️ عرض الصورة</a>
      </div>
    </div>

    <div class="detail-tabs">
      <button class="dtab active" data-dtab="header">📄 معلومات</button>
      ${items.length ? '<button class="dtab" data-dtab="items">📦 المنتجات + SCF</button>' : ''}
      ${je ? '<button class="dtab" data-dtab="journal">📒 قيد اليومية</button>' : ''}
      <button class="dtab" data-dtab="parties">🏢 الأطراف</button>
      ${bank.bank_name ? '<button class="dtab" data-dtab="bank">💳 بيانات بنكية</button>' : ''}
      <button class="dtab" data-dtab="raw">🔧 JSON</button>
    </div>

    <div class="dtab-content dtab-content-active" data-dtab="header">
      ${renderHeaderTab(d, totals)}
    </div>
    ${items.length ? `<div class="dtab-content" data-dtab="items">${renderItemsTab(items)}</div>` : ''}
    ${je ? `<div class="dtab-content" data-dtab="journal">${renderJournalTab(je, r.index)}</div>` : ''}
    <div class="dtab-content" data-dtab="parties">${renderPartiesTab(supplier, customer)}</div>
    ${bank.bank_name ? `<div class="dtab-content" data-dtab="bank">${renderBankTab(bank)}</div>` : ''}
    <div class="dtab-content" data-dtab="raw">
      <pre class="json-view">${escapeHtml(JSON.stringify(d, null, 2))}</pre>
    </div>
  `;

  detail.innerHTML = html;

  // فعّل التبويبات الفرعية
  detail.querySelectorAll(".dtab").forEach(t => {
    t.addEventListener("click", () => {
      const target = t.dataset.dtab;
      detail.querySelectorAll(".dtab").forEach(x => x.classList.toggle("active", x === t));
      detail.querySelectorAll(".dtab-content").forEach(c =>
        c.classList.toggle("dtab-content-active", c.dataset.dtab === target));
    });
  });
}

function renderHeaderTab(d, totals) {
  const dti = d.document_type_info || {};
  return `
    <div class="field-grid">
      <div class="field-row"><label>نوع الوثيقة:</label>
        <div class="field-value found">${dti.icon || ''} ${dti.label_ar || '—'}</div></div>
      <div class="field-row"><label>رقم الوثيقة:</label>
        <div class="field-value">${escapeHtml(d.invoice_number || d.document_number || '—')}</div></div>
      <div class="field-row"><label>تاريخ الإصدار:</label>
        <div class="field-value">${d.invoice_date || d.document_date || '—'}</div></div>
      ${d.due_date ? `<div class="field-row"><label>تاريخ الاستحقاق:</label><div class="field-value">${d.due_date}</div></div>` : ''}
      ${d.payment_method ? `<div class="field-row"><label>طريقة الدفع:</label><div class="field-value">${escapeHtml(d.payment_method)}</div></div>` : ''}
      ${totals.total_ht  != null ? `<div class="field-row"><label>المبلغ HT:</label><div class="field-value">${formatMoney(totals.total_ht)}</div></div>` : ''}
      ${totals.tva_amount != null ? `<div class="field-row highlight"><label>مبلغ TVA:</label><div class="field-value">${formatMoney(totals.tva_amount)}</div></div>` : ''}
      ${totals.stamp_duty ? `<div class="field-row"><label>حقوق الطابع:</label><div class="field-value">${formatMoney(totals.stamp_duty)}</div></div>` : ''}
      ${totals.total_ttc != null ? `<div class="field-row highlight-strong"><label>المبلغ الإجمالي TTC:</label><div class="field-value">${formatMoney(totals.total_ttc)}</div></div>` : ''}
    </div>
    ${d.notes ? `<div class="notes-block"><h4>📝 ملاحظات</h4><p>${escapeHtml(d.notes)}</p></div>` : ''}
    ${d.confidence_notes ? `<div class="notes-block" style="border-right-color:#d97706"><h4>⚠️ ملاحظات القراءة</h4><p>${escapeHtml(d.confidence_notes)}</p></div>` : ''}
  `;
}

function renderItemsTab(items) {
  const rows = items.map((it, i) => `
    <tr>
      <td>${i + 1}</td>
      <td>${escapeHtml(it.description || '—')}</td>
      <td class="num">${it.quantity ?? '—'}</td>
      <td class="num">${formatNumber(it.unit_price)}</td>
      <td class="num">${it.tva_rate != null ? it.tva_rate + '%' : '—'}</td>
      <td class="num"><strong>${formatNumber(it.total_ht)}</strong></td>
      <td class="scf-cell">
        ${it.scf_account
          ? `<span class="scf-badge">${escapeHtml(it.scf_account)}</span>`
          : '<span class="scf-badge scf-badge-empty">—</span>'}
        ${it.category ? `<div class="scf-category">${escapeHtml(it.category)}</div>` : ''}
      </td>
    </tr>
  `).join("");
  return `
    <table class="items-table">
      <thead><tr>
        <th>#</th><th>الوصف</th><th>الكمية</th><th>سعر الوحدة</th>
        <th>TVA</th><th>الإجمالي HT</th><th>🏦 حساب SCF</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderJournalTab(je, docIdx) {
  const rows = je.entries.map(e => `
    <tr>
      <td class="je-account"><strong>${escapeHtml(e.account)}</strong></td>
      <td class="je-name">${escapeHtml(e.name || '')}</td>
      <td class="je-libelle">${escapeHtml(e.libelle || '')}</td>
      <td class="je-debit num">${e.debit ? formatNumber(e.debit) : ''}</td>
      <td class="je-credit num">${e.credit ? formatNumber(e.credit) : ''}</td>
    </tr>
  `).join("");
  const badgeClass = je.balanced ? "je-balanced" : "je-unbalanced";
  const badgeText  = je.balanced ? "✅ متوازن" : "⚠️ غير متوازن";
  return `
    <div class="journal-header">
      <div class="journal-info">
        <div><strong>${je.journal_type || '📒 قيد'}</strong></div>
        <div><strong>📅 التاريخ:</strong> ${je.date || '—'}</div>
        <div><strong>📝 البيان:</strong> ${escapeHtml(je.libelle || '')}</div>
      </div>
      <div class="journal-badge ${badgeClass}">${badgeText}</div>
    </div>
    ${je.note ? `<div class="notes-block"><p>ℹ️ ${escapeHtml(je.note)}</p></div>` : ''}
    <table class="journal-table">
      <thead><tr>
        <th>الحساب</th><th>التسمية</th><th>البيان</th><th>مدين</th><th>دائن</th>
      </tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr>
        <td colspan="3"><strong>المجموع</strong></td>
        <td class="num"><strong>${formatNumber(je.total_debit)}</strong></td>
        <td class="num"><strong>${formatNumber(je.total_credit)}</strong></td>
      </tr></tfoot>
    </table>
    <div class="journal-actions">
      <button class="btn btn-ghost" onclick="copyJournalToClipboard(${docIdx})">📋 نسخ القيد</button>
      <button class="btn btn-ghost" onclick="exportSingleJournalCSV(${docIdx})">📥 تصدير CSV</button>
    </div>
  `;
}

function renderPartiesTab(supplier, customer) {
  const renderParty = (title, party) => {
    const fields = ["name", "address", "phone", "email", "nif", "rc", "nis", "ai"];
    const labels = {
      name: "الاسم", address: "العنوان", phone: "الهاتف", email: "البريد",
      nif: "NIF", rc: "RC", nis: "NIS", ai: "AI"
    };
    const rows = fields
      .filter(k => party[k])
      .map(k => `<div class="field-row"><label>${labels[k]}:</label><div class="field-value found">${escapeHtml(party[k])}</div></div>`)
      .join("");
    return `<div class="party-block"><h3>${title}</h3>${rows || '<p class="empty-hint" style="padding:12px">لا توجد بيانات</p>'}</div>`;
  };
  return renderParty("🏢 المورّد (Fournisseur)", supplier) +
         renderParty("👤 الزبون (Client)", customer);
}

function renderBankTab(bank) {
  const rows = [
    ["اسم البنك", bank.bank_name],
    ["رقم الشيك", bank.cheque_number],
    ["رقم الحساب (RIB)", bank.account_number],
    ["المستفيد", bank.beneficiary],
    ["المبلغ بالحروف", bank.amount_in_words],
  ].filter(([_, v]) => v).map(([l, v]) =>
    `<div class="field-row"><label>${l}:</label><div class="field-value found">${escapeHtml(v)}</div></div>`
  ).join("");
  return `<div class="field-grid">${rows}</div>`;
}

// ==========================================================
// الدفتر المُوحَّد
// ==========================================================
function renderConsolidatedJournal(data) {
  const container = $("#consolidated-journal");
  const journals = data.consolidated_journal || [];

  if (journals.length === 0) {
    container.innerHTML = '<p class="empty-hint">لم يتم توليد أي قيد.</p>';
    return;
  }

  let html = "";
  journals.forEach(j => {
    const je = j.journal_entry;
    const rows = je.entries.map(e => `
      <tr>
        <td class="je-account"><strong>${escapeHtml(e.account)}</strong></td>
        <td class="je-name">${escapeHtml(e.name || '')}</td>
        <td class="je-debit num">${e.debit ? formatNumber(e.debit) : ''}</td>
        <td class="je-credit num">${e.credit ? formatNumber(e.credit) : ''}</td>
      </tr>
    `).join("");
    html += `
      <div class="grand-livre-entry">
        <div class="gle-header">
          <div>
            <strong>${je.journal_type || '📒'}</strong> · #${j.document_index} · ${je.date || '—'}
          </div>
          <div>${escapeHtml(j.document_filename)}</div>
        </div>
        <div class="gle-libelle">📝 ${escapeHtml(je.libelle || '')}</div>
        <table class="journal-table">
          <thead><tr><th>الحساب</th><th>التسمية</th><th>مدين</th><th>دائن</th></tr></thead>
          <tbody>${rows}</tbody>
          <tfoot><tr>
            <td colspan="2"><strong>مجموع</strong></td>
            <td class="num"><strong>${formatNumber(je.total_debit)}</strong></td>
            <td class="num"><strong>${formatNumber(je.total_credit)}</strong></td>
          </tr></tfoot>
        </table>
      </div>
    `;
  });

  // إجمالي الدفتر
  const grandDebit  = journals.reduce((s, j) => s + (j.journal_entry.total_debit || 0), 0);
  const grandCredit = journals.reduce((s, j) => s + (j.journal_entry.total_credit || 0), 0);
  html = `
    <div class="grand-livre-total">
      <div>🧮 <strong>إجمالي الدفتر:</strong> ${journals.length} قيد</div>
      <div>مجموع مدين: <strong style="color:var(--success)">${formatMoney(grandDebit)}</strong></div>
      <div>مجموع دائن: <strong style="color:var(--danger)">${formatMoney(grandCredit)}</strong></div>
    </div>
  ` + html;

  container.innerHTML = html;
}

// ==========================================================
// تصدير القيود
// ==========================================================
window.copyJournalToClipboard = function(docIdx) {
  const r = batchResult?.results?.[docIdx];
  const je = r?.data?.journal_entry;
  if (!je) return;
  let text = `${je.journal_type || 'Journal Entry'}\nDate: ${je.date}\nLibellé: ${je.libelle}\n\n`;
  text += "Compte  | Nom".padEnd(50) + " | Débit         | Crédit\n";
  text += "-".repeat(90) + "\n";
  je.entries.forEach(e => {
    text += `${e.account.padEnd(7)} | ${(e.name || "").padEnd(40).slice(0, 40)} | ` +
            `${(e.debit ? formatNumber(e.debit) : "").padStart(13)} | ` +
            `${(e.credit ? formatNumber(e.credit) : "").padStart(13)}\n`;
  });
  text += "-".repeat(90) + "\n";
  text += `Total`.padEnd(50) + ` | ${formatNumber(je.total_debit).padStart(13)} | ${formatNumber(je.total_credit).padStart(13)}\n`;

  navigator.clipboard.writeText(text).then(() => showToast("✅ تم نسخ القيد", "success"));
};

window.exportSingleJournalCSV = function(docIdx) {
  const r = batchResult?.results?.[docIdx];
  const je = r?.data?.journal_entry;
  if (!je) return;
  exportJournalsAsCSV([{
    document_filename: r.original_filename,
    document_index: r.index,
    journal_entry: je
  }], `journal_doc${r.index}_${je.date || ''}.csv`);
};

window.exportAllJournalsCSV = function() {
  if (!batchResult?.consolidated_journal?.length) {
    showToast("لا توجد قيود للتصدير", "warning");
    return;
  }
  exportJournalsAsCSV(batchResult.consolidated_journal, `grand_livre_${batchResult.batch_id}.csv`);
};

function exportJournalsAsCSV(journals, filename) {
  let csv = "Doc#,Fichier,Type,Date,Compte,Nom,Libellé,Débit,Crédit\n";
  journals.forEach(j => {
    const je = j.journal_entry;
    je.entries.forEach(e => {
      const row = [
        j.document_index,
        `"${(j.document_filename || '').replace(/"/g, '""')}"`,
        `"${(je.journal_type || '').replace(/"/g, '""')}"`,
        je.date || "",
        e.account,
        `"${(e.name || '').replace(/"/g, '""')}"`,
        `"${(e.libelle || '').replace(/"/g, '""')}"`,
        e.debit || "",
        e.credit || "",
      ].join(",");
      csv += row + "\n";
    });
  });
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
  showToast("✅ تم تصدير CSV", "success");
}

// ==========================================================
// تبديل الـ views
// ==========================================================
window.switchView = function(view) {
  $$(".view").forEach(v => v.classList.remove("active"));
  $(`#view-${view}`).classList.add("active");
  $$(".menu-item").forEach(m => m.classList.toggle("active", m.dataset.view === view));
};

$$(".menu-item").forEach(item => {
  if (item.dataset.view) {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      switchView(item.dataset.view);
    });
  }
});

// ==========================================================
// أدوات مساعدة
// ==========================================================
function formatNumber(n) {
  if (n == null) return "—";
  if (typeof n !== "number") return String(n);
  return new Intl.NumberFormat("fr-DZ", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(n);
}
function formatMoney(n) {
  if (n == null) return "—";
  return formatNumber(n) + " DA";
}
function escapeHtml(s) {
  return (s ?? "").toString().replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
function showToast(msg, type = "error") {
  toast.textContent = msg;
  toast.className = "toast " + (type === "success" ? "success" : type === "warning" ? "warning" : "");
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 4500);
}

const DOC_TYPE_LABELS = {
  facture:        { icon: "🧾", name_ar: "فاتورة شراء" },
  facture_vente:  { icon: "💼", name_ar: "فاتورة بيع" },
  facture_avoir:  { icon: "↩️", name_ar: "فاتورة إرجاع" },
  bon_commande:   { icon: "📋", name_ar: "طلبية" },
  bon_livraison:  { icon: "🚚", name_ar: "وصل تسليم" },
  bon_reception:  { icon: "📥", name_ar: "وصل استلام" },
  cheque_bancaire:{ icon: "💳", name_ar: "شيك بنكي" },
  recu_paiement:  { icon: "🧾", name_ar: "وصل دفع" },
  devis:          { icon: "📝", name_ar: "عرض سعر" },
  unknown:        { icon: "❓", name_ar: "غير محدّد" },
};
function getDocTypeLabel(code) {
  return DOC_TYPE_LABELS[code] || DOC_TYPE_LABELS.unknown;
}
