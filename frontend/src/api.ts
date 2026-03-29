// TrustFlow API Client — connects frontend to FastAPI backend

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  company_id: string;
}

// ── Token Management ──
function getTokens(): TokenPair | null {
  const raw = localStorage.getItem('trustflow_tokens');
  return raw ? JSON.parse(raw) : null;
}

function setTokens(t: TokenPair) {
  localStorage.setItem('trustflow_tokens', JSON.stringify(t));
}

function clearTokens() {
  localStorage.removeItem('trustflow_tokens');
  localStorage.removeItem('trustflow_user');
}

function getUser(): User | null {
  const raw = localStorage.getItem('trustflow_user');
  return raw ? JSON.parse(raw) : null;
}

function setUser(u: User) {
  localStorage.setItem('trustflow_user', JSON.stringify(u));
}

// ── Authenticated Fetch ──
async function apiFetch(path: string, opts: RequestInit = {}): Promise<Response> {
  const tokens = getTokens();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> || {}),
  };

  if (tokens) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });

  if (res.status === 401 && tokens?.refresh_token) {
    // Try refresh
    const refreshRes = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    });
    if (refreshRes.ok) {
      const newTokens = await refreshRes.json();
      setTokens(newTokens);
      headers['Authorization'] = `Bearer ${newTokens.access_token}`;
      return fetch(`${API_BASE}${path}`, { ...opts, headers });
    } else {
      clearTokens();
      window.location.hash = '#/login';
      throw new Error('Session expired');
    }
  }

  return res;
}

// ── File Upload Fetch ──
async function apiUpload(path: string, formData: FormData): Promise<Response> {
  const tokens = getTokens();
  const headers: Record<string, string> = {};
  if (tokens) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`;
  }
  // Don't set Content-Type for FormData
  return fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: formData });
}

// ── Auth API ──
export const auth = {
  async login(email: string, password: string): Promise<TokenPair> {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    setTokens(data);
    return data;
  },

  async signup(payload: {
    email: string;
    password: string;
    full_name: string;
    company_name?: string;
    role?: string;
    country?: string;
  }): Promise<any> {
    const res = await fetch(`${API_BASE}/api/v1/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Signup failed' }));
      throw new Error(err.detail || 'Signup failed');
    }
    return res.json();
  },

  async me(): Promise<User> {
    const res = await apiFetch('/api/v1/auth/me');
    if (!res.ok) throw new Error('Failed to fetch user');
    const user = await res.json();
    setUser(user);
    return user;
  },

  async logout(): Promise<void> {
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST' });
    } catch { /* ignore */ }
    clearTokens();
  },

  isAuthenticated(): boolean {
    return !!getTokens()?.access_token;
  },

  getUser,
  clearTokens,
};

// ── Expenses API ──
export const expenses = {
  async list(params?: { status?: string; category?: string; page?: number; per_page?: number }): Promise<any> {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.category) qs.set('category', params.category);
    if (params?.page) qs.set('page', String(params.page));
    if (params?.per_page) qs.set('per_page', String(params.per_page));
    const res = await apiFetch(`/api/v1/expenses?${qs}`);
    if (!res.ok) throw new Error('Failed to load expenses');
    return res.json();
  },

  async get(id: string): Promise<any> {
    const res = await apiFetch(`/api/v1/expenses/${id}`);
    if (!res.ok) throw new Error('Expense not found');
    return res.json();
  },

  async create(payload: FormData): Promise<any> {
    const res = await apiUpload('/api/v1/expenses', payload);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Submission failed' }));
      throw new Error(err.detail || 'Submission failed');
    }
    return res.json();
  },

  async pollJob(expenseId: string): Promise<any> {
    const res = await apiFetch(`/api/v1/jobs/${expenseId}`);
    return res.json();
  },
};

// ── Approvals API ──
export const approvals = {
  async pending(): Promise<any> {
    const res = await apiFetch('/api/v1/approvals/pending');
    if (!res.ok) throw new Error('Failed to load approvals');
    return res.json();
  },

  async approve(id: string, comment?: string): Promise<any> {
    const res = await apiFetch(`/api/v1/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    });
    if (!res.ok) throw new Error('Approval failed');
    return res.json();
  },

  async reject(id: string, reason: string): Promise<any> {
    const res = await apiFetch(`/api/v1/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error('Rejection failed');
    return res.json();
  },
};

// ── Groups API ──
export const groups = {
  async list(): Promise<any> {
    const res = await apiFetch('/api/v1/groups');
    if (!res.ok) throw new Error('Failed to load groups');
    return res.json();
  },

  async create(name: string, description?: string): Promise<any> {
    const res = await apiFetch('/api/v1/groups', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    });
    if (!res.ok) throw new Error('Failed to create group');
    return res.json();
  },

  async get(id: string): Promise<any> {
    const res = await apiFetch(`/api/v1/groups/${id}`);
    if (!res.ok) throw new Error('Group not found');
    return res.json();
  },
};

// ── Witnesses API ──
export const witnesses = {
  async add(expenseId: string, email: string): Promise<any> {
    const res = await apiFetch(`/api/v1/expenses/${expenseId}/witnesses`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
    if (!res.ok) throw new Error('Failed to add witness');
    return res.json();
  },
};

// ── Currencies API ──
export const currencies = {
  async list(): Promise<any> {
    const res = await apiFetch('/api/v1/currencies');
    if (!res.ok) throw new Error('Failed to load currencies');
    return res.json();
  },
};

// ── Dashboard summary (aggregated) ──
export const dashboard = {
  async summary(): Promise<any> {
    // Backend may not have a dedicated summary endpoint,
    // so we fetch expenses and compute. 
    const data = await expenses.list({ per_page: 100 });
    const list = data.expenses || data.items || data || [];
    const total = list.reduce((s: number, e: any) => s + (e.amount || 0), 0);
    const pending = list.filter((e: any) => e.status === 'pending_approval' || e.status === 'pending_review');
    const avgTrust = list.length > 0
      ? Math.round(list.reduce((s: number, e: any) => s + (e.trust_score || 0), 0) / list.length)
      : 0;
    return {
      total_expenses: total,
      pending_count: pending.length,
      average_trust: avgTrust,
      recent: list.slice(0, 8),
      all: list,
    };
  },
};
