// TrustFlow Frontend — Main Entry Point
import './style.css';
import { route, startRouter } from './router';
import { renderLogin } from './pages/login';
import { renderSignup } from './pages/signup';
import { renderDashboard } from './pages/dashboard';
import { renderSubmit } from './pages/submit';
import { renderExpenses } from './pages/expenses';
import { renderExpenseDetail } from './pages/detail';
import { renderApprovals } from './pages/approvals';
import { renderGroups } from './pages/groups';
import { renderSettings } from './pages/settings';
import { auth } from './api';

// ── Register Routes ──
route('/login', renderLogin);
route('/signup', renderSignup);
route('/dashboard', renderDashboard);
route('/submit', renderSubmit);
route('/expenses', renderExpenses);
route('/expenses/:id', renderExpenseDetail);
route('/approvals', renderApprovals);
route('/groups', renderGroups);
route('/settings', renderSettings);

// ── Default Route ──
route('/', () => {
  if (auth.isAuthenticated()) {
    window.location.hash = '#/dashboard';
  } else {
    window.location.hash = '#/login';
  }
});

// ── Start Router ──
startRouter();
