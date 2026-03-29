// Manager Approvals Page
import { approvals } from '../api';
import { renderPage, requireAuth, formatINR, formatDate, trustClass, trustGrade, toast } from '../components';

export async function renderApprovals() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;

  app.innerHTML = renderPage('/approvals', 'Pending Approvals', `
    <div class="page-content" style="display:flex;align-items:center;justify-content:center;min-height:60vh">
      <div class="spinner" style="width:40px;height:40px;border-width:4px"></div>
    </div>
  `);

  try {
    const data = await approvals.pending();
    const list = data.approvals || data.items || data || [];

    app.innerHTML = renderPage('/approvals', 'Pending Approvals', `
      <div class="metrics-grid" style="padding-bottom:0">
        <div class="metric-card">
          <div class="metric-label">Pending Review</div>
          <div class="metric-value" style="color:var(--warning)">${list.length}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Average Trust Score</div>
          <div class="metric-value">${list.length ? Math.round(list.reduce((s: number, a: any) => s + (a.expense?.trust_score || a.trust_score || 0), 0) / list.length) : '—'}</div>
        </div>
      </div>

      <div class="page-content" style="padding-top:0">
        ${list.length > 0 ? `
          <div style="display:flex;flex-direction:column;gap:16px">
            ${list.map((a: any) => {
              const e = a.expense || a;
              const score = e.trust_score || a.trust_score || 0;
              const grade = trustGrade(score);
              const borderColor = score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--danger)';
              return `
                <div class="card card-glass" style="border-left:4px solid ${borderColor}">
                  <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px">
                    <div>
                      <div style="font-weight:600">${e.submitter_name || e.user_name || 'Employee'}</div>
                      <div style="font-size:0.8rem;color:var(--on-surface-variant);text-transform:capitalize">${(e.category || '—').replace(/_/g, ' ')}</div>
                    </div>
                    <div style="text-align:right">
                      <div style="font-size:1.25rem;font-weight:700">${formatINR(e.amount || 0)}</div>
                      <div style="font-size:0.75rem;color:var(--on-surface-variant)">${formatDate(e.expense_date || e.created_at)}</div>
                    </div>
                  </div>
                  <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px">
                    <span class="trust-badge ${trustClass(score)}">${score}</span>
                    <span class="status-pill ${score >= 80 ? 'status-approved' : score >= 60 ? 'status-pending' : 'status-rejected'}">${grade}</span>
                    ${e.vendor_name ? `<span style="font-size:0.8rem;color:var(--on-surface-variant)">📍 ${e.vendor_name}</span>` : ''}
                  </div>
                  ${score < 60 ? `<div style="background:rgba(244,63,94,0.1);color:var(--danger);padding:8px 12px;border-radius:8px;font-size:0.8rem;margin-bottom:16px">⚠️ Low trust score — requires careful review</div>` : ''}
                  <div style="display:flex;gap:8px;justify-content:flex-end">
                    <a href="#/expenses/${e.id}" class="btn btn-outline btn-sm">Review Details</a>
                    <button class="btn btn-success btn-sm approve-btn" data-id="${a.id || a.approval_id}">✓ Approve</button>
                    <button class="btn btn-danger-outline btn-sm reject-btn" data-id="${a.id || a.approval_id}">✕ Reject</button>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        ` : `
          <div class="empty-state">
            <div class="empty-state-icon">✅</div>
            <h3>No pending approvals</h3>
            <p>All caught up! New approvals will appear here.</p>
          </div>
        `}
      </div>
    `);

    // Approve handlers
    document.querySelectorAll('.approve-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = (btn as HTMLElement).dataset.id!;
        try {
          await approvals.approve(id);
          toast('Expense approved!', 'success');
          renderApprovals(); // refresh
        } catch (err: any) { toast(err.message, 'error'); }
      });
    });

    // Reject handlers
    document.querySelectorAll('.reject-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = (btn as HTMLElement).dataset.id!;
        const reason = prompt('Rejection reason:');
        if (!reason) return;
        try {
          await approvals.reject(id, reason);
          toast('Expense rejected', 'info');
          renderApprovals();
        } catch (err: any) { toast(err.message, 'error'); }
      });
    });
  } catch (err: any) {
    app.innerHTML = renderPage('/approvals', 'Pending Approvals', `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h3>Could not load approvals</h3>
        <p>${err.message}</p>
        <button class="btn btn-primary" onclick="location.reload()">Retry</button>
      </div>
    `);
  }
}
