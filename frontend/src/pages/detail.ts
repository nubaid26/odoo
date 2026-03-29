// Expense Detail Page
import { expenses, witnesses } from '../api';
import { renderPage, requireAuth, formatINR, formatDate, statusClass, trustClass, trustGrade, toast } from '../components';
import { getParam } from '../router';

export async function renderExpenseDetail() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;
  const id = getParam('/expenses/:id', 'id');
  if (!id) return;

  app.innerHTML = renderPage('/expenses', 'Expense Detail', `
    <div class="page-content" style="display:flex;align-items:center;justify-content:center;min-height:60vh">
      <div class="spinner" style="width:40px;height:40px;border-width:4px"></div>
    </div>
  `);

  try {
    const e = await expenses.get(id);
    const score = e.trust_score || 0;
    const grade = trustGrade(score);

    app.innerHTML = renderPage('/expenses', `Expense: ${(e.id || '').slice(0, 8)}...`, `
      <div class="page-content">
        <div style="display:grid;grid-template-columns:1fr 380px;gap:32px">
          <!-- Left Column -->
          <div style="display:flex;flex-direction:column;gap:24px">
            <!-- Summary Card -->
            <div class="card card-glass">
              <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:24px">
                <div>
                  <span class="status-pill ${statusClass(e.status)}" style="margin-bottom:8px">${(e.status || '').replace(/_/g, ' ')}</span>
                  <h2 style="font-size:1.5rem;font-weight:700;margin-top:8px">${formatINR(e.amount || 0)}</h2>
                </div>
                <div style="text-align:right">
                  <div class="metric-label">ID</div>
                  <div style="font-family:var(--font-mono);font-size:0.75rem">${e.id}</div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div><div class="metric-label">Category</div><div style="text-transform:capitalize">${(e.category || '—').replace(/_/g, ' ')}</div></div>
                <div><div class="metric-label">Vendor</div><div>${e.vendor_name || '—'}</div></div>
                <div><div class="metric-label">Date</div><div>${formatDate(e.expense_date || e.created_at)}</div></div>
                <div><div class="metric-label">Currency</div><div>${e.currency || 'INR'}</div></div>
                ${e.gstin ? `<div><div class="metric-label">GSTIN</div><div style="font-family:var(--font-mono);font-size:0.8rem">${e.gstin} <span style="color:var(--success)">✓</span></div></div>` : ''}
                ${e.latitude ? `<div><div class="metric-label">GPS Location</div><div style="font-size:0.8rem">${e.latitude?.toFixed(4)}°N, ${e.longitude?.toFixed(4)}°E</div></div>` : ''}
              </div>
              ${e.description ? `<div style="margin-top:16px"><div class="metric-label">Description</div><div style="font-size:0.85rem;color:var(--on-surface-variant)">${e.description}</div></div>` : ''}
            </div>

            <!-- Receipt / OCR -->
            <div class="card">
              <h3 style="font-size:0.9rem;font-weight:700;margin-bottom:16px">📎 Receipt & OCR</h3>
              ${e.receipt_url ? `
                <div style="background:var(--surface-container-lowest);border-radius:8px;padding:16px;text-align:center;margin-bottom:16px">
                  <img src="${e.receipt_url}" alt="Receipt" style="max-width:100%;max-height:300px;border-radius:8px" onerror="this.parentElement.innerHTML='<div style=\\'padding:32px;color:var(--on-surface-variant)\\'>Receipt image unavailable</div>'" />
                </div>
              ` : `
                <div class="empty-state" style="padding:32px">
                  <div class="empty-state-icon" style="font-size:2rem">🧾</div>
                  <p>No receipt uploaded</p>
                </div>
              `}
              ${e.ocr_data ? `
                <div style="background:var(--surface-container-lowest);border-radius:8px;padding:16px">
                  <div class="metric-label" style="margin-bottom:8px">OCR Extracted Data</div>
                  <pre style="font-family:var(--font-mono);font-size:0.75rem;color:var(--on-surface-variant);white-space:pre-wrap">${JSON.stringify(e.ocr_data, null, 2)}</pre>
                </div>
              ` : ''}
            </div>

            <!-- Witnesses -->
            <div class="card">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                <h3 style="font-size:0.9rem;font-weight:700">👥 Witnesses</h3>
                <button class="btn btn-outline btn-sm" id="add-witness-btn">+ Add Witness</button>
              </div>
              ${e.witnesses?.length ? `
                <div style="display:flex;flex-direction:column;gap:12px">
                  ${e.witnesses.map((w: any) => `
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:var(--surface-container);border-radius:8px">
                      <span>${w.email || w.name}</span>
                      <span class="status-pill ${w.confirmed ? 'status-approved' : 'status-pending'}">${w.confirmed ? 'Confirmed' : 'Pending'}</span>
                    </div>
                  `).join('')}
                </div>
              ` : `
                <div style="text-align:center;padding:24px;color:var(--on-surface-variant);font-size:0.85rem">
                  No witnesses added yet
                </div>
              `}
            </div>
          </div>

          <!-- Right Column -->
          <div style="display:flex;flex-direction:column;gap:24px">
            <!-- Trust Score -->
            <div class="card">
              <h3 style="font-size:0.9rem;font-weight:700;margin-bottom:16px">🛡️ Trust Score</h3>
              <div style="text-align:center;margin-bottom:24px">
                <div style="width:100px;height:100px;border-radius:50%;border:6px solid ${score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--danger)'};display:flex;align-items:center;justify-content:center;margin:0 auto 8px">
                  <span style="font-size:1.8rem;font-weight:800">${score || '—'}</span>
                </div>
                <span class="status-pill ${score >= 80 ? 'status-approved' : score >= 60 ? 'status-pending' : 'status-rejected'}">${grade}</span>
              </div>
              ${e.trust_breakdown ? `
                <div style="display:flex;flex-direction:column;gap:12px">
                  ${Object.entries(e.trust_breakdown).map(([key, val]: any) => `
                    <div>
                      <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:4px">
                        <span style="text-transform:capitalize">${key.replace(/_/g, ' ')}</span>
                        <span>${val}%</span>
                      </div>
                      <div class="progress-bar">
                        <div class="progress-fill" style="width:${val}%;background:${val >= 80 ? 'var(--success)' : val >= 60 ? 'var(--warning)' : 'var(--danger)'}"></div>
                      </div>
                    </div>
                  `).join('')}
                </div>
              ` : `<div style="color:var(--on-surface-variant);font-size:0.85rem;text-align:center">Awaiting trust analysis</div>`}
            </div>

            <!-- Audit Trail -->
            <div class="card">
              <h3 style="font-size:0.9rem;font-weight:700;margin-bottom:16px">📋 Audit Trail</h3>
              ${e.audit_trail?.length ? `
                <div style="display:flex;flex-direction:column;gap:0;padding-left:16px;border-left:2px solid var(--surface-container-highest)">
                  ${e.audit_trail.map((a: any) => `
                    <div style="position:relative;padding:8px 0 16px 16px">
                      <div style="position:absolute;left:-21px;top:10px;width:10px;height:10px;border-radius:50%;background:var(--primary)"></div>
                      <div style="font-size:0.8rem;font-weight:600">${a.action || a.event}</div>
                      <div style="font-size:0.7rem;color:var(--on-surface-variant)">${formatDate(a.timestamp || a.created_at)}</div>
                    </div>
                  `).join('')}
                </div>
              ` : `<div style="color:var(--on-surface-variant);font-size:0.85rem;text-align:center">Awaiting activity</div>`}
            </div>
          </div>
        </div>
      </div>
    `, `<a href="#/expenses" class="btn btn-outline btn-sm">← Back to List</a>`);

    // Add witness handler
    document.getElementById('add-witness-btn')?.addEventListener('click', () => {
      const email = prompt('Enter witness email:');
      if (email) {
        witnesses.add(id, email).then(() => {
          toast('Witness invitation sent!', 'success');
          renderExpenseDetail(); // refresh
        }).catch((err) => toast(err.message, 'error'));
      }
    });
  } catch (err: any) {
    app.innerHTML = renderPage('/expenses', 'Expense Detail', `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h3>Expense not found</h3>
        <p>${err.message}</p>
        <a href="#/expenses" class="btn btn-primary">Back to List</a>
      </div>
    `);
  }
}
