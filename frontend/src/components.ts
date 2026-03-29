// Shared components — sidebar, top bar, toast notifications

import { auth } from './api';
import { navigate } from './router';

// ── Toast System ──
let toastContainer: HTMLDivElement | null = null;

function ensureToastContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

export function toast(message: string, type: 'success' | 'error' | 'info' = 'info') {
  const container = ensureToastContainer();
  const el = document.createElement('div');
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(100%)';
    el.style.transition = 'all 0.3s';
    setTimeout(() => el.remove(), 300);
  }, 4000);
}

// ── Sidebar ──
const navItems = [
  { icon: '📊', label: 'Dashboard', path: '/dashboard' },
  { icon: '📋', label: 'My Expenses', path: '/expenses' },
  { icon: '➕', label: 'Submit Expense', path: '/submit' },
  { icon: '✅', label: 'Approvals', path: '/approvals' },
  { icon: '📁', label: 'Groups', path: '/groups' },
  { icon: '⚙️', label: 'Settings', path: '/settings' },
];

export function renderSidebar(activeRoute: string): string {
  const user = auth.getUser();
  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase()
    : '?';

  return `
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-icon">🛡️</div>
        <span class="logo-text">TrustFlow</span>
      </div>
      <nav class="sidebar-nav">
        ${navItems.map(item => `
          <a href="#${item.path}" class="nav-item ${activeRoute === item.path ? 'active' : ''}">
            <span class="nav-icon">${item.icon}</span>
            <span>${item.label}</span>
          </a>
        `).join('')}
      </nav>
      <div class="sidebar-user">
        <div class="avatar">${initials}</div>
        <div class="user-info">
          <div class="user-name">${user?.full_name || 'User'}</div>
          <div class="user-role">${user?.role || 'Employee'}</div>
        </div>
        <button onclick="document.dispatchEvent(new CustomEvent('logout'))" 
          style="background:none;border:none;color:var(--on-surface-variant);cursor:pointer;font-size:1.1rem;" title="Logout">
          🚪
        </button>
      </div>
    </aside>
  `;
}

// ── Page Shell (sidebar + top bar + content) ──
export function renderPage(activeRoute: string, title: string, content: string, actions: string = ''): string {
  return `
    <div class="app-layout">
      ${renderSidebar(activeRoute)}
      <main class="main-content">
        <div class="top-bar">
          <h1>${title}</h1>
          <div class="top-bar-actions">${actions}</div>
        </div>
        ${content}
      </main>
    </div>
  `;
}

// ── Format Currency ──
export function formatINR(amount: number): string {
  return '₹' + amount.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

// ── Format Date ──
export function formatDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ── Trust Score Color ──
export function trustClass(score: number): string {
  if (score >= 80) return 'trust-high';
  if (score >= 60) return 'trust-medium';
  return 'trust-low';
}

export function trustGrade(score: number): string {
  if (score >= 80) return 'HIGH';
  if (score >= 60) return 'MEDIUM';
  if (score >= 40) return 'LOW';
  return 'BLOCKED';
}

// ── Status Color ──
export function statusClass(status: string): string {
  const s = status?.toLowerCase().replace(/[_\s]/g, '');
  if (s?.includes('approved')) return 'status-approved';
  if (s?.includes('pending')) return 'status-pending';
  if (s?.includes('processing') || s?.includes('ocr') || s?.includes('valid')) return 'status-processing';
  if (s?.includes('rejected')) return 'status-rejected';
  if (s?.includes('blocked')) return 'status-blocked';
  return 'status-pending';
}

// ── Auth Guard ──
export function requireAuth(): boolean {
  if (!auth.isAuthenticated()) {
    navigate('/login');
    return false;
  }
  return true;
}

// ── Global Logout Handler ──
document.addEventListener('logout', async () => {
  await auth.logout();
  toast('Logged out successfully', 'info');
  navigate('/login');
});
