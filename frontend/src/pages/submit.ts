// Submit Expense Page
import { expenses } from '../api';
import { renderPage, requireAuth, toast } from '../components';
import { navigate } from '../router';

export function renderSubmit() {
  if (!requireAuth()) return;
  const app = document.getElementById('app')!;

  app.innerHTML = renderPage('/submit', 'Submit New Expense', `
    <div class="page-content">
      <div style="display:grid;grid-template-columns:1fr 320px;gap:32px;max-width:1200px">
        <!-- Main Form -->
        <div class="card card-glass">
          <!-- Step Indicator -->
          <div style="display:flex;gap:8px;margin-bottom:32px">
            <div style="flex:1;text-align:center">
              <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--primary),var(--primary-container));color:var(--on-primary-fixed);margin:0 auto 8px;display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700">1</div>
              <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--primary)">Details</span>
            </div>
            <div style="flex:1;text-align:center;opacity:0.4">
              <div style="width:32px;height:32px;border-radius:50%;background:var(--surface-container-highest);margin:0 auto 8px;display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700">2</div>
              <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Receipt</span>
            </div>
            <div style="flex:1;text-align:center;opacity:0.4">
              <div style="width:32px;height:32px;border-radius:50%;background:var(--surface-container-highest);margin:0 auto 8px;display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700">3</div>
              <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Verify</span>
            </div>
          </div>

          <form id="expense-form">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
              <div class="form-group">
                <label class="form-label" for="exp-category">Expense Category</label>
                <select class="form-input form-select" id="exp-category" required>
                  <option value="">Select category</option>
                  <option value="travel">Travel</option>
                  <option value="meals">Meals & Entertainment</option>
                  <option value="accommodation">Accommodation</option>
                  <option value="office_supplies">Office Supplies</option>
                  <option value="client_entertainment">Client Entertainment</option>
                  <option value="communication">Communication</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label" for="exp-amount">Amount (₹)</label>
                <input class="form-input" type="number" id="exp-amount" placeholder="0.00" step="0.01" min="1" required />
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
              <div class="form-group">
                <label class="form-label" for="exp-date">Date</label>
                <input class="form-input" type="date" id="exp-date" required />
              </div>
              <div class="form-group">
                <label class="form-label" for="exp-vendor">Merchant / Vendor</label>
                <input class="form-input" type="text" id="exp-vendor" placeholder="Vendor name" required />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="exp-desc">Description</label>
              <textarea class="form-input" id="exp-desc" placeholder="Brief description of the expense" rows="3"></textarea>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
              <div class="form-group">
                <label class="form-label" for="exp-gstin">GSTIN Number</label>
                <input class="form-input" type="text" id="exp-gstin" placeholder="e.g. 27AABCU9603R1ZM" />
                <div class="form-helper">Optional — improves trust score</div>
              </div>
              <div class="form-group">
                <label class="form-label">GPS Location</label>
                <button type="button" class="btn btn-secondary btn-full" id="gps-btn">📍 Capture Current Location</button>
                <div class="form-helper" id="gps-status">Click to capture GPS coordinates</div>
                <input type="hidden" id="exp-lat" />
                <input type="hidden" id="exp-lng" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Receipt Upload</label>
              <div class="upload-zone" id="upload-zone">
                <div style="font-size:2rem;margin-bottom:8px">☁️</div>
                <p style="font-size:0.9rem;font-weight:500">Drag and drop your receipt here</p>
                <p style="font-size:0.75rem;color:var(--on-surface-variant)">JPG, PNG, PDF — Max 10MB</p>
                <input type="file" id="exp-receipt" accept="image/*,.pdf" style="display:none" />
              </div>
              <div id="receipt-preview" style="margin-top:8px"></div>
            </div>

            <button type="submit" class="btn btn-primary btn-full btn-lg" id="submit-btn">
              Submit Expense
            </button>
          </form>
        </div>

        <!-- Tips Sidebar -->
        <div>
          <div class="card" style="position:sticky;top:100px">
            <h3 style="font-size:0.9rem;font-weight:700;margin-bottom:16px">💡 Tips to Maximize Trust Score</h3>
            <ul style="list-style:none;display:flex;flex-direction:column;gap:12px">
              <li style="display:flex;align-items:start;gap:8px;font-size:0.8rem;color:var(--on-surface-variant)">
                <span style="color:var(--success)">✓</span> Upload a clear receipt photo
              </li>
              <li style="display:flex;align-items:start;gap:8px;font-size:0.8rem;color:var(--on-surface-variant)">
                <span style="color:var(--success)">✓</span> Include GSTIN number
              </li>
              <li style="display:flex;align-items:start;gap:8px;font-size:0.8rem;color:var(--on-surface-variant)">
                <span style="color:var(--success)">✓</span> Enable GPS location capture
              </li>
              <li style="display:flex;align-items:start;gap:8px;font-size:0.8rem;color:var(--on-surface-variant)">
                <span style="color:var(--success)">✓</span> Add witnesses for high-value expenses
              </li>
              <li style="display:flex;align-items:start;gap:8px;font-size:0.8rem;color:var(--on-surface-variant)">
                <span style="color:var(--success)">✓</span> Use consistent vendor names
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  `);

  // Set default date to today
  const dateInput = document.getElementById('exp-date') as HTMLInputElement;
  dateInput.value = new Date().toISOString().split('T')[0];

  // GPS Capture
  document.getElementById('gps-btn')!.addEventListener('click', () => {
    const status = document.getElementById('gps-status')!;
    status.textContent = 'Capturing location...';
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          (document.getElementById('exp-lat') as HTMLInputElement).value = String(pos.coords.latitude);
          (document.getElementById('exp-lng') as HTMLInputElement).value = String(pos.coords.longitude);
          status.innerHTML = `<span style="color:var(--success)">📍 ${pos.coords.latitude.toFixed(4)}°N, ${pos.coords.longitude.toFixed(4)}°E</span>`;
        },
        () => { status.textContent = 'Could not capture GPS. Try again.'; }
      );
    } else {
      status.textContent = 'GPS not available in this browser.';
    }
  });

  // File Upload
  const uploadZone = document.getElementById('upload-zone')!;
  const fileInput = document.getElementById('exp-receipt') as HTMLInputElement;

  uploadZone.addEventListener('click', () => fileInput.click());
  uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.style.borderColor = 'var(--primary)'; });
  uploadZone.addEventListener('dragleave', () => { uploadZone.style.borderColor = ''; });
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = '';
    if (e.dataTransfer?.files.length) {
      fileInput.files = e.dataTransfer.files;
      showPreview(fileInput.files[0]);
    }
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files?.length) showPreview(fileInput.files[0]);
  });

  function showPreview(file: File) {
    const preview = document.getElementById('receipt-preview')!;
    preview.innerHTML = `<div style="display:flex;align-items:center;gap:8px;padding:8px;background:var(--surface-container);border-radius:8px">
      <span>📎</span>
      <span style="font-size:0.8rem;flex:1">${file.name} (${(file.size / 1024).toFixed(1)} KB)</span>
      <span style="color:var(--success);font-size:0.8rem">✓</span>
    </div>`;
  }

  // Submit Handler
  document.getElementById('expense-form')!.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submit-btn')!;
    btn.innerHTML = '<div class="spinner" style="width:20px;height:20px"></div> Submitting...';
    btn.setAttribute('disabled', 'true');

    try {
      const formData = new FormData();
      formData.append('category', (document.getElementById('exp-category') as HTMLSelectElement).value);
      formData.append('amount', (document.getElementById('exp-amount') as HTMLInputElement).value);
      formData.append('expense_date', (document.getElementById('exp-date') as HTMLInputElement).value);
      formData.append('vendor_name', (document.getElementById('exp-vendor') as HTMLInputElement).value);
      formData.append('description', (document.getElementById('exp-desc') as HTMLTextAreaElement).value);

      const gstin = (document.getElementById('exp-gstin') as HTMLInputElement).value;
      if (gstin) formData.append('gstin', gstin);

      const lat = (document.getElementById('exp-lat') as HTMLInputElement).value;
      const lng = (document.getElementById('exp-lng') as HTMLInputElement).value;
      if (lat && lng) {
        formData.append('latitude', lat);
        formData.append('longitude', lng);
      }

      const receipt = (document.getElementById('exp-receipt') as HTMLInputElement).files?.[0];
      if (receipt) formData.append('receipt', receipt);

      await expenses.create(formData);
      toast('Expense submitted! Processing will begin shortly.', 'success');
      navigate('/expenses');
    } catch (err: any) {
      toast(err.message || 'Submission failed', 'error');
      btn.innerHTML = 'Submit Expense';
      btn.removeAttribute('disabled');
    }
  });
}
