const API_BASE = "http://localhost:8000/api";

// DOM Elements
const packagesContainer = document.getElementById('packages-list');
const btnOptimize = document.getElementById('btn-optimize');
const progressContainer = document.getElementById('progress-container');
const progressBar = document.getElementById('progress-bar');
const resultsTableBody = document.querySelector('#results-table tbody');

// Load Packages on Start
async function loadPackages() {
    try {
        const res = await fetch(`${API_BASE}/packages`);
        const packages = await res.json();

        packagesContainer.innerHTML = '';
        packages.forEach(pkg => {
            const div = document.createElement('div');
            div.className = 'pkg-checkbox';
            div.innerHTML = `
                <input type="checkbox" value="${pkg}" checked>
                <span>${pkg}</span>
            `;
            packagesContainer.appendChild(div);
        });
    } catch (e) {
        packagesContainer.innerHTML = '<div style="color:red">Failed to connect to backend. Is it running?</div>';
    }
}

// Gather Inputs
function getConstraints() {
    const packages = Array.from(packagesContainer.querySelectorAll('input:checked')).map(cb => cb.value);

    return {
        target_cap: parseFloat(document.getElementById('target_cap').value),
        tolerance: parseFloat(document.getElementById('tolerance').value),
        dc_bias: parseFloat(document.getElementById('dc_bias').value),
        max_count: parseInt(document.getElementById('max_count').value),
        min_rated_volt: parseFloat(document.getElementById('min_rated').value),
        min_temp: parseFloat(document.getElementById('min_temp').value),
        conn_type: parseInt(document.getElementById('conn_type').value),
        packages: packages
    };
}

// Run Optimization
async function runOptimization() {
    // UI State -> Loading
    btnOptimize.style.display = 'none';
    progressContainer.style.display = 'block';
    resultsTableBody.innerHTML = ''; // Clear prev results

    // Fake progress animation since backend is sync
    let progress = 0;
    const interval = setInterval(() => {
        progress += 5;
        if (progress > 90) progress = 90; // Stall at 90%
        progressBar.style.width = `${progress}%`;
    }, 100);

    try {
        const payload = getConstraints();

        const res = await fetch(`${API_BASE}/optimize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const results = await res.json();

        renderResults(results);

    } catch (e) {
        alert("Optimization Failed: " + e.message);
    } finally {
        // UI State -> Done
        clearInterval(interval);
        progressBar.style.width = '100%';

        setTimeout(() => {
            progressContainer.style.display = 'none';
            btnOptimize.style.display = 'block';
            progressBar.style.width = '0%';
        }, 500);
    }
}

function renderResults(results) {
    if (!results || results.length === 0) {
        resultsTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center">No valid solutions found.</td></tr>';
        return;
    }

    results.forEach((r, index) => {
        const row = document.createElement('tr');

        let tagClass = 'tag-1p';
        if (r.Type === '2p') tagClass = 'tag-2p';
        if (r.Type === '3p') tagClass = 'tag-3p';

        row.innerHTML = `
            <td style="text-align:center; color:var(--accent-color)">${index + 1}</td>
            <td style="text-align:center"><span class="tag ${tagClass}">${r.Type}</span></td>
            <td style="text-align:center">${parseFloat(r.Vol).toFixed(4)}</td>
            <td style="text-align:center">${(r.Cap * 1e6).toFixed(2)}</td>
            <td>${r.Cfg}</td>
        `;
        resultsTableBody.appendChild(row);
    });
}

// Init
loadPackages();
