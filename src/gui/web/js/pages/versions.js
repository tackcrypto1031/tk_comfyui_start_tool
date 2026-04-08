/**
 * versions.js — Version control page
 */
(function() {

    let selectedRef = null;      // unified: tag name or commit hash
    let selectedRefLabel = null;  // display label for confirmation
    let cachedEnvs = [];          // cached env list with comfyui_commit

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-8">
                <!-- Environment selector + unified action buttons -->
                <div class="flex items-center gap-4 flex-wrap">
                    <label class="input-label">${t('version_environment')}</label>
                    <select id="ver-env" class="select w-64"></select>
                    <label class="input-label ml-4">${t('version_target')}</label>
                    <select id="ver-target" class="select w-40">
                        <option value="comfyui">comfyui</option>
                    </select>
                    <button id="ver-btn-refresh" class="btn btn-icon" title="${t('env_refresh')}">
                        <span class="material-symbols-outlined">refresh</span>
                    </button>
                </div>

                <!-- Selected version indicator -->
                <div id="ver-selected" class="text-xs text-on-surface-variant"></div>
                <!-- Current version not on tag notice -->
                <div id="ver-current-notice" class="text-xs text-on-surface-variant" style="display:none"></div>

                <!-- Remote Tags Section -->
                <div class="card">
                    <div class="flex items-center justify-between">
                        <div class="card-header">${t('version_available_tags')}</div>
                        <button id="ver-btn-fetch" class="btn btn-primary text-xs">
                            <span class="material-symbols-outlined text-[16px]">cloud_download</span>
                            ${t('version_refresh_versions')}
                        </button>
                    </div>
                    <div id="ver-tags-status" class="text-xs text-on-surface-variant mt-2"></div>
                    <div class="mt-4 max-h-48 overflow-y-auto border border-surface-container">
                        <table class="data-table" id="ver-tags-table">
                            <thead>
                                <tr>
                                    <th>${t('version_tag')}</th>
                                    <th>${t('version_col_date')}</th>
                                </tr>
                            </thead>
                            <tbody id="ver-tags-body"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Action buttons -->
                <div class="flex gap-2">
                    <button id="ver-btn-switch" class="btn btn-primary">
                        ${t('version_switch')}
                    </button>
                    <button id="ver-btn-update" class="btn btn-secondary">
                        ${t('version_update')}
                    </button>
                </div>

                <!-- Status -->
                <div id="ver-status" class="text-xs font-label uppercase tracking-wider text-on-surface-variant"></div>
            </div>
        `;

        // Bind events
        document.getElementById('ver-btn-refresh').addEventListener('click', loadEnvs);
        document.getElementById('ver-btn-fetch').addEventListener('click', fetchTags);
        document.getElementById('ver-btn-switch').addEventListener('click', switchToSelected);
        document.getElementById('ver-btn-update').addEventListener('click', updateToLatest);
        document.getElementById('ver-env').addEventListener('change', reapplyHighlight);

        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            const select = document.getElementById('ver-env');
            if (!select) return;
            cachedEnvs = envs;
            const prev = select.value;
            select.innerHTML = '';
            envs.forEach(env => {
                const opt = document.createElement('option');
                opt.value = env.name;
                opt.textContent = env.name;
                select.appendChild(opt);
            });
            if (prev) select.value = prev;
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function updateSelectedIndicator() {
        const el = document.getElementById('ver-selected');
        if (el) {
            el.textContent = selectedRef
                ? (t('version_selected') || 'Selected') + ': ' + selectedRefLabel
                : '';
        }
    }

    function clearAllSelections() {
        document.querySelectorAll('#ver-tags-body tr.selected').forEach(r => r.classList.remove('selected'));
    }

    function fetchTags() {
        const statusEl = document.getElementById('ver-tags-status');
        statusEl.textContent = t('version_fetching');
        document.getElementById('ver-btn-fetch').disabled = true;

        BridgeAPI.listRemoteVersions().then(function(versions) {
            const tbody = document.getElementById('ver-tags-body');
            tbody.innerHTML = '';

            // Get current env's commit for highlight comparison
            const envSelect = document.getElementById('ver-env');
            const currentEnv = cachedEnvs.find(e => e.name === envSelect.value);
            const currentCommit = currentEnv ? currentEnv.comfyui_commit : '';
            let matched = false;

            versions.tags.forEach(tag => {
                const tr = document.createElement('tr');
                tr.className = 'cursor-pointer';
                const isCurrentVersion = currentCommit && tag.hash && tag.hash === currentCommit;
                if (isCurrentVersion) {
                    matched = true;
                    tr.style.background = 'var(--md-sys-color-primary-container)';
                }
                const currentLabel = isCurrentVersion
                    ? ` <span class="text-xs ml-2 text-primary">\u2190 ${t('version_current')}</span>`
                    : '';
                tr.innerHTML = `<td class="text-primary font-mono">${tag.name}${currentLabel}</td><td class="text-on-surface-variant text-xs">${tag.date || tag.hash?.substring(0, 7) || '\u2014'}</td>`;
                tr.addEventListener('click', () => {
                    clearAllSelections();
                    tr.classList.add('selected');
                    selectedRef = tag.name;
                    selectedRefLabel = tag.name;
                    updateSelectedIndicator();
                });
                tbody.appendChild(tr);
            });

            // Show status: tag count + optional no-match notice
            const noticeEl = document.getElementById('ver-current-notice');
            if (noticeEl) {
                if (!matched && currentCommit) {
                    noticeEl.textContent = t('version_not_on_tag', currentCommit.substring(0, 7));
                    noticeEl.style.display = '';
                } else {
                    noticeEl.textContent = '';
                    noticeEl.style.display = 'none';
                }
            }

            statusEl.textContent = t('version_tag_count', versions.tags.length);
            document.getElementById('ver-btn-fetch').disabled = false;
        }).catch(function(e) {
            statusEl.textContent = t('version_fetch_failed', e.toString());
            document.getElementById('ver-btn-fetch').disabled = false;
        });
    }

    function reapplyHighlight() {
        // Re-render highlights when env changes (only if tags are already loaded)
        const tbody = document.getElementById('ver-tags-body');
        if (!tbody || tbody.children.length === 0) return;
        // Re-fetch tags to re-render with new env's commit
        fetchTags();
    }

    function switchToSelected() {
        const envName = document.getElementById('ver-env').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }
        if (!selectedRef) { App.showToast(t('version_select_commit'), 'info'); return; }

        App.confirm(t('version_confirm_switch', selectedRef)).then(ok => {
            if (!ok) return;
            const target = document.getElementById('ver-target').value;
            document.getElementById('ver-status').textContent = t('version_switching');
            BridgeAPI.switchVersion(envName, selectedRef, target).then(() => {
                document.getElementById('ver-status').textContent = t('version_switched');
                App.showToast(t('version_switched'), 'success');
            }).catch(e => {
                document.getElementById('ver-status').textContent = t('error') + ': ' + e;
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function updateToLatest() {
        const envName = document.getElementById('ver-env').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }

        App.confirm(t('version_confirm_update')).then(ok => {
            if (!ok) return;
            document.getElementById('ver-status').textContent = t('version_updating');
            BridgeAPI.updateComfyUI(envName).then(() => {
                document.getElementById('ver-status').textContent = t('version_updated');
                App.showToast(t('version_updated'), 'success');
            }).catch(e => {
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    App.registerPage('versions', { render });
})();
