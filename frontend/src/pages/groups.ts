// Expense Groups Page
import { groups } from '../api';
import { renderPage, requireAuth, formatINR, toast } from '../components';

export async function renderGroups() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;

  app.innerHTML = renderPage('/groups', 'Expense Groups', `
    <div class="page-content" style="display:flex;align-items:center;justify-content:center;min-height:60vh">
      <div class="spinner" style="width:40px;height:40px;border-width:4px"></div>
    </div>
  `, `<button class="btn btn-primary btn-sm" id="create-group-btn">+ Create Group</button>`);

  try {
    const data = await groups.list();
    const list = data.groups || data.items || data || [];

    app.innerHTML = renderPage('/groups', 'Expense Groups', `
      <div class="page-content">
        ${list.length > 0 ? `
          <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(320px, 1fr));gap:24px">
            ${list.map((g: any) => `
              <div class="card card-glass" style="cursor:pointer" onclick="location.hash='#/groups/${g.id}'">
                <h3 style="font-size:1rem;font-weight:700;margin-bottom:8px">${g.name}</h3>
                <p style="font-size:0.8rem;color:var(--on-surface-variant);margin-bottom:16px">${g.description || 'No description'}</p>
                <div style="display:flex;justify-content:space-between;font-size:0.8rem;color:var(--on-surface-variant)">
                  <span>${g.expense_count || 0} expenses</span>
                  <span style="font-weight:600;color:var(--on-surface)">${formatINR(g.total_amount || 0)}</span>
                </div>
              </div>
            `).join('')}
            <!-- Create New Card -->
            <div class="upload-zone" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:180px;cursor:pointer" id="create-card">
              <div style="font-size:2rem;margin-bottom:8px">📁</div>
              <span style="font-size:0.9rem;font-weight:600;color:var(--primary)">+ Create New Group</span>
            </div>
          </div>
        ` : `
          <div class="empty-state">
            <div class="empty-state-icon">📁</div>
            <h3>No expense groups yet</h3>
            <p>Create your first group to organize related expenses.</p>
            <button class="btn btn-primary" id="create-empty-btn">Create New Group</button>
          </div>
        `}
      </div>
    `, `<button class="btn btn-primary btn-sm" id="create-group-header-btn">+ Create Group</button>`);

    // Create group handler
    const createHandler = async () => {
      const name = prompt('Group name:');
      if (!name) return;
      const desc = prompt('Description (optional):') || '';
      try {
        await groups.create(name, desc);
        toast('Group created!', 'success');
        renderGroups();
      } catch (err: any) { toast(err.message, 'error'); }
    };

    document.getElementById('create-card')?.addEventListener('click', createHandler);
    document.getElementById('create-empty-btn')?.addEventListener('click', createHandler);
    document.getElementById('create-group-header-btn')?.addEventListener('click', createHandler);
  } catch (err: any) {
    app.innerHTML = renderPage('/groups', 'Expense Groups', `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h3>Could not load groups</h3>
        <p>${err.message}</p>
      </div>
    `);
  }
}
