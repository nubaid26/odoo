// Dashboard Page
import { dashboard } from '../api';
import { renderPage, requireAuth, formatINR, formatDate, statusClass, trustClass, toast } from '../components';

export async function renderDashboard() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;

  // Show loading state
  app.innerHTML = renderPage('/dashboard', 'Dashboard', `
    <div class="page-content" style="display:flex;align-items:center;justify-content:center;min-height:60vh">
      <div class="spinner" style="width:40px;height:40px;border-width:4px"></div>
    </div>
  `);

  try {
    const data = await dashboard.summary();
    const recent = data.recent || [];

    app.innerHTML = renderPage('/dashboard', 'Dashboard', `
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Total Expenses</div>
          <div class="metric-value">${formatINR(data.total_expenses)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Pending Review</div>
          <div class="metric-value">${data.pending_count}
            ${data.pending_count > 0 ? '<span class="metric-badge badge-amber">action needed</span>' : ''}
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Average Trust Score</div>
          <div class="metric-value">
            <span class="${trustClass(data.average_trust)}" style="font-size:inherit;width:auto;height:auto;background:none">
              ${data.average_trust || '—'}
            </span>/100
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-label">All Expenses</div>
          <div class="metric-value">${data.all?.length || 0}</div>
        </div>
      </div>

      <div class="page-content" style="padding-top:0">
        <div class="section-header">
          <h2>Recent Expenses</h2>
          <a href="#/expenses" class="btn btn-secondary btn-sm">View All</a>
        </div>
        <div class="card" style="padding:0;overflow:hidden">
          ${recent.length > 0 ? `
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
                ${recent.map((e: any) => `
                  <tr>
                    <td style="font-family:var(--font-mono);font-size:0.75rem">${(e.id || '').slice(0, 8)}...</td>
                    <td>${formatDate(e.created_at)}</td>
                    <td>${e.category || '—'}</td>
                    <td>${e.vendor_name || '—'}</td>
                    <td style="font-weight:600">${formatINR(e.amount || 0)}</td>
                    <td><span class="trust-badge ${trustClass(e.trust_score || 0)}">${e.trust_score || '—'}</span></td>
                    <td><span class="status-pill ${statusClass(e.status)}">${(e.status || '').replace(/_/g, ' ')}</span></td>
                    <td><a href="#/expenses/${e.id}" class="btn btn-outline btn-sm">View</a></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : `
            <div class="empty-state">
              <div class="empty-state-icon">📊</div>
              <h3>No expenses yet</h3>
              <p>Submit your first expense to see your dashboard come alive.</p>
              <a href="#/submit" class="btn btn-primary">Submit Your First Expense</a>
            </div>
          `}
        </div>
      </div>
    `);
  } catch (err: any) {
    app.innerHTML = renderPage('/dashboard', 'Dashboard', `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h3>Could not load dashboard</h3>
        <p>${err.message || 'Backend may be offline. Check your connection.'}</p>
        <button class="btn btn-primary" onclick="location.reload()">Retry</button>
      </div>
    `);
  }
}
