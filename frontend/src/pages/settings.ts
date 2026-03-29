// Settings Page
import { auth } from '../api';
import { renderPage, requireAuth, toast } from '../components';

export function renderSettings() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;
  const user = auth.getUser();

  app.innerHTML = renderPage('/settings', 'Settings', `
    <div class="page-content">
      <div style="display:grid;grid-template-columns:200px 1fr;gap:32px;max-width:1000px">
        <!-- Settings Nav -->
        <div style="display:flex;flex-direction:column;gap:4px">
          <button class="nav-item active" data-tab="profile" onclick="document.querySelectorAll('.settings-tab').forEach(t=>t.style.display='none');document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));this.classList.add('active');document.getElementById('tab-profile').style.display='block'">
            <span class="nav-icon">👤</span> Profile
          </button>
          <button class="nav-item" data-tab="company" onclick="document.querySelectorAll('.settings-tab').forEach(t=>t.style.display='none');document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));this.classList.add('active');document.getElementById('tab-company').style.display='block'">
            <span class="nav-icon">🏢</span> Company
          </button>
          <button class="nav-item" data-tab="notifications" onclick="document.querySelectorAll('.settings-tab').forEach(t=>t.style.display='none');document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));this.classList.add('active');document.getElementById('tab-notifications').style.display='block'">
            <span class="nav-icon">🔔</span> Notifications
          </button>
          <button class="nav-item" data-tab="security" onclick="document.querySelectorAll('.settings-tab').forEach(t=>t.style.display='none');document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));this.classList.add('active');document.getElementById('tab-security').style.display='block'">
            <span class="nav-icon">🔒</span> Security
          </button>
        </div>

        <!-- Settings Content -->
        <div>
          <!-- Profile Tab -->
          <div id="tab-profile" class="settings-tab">
            <div class="card" style="margin-bottom:24px">
              <div style="display:flex;align-items:center;gap:24px;margin-bottom:24px">
                <div class="avatar" style="width:72px;height:72px;font-size:1.5rem">
                  ${user?.full_name ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase() : '?'}
                </div>
                <div>
                  <div style="font-size:1.1rem;font-weight:700">${user?.full_name || 'Your Name'}</div>
                  <div style="font-size:0.8rem;color:var(--on-surface-variant)">${user?.role || 'Employee'}</div>
                </div>
              </div>
              <form id="profile-form">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
                  <div class="form-group">
                    <label class="form-label">Full Name</label>
                    <input class="form-input" type="text" value="${user?.full_name || ''}" placeholder="Your full name" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Email</label>
                    <input class="form-input" type="email" value="${user?.email || ''}" disabled style="opacity:0.6" />
                    <div class="form-helper" style="color:var(--success)">✓ Verified</div>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Role</label>
                    <input class="form-input" value="${user?.role || '—'}" disabled style="opacity:0.6;text-transform:capitalize" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input class="form-input" type="tel" placeholder="+91 98765 43210" />
                  </div>
                </div>
                <div style="margin-top:24px;text-align:right">
                  <button type="submit" class="btn btn-primary">Save Changes</button>
                </div>
              </form>
            </div>
          </div>

          <!-- Company Tab -->
          <div id="tab-company" class="settings-tab" style="display:none">
            <div class="card">
              <h3 style="font-size:1rem;font-weight:700;margin-bottom:24px">Company Settings</h3>
              <div class="form-group">
                <label class="form-label">Company Name</label>
                <input class="form-input" placeholder="Your company name" />
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
                <div class="form-group">
                  <label class="form-label">Country</label>
                  <select class="form-input form-select">
                    <option value="IN" selected>India</option>
                    <option value="US">United States</option>
                    <option value="GB">United Kingdom</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Default Currency</label>
                  <select class="form-input form-select">
                    <option value="INR" selected>INR (₹)</option>
                    <option value="USD">USD ($)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">Auto-Approve Threshold</label>
                <input class="form-input" type="number" placeholder="2000" />
                <div class="form-helper">Expenses below this amount with HIGH trust scores can be auto-approved</div>
              </div>
              <div class="form-group">
                <label class="form-label">GSTIN Required Above</label>
                <input class="form-input" type="number" placeholder="5000" />
                <div class="form-helper">GSTIN is required for expenses above this amount</div>
              </div>
              <div style="margin-top:24px;text-align:right">
                <button class="btn btn-primary">Save Company Settings</button>
              </div>
            </div>
          </div>

          <!-- Notifications Tab -->
          <div id="tab-notifications" class="settings-tab" style="display:none">
            <div class="card">
              <h3 style="font-size:1rem;font-weight:700;margin-bottom:24px">Notification Preferences</h3>
              <div style="display:flex;flex-direction:column;gap:20px">
                ${[
                  ['Email on approval/rejection', true],
                  ['Push notifications', false],
                  ['Weekly expense digest', true],
                  ['Trust score alerts', true],
                  ['New expense from team', false],
                ].map(([label, checked]) => `
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-size:0.9rem">${label}</span>
                    <label style="position:relative;width:44px;height:24px;cursor:pointer">
                      <input type="checkbox" ${checked ? 'checked' : ''} style="opacity:0;width:0;height:0;position:absolute" onchange="this.parentElement.querySelector('span').style.background=this.checked?'var(--override-primary)':'var(--surface-container-highest)';this.parentElement.querySelector('span::before')">
                      <span style="position:absolute;inset:0;background:${checked ? 'var(--override-primary)' : 'var(--surface-container-highest)'};border-radius:12px;transition:0.3s"></span>
                    </label>
                  </div>
                `).join('')}
              </div>
              <div style="margin-top:24px;text-align:right">
                <button class="btn btn-primary">Save Preferences</button>
              </div>
            </div>
          </div>

          <!-- Security Tab -->
          <div id="tab-security" class="settings-tab" style="display:none">
            <div class="card" style="margin-bottom:24px">
              <h3 style="font-size:1rem;font-weight:700;margin-bottom:24px">Security</h3>
              <div class="form-group">
                <label class="form-label">Change Password</label>
                <input class="form-input" type="password" placeholder="Current password" style="margin-bottom:12px" />
                <input class="form-input" type="password" placeholder="New password" style="margin-bottom:12px" />
                <input class="form-input" type="password" placeholder="Confirm new password" />
              </div>
              <button class="btn btn-primary btn-sm">Update Password</button>
            </div>
            <div class="card">
              <h3 style="font-size:1rem;font-weight:700;margin-bottom:16px">Active Sessions</h3>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:var(--surface-container);border-radius:8px;margin-bottom:12px">
                <div>
                  <div style="font-size:0.85rem;font-weight:600">Current Session</div>
                  <div style="font-size:0.75rem;color:var(--on-surface-variant)">This browser — Active now</div>
                </div>
                <span class="status-pill status-approved">Active</span>
              </div>
              <button class="btn btn-danger-outline btn-sm" onclick="document.dispatchEvent(new CustomEvent('logout'))">
                Sign Out All Sessions
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `);

  // Profile save handler
  document.getElementById('profile-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    toast('Profile saved (demo — backend integration pending)', 'success');
  });
}
