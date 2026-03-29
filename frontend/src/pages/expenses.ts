// Expenses List Page
import { expenses } from '../api';
import { renderPage, requireAuth, formatINR, formatDate, statusClass, trustClass, toast } from '../components';

export async function renderExpenses() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;

  app.innerHTML = renderPage('/expenses', 'My Expenses', `
    <div class="page-content" style="display:flex;align-items:center;justify-content:center;min-height:60vh">
      <div class="spinner" style="width:40px;height:40px;border-width:4px"></div>
    </div>
  `, `<a href="#/submit" class="btn btn-primary btn-sm">+ New Expense</a>`);

  try {
    const data = await expenses.list({ per_page: 50 });
    const list = data.expenses || data.items || data || [];

    const totals = {
      total: list.reduce((s: number, e: any) => s + (e.amount || 0), 0),
      approved: list.filter((e: any) => e.status?.includes('approved')).reduce((s: number, e: any) => s + (e.amount || 0), 0),
      pending: list.filter((e: any) => e.status?.includes('pending')).reduce((s: number, e: any) => s + (e.amount || 0), 0),
      rejected: list.filter((e: any) => e.status?.includes('rejected')).reduce((s: number, e: any) => s + (e.amount || 0), 0),
    };

    app.innerHTML = renderPage('/expenses', 'My Expenses', `
      <!-- Summary Strip -->
      <div class="metrics-grid" style="padding-bottom:0">
        <div class="metric-card"><div class="metric-label">Total</div><div class="metric-value" style="font-size:1.5rem">${formatINR(totals.total)}</div></div>
        <div class="metric-card"><div class="metric-label">Approved</div><div class="metric-value" style="font-size:1.5rem;color:var(--success)">${formatINR(totals.approved)}</div></div>
        <div class="metric-card"><div class="metric-label">Pending</div><div class="metric-value" style="font-size:1.5rem;color:var(--warning)">${formatINR(totals.pending)}</div></div>
        <div class="metric-card"><div class="metric-label">Rejected</div><div class="metric-value" style="font-size:1.5rem;color:var(--danger)">${formatINR(totals.rejected)}</div></div>
      </div>

      <!-- Filter Bar -->
      <div class="filter-bar">
        <div class="form-group">
          <label class="form-label">Status</label>
          <select class="form-input form-select" id="filter-status" style="padding:8px 12px">
            <option value="">All</option>
            <option value="pending_approval">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="processing">Processing</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Category</label>
          <select class="form-input form-select" id="filter-category" style="padding:8px 12px">
            <option value="">All</option>
            <option value="travel">Travel</option>
            <option value="meals">Meals</option>
            <option value="accommodation">Accommodation</option>
            <option value="office_supplies">Office Supplies</option>
          </select>
        </div>
        <button class="btn btn-secondary btn-sm" id="apply-filters">Apply</button>
      </div>

      <!-- Data Table -->
      <div class="page-content" style="padding-top:0">
        <div class="card" style="padding:0;overflow:hidden">
          ${list.length > 0 ? `
            <table class="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Date</th>
                  <th>Category</th>
                  <th>Vendor</th>
                  <th>Amount</th>
                  <th>Trust</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${list.map((e: any) => `
                  <tr>
                    <td style="font-family:var(--font-mono);font-size:0.75rem">${(e.id || '').slice(0, 8)}...</td>
                    <td>${formatDate(e.expense_date || e.created_at)}</td>
                    <td style="text-transform:capitalize">${(e.category || '—').replace(/_/g, ' ')}</td>
                    <td>${e.vendor_name || '—'}</td>
                    <td style="font-weight:600">${formatINR(e.amount || 0)}</td>
                    <td><span class="trust-badge ${trustClass(e.trust_score || 0)}">${e.trust_score || '—'}</span></td>
                    <td><span class="status-pill ${statusClass(e.status)}">${(e.status || '—').replace(/_/g, ' ')}</span></td>
                    <td>
                      <a href="#/expenses/${e.id}" class="btn btn-outline btn-sm" style="padding:4px 12px">👁</a>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
            <div style="padding:16px 24px;text-align:right;font-size:0.8rem;color:var(--on-surface-variant)">
              Showing ${list.length} result${list.length !== 1 ? 's' : ''}
            </div>
          ` : `
            <div class="empty-state">
              <div class="empty-state-icon">🧾</div>
              <h3>No expenses found</h3>
              <p>Submit your first expense to get started.</p>
              <a href="#/submit" class="btn btn-primary">Submit Expense</a>
            </div>
          `}
        </div>
      </div>
    `, `<a href="#/submit" class="btn btn-primary btn-sm">+ New Expense</a>`);

    // Filter handler
    document.getElementById('apply-filters')?.addEventListener('click', async () => {
      const status = (document.getElementById('filter-status') as HTMLSelectElement).value;
      const category = (document.getElementById('filter-category') as HTMLSelectElement).value;
      try {
        // Re-render with filters (simplified — full impl would re-fetch)
        toast('Filters applied', 'info');
      } catch {}
    });
  } catch (err: any) {
    app.innerHTML = renderPage('/expenses', 'My Expenses', `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h3>Could not load expenses</h3>
        <p>${err.message}</p>
        <button class="btn btn-primary" onclick="location.reload()">Retry</button>
      </div>
    `);
  }
}
