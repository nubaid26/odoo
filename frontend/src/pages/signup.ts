// Sign Up Page
import { auth } from '../api';
import { navigate } from '../router';
import { toast } from '../components';

export function renderSignup() {
  const app = document.getElementById('app')!;
  app.innerHTML = `
    <div class="auth-layout">
      <div class="auth-brand">
        <div class="auth-brand-content">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:48px">
            <div style="width:56px;height:56px;background:linear-gradient(135deg,var(--primary),var(--primary-container));border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:1.6rem">🛡️</div>
            <div>
              <h2 style="font-size:1.5rem;font-weight:800">TrustFlow</h2>
              <p style="font-size:0.8rem;color:var(--on-surface-variant);margin:0">Intelligent Expense Trust Scoring</p>
            </div>
          </div>
          <h1>Start Building<br>Trust Today</h1>
          <p>Join thousands of Indian enterprises using AI-powered expense validation.</p>
          <ul class="auth-features">
            <li>Automated receipt OCR processing</li>
            <li>GST compliance verification</li>
            <li>GPS-based vendor validation</li>
            <li>AI trust scoring engine</li>
          </ul>
        </div>
      </div>
      <div class="auth-form-side">
        <div class="auth-card">
          <h2>Create Your Account</h2>
          <p class="subtitle">Get started with intelligent expense management.</p>
          <form id="signup-form">
            <div class="form-group">
              <label class="form-label" for="signup-name">Full Name</label>
              <input class="form-input" type="text" id="signup-name" placeholder="Enter your full name" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-email">Work Email</label>
              <input class="form-input" type="email" id="signup-email" placeholder="name@company.com" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-company">Company Name</label>
              <input class="form-input" type="text" id="signup-company" placeholder="Your company name" />
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-country">Country</label>
              <select class="form-input form-select" id="signup-country">
                <option value="IN" selected>India</option>
                <option value="US">United States</option>
                <option value="GB">United Kingdom</option>
                <option value="SG">Singapore</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-password">Password</label>
              <input class="form-input" type="password" id="signup-password" placeholder="Create a strong password" required minlength="8" />
              <div id="password-strength" style="margin-top:8px;height:4px;border-radius:999px;background:var(--surface-container-lowest)">
                <div style="height:100%;width:0%;border-radius:999px;transition:all 0.3s" id="strength-bar"></div>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label" for="signup-confirm">Confirm Password</label>
              <input class="form-input" type="password" id="signup-confirm" placeholder="Re-enter password" required />
            </div>
            <div class="form-group">
              <label class="form-label">Role</label>
              <div style="display:flex;gap:16px">
                <label style="display:flex;align-items:center;gap:8px;font-size:0.85rem;cursor:pointer;color:var(--on-surface-variant)">
                  <input type="radio" name="role" value="employee" checked style="accent-color:var(--override-primary)"> Employee
                </label>
                <label style="display:flex;align-items:center;gap:8px;font-size:0.85rem;cursor:pointer;color:var(--on-surface-variant)">
                  <input type="radio" name="role" value="manager" style="accent-color:var(--override-primary)"> Manager
                </label>
              </div>
            </div>
            <div style="margin-bottom:24px">
              <label style="display:flex;align-items:start;gap:8px;font-size:0.8rem;color:var(--on-surface-variant);cursor:pointer">
                <input type="checkbox" id="signup-terms" required style="accent-color:var(--override-primary);margin-top:2px">
                I agree to the Terms of Service and Privacy Policy
              </label>
            </div>
            <button type="submit" class="btn btn-primary btn-full btn-lg" id="signup-btn">
              Create Account
            </button>
          </form>
          <p style="text-align:center;margin-top:24px;font-size:0.85rem;color:var(--on-surface-variant)">
            Already have an account? <a href="#/login">Sign In</a>
          </p>
        </div>
      </div>
    </div>
  `;

  // Password strength meter
  document.getElementById('signup-password')!.addEventListener('input', (e) => {
    const val = (e.target as HTMLInputElement).value;
    const bar = document.getElementById('strength-bar')!;
    let strength = 0;
    if (val.length >= 8) strength += 25;
    if (/[A-Z]/.test(val)) strength += 25;
    if (/[0-9]/.test(val)) strength += 25;
    if (/[^A-Za-z0-9]/.test(val)) strength += 25;
    bar.style.width = strength + '%';
    bar.style.background = strength <= 25 ? 'var(--danger)' : strength <= 50 ? 'var(--warning)' : strength <= 75 ? 'var(--info)' : 'var(--success)';
  });

  // Signup handler
  document.getElementById('signup-form')!.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('signup-btn')!;
    const password = (document.getElementById('signup-password') as HTMLInputElement).value;
    const confirm = (document.getElementById('signup-confirm') as HTMLInputElement).value;

    if (password !== confirm) {
      toast('Passwords do not match', 'error');
      return;
    }

    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px"></div> Creating...';
    btn.setAttribute('disabled', 'true');

    try {
      const role = (document.querySelector('input[name="role"]:checked') as HTMLInputElement)?.value || 'employee';
      await auth.signup({
        full_name: (document.getElementById('signup-name') as HTMLInputElement).value,
        email: (document.getElementById('signup-email') as HTMLInputElement).value,
        password,
        company_name: (document.getElementById('signup-company') as HTMLInputElement).value || undefined,
        role,
        country: (document.getElementById('signup-country') as HTMLSelectElement).value,
      });
      toast('Account created! Please sign in.', 'success');
      navigate('/login');
    } catch (err: any) {
      toast(err.message || 'Signup failed', 'error');
      btn.innerHTML = 'Create Account';
      btn.removeAttribute('disabled');
    }
  });
}
