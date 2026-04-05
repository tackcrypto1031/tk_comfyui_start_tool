/**
 * versions.js — Version control page
 */
(function() {

    let selectedCommitHash = null;

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-8">
                <!-- Environment selector -->
                <div class="flex items-center gap-4">
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
                    <div class="mt-3">
                        <button id="ver-btn-install-tag" class="btn btn-secondary">
                            <span class="material-symbols-outlined text-[16px]">install_desktop</span>
                            ${t('version_install_tag')}
                        </button>
                    </div>
                </div>

                <!-- Git History Section -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="font-headline text-sm font-bold uppercase tracking-wider text-on-surface">${t('version_load')}</h3>
                        <div class="flex gap-2">
                            <button id="ver-btn-load" class="btn btn-secondary">
                                <span class="material-symbols-outlined text-[16px]">history</span>
                                ${t('version_load')}
                            </button>
                            <button id="ver-btn-switch" class="btn btn-primary">
                                ${t('version_switch')}
                            </button>
                            <button id="ver-btn-update" class="btn btn-secondary">
                                ${t('version_update')}
                            </button>
                        </div>
                    </div>
                    <div id="ver-timeline" class="space-y-0">
                        <!-- Timeline items populated by JS -->
                        <div class="text-on-surface-variant text-sm py-4">${t('version_loading')}</div>
                    </div>
                </div>

                <!-- Status -->
                <div id="ver-status" class="text-xs font-label uppercase tracking-wider text-on-surface-variant"></div>
            </div>
        `;

        // Bind events
        document.getElementById('ver-btn-refresh').addEventListener('click', loadEnvs);
        document.getElementById('ver-btn-fetch').addEventListener('click', fetchTags);
        document.getElementById('ver-btn-install-tag').addEventListener('click', installSelectedTag);
        document.getElementById('ver-btn-load').addEventListener('click', loadCommits);
        document.getElementById('ver-btn-switch').addEventListener('click', switchToSelected);
        document.getElementById('ver-btn-update').addEventListener('click', updateToLatest);

        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            const select = document.getElementById('ver-env');
            if (!select) return;
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

    let selectedTagName = null;

    function fetchTags() {
        const statusEl = document.getElementById('ver-tags-status');
        statusEl.textContent = t('version_fetching');
        document.getElementById('ver-btn-fetch').disabled = true;

        BridgeAPI.listRemoteVersions().then(function(versions) {
            const tbody = document.getElementById('ver-tags-body');
            tbody.innerHTML = '';
            versions.tags.forEach(tag => {
                const tr = document.createElement('tr');
                tr.className = 'cursor-pointer';
                tr.innerHTML = `<td class="text-primary font-mono">${tag.name}</td><td class="text-on-surface-variant text-xs">${tag.date || tag.hash || '—'}</td>`;
                tr.addEventListener('click', () => {
                    document.querySelectorAll('#ver-tags-body tr.selected').forEach(r => r.classList.remove('selected'));
                    tr.classList.add('selected');
                    selectedTagName = tag.name;
                });
                tbody.appendChild(tr);
            });
            statusEl.textContent = t('version_tag_count', versions.tags.length);
            document.getElementById('ver-btn-fetch').disabled = false;
        }).catch(function(e) {
            statusEl.textContent = t('version_fetch_failed', e.toString());
            document.getElementById('ver-btn-fetch').disabled = false;
        });
    }

    function installSelectedTag() {
        const envName = document.getElementById('ver-env').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }
        if (!selectedTagName) { App.showToast(t('version_select_commit'), 'info'); return; }

        App.confirm(t('version_confirm_switch', selectedTagName)).then(ok => {
            if (!ok) return;
            const target = document.getElementById('ver-target').value;
            document.getElementById('ver-status').textContent = t('version_switching');
            BridgeAPI.switchVersion(envName, selectedTagName, target).then(() => {
                document.getElementById('ver-status').textContent = t('version_switched');
                App.showToast(t('version_switched'), 'success');
            }).catch(e => {
                document.getElementById('ver-status').textContent = t('error') + ': ' + e;
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function loadCommits() {
        const envName = document.getElementById('ver-env').value;
        const target = document.getElementById('ver-target').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }

        document.getElementById('ver-status').textContent = t('version_loading');

        BridgeAPI.listCommits(envName, target).then(function(commits) {
            renderTimeline(commits);
            document.getElementById('ver-status').textContent = commits.length + ' commit(s)';
        }).catch(function(e) {
            document.getElementById('ver-status').textContent = t('error') + ': ' + e;
            App.showToast(e.toString(), 'error');
        });
    }

    function renderTimeline(commits) {
        const container = document.getElementById('ver-timeline');
        container.innerHTML = '';

        commits.forEach((commit, i) => {
            const isFirst = i === 0;
            const hashShort = commit.hash.substring(0, 7);
            const date = commit.date ? new Date(commit.date).toLocaleString() : '';
            const msgShort = commit.message.length > 80 ? commit.message.substring(0, 80) + '...' : commit.message;

            const item = document.createElement('div');
            item.className = 'flex gap-4 group cursor-pointer py-3 px-4 hover:bg-surface-container-low transition-colors';
            if (isFirst) item.className += ' bg-surface-container-low';
            item.dataset.hash = hashShort;

            item.innerHTML = `
                <div class="flex flex-col items-center">
                    <div class="timeline-node ${isFirst ? 'active' : ''}"></div>
                    ${i < commits.length - 1 ? '<div class="timeline-line flex-1 mt-1"></div>' : '<div class="flex-1"></div>'}
                </div>
                <div class="flex-1 min-w-0 pb-2">
                    <div class="flex items-center gap-2">
                        <span class="font-mono text-xs ${isFirst ? 'text-primary text-glow' : 'text-on-surface-variant'}">${hashShort}</span>
                        ${isFirst ? '<span class="badge badge-primary">HEAD</span>' : ''}
                    </div>
                    <div class="text-sm text-on-surface mt-1">${escapeHtml(msgShort)}</div>
                    <div class="text-xs text-on-surface-variant mt-1">
                        <span>${escapeHtml(commit.author)}</span>
                        <span class="mx-2">·</span>
                        <span>${date}</span>
                    </div>
                </div>
            `;

            item.addEventListener('click', () => {
                document.querySelectorAll('#ver-timeline > div').forEach(el => {
                    el.classList.remove('bg-surface-container');
                    el.querySelector('.timeline-node')?.classList.remove('active');
                });
                item.classList.add('bg-surface-container');
                item.querySelector('.timeline-node')?.classList.add('active');
                selectedCommitHash = hashShort;
            });

            container.appendChild(item);
        });
    }

    function switchToSelected() {
        const envName = document.getElementById('ver-env').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }
        if (!selectedCommitHash) { App.showToast(t('version_select_commit'), 'info'); return; }

        App.confirm(t('version_confirm_switch', selectedCommitHash)).then(ok => {
            if (!ok) return;
            const target = document.getElementById('ver-target').value;
            document.getElementById('ver-status').textContent = t('version_switching');
            BridgeAPI.switchVersion(envName, selectedCommitHash, target).then(() => {
                document.getElementById('ver-status').textContent = t('version_switched');
                App.showToast(t('version_switched'), 'success');
            }).catch(e => {
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
