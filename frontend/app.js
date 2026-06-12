/* ==========================================
   INSPECTSHIELD PRO FRONTEND APP CONTROLLER
   ========================================== */

const API_BASE = window.location.origin;

// State management
let state = {
    token: localStorage.getItem('access_token') || '',
    user: null,
    projects: [],
    inspections: [],
    activePanel: 'panel-dashboard',
    theme: localStorage.getItem('theme') || 'light-theme',
    
    // Calibration state
    calibration: {
        isCalibrating: false,
        img: null,
        startX: 0,
        startY: 0,
        endX: 0,
        endY: 0,
        isDrawing: false
    },
    uploadedFile: null,
    
    // Polling handles
    trainingPollInterval: null,
    severityChart: null
};

// --- CORE SYSTEM INITIALIZATION ---

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setupEventListeners();
    checkAuthSession();
});

function initTheme() {
    document.body.className = state.theme;
}

function setupEventListeners() {
    // Theme Toggle
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

    // Auth forms
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('signup-form').addEventListener('submit', handleSignup);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    
    // Tab switching in Auth card
    document.getElementById('tab-login-btn').addEventListener('click', () => toggleAuthTabs('login'));
    document.getElementById('tab-signup-btn').addEventListener('click', () => toggleAuthTabs('signup'));

    // Sidebar navigation
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = e.currentTarget.getAttribute('data-target');
            switchPanel(target);
        });
    });

    // Projects Form
    document.getElementById('new-project-form').addEventListener('submit', handleCreateProject);

    // Metrology Settings events
    document.getElementById('met-method').addEventListener('change', (e) => {
        const frangiGroup = document.getElementById('frangi-slider-group');
        frangiGroup.style.display = e.target.value === 'frangi' ? 'block' : 'none';
    });
    
    document.getElementById('met-frangi-thresh').addEventListener('input', (e) => {
        document.getElementById('frangi-thresh-val').textContent = e.target.value;
    });

    // File input preview
    const fileInput = document.getElementById('file-input');
    fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop for uploads
    const dropZone = document.getElementById('drop-zone');
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect({ target: fileInput });
        }
    });

    // Metrology Form execution
    document.getElementById('metrology-form').addEventListener('submit', executeMetrology);

    // Image Output visual matrix tab selectors
    document.querySelectorAll('.matrix-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.matrix-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.matrix-tab-content').forEach(c => c.classList.remove('active'));
            
            e.currentTarget.classList.add('active');
            const targetId = e.currentTarget.getAttribute('data-tab');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Interactive Calibration Canvas Ruler Events
    const openCalibBtn = document.getElementById('open-calibrate-btn');
    openCalibBtn.addEventListener('click', startCalibrationMode);
    
    const closeCalibBtn = document.getElementById('close-calibration-btn');
    closeCalibBtn.addEventListener('click', stopCalibrationMode);

    const canvas = document.getElementById('calibration-canvas');
    canvas.addEventListener('mousedown', canvasMouseDown);
    canvas.addEventListener('mousemove', canvasMouseMove);
    window.addEventListener('mouseup', canvasMouseUp);

    // Calibration modal actions
    document.getElementById('apply-calibration-btn').addEventListener('click', applyCalibration);
    document.getElementById('cancel-calibration-btn').addEventListener('click', () => {
        document.getElementById('calibration-prompt-modal').style.display = 'none';
        stopCalibrationMode();
    });

    // Ledger Search & Filters
    document.getElementById('ledger-search').addEventListener('input', renderLedgerTable);
    document.getElementById('ledger-severity-filter').addEventListener('change', renderLedgerTable);
    document.getElementById('export-csv-btn').addEventListener('click', handleExportCSV);

    // Model management
    document.getElementById('change-backbone-form').addEventListener('submit', handleActiveBackboneChange);
    document.getElementById('seed-data-form').addEventListener('submit', handleSeedSynthetic);
    document.getElementById('train-model-form').addEventListener('submit', handleStartTraining);
}


// --- API CLIENT WRAPPERS (With JWT authentication) ---

async function apiRequest(endpoint, options = {}) {
    const headers = options.headers || {};
    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (response.status === 401 && endpoint !== '/api/auth/login' && endpoint !== '/api/auth/me') {
        // Expired credentials fallback
        handleLogout();
        throw new Error("Authorization credentials expired.");
    }

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "Server communication error.");
    }
    return data;
}


// --- THEME & UTILS ---

function toggleTheme() {
    state.theme = state.theme === 'dark-theme' ? 'light-theme' : 'dark-theme';
    localStorage.setItem('theme', state.theme);
    initTheme();
    // Re-draw chart to match colors
    if (state.severityChart) {
        buildDashboardChart();
    }
}

function updateSystemClock() {
    const now = new Date();
    document.getElementById('current-time-string').textContent = 
        `SYSTEM ACTIVE: ${now.toLocaleDateString()} | ${now.toLocaleTimeString()}`;
}
setInterval(updateSystemClock, 1000);


// --- AUTHENTICATION FLOWS ---

function toggleAuthTabs(mode) {
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const loginTabBtn = document.getElementById('tab-login-btn');
    const signupTabBtn = document.getElementById('tab-signup-btn');
    
    document.getElementById('auth-status-msg').className = 'status-msg';
    document.getElementById('auth-status-msg').textContent = '';

    if (mode === 'login') {
        loginForm.classList.add('active');
        signupForm.classList.remove('active');
        loginTabBtn.classList.add('active');
        signupTabBtn.classList.remove('active');
    } else {
        loginForm.classList.remove('active');
        signupForm.classList.add('active');
        loginTabBtn.classList.remove('active');
        signupTabBtn.classList.add('active');
    }
}

async function checkAuthSession() {
    if (!state.token) {
        showAuthScreen();
        return;
    }

    try {
        const user = await apiRequest('/api/auth/me');
        state.user = user;
        showMainApp();
    } catch (err) {
        handleLogout();
    }
}

function showAuthScreen() {
    document.getElementById('auth-container').style.display = 'flex';
    document.getElementById('app-container').style.display = 'none';
}

function showMainApp() {
    document.getElementById('auth-container').style.display = 'none';
    document.getElementById('app-container').style.display = 'flex';
    
    // Update profile view
    document.getElementById('user-display-name').textContent = state.user.username;
    
    const roleBadge = document.getElementById('user-role-badge');
    roleBadge.textContent = state.user.role === 'administrator' ? 'Administrator' : 'Inspector';
    roleBadge.className = `badge ${state.user.role === 'administrator' ? 'badge-blue' : 'badge-gray'}`;

    // Load initial data
    loadProjects();
    loadInspections();
    loadActiveModelDetails();
    switchPanel('panel-dashboard');
}

async function handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('login-username').value;
    const passwordInput = document.getElementById('login-password').value;
    const msg = document.getElementById('auth-status-msg');

    try {
        const params = new URLSearchParams();
        params.append('username', usernameInput);
        params.append('password', passwordInput);

        const res = await apiRequest('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params
        });

        state.token = res.access_token;
        localStorage.setItem('access_token', res.access_token);
        
        // Clear inputs
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';
        
        await checkAuthSession();
    } catch (err) {
        msg.className = 'status-msg error';
        msg.textContent = err.message;
    }
}

async function handleSignup(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('signup-username').value;
    const passwordInput = document.getElementById('signup-password').value;
    const msg = document.getElementById('auth-status-msg');

    try {
        const params = new URLSearchParams();
        params.append('username', usernameInput);
        params.append('password', passwordInput);

        const res = await apiRequest('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params
        });

        msg.className = 'status-msg success';
        msg.textContent = 'Account created! Please log in above.';
        
        // Clear inputs and switch back
        document.getElementById('signup-username').value = '';
        document.getElementById('signup-password').value = '';
        setTimeout(() => toggleAuthTabs('login'), 1500);
    } catch (err) {
        msg.className = 'status-msg error';
        msg.textContent = err.message;
    }
}

function handleLogout() {
    state.token = '';
    state.user = null;
    localStorage.removeItem('access_token');
    
    // Clear state intervals
    if (state.trainingPollInterval) {
        clearInterval(state.trainingPollInterval);
    }
    
    showAuthScreen();
}


// --- VIEWPORT ROUTER SWITCHING ---

function switchPanel(panelId) {
    // Hide all panels
    document.querySelectorAll('.app-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    
    // Show active panel
    const targetPanel = document.getElementById(panelId);
    if (targetPanel) {
        targetPanel.classList.add('active');
        state.activePanel = panelId;
    }
    
    // Highlight sidebar link
    const sidebarLink = document.querySelector(`.nav-link[data-target="${panelId}"]`);
    if (sidebarLink) {
        sidebarLink.classList.add('active');
    }

    // Dynamic routing hooks
    if (panelId === 'panel-dashboard') {
        document.getElementById('page-title-heading').textContent = "Dashboard Overview";
        loadInspections(); // reload metrics
    } else if (panelId === 'panel-projects') {
        document.getElementById('page-title-heading').textContent = "Tracked Sites & Projects";
        loadProjects();
    } else if (panelId === 'panel-metrology') {
        document.getElementById('page-title-heading').textContent = "Interactive Metrology Studio";
        populateProjectsDropdown();
    } else if (panelId === 'panel-ledger') {
        document.getElementById('page-title-heading').textContent = "Structural Safety Ledger";
        loadInspections();
    } else if (panelId === 'panel-model') {
        document.getElementById('page-title-heading').textContent = "Model Training Suite";
        loadActiveModelDetails();
        checkTrainingRunsHistory();
    }
}


// --- PROJECTS SCOPE LOGIC ---

async function loadProjects() {
    try {
        const list = await apiRequest('/api/projects');
        state.projects = list;
        renderProjectsList();
    } catch (err) {
        console.error(err);
    }
}

function renderProjectsList() {
    const listContainer = document.getElementById('projects-list');
    listContainer.innerHTML = '';
    
    if (state.projects.length === 0) {
        listContainer.innerHTML = '<p class="text-center" style="grid-column: 1/-1; color: var(--text-muted);">No construction sites cataloged yet.</p>';
        return;
    }

    state.projects.forEach(p => {
        const card = document.createElement('div');
        card.className = 'project-card';
        card.innerHTML = `
            <h4>🏢 ${p.name}</h4>
            <span class="project-location">📍 ${p.location || 'Unknown location'}</span>
            <p>${p.description || 'No description provided.'}</p>
            <div class="project-card-footer">
                <small style="color: var(--text-muted);">Created: ${new Date(p.created_at).toLocaleDateString()}</small>
                <button class="btn btn-danger btn-xs" onclick="deleteProject(${p.id})">Purge Site</button>
            </div>
        `;
        listContainer.appendChild(card);
    });
}

async function handleCreateProject(e) {
    e.preventDefault();
    const name = document.getElementById('proj-name').value;
    const location = document.getElementById('proj-location').value;
    const description = document.getElementById('proj-desc').value;

    try {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('location', location);
        formData.append('description', description);

        await apiRequest('/api/projects', {
            method: 'POST',
            body: formData
        });

        // Reset form
        document.getElementById('proj-name').value = '';
        document.getElementById('proj-location').value = '';
        document.getElementById('proj-desc').value = '';
        
        loadProjects();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteProject(id) {
    if (!confirm("Caution! Deleting this project will unlink all associated inspections in the database. Continue?")) {
        return;
    }
    try {
        await apiRequest(`/api/projects/${id}`, { method: 'DELETE' });
        loadProjects();
    } catch (err) {
        alert(err.message);
    }
}

function populateProjectsDropdown() {
    const select = document.getElementById('met-project-select');
    select.innerHTML = '<option value="">Unassigned (General Audit)</option>';
    state.projects.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        select.appendChild(opt);
    });
}


// --- INSPECTIONS & METROLOGY STUDIO LOGIC ---

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    state.uploadedFile = file;
    document.getElementById('execute-metrology-btn').disabled = false;
    
    // Hide matrix view
    document.getElementById('output-matrix').style.display = 'none';

    // Show image preview
    const reader = new FileReader();
    reader.onload = (event) => {
        const preview = document.getElementById('image-preview');
        preview.src = event.target.result;
        
        const previewBox = document.getElementById('preview-container');
        previewBox.style.display = 'flex';
        
        // Hide canvas calibration stuff until activated
        const canvas = document.getElementById('calibration-canvas');
        canvas.style.display = 'none';
        document.getElementById('calibration-instructions').style.display = 'none';
        
        // Save image representation for canvas draw tasks
        state.calibration.img = new Image();
        state.calibration.img.src = event.target.result;
    };
    reader.readAsDataURL(file);
}

// --- INTERACTIVE DRAWING CALIBRATION CONTROLLER ---

function startCalibrationMode() {
    if (!state.uploadedFile) {
        alert("Upload a concrete surface scan image first.");
        return;
    }

    state.calibration.isCalibrating = true;
    
    const canvas = document.getElementById('calibration-canvas');
    const preview = document.getElementById('image-preview');
    
    // Fit canvas bounds exactly to the image's layout sizes
    canvas.style.display = 'block';
    canvas.width = preview.clientWidth;
    canvas.height = preview.clientHeight;
    
    document.getElementById('calibration-instructions').style.display = 'flex';
    
    // Render initial canvas contents
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function stopCalibrationMode() {
    state.calibration.isCalibrating = false;
    document.getElementById('calibration-canvas').style.display = 'none';
    document.getElementById('calibration-instructions').style.display = 'none';
}

function canvasMouseDown(e) {
    if (!state.calibration.isCalibrating) return;
    
    const rect = e.currentTarget.getBoundingClientRect();
    state.calibration.startX = e.clientX - rect.left;
    state.calibration.startY = e.clientY - rect.top;
    state.calibration.isDrawing = true;
}

function canvasMouseMove(e) {
    if (!state.calibration.isCalibrating || !state.calibration.isDrawing) return;
    
    const canvas = e.currentTarget;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    
    state.calibration.endX = e.clientX - rect.left;
    state.calibration.endY = e.clientY - rect.top;
    
    // Clear and redraw ruler line
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 3;
    ctx.setLineDash([5, 5]);
    
    ctx.beginPath();
    ctx.moveTo(state.calibration.startX, state.calibration.startY);
    ctx.lineTo(state.calibration.endX, state.calibration.endY);
    ctx.stroke();
    
    // Draw circles at anchors
    ctx.fillStyle = '#ef4444';
    ctx.beginPath();
    ctx.arc(state.calibration.startX, state.calibration.startY, 5, 0, 2*Math.PI);
    ctx.arc(state.calibration.endX, state.calibration.endY, 5, 0, 2*Math.PI);
    ctx.fill();
}

function canvasMouseUp(e) {
    if (!state.calibration.isCalibrating || !state.calibration.isDrawing) return;
    state.calibration.isDrawing = false;
    
    // Calculate pixel distance drawn
    const dx = state.calibration.endX - state.calibration.startX;
    const dy = state.calibration.endY - state.calibration.startY;
    const distancePixels = Math.sqrt(dx*dx + dy*dy);
    
    if (distancePixels < 5) return; // ignore jitter
    
    // Compute scaling relative to original full resolution image file
    const preview = document.getElementById('image-preview');
    const naturalWidth = state.calibration.img.naturalWidth;
    const renderedWidth = preview.clientWidth;
    const scaleFactor = naturalWidth / renderedWidth;
    
    const actualPixels = distancePixels * scaleFactor;
    
    document.getElementById('drawn-pixels-count').textContent = Math.round(actualPixels);
    document.getElementById('calibration-prompt-modal').style.display = 'flex';
}

function applyCalibration() {
    const pixels = parseFloat(document.getElementById('drawn-pixels-count').textContent);
    const mm = parseFloat(document.getElementById('real-world-distance').value);
    
    if (isNaN(pixels) || isNaN(mm) || mm <= 0) {
        alert("Enter a valid physical reference dimension.");
        return;
    }
    
    const ratio = mm / pixels;
    
    // Set ratio in setting inputs
    document.getElementById('met-scale-ratio').value = ratio.toFixed(4);
    document.getElementById('scale-ratio-val').textContent = ratio.toFixed(4);
    
    // Hide modal and close ruler Mode
    document.getElementById('calibration-prompt-modal').style.display = 'none';
    stopCalibrationMode();
}

// --- EXECUTE METROLOGY ENGINE ---

async function executeMetrology(e) {
    e.preventDefault();
    if (!state.uploadedFile) return;

    const btn = document.getElementById('execute-metrology-btn');
    const badge = document.getElementById('stage-status-badge');
    
    btn.disabled = true;
    badge.textContent = "RUNNING STAGES...";
    badge.className = "badge badge-blue";

    const projectId = document.getElementById('met-project-select').value;
    const ratio = document.getElementById('met-scale-ratio').value;
    const forceStage2 = document.getElementById('met-force-stage2').checked;
    const method = document.getElementById('met-method').value;
    const frangiThresh = document.getElementById('met-frangi-thresh').value;
    const notes = document.getElementById('met-notes').value;

    try {
        const formData = new FormData();
        formData.append('file', state.uploadedFile);
        formData.append('pixel_to_mm_ratio', ratio);
        formData.append('use_frangi', method === 'frangi');
        formData.append('frangi_thresh', frangiThresh);
        formData.append('force_stage_2', forceStage2);
        if (projectId) formData.append('project_id', projectId);
        if (notes) formData.append('notes', notes);

        const res = await apiRequest('/api/inspections', {
            method: 'POST',
            body: formData
        });

        // Display results
        document.getElementById('out-width').textContent = `${res.max_width_mm.toFixed(2)} mm`;
        document.getElementById('out-length').textContent = `${res.length_mm.toFixed(2)} mm`;
        
        const badgeEl = document.getElementById('out-severity-badge');
        badgeEl.textContent = res.severity;
        
        // Determine coloring class
        badgeEl.className = 'badge';
        if (res.severity.includes('Intact')) badgeEl.classList.add('badge-green');
        else if (res.severity.includes('Hairline')) badgeEl.classList.add('badge-blue');
        else if (res.severity.includes('Medium')) badgeEl.classList.add('badge-yellow');
        else badgeEl.classList.add('badge-red');

        // Set images
        document.getElementById('out-img-raw').src = res.raw_image_url;
        document.getElementById('out-img-mask').src = res.mask_url;
        document.getElementById('out-img-skel').src = res.skeleton_url;

        // Show visual matrix
        document.getElementById('output-matrix').style.display = 'block';
        
        // Default to showing raw tab
        document.querySelector('.matrix-tab[data-tab="tab-raw"]').click();
        
        // Reset status
        badge.textContent = "COMPLETED";
        badge.className = "badge badge-green";
        
        // Clear notes form input
        document.getElementById('met-notes').value = '';
        
    } catch (err) {
        alert(err.message);
        badge.textContent = "FAILED";
        badge.className = "badge badge-red";
    } finally {
        btn.disabled = false;
    }
}


// --- INSPECTION LEDGER LISTING LOGIC ---

async function loadInspections() {
    try {
        const list = await apiRequest('/api/inspections');
        state.inspections = list;
        
        if (state.activePanel === 'panel-dashboard') {
            updateDashboardMetrics();
        } else if (state.activePanel === 'panel-ledger') {
            renderLedgerTable();
        }
    } catch (err) {
        console.error(err);
    }
}

function updateDashboardMetrics() {
    let total = state.inspections.length;
    let warning = 0;
    let critical = 0;
    let clean = 0;

    state.inspections.forEach(ins => {
        if (ins.severity.includes('Intact')) clean++;
        else if (ins.severity.includes('Medium')) warning++;
        else if (ins.severity.includes('CRITICAL')) critical++;
        else clean++; // hairline as safe/clean
    });

    document.getElementById('dash-total-inspections').textContent = total;
    document.getElementById('dash-warning-inspections').textContent = warning;
    document.getElementById('dash-critical-inspections').textContent = critical;
    document.getElementById('dash-clean-inspections').textContent = clean;

    // Load recent tables
    const recentBody = document.getElementById('dash-recent-inspections');
    recentBody.innerHTML = '';
    
    if (state.inspections.length === 0) {
        recentBody.innerHTML = '<tr><td colspan="4" class="text-center">No reports cataloged yet.</td></tr>';
    } else {
        state.inspections.slice(0, 5).forEach(ins => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${new Date(ins.created_at).toLocaleDateString()}</td>
                <td>${ins.filename}</td>
                <td>${ins.max_width_mm.toFixed(2)} mm</td>
                <td><span class="badge ${ins.severity.includes('Intact') ? 'badge-green' : ins.severity.includes('CRITICAL') ? 'badge-red' : 'badge-yellow'}">${ins.severity.split(' ')[0]}</span></td>
            `;
            recentBody.appendChild(tr);
        });
    }

    buildDashboardChart();
}

function buildDashboardChart() {
    const ctx = document.getElementById('severityPieChart').getContext('2d');
    
    let clean = 0, hairline = 0, moderate = 0, critical = 0;
    state.inspections.forEach(i => {
        if (i.severity.includes('Intact')) clean++;
        else if (i.severity.includes('Hairline')) hairline++;
        else if (i.severity.includes('Medium')) moderate++;
        else if (i.severity.includes('CRITICAL')) critical++;
    });

    if (state.severityChart) {
        state.severityChart.destroy();
    }

    if (state.inspections.length === 0) {
        // Draw empty indicator
        state.severityChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['No Data'],
                datasets: [{
                    data: [1],
                    backgroundColor: ['#475569']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
        return;
    }

    const isDark = state.theme === 'dark-theme';
    const textColor = isDark ? '#f8fafc' : '#0f172a';

    state.severityChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Intact', 'Hairline', 'Moderate', 'Critical'],
            datasets: [{
                data: [clean, hairline, moderate, critical],
                backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'],
                borderWidth: 2,
                borderColor: isDark ? '#1e293b' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: textColor,
                        font: { family: 'Inter' }
                    }
                }
            }
        }
    });
}

function renderLedgerTable() {
    const searchVal = document.getElementById('ledger-search').value.toLowerCase();
    const severityVal = document.getElementById('ledger-severity-filter').value;
    const body = document.getElementById('ledger-rows');
    
    body.innerHTML = '';
    
    const filtered = state.inspections.filter(ins => {
        const matchesSearch = ins.filename.toLowerCase().includes(searchVal) || 
                              (ins.notes && ins.notes.toLowerCase().includes(searchVal));
        
        let matchesSeverity = true;
        if (severityVal) {
            matchesSeverity = ins.severity.includes(severityVal);
        }
        
        return matchesSearch && matchesSeverity;
    });

    if (filtered.length === 0) {
        body.innerHTML = '<tr><td colspan="8" class="text-center" style="color: var(--text-muted);">No reports match the active filter criteria.</td></tr>';
        return;
    }

    filtered.forEach(ins => {
        const tr = document.createElement('tr');
        
        let badgeClass = 'badge-green';
        if (ins.severity.includes('Hairline')) badgeClass = 'badge-blue';
        else if (ins.severity.includes('Medium')) badgeClass = 'badge-yellow';
        else if (ins.severity.includes('CRITICAL')) badgeClass = 'badge-red';
        
        tr.innerHTML = `
            <td>${new Date(ins.created_at).toLocaleString()}</td>
            <td><strong>${ins.project_name}</strong></td>
            <td><a href="${ins.raw_image_path}" target="_blank" style="color: var(--primary); text-decoration:none;">🔗 ${ins.filename}</a></td>
            <td>${ins.max_width_mm.toFixed(2)} mm</td>
            <td>${ins.length_mm.toFixed(2)} mm</td>
            <td><span class="badge ${badgeClass}">${ins.severity.split(' ')[0]}</span></td>
            <td><span style="font-size:12px; color: var(--text-secondary);">${ins.notes || '--'}</span></td>
            <td class="text-right">
                <button class="btn btn-danger btn-xs" onclick="deleteInspection(${ins.id})">Purge</button>
            </td>
        `;
        body.appendChild(tr);
    });
}

async function deleteInspection(id) {
    if (!confirm("Are you sure you want to permanently delete this metrology report?")) {
        return;
    }
    try {
        await apiRequest(`/api/inspections/${id}`, { method: 'DELETE' });
        loadInspections();
    } catch (err) {
        alert(err.message);
    }
}

async function handleExportCSV(e) {
    e.preventDefault();
    if (!state.token) return;

    try {
        // Fetch raw data using authorization tokens
        const response = await fetch(`${API_BASE}/api/reports/export`, {
            headers: {
                'Authorization': `Bearer ${state.token}`
            }
        });

        if (!response.ok) throw new Error("CSV generation failed.");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `inspectshield_${state.user.username}_history.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        alert(err.message);
    }
}


// --- MODEL ENGINE & TRAINING WORKER ---

async function loadActiveModelDetails() {
    try {
        const details = await apiRequest('/api/models/active');
        document.getElementById('active-backbone-name').textContent = details.active_backbone.toUpperCase();
        document.getElementById('active-weights-status').textContent = details.weights_loaded ? "Trained weights activated" : "Default uninitialized fallback";
        document.getElementById('active-device-status').textContent = details.device;
        document.getElementById('active-modified-time').textContent = details.last_modified ? new Date(details.last_modified).toLocaleString() : "N/A";
        
        // Select matching option
        document.getElementById('change-backbone-select').value = details.active_backbone;
    } catch (err) {
        console.error(err);
    }
}

async function handleActiveBackboneChange(e) {
    e.preventDefault();
    if (state.user.role !== 'administrator') {
        alert("Administrator role credentials required to modify active backbone weights.");
        return;
    }

    const val = document.getElementById('change-backbone-select').value;
    try {
        const formData = new FormData();
        formData.append('backbone_name', val);

        await apiRequest('/api/models/active', {
            method: 'POST',
            body: formData
        });

        alert("Backbone switched successfully!");
        loadActiveModelDetails();
    } catch (err) {
        alert(err.message);
    }
}

async function handleSeedSynthetic(e) {
    e.preventDefault();
    if (state.user.role !== 'administrator') {
        alert("Administrator credentials required.");
        return;
    }
    
    const count = document.getElementById('seed-count').value;
    const btn = e.submitter;
    btn.disabled = true;
    btn.textContent = "Seeding data...";

    try {
        const formData = new FormData();
        formData.append('count', count);
        
        const res = await apiRequest('/api/models/synthetic', {
            method: 'POST',
            body: formData
        });
        
        alert(res.message + " Please wait a few seconds for completion before starting optimization.");
    } catch (err) {
        alert(err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Generate Synthetic Dataset";
    }
}

async function handleStartTraining(e) {
    e.preventDefault();
    const backbone = document.getElementById('train-backbone-select').value;
    const epochs = document.getElementById('train-epochs').value;
    const btn = document.getElementById('start-training-btn');

    btn.disabled = true;
    btn.textContent = "Queuing optimization session...";

    try {
        const formData = new FormData();
        formData.append('backbone_name', backbone);
        formData.append('epochs', epochs);

        const res = await apiRequest('/api/models/train', {
            method: 'POST',
            body: formData
        });

        document.getElementById('training-progress-box').style.display = 'block';
        startTrainingStatusPolling();
    } catch (err) {
        alert(err.message);
        btn.disabled = false;
        btn.textContent = "Run Model Optimization";
    }
}

async function checkTrainingRunsHistory() {
    try {
        const history = await apiRequest('/api/models/training-status');
        if (history.length > 0) {
            const latest = history[0];
            
            // If latest is running or queued, resume polling
            if (latest.status === 'running' || latest.status === 'queued') {
                document.getElementById('training-progress-box').style.display = 'block';
                document.getElementById('start-training-btn').disabled = true;
                startTrainingStatusPolling();
            } else {
                updateTrainingUI(latest);
            }
        }
    } catch (err) {
        console.error(err);
    }
}

function startTrainingStatusPolling() {
    if (state.trainingPollInterval) {
        clearInterval(state.trainingPollInterval);
    }

    state.trainingPollInterval = setInterval(async () => {
        try {
            const history = await apiRequest('/api/models/training-status');
            if (history.length === 0) return;

            const latest = history[0];
            updateTrainingUI(latest);

            if (latest.status !== 'running' && latest.status !== 'queued') {
                // Done or failed
                clearInterval(state.trainingPollInterval);
                state.trainingPollInterval = null;
                document.getElementById('start-training-btn').disabled = false;
                document.getElementById('start-training-btn').textContent = "Run Model Optimization";
                loadActiveModelDetails(); // reload details if weights changed
            }
        } catch (err) {
            console.error("Polling error: ", err);
            clearInterval(state.trainingPollInterval);
        }
    }, 2000);
}

function updateTrainingUI(session) {
    const statusLabel = document.getElementById('train-status-label');
    const epochLabel = document.getElementById('train-epoch-label');
    const lossLabel = document.getElementById('train-loss-label');
    const accLabel = document.getElementById('train-acc-label');
    const progressBar = document.getElementById('train-progress-bar');
    const consoleLog = document.getElementById('training-log-console');

    statusLabel.textContent = session.status.toUpperCase();
    statusLabel.className = '';
    
    if (session.status === 'queued') statusLabel.classList.add('text-muted');
    else if (session.status === 'running') statusLabel.classList.add('text-yellow');
    else if (session.status === 'completed') statusLabel.classList.add('text-green');
    else statusLabel.classList.add('text-red');

    epochLabel.textContent = `${session.current_epoch}/${session.epochs}`;
    lossLabel.textContent = session.loss !== null ? session.loss.toFixed(4) : '--';
    accLabel.textContent = session.accuracy !== null ? `${(session.accuracy * 100).toFixed(2)}%` : '--';

    // Update progress bar
    const pct = session.epochs > 0 ? (session.current_epoch / session.epochs) * 100 : 0;
    progressBar.style.width = `${pct}%`;
    
    if (session.status === 'completed') progressBar.style.backgroundColor = '#10b981';
    else if (session.status === 'failed') progressBar.style.backgroundColor = '#ef4444';
    else progressBar.style.backgroundColor = '#f59e0b';

    // Update logs
    consoleLog.textContent = session.logs || 'Console awaiting stream...';
    consoleLog.scrollTop = consoleLog.scrollHeight;
}
