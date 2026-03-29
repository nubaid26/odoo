// Login Page
import { auth } from '../api';
import { navigate } from '../router';
import { toast } from '../components';

export function renderLogin() {
  const app = document.getElementById('app')!;
  app.innerHTML = `
    <div class="auth-layout">
      <div class="auth-brand">
        <div class="auth-brand-content">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:48px">
            <div style="width:56px;height:56px;background:linear-gradient(135deg,var(--primary),var(--primary-container));border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:1.6rem">🛡️</div>
            <div>
              <h2 style="font-size:1.5rem;font-weight:800;letter-spacing:-0.02em">TrustFlow</h2>
              <p style="font-size:0.8rem;color:var(--on-surface-variant);margin:0">Intelligent Expense Trust Scoring</p>
            </div>
          </div>
          <h1>The Vault of<br>Financial Trust</h1>
          <p>Enterprise expense management powered by AI trust scoring, automated OCR, and GPS-based vendor validation.</p>
          <ul class="auth-features">
            <li>Real-time receipt analysis with OCR</li>
            <li>GST compliance verification</li>
            <li>GPS-based vendor location validation</li>
            <li>AI-powered trust scoring engine</li>
            <li>Multi-level smart approval routing</li>
          </ul>
        </div>
      </div>
      <div class="auth-form-side">
        <div class="auth-card">
          <h2>Welcome Back</h2>
          <p class="subtitle">Enter your credentials to access the vault.</p>
          <form id="login-form">
            <div class="form-group">
              <label class="form-label" for="login-email">Work Email</label>
              <input class="form-input" type="email" id="login-email" placeholder="name@company.com" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="login-password">Password</label>
              <input class="form-input" type="password" id="login-password" placeholder="Enter your password" required />
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
              <label style="display:flex;align-items:center;gap:8px;font-size:0.8rem;color:var(--on-surface-variant);cursor:pointer">
                <input type="checkbox" style="accent-color:var(--override-primary)"> Remember me
              </label>
              <a href="#" style="font-size:0.8rem">Forgot Password?</a>
            </div>
            <button type="submit" class="btn btn-primary btn-full btn-lg" id="login-btn">
              Sign In
            </button>
          </form>
          <p style="text-align:center;margin-top:24px;font-size:0.85rem;color:var(--on-surface-variant)">
            Don't have an account? <a href="#/signup">Sign Up</a>
          </p>
          <div class="divider">or</div>
          <div style="display:flex;flex-direction:column;gap:12px">
            <button class="btn btn-outline btn-full" disabled>
              <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"/><path fill="#FBBC05" d="M3.964 10.706a5.41 5.41 0 010-3.412V4.962H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.166 6.656 3.58 9 3.58z"/></svg>
              Continue with Google
            </button>
            <button class="btn btn-outline btn-full" disabled>
              <svg width="18" height="18" viewBox="0 0 21 21"><path fill="#f3f3f3" d="M0 0h10v10H0zm11 0h10v10H11zM0 11h10v10H0zm11 0h10v10H11z"/></svg>
              Continue with Microsoft
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  // ── Login Form Handler ──
  document.getElementById('login-form')!.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn')!;
    const email = (document.getElementById('login-email') as HTMLInputElement).value;
    const password = (document.getElementById('login-password') as HTMLInputElement).value;

    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px"></div> Signing in...';
    btn.setAttribute('disabled', 'true');

    try {
      await auth.login(email, password);
      try { await auth.me(); } catch {}
      toast('Welcome back!', 'success');
      navigate('/dashboard');
    } catch (err: any) {
      toast(err.message || 'Login failed', 'error');
      btn.innerHTML = 'Sign In';
      btn.removeAttribute('disabled');
    }
  });
}
