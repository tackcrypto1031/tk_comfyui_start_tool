/**
 * plugins.js — Plugin conflict analysis page
 */
(function() {

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-6">
                <!-- Controls -->
                <div class="card">
                    <div class="card-header">${t('plugin_conflict_report')}</div>
                    <div class="flex items-end gap-4 mt-4">
                        <div>
                            <label class="input-label">${t('plugin_environment')}</label>
                            <select id="plug-env" class="select w-64"></select>
                        </div>
                        <div class="flex-1">
                            <label class="input-label">Plugin Path</label>
                            <input type="text" id="plug-path" class="input" placeholder="${t('plugin_url_placeholder')}">
                        </div>
                        <button id="plug-btn-analyze" class="btn btn-primary">
                            <span class="material-symbols-outlined text-[16px]">search</span>
                            ${t('plugin_analyze')}
                        </button>
                    </div>
                </div>

                <!-- Results -->
                <div id="plug-results" class="hidden space-y-4">
                    <!-- Risk level banner -->
                    <div id="plug-risk-banner" class="card border-l-4 p-4"></div>

                    <!-- Summary -->
                    <div id="plug-summary" class="text-on-surface-variant text-sm"></div>

                    <!-- Recommendations -->
                    <div id="plug-recommendations" class="space-y-2"></div>

                    <!-- Conflicts table -->
                    <div class="border border-surface-container">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>${t('plugin_col_package')}</th>
                                    <th>${t('plugin_col_current')}</th>
                                    <th>${t('plugin_col_new')}</th>
                                    <th>${t('plugin_col_type')}</th>
                                    <th>${t('plugin_col_risk')}</th>
                                </tr>
                            </thead>
                            <tbody id="plug-conflicts-body"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Status -->
                <div id="plug-status" class="text-xs font-label uppercase tracking-wider text-on-surface-variant"></div>
            </div>
        `;

        document.getElementById('plug-btn-analyze').addEventListener('click', doAnalyze);
        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            const select = document.getElementById('plug-env');
            select.innerHTML = '';
            envs.forEach(env => {
                const opt = document.createElement('option');
                opt.value = env.name;
                opt.textContent = env.name;
                select.appendChild(opt);
            });
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function doAnalyze() {
        const envName = document.getElementById('plug-env').value;
        const pluginPath = document.getElementById('plug-path').value.trim();
        if (!envName || !pluginPath) {
            App.showToast(t('plugin_select_env_and_path'), 'info');
            return;
        }

        const statusEl = document.getElementById('plug-status');
        statusEl.textContent = t('plugin_analyzing');
        document.getElementById('plug-btn-analyze').disabled = true;
        document.getElementById('plug-results').classList.add('hidden');

        BridgeAPI.analyzePlugin(envName, pluginPath).then(report => {
            renderReport(report);
            statusEl.textContent = t('plugin_analysis_complete');
            document.getElementById('plug-btn-analyze').disabled = false;
        }).catch(e => {
            statusEl.textContent = t('error') + ': ' + e;
            document.getElementById('plug-btn-analyze').disabled = false;
            App.showToast(e.toString(), 'error');
        });
    }

    function renderReport(report) {
        document.getElementById('plug-results').classList.remove('hidden');

        // Risk banner
        const banner = document.getElementById('plug-risk-banner');
        const riskColors = {
            GREEN: { border: 'border-green-500', bg: 'bg-green-500/10', text: 'text-green-400', icon: 'check_circle' },
            YELLOW: { border: 'border-yellow-500', bg: 'bg-yellow-500/10', text: 'text-yellow-400', icon: 'warning' },
            HIGH: { border: 'border-orange-500', bg: 'bg-orange-500/10', text: 'text-orange-400', icon: 'error' },
            CRITICAL: { border: 'border-red-500', bg: 'bg-red-500/10', text: 'text-red-400', icon: 'dangerous' },
        };
        const rc = riskColors[report.risk_level] || riskColors.GREEN;
        banner.className = `card ${rc.border} ${rc.bg} border-l-4 p-4 flex items-center gap-3`;
        banner.innerHTML = `
            <span class="material-symbols-outlined text-2xl ${rc.text}">${rc.icon}</span>
            <div>
                <div class="font-label text-sm font-bold uppercase ${rc.text}">${t('plugin_risk_level')}: ${report.risk_level}</div>
                <div class="text-sm text-on-surface-variant mt-1">${escapeHtml(report.plugin_name || '')}</div>
            </div>
        `;

        // Summary
        document.getElementById('plug-summary').textContent = report.summary || '';

        // Recommendations
        const recsContainer = document.getElementById('plug-recommendations');
        recsContainer.innerHTML = '';
        if (report.recommendations && report.recommendations.length > 0) {
            report.recommendations.forEach(rec => {
                const div = document.createElement('div');
                div.className = 'flex items-start gap-2 text-sm text-on-surface-variant';
                div.innerHTML = `<span class="material-symbols-outlined text-[16px] text-primary mt-0.5">arrow_right</span><span>${escapeHtml(rec)}</span>`;
                recsContainer.appendChild(div);
            });
        }

        // Conflicts table
        const tbody = document.getElementById('plug-conflicts-body');
        tbody.innerHTML = '';
        if (report.conflicts && report.conflicts.length > 0) {
            report.conflicts.forEach(conflict => {
                const riskBadgeClass = {
                    GREEN: 'badge-success',
                    YELLOW: 'badge-warning',
                    HIGH: 'badge-warning',
                    CRITICAL: 'badge-danger',
                }[conflict.risk_level] || 'badge-primary';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="${conflict.is_critical ? 'text-primary font-bold' : ''}">${escapeHtml(conflict.package)}</td>
                    <td class="font-mono text-xs text-on-surface-variant">${escapeHtml(conflict.current_version || '—')}</td>
                    <td class="font-mono text-xs">${escapeHtml(conflict.required_version || '—')}</td>
                    <td><span class="badge badge-primary">${conflict.change_type}</span></td>
                    <td><span class="badge ${riskBadgeClass}">${conflict.risk_level}</span></td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-on-surface-variant py-4">No conflicts detected</td></tr>';
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    App.registerPage('plugins', { render });
})();
