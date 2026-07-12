/* ==========================================================
   محاسب DZ الذكي v4 — Multi-Company Analyzer
   ========================================================== */
console.log("%c✅ app.js v6 loaded (Multi-Company)", "color:#7c3aed;font-weight:bold");

const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ==========================================================
// State
// ==========================================================
let currentCompany = null;   // الشركة المُختارة حالياً
let selectedFiles  = [];     // ملفات جاهزة للتحليل
let batchResult    = null;   // نتيجة آخر دفعة تحليل
let selectedDocIdx = -1;     // مؤشر الوثيقة المعروضة

// ==========================================================
// DOM refs (Views + Sidebar)
// ==========================================================
const sidebar = $("#sidebar");
const toast = $("#toast");
if (toast) toast.hidden = true;

// ==========================================================
// عند فتح الصفحة: تحميل الشركات
// ==========================================================
document.addEventListener("DOMContentLoaded", () => {
  loadCompaniesList();
  setupColorPicker();
});

// ==========================================================
// تحميل قائمة الشركات
// ==========================================================
async function loadCompaniesList() {
  try {
    const res = await fetch("/api/companies");
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    renderCompaniesGrid(data.companies);
  } catch (err) {
    showToast("❌ فشل تحميل الشركات: " + err.message, "error");
  }
}

function renderCompaniesGrid(companies) {
  const grid = $("#companies-grid");
  if (!companies || companies.length === 0) {
    grid.innerHTML = `
      <div class="empty-hint" style="grid-column: 1 / -1">
        <div style="font-size:48px; margin-bottom:12px">🏢</div>
        <p style="font-size:16px; margin-bottom:8px">لا توجد شركات بعد</p>
        <p>ابدأ بإضافة شركتك الأولى باستعمال الزر أعلاه</p>
      </div>`;
    return;
  }
  grid.innerHTML = companies.map(c => {
    const stats = c.stats || {};
    const initials = c.name.slice(0, 2).toUpperCase();
    return `
      <div class="company-card" onclick="selectCompany('${c.id}')">
        <div class="company-card-header">
          <div class="company-avatar" style="background: linear-gradient(135deg, ${c.logo_color || '#2563eb'}, ${adjustColor(c.logo_color || '#2563eb', -30)})">${escapeHtml(initials)}</div>
          <div class="company-actions">
            <button class="icon-btn" onclick="event.stopPropagation(); editCompany('${c.id}')" title="تعديل">✏️</button>
            <button class="icon-btn icon-btn-danger" onclick="event.stopPropagation(); confirmDeleteCompany('${c.id}', '${escapeHtml(c.name).replace(/'/g, "\\'")}')" title="حذف">🗑️</button>
          </div>
        </div>
        <div class="company-name">${escapeHtml(c.name)}</div>
        ${c.activity ? `<div class="company-activity">${escapeHtml(c.activity)}</div>` : ''}
        <div class="company-meta">
          ${c.nif ? `<div><strong>NIF:</strong> ${escapeHtml(c.nif)}</div>` : ''}
          ${c.rc  ? `<div><strong>RC:</strong> ${escapeHtml(c.rc)}</div>` : ''}
        </div>
        <div class="company-stats">
          <span title="عدد الوثائق">📄 ${stats.uploads_count || 0}</span>
          <span title="عدد القيود">📒 ${stats.journal_entries_count || 0}</span>
        </div>
      </div>`;
  }).join("");
}

// ==========================================================
// اختيار شركة
// ==========================================================
async function selectCompany(companyId) {
  try {
    const res = await fetch(`/api/companies/${companyId}/select`, { method: "POST" });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    currentCompany = data.company;
    showCompanyInSidebar(data.company);

    // إظهار الشريط الجانبي والانتقال للتحليل
    sidebar.hidden = false;
    document.body.classList.add("has-sidebar");
    switchView("upload");
  } catch (err) {
    showToast("❌ " + err.message, "error");
  }
}

function showCompanyInSidebar(company) {
  $("#current-company-name").textContent = company.name;
  const meta = [company.nif && `NIF: ${company.nif}`, company.activity].filter(Boolean).join(" · ");
  $("#current-company-nif").textContent = meta || "—";
  const initials = company.name.slice(0, 2).toUpperCase();
  const logo = $("#brand-logo");
  logo.textContent = initials;
  logo.style.background = `linear-gradient(135deg, ${company.logo_color || '#2563eb'}, ${adjustColor(company.logo_color || '#2563eb', -30)})`;
}

// ==========================================================
// نموذج إنشاء/تعديل شركة
// ==========================================================
window.openCompanyForm = function(company = null) {
  const modal = $("#company-form-modal");
  $("#company-form-title").textContent = company ? "تعديل الشركة" : "إضافة شركة جديدة";
  $("#company-id").value = company?.id || "";
  $("#c-name").value = company?.name || "";
  $("#c-activity").value = company?.activity || "";
  $("#c-nif").value = company?.nif || "";
  $("#c-rc").value  = company?.rc  || "";
  $("#c-nis").value = company?.nis || "";
  $("#c-ai").value  = company?.ai  || "";
  $("#c-address").value = company?.address || "";
  $("#c-phone").value = company?.phone || "";
  $("#c-email").value = company?.email || "";
  const color = company?.logo_color || "#2563eb";
  $("#c-logo-color").value = color;
  $$(".color-swatch").forEach(s => s.classList.toggle("selected", s.dataset.color === color));
  modal.hidden = false;
};

window.closeCompanyForm = function() {
  $("#company-form-modal").hidden = true;
};

window.submitCompanyForm = async function(e) {
  e.preventDefault();
  const btn = $("#submit-company-btn");
  btn.disabled = true;
  btn.textContent = "جارٍ الحفظ...";

  const payload = {
    name: $("#c-name").value.trim(),
    activity: $("#c-activity").value.trim(),
    nif: $("#c-nif").value.trim(),
    rc: $("#c-rc").value.trim(),
    nis: $("#c-nis").value.trim(),
    ai: $("#c-ai").value.trim(),
    address: $("#c-address").value.trim(),
    phone: $("#c-phone").value.trim(),
    email: $("#c-email").value.trim(),
    logo_color: $("#c-logo-color").value,
  };
  const companyId = $("#company-id").value;

  try {
    const url = companyId ? `/api/companies/${companyId}` : "/api/companies";
    const method = companyId ? "PATCH" : "POST";
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    showToast(companyId ? "✅ تم تحديث الشركة" : "✅ تم إنشاء الشركة", "success");
    closeCompanyForm();
    loadCompaniesList();
  } catch (err) {
    showToast("❌ " + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "حفظ الشركة";
  }
  return false;
};

window.editCompany = async function(companyId) {
  try {
    const res = await fetch(`/api/companies/${companyId}`);
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    openCompanyForm(data.company);
  } catch (err) {
    showToast("❌ " + err.message, "error");
  }
};

window.confirmDeleteCompany = function(companyId, companyName) {
  showConfirm(
    `حذف شركة "${companyName}"`,
    `⚠️ سيتم حذف الشركة وكل بياناتها (الوثائق، القيود، الدفتر) نهائياً.\n\nهل أنت متأكّد؟`,
    async (ok) => {
      if (!ok) return;
      try {
        const res = await fetch(`/api/companies/${companyId}?delete_data=1`, { method: "DELETE" });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        showToast("🗑️ تم حذف الشركة نهائياً", "success");
        loadCompaniesList();
      } catch (err) {
        showToast("❌ " + err.message, "error");
      }
    }
  );
};

// ==========================================================
// Color picker
// ==========================================================
function setupColorPicker() {
  $$(".color-swatch").forEach(s => {
    s.addEventListener("click", (e) => {
      e.preventDefault();
      $$(".color-swatch").forEach(x => x.classList.remove("selected"));
      s.classList.add("selected");
      $("#c-logo-color").value = s.dataset.color;
    });
  });
}

function adjustColor(hex, amount) {
  // تعديل بسيط للسطوع
  const num = parseInt(hex.slice(1), 16);
  const r = Math.max(0, Math.min(255, (num >> 16) + amount));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 0xff) + amount));
  const b = Math.max(0, Math.min(255, (num & 0xff) + amount));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

// ==========================================================
// رفع الوثائق (Drop zone)
// ==========================================================
document.addEventListener("DOMContentLoaded", () => {
  const dropZone = $("#drop-zone");
  const fileInput = $("#file-input");
  if (!dropZone) return;

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

  $("#btn-reset").addEventListener("click", resetUpload);
  $("#btn-run").addEventListener("click", runAnalysis);
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
  const grid = $("#preview-grid");
  const dz = $("#drop-zone");
  if (selectedFiles.length === 0) {
    grid.innerHTML = "";
    dz.classList.remove("has-images");
    return;
  }
  dz.classList.add("has-images");
  grid.innerHTML = selectedFiles.map((f, i) => `
    <div class="preview-item">
      <img src="${URL.createObjectURL(f)}" alt="">
      <div class="preview-name">${escapeHtml(f.name)}</div>
      <div class="preview-size">${(f.size / 1024).toFixed(0)} KB</div>
      <button class="preview-remove" onclick="removeFile(${i})">✕</button>
    </div>`).join("");
}

window.removeFile = function(idx) {
  selectedFiles.splice(idx, 1);
  renderPreviews();
  updateButtons();
};

function updateButtons() {
  const n = selectedFiles.length;
  const btnRun = $("#btn-run");
  const btnReset = $("#btn-reset");
  const btnRunText = $("#btn-run-text");
  if (!btnRun) return;
  btnRun.disabled = (n === 0);
  btnReset.disabled = (n === 0);
  btnRunText.textContent = n === 0 ? "تحليل الوثائق"
    : (n === 1 ? "تحليل الوثيقة" : `تحليل ${n} وثائق`);
}

function resetUpload() {
  selectedFiles = [];
  $("#file-input").value = "";
  renderPreviews();
  updateButtons();
}

// ==========================================================
// تحليل الوثائق (يستدعي API الشركة الحالية)
// ==========================================================
async function runAnalysis() {
  if (!currentCompany) {
    showToast("اختر شركة أوّلاً", "error");
    return;
  }
  if (selectedFiles.length === 0) return;

  const btnRun = $("#btn-run");
  const btnReset = $("#btn-reset");
  const progressBox = $("#progress-box");
  btnRun.disabled = true;
  btnReset.disabled = true;
  progressBox.hidden = false;
  updateProgress(0, selectedFiles.length, "جارٍ التحليل...");

  const controller = new AbortController();
  const timeoutMs = Math.max(180000, selectedFiles.length * 90000);
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // شريط تقدّم بسيط (بدون تفاصيل عن مزوّد الـ AI)
  let fakeProgress = 0;
  const fakeInterval = setInterval(() => {
    fakeProgress = Math.min(fakeProgress + 1, selectedFiles.length - 0.3);
    updateProgress(fakeProgress, selectedFiles.length, "جارٍ التحليل...");
  }, 3500);

  try {
    const fd = new FormData();
    selectedFiles.forEach(f => fd.append("files", f));

    const res = await fetch(`/api/companies/${currentCompany.id}/analyze`, {
      method: "POST",
      body: fd,
      signal: controller.signal,
    });
    clearInterval(fakeInterval);

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
    updateProgress(selectedFiles.length, selectedFiles.length, "✓ اكتمل");

    renderSummary(data);
    renderResultsList(data);

    const msg = `✅ تمت معالجة ${data.stats.success}/${data.stats.total} وثيقة`;
    showToast(msg, data.stats.failed > 0 ? "warning" : "success");

    $("#results-count").textContent = data.stats.total;
    $("#results-count").hidden = false;

    setTimeout(() => progressBox.hidden = true, 1200);

  } catch (err) {
    clearInterval(fakeInterval);
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
}

function updateProgress(done, total, msg) {
  const pct = total > 0 ? (done / total) * 100 : 0;
  $("#progress-bar").style.width = pct + "%";
  $("#progress-text").textContent = `${Math.round(done)} / ${total}`;
  if (msg) $("#progress-current").textContent = msg;
}

// ==========================================================
// عرض الملخّص
// ==========================================================
function renderSummary(data) {
  $("#empty-summary").hidden = true;
  $("#summary-content").hidden = false;

  const s = data.stats;
  $("#stat-total").textContent = s.total;
  $("#stat-success").textContent = s.success;
  $("#stat-failed").textContent = s.failed;
  $("#stat-entries").textContent = data.consolidated_journal?.length || 0;

  const ts = s.totals_sum;
  $("#sum-ht").textContent  = formatMoney(ts.total_ht);
  $("#sum-tva").textContent = formatMoney(ts.tva_amount);
  $("#sum-ttc").textContent = formatMoney(ts.total_ttc);

  const typeList = $("#type-list");
  const types = s.by_document_type || {};
  if (Object.keys(types).length === 0) {
    typeList.innerHTML = '<p class="empty-hint">لا توجد بيانات</p>';
  } else {
    typeList.innerHTML = Object.entries(types).map(([code, count]) => {
      const label = getDocTypeLabel(code);
      return `<div class="type-row"><span>${label.icon} ${label.name_ar}</span><strong>${count}</strong></div>`;
    }).join("");
  }
}

// ==========================================================
// قائمة النتائج
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
      <div class="doc-item ${r.success ? '' : 'doc-item-failed'}" onclick="selectDoc(${i})">
        <div class="doc-item-header">
          <span class="doc-item-status">${status}</span>
          <span class="doc-item-index">#${r.index}</span>
          <span class="doc-item-icon">${icon}</span>
        </div>
        <div class="doc-item-type">${typeName}</div>
        <div class="doc-item-num">${escapeHtml(invoiceNum)}</div>
        ${totalTtc ? `<div class="doc-item-amount">${formatMoney(totalTtc)}</div>` : ''}
        <div class="doc-item-file">${escapeHtml(r.original_filename)}</div>
      </div>`;
  }).join("");
  if (results.length > 0) selectDoc(0);
}

window.selectDoc = function(idx) {
  selectedDocIdx = idx;
  $$(".doc-item").forEach((el, i) => el.classList.toggle("active", i === idx));
  const r = batchResult?.results?.[idx];
  if (r) renderDocDetail(r);
};

function renderDocDetail(r) {
  const detail = $("#doc-detail");
  if (!r.success) {
    detail.innerHTML = `
      <div class="doc-detail-header">
        <h3>❌ فشل التحليل</h3>
        <p>${escapeHtml(r.original_filename)}</p>
      </div>
      <div class="error-block">${escapeHtml(r.error || "خطأ غير معروف")}</div>`;
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
        <p>${escapeHtml(r.original_filename)} · ${r.elapsed_seconds}s</p>
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
    <div class="dtab-content dtab-content-active" data-dtab="header">${renderHeaderTab(d, totals)}</div>
    ${items.length ? `<div class="dtab-content" data-dtab="items">${renderItemsTab(items)}</div>` : ''}
    ${je ? `<div class="dtab-content" data-dtab="journal">${renderJournalTab(je, r.index)}</div>` : ''}
    <div class="dtab-content" data-dtab="parties">${renderPartiesTab(supplier, customer)}</div>
    ${bank.bank_name ? `<div class="dtab-content" data-dtab="bank">${renderBankTab(bank)}</div>` : ''}
    <div class="dtab-content" data-dtab="raw"><pre class="json-view">${escapeHtml(JSON.stringify(d, null, 2))}</pre></div>`;
  detail.innerHTML = html;

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
      <div class="field-row"><label>نوع الوثيقة:</label><div class="field-value found">${dti.icon || ''} ${dti.label_ar || '—'}</div></div>
      <div class="field-row"><label>رقم الوثيقة:</label><div class="field-value">${escapeHtml(d.invoice_number || d.document_number || '—')}</div></div>
      <div class="field-row"><label>تاريخ الإصدار:</label><div class="field-value">${d.invoice_date || d.document_date || '—'}</div></div>
      ${d.due_date ? `<div class="field-row"><label>تاريخ الاستحقاق:</label><div class="field-value">${d.due_date}</div></div>` : ''}
      ${d.payment_method ? `<div class="field-row"><label>طريقة الدفع:</label><div class="field-value">${escapeHtml(d.payment_method)}</div></div>` : ''}
      ${totals.total_ht  != null ? `<div class="field-row"><label>المبلغ HT:</label><div class="field-value">${formatMoney(totals.total_ht)}</div></div>` : ''}
      ${totals.tva_amount != null ? `<div class="field-row highlight"><label>مبلغ TVA:</label><div class="field-value">${formatMoney(totals.tva_amount)}</div></div>` : ''}
      ${totals.stamp_duty ? `<div class="field-row"><label>حقوق الطابع:</label><div class="field-value">${formatMoney(totals.stamp_duty)}</div></div>` : ''}
      ${totals.total_ttc != null ? `<div class="field-row highlight-strong"><label>المبلغ الإجمالي TTC:</label><div class="field-value">${formatMoney(totals.total_ttc)}</div></div>` : ''}
    </div>
    ${d.notes ? `<div class="notes-block"><h4>📝 ملاحظات</h4><p>${escapeHtml(d.notes)}</p></div>` : ''}
    ${d.confidence_notes ? `<div class="notes-block" style="border-right-color:#d97706"><h4>⚠️ ملاحظات القراءة</h4><p>${escapeHtml(d.confidence_notes)}</p></div>` : ''}`;
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
        ${it.scf_account ? `<span class="scf-badge">${escapeHtml(it.scf_account)}</span>` : '<span class="scf-badge scf-badge-empty">—</span>'}
        ${it.category ? `<div class="scf-category">${escapeHtml(it.category)}</div>` : ''}
      </td>
    </tr>`).join("");
  return `<table class="items-table">
    <thead><tr><th>#</th><th>الوصف</th><th>الكمية</th><th>سعر الوحدة</th><th>TVA</th><th>الإجمالي HT</th><th>🏦 حساب SCF</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function renderJournalTab(je, docIdx) {
  const rows = je.entries.map(e => `
    <tr>
      <td class="je-account"><strong>${escapeHtml(e.account)}</strong></td>
      <td class="je-name">${escapeHtml(e.name || '')}</td>
      <td class="je-libelle">${escapeHtml(e.libelle || '')}</td>
      <td class="je-debit num">${e.debit ? formatNumber(e.debit) : ''}</td>
      <td class="je-credit num">${e.credit ? formatNumber(e.credit) : ''}</td>
    </tr>`).join("");
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
      <thead><tr><th>الحساب</th><th>التسمية</th><th>البيان</th><th>مدين</th><th>دائن</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><td colspan="3"><strong>المجموع</strong></td>
        <td class="num"><strong>${formatNumber(je.total_debit)}</strong></td>
        <td class="num"><strong>${formatNumber(je.total_credit)}</strong></td></tr></tfoot>
    </table>
    <div class="journal-actions">
      <button class="btn btn-ghost" onclick="copyJournalToClipboard(${docIdx})">📋 نسخ القيد</button>
      <button class="btn btn-ghost" onclick="exportSingleJournalCSV(${docIdx})">📥 تصدير CSV</button>
    </div>`;
}

function renderPartiesTab(supplier, customer) {
  const renderParty = (title, party) => {
    const labels = { name: "الاسم", address: "العنوان", phone: "الهاتف",
                     email: "البريد", nif: "NIF", rc: "RC", nis: "NIS", ai: "AI" };
    const rows = Object.entries(labels)
      .filter(([k]) => party[k])
      .map(([k, l]) => `<div class="field-row"><label>${l}:</label><div class="field-value found">${escapeHtml(party[k])}</div></div>`)
      .join("");
    return `<div class="party-block"><h3>${title}</h3>${rows || '<p class="empty-hint" style="padding:12px">لا توجد بيانات</p>'}</div>`;
  };
  return renderParty("🏢 المورّد", supplier) + renderParty("👤 الزبون", customer);
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
// دفتر يومية الشركة (المتراكم)
// ==========================================================
window.loadCompanyJournal = async function() {
  if (!currentCompany) return;
  const container = $("#journal-container");
  container.innerHTML = '<p class="empty-hint">جارٍ التحميل...</p>';
  try {
    const res = await fetch(`/api/companies/${currentCompany.id}/journal`);
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    renderCompanyJournal(data);
  } catch (err) {
    container.innerHTML = `<p class="empty-hint">❌ ${escapeHtml(err.message)}</p>`;
  }
};

function renderCompanyJournal(data) {
  const container = $("#journal-container");
  const entries = data.entries || [];
  if (entries.length === 0) {
    container.innerHTML = '<p class="empty-hint">لم يتم تحليل أي وثيقة بعد.</p>';
    return;
  }
  const totals = data.totals;
  let html = `
    <div class="grand-livre-total">
      <div>🧮 <strong>إجمالي الدفتر:</strong> ${totals.count} قيد</div>
      <div>مجموع مدين: <strong style="color:#4ade80">${formatMoney(totals.grand_debit)}</strong></div>
      <div>مجموع دائن: <strong style="color:#f87171">${formatMoney(totals.grand_credit)}</strong></div>
    </div>`;

  entries.forEach(e => {
    const rows = (e.entries || []).map(l => `
      <tr>
        <td class="je-account"><strong>${escapeHtml(l.account)}</strong></td>
        <td class="je-name">${escapeHtml(l.name || '')}</td>
        <td class="je-debit num">${l.debit ? formatNumber(l.debit) : ''}</td>
        <td class="je-credit num">${l.credit ? formatNumber(l.credit) : ''}</td>
      </tr>`).join("");
    html += `
      <div class="grand-livre-entry">
        <div class="gle-header">
          <div><strong>${e.journal_type || '📒'}</strong> · ${e.date || '—'}</div>
          <div style="font-size:11px; color:#6b7280">${escapeHtml(e.document_filename || '')}</div>
        </div>
        <div class="gle-libelle">📝 ${escapeHtml(e.libelle || '')}</div>
        <table class="journal-table">
          <thead><tr><th>الحساب</th><th>التسمية</th><th>مدين</th><th>دائن</th></tr></thead>
          <tbody>${rows}</tbody>
          <tfoot><tr><td colspan="2"><strong>مجموع</strong></td>
            <td class="num"><strong>${formatNumber(e.total_debit)}</strong></td>
            <td class="num"><strong>${formatNumber(e.total_credit)}</strong></td></tr></tfoot>
        </table>
      </div>`;
  });
  container.innerHTML = html;
}

window.exportCompanyJournalCSV = async function() {
  if (!currentCompany) return;
  try {
    const res = await fetch(`/api/companies/${currentCompany.id}/journal`);
    const data = await res.json();
    if (!data.success) throw new Error(data.error);
    if (!data.entries.length) {
      showToast("لا توجد قيود للتصدير", "warning");
      return;
    }
    let csv = "Date,Type,Fichier,Libellé,Compte,Nom,Débit,Crédit\n";
    data.entries.forEach(e => {
      (e.entries || []).forEach(l => {
        const row = [
          e.date || "",
          `"${(e.journal_type || '').replace(/"/g, '""')}"`,
          `"${(e.document_filename || '').replace(/"/g, '""')}"`,
          `"${(e.libelle || '').replace(/"/g, '""')}"`,
          l.account,
          `"${(l.name || '').replace(/"/g, '""')}"`,
          l.debit || "",
          l.credit || "",
        ].join(",");
        csv += row + "\n";
      });
    });
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `journal_${currentCompany.name.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("✅ تم تصدير الدفتر", "success");
  } catch (err) {
    showToast("❌ " + err.message, "error");
  }
};

// ==========================================================
// تصدير قيد فردي
// ==========================================================
window.copyJournalToClipboard = function(docIdx) {
  const r = batchResult?.results?.[docIdx];
  const je = r?.data?.journal_entry;
  if (!je) return;
  let text = `${je.journal_type || 'Journal Entry'}\nDate: ${je.date}\nLibellé: ${je.libelle}\n\n`;
  text += "Compte  | Nom".padEnd(50) + " | Débit         | Crédit\n" + "-".repeat(90) + "\n";
  je.entries.forEach(e => {
    text += `${e.account.padEnd(7)} | ${(e.name || "").padEnd(40).slice(0, 40)} | ${(e.debit ? formatNumber(e.debit) : "").padStart(13)} | ${(e.credit ? formatNumber(e.credit) : "").padStart(13)}\n`;
  });
  text += "-".repeat(90) + "\n" + `Total`.padEnd(50) + ` | ${formatNumber(je.total_debit).padStart(13)} | ${formatNumber(je.total_credit).padStart(13)}\n`;
  navigator.clipboard.writeText(text).then(() => showToast("✅ تم نسخ القيد", "success"));
};

window.exportSingleJournalCSV = function(docIdx) {
  const r = batchResult?.results?.[docIdx];
  const je = r?.data?.journal_entry;
  if (!je) return;
  let csv = "Date,Compte,Nom,Libellé,Débit,Crédit\n";
  je.entries.forEach(e => {
    csv += [
      je.date || "",
      e.account,
      `"${(e.name || '').replace(/"/g, '""')}"`,
      `"${(e.libelle || '').replace(/"/g, '""')}"`,
      e.debit || "",
      e.credit || "",
    ].join(",") + "\n";
  });
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `journal_doc${r.index}_${je.date || ''}.csv`; a.click();
  URL.revokeObjectURL(url);
};

// ==========================================================
// تبديل الـ views
// ==========================================================
window.switchView = function(view) {
  $$(".view").forEach(v => v.classList.remove("active"));

  if (view === "companies-list") {
    // ارجع لقائمة الشركات (اخفِ الشريط الجانبي)
    sidebar.hidden = true;
    document.body.classList.remove("has-sidebar");
    currentCompany = null;
    $("#view-companies-list").classList.add("active");
    loadCompaniesList();
    return;
  }

  $(`#view-${view}`).classList.add("active");
  $$(".menu-item").forEach(m => m.classList.toggle("active", m.dataset.view === view));

  // تحميل الدفتر عند فتحه
  if (view === "journal") loadCompanyJournal();
};

document.addEventListener("DOMContentLoaded", () => {
  $$(".menu-item").forEach(item => {
    if (item.dataset.view) {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        switchView(item.dataset.view);
      });
    }
  });
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

// ==========================================================
// Confirm Dialog
// ==========================================================
let confirmCallback = null;
function showConfirm(title, msg, callback) {
  $("#confirm-title").textContent = title;
  $("#confirm-msg").textContent = msg;
  $("#confirm-modal").hidden = false;
  confirmCallback = callback;
}
window.closeConfirm = function(ok) {
  $("#confirm-modal").hidden = true;
  if (confirmCallback) {
    confirmCallback(ok);
    confirmCallback = null;
  }
};
