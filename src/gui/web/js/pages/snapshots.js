/**
 * snapshots.js — Snapshot management page
 */
(function() {

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-6">
                <!-- Controls -->
                <div class="flex items-center gap-4">
                    <label class="input-label">${t('snapshot_environment')}</label>
                    <select id="snap-env" class="select w-64"></select>
                    <button id="snap-btn-create" class="btn btn-primary">
                        <span class="material-symbols-outlined text-[16px]">add_a_photo</span>
                        ${t('snapshot_create')}
                    </button>
                    <div class="flex-1"></div>
                    <button id="snap-btn-refresh" class="btn btn-icon" title="${t('snapshot_refresh')}">
                        <span class="material-symbols-outlined">refresh</span>
                    </button>
                </div>

                <!-- Snapshot cards -->
                <div id="snap-list" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <!-- Populated by JS -->
                </div>

                <!-- Status -->
                <div id="snap-status" class="text-xs font-label uppercase tracking-wider text-on-surface-variant"></div>
            </div>
        `;

        document.getElementById('snap-btn-create').addEventListener('click', createSnapshot);
        document.getElementById('snap-btn-refresh').addEventListener('click', loadSnapshots);
        document.getElementById('snap-env').addEventListener('change', loadSnapshots);

        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            const select = document.getElementById('snap-env');
            select.innerHTML = '';
            envs.forEach(env => {
                const opt = document.createElement('option');
                opt.value = env.name;
                opt.textContent = env.name;
                select.appendChild(opt);
            });
            if (envs.length > 0) loadSnapshots();
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function loadSnapshots() {
        const envName = document.getElementById('snap-env').value;
        if (!envName) return;

        const statusEl = document.getElementById('snap-status');
        statusEl.textContent = t('loading');

        BridgeAPI.listSnapshots(envName).then(function(snaps) {
            const list = document.getElementById('snap-list');
            list.innerHTML = '';

            if (snaps.length === 0) {
                list.innerHTML = '<div class="col-span-full text-center text-on-surface-variant py-8">' + t('snapshot_count', 0) + '</div>';
            } else {
                snaps.forEach(snap => {
                    const card = document.createElement('div');
                    card.className = 'card border-glow group';

                    const triggerBadge = getTriggerBadge(snap.trigger);
                    const dateStr = snap.created_at ? new Date(snap.created_at).toLocaleString() : '';
                    const pyVer = snap.python_version || 'N/A';
                    const cudaVer = snap.cuda_version || 'N/A';

                    card.innerHTML = `
                        <div class="flex items-start justify-between">
                            <div>
                                <div class="font-label text-xs font-bold uppercase tracking-wider text-on-surface">${escapeHtml(snap.env_name)}</div>
                                <div class="text-xs text-on-surface-variant mt-1">${dateStr}</div>
                            </div>
                            ${triggerBadge}
                        </div>
                        <div class="mt-3 flex items-center gap-2 text-xs text-on-surface-variant">
                            <span class="material-symbols-outlined text-[14px]">memory</span>
                            <span>Python ${pyVer} | CUDA ${cudaVer}</span>
                        </div>
                        <div class="mt-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button class="btn btn-secondary text-[10px] py-1 px-3 snap-restore" data-id="${snap.id}">
                                <span class="material-symbols-outlined text-[14px]">restore</span>
                                ${t('snapshot_restore')}
                            </button>
                            <button class="btn btn-danger text-[10px] py-1 px-3 snap-delete" data-id="${snap.id}">
                                <span class="material-symbols-outlined text-[14px]">delete</span>
                                ${t('snapshot_delete')}
                            </button>
                        </div>
                    `;

                    card.querySelector('.snap-restore').addEventListener('click', () => restoreSnapshot(snap.id));
                    card.querySelector('.snap-delete').addEventListener('click', () => deleteSnapshot(snap.id));

                    list.appendChild(card);
                });
            }
            App.applyFallbackIcons();
            statusEl.textContent = t('snapshot_count', snaps.length);
        }).catch(function(e) {
            statusEl.textContent = t('error') + ': ' + e;
            App.showToast(e.toString(), 'error');
        });
    }

    function getTriggerBadge(trigger) {
        const map = {
            manual: 'badge-primary',
            clone: 'badge-success',
            merge: 'badge-warning',
            version_switch: 'badge-primary',
            update: 'badge-success',
        };
        const cls = map[trigger] || 'badge-primary';
        return `<span class="badge ${cls}">${escapeHtml(trigger.toUpperCase())}</span>`;
    }

    function createSnapshot() {
        const envName = document.getElementById('snap-env').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }

        BridgeAPI.createSnapshot(envName, 'manual').then(function(result) {
            App.showToast(t('snapshot_created', result.id), 'success');
            loadSnapshots();
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function restoreSnapshot(snapshotId) {
        const envName = document.getElementById('snap-env').value;
        App.confirm(t('snapshot_confirm_restore', snapshotId)).then(ok => {
            if (!ok) return;

            var progressId = 'restore-' + Date.now();
            var stepLabels = {
                comfyui: t('snapshot_restoring') + ' ComfyUI...',
                nodes: t('snapshot_restoring') + ' Custom Nodes...',
                pytorch: t('snapshot_restoring') + ' PyTorch...',
                packages: t('snapshot_restoring') + ' Pip Packages...',
                configs: t('snapshot_restoring') + ' Configs...',
                metadata: t('snapshot_restoring') + ' Metadata...',
                done: t('snapshot_restored', snapshotId),
            };

            App.showProgress(progressId, t('snapshot_restoring'));

            BridgeAPI.restoreSnapshot(envName, snapshotId, function(msg) {
                App.updateProgress(
                    progressId,
                    stepLabels[msg.step] || msg.step,
                    msg.percent,
                    msg.detail
                );
            }).then(() => {
                App.updateProgress(progressId, stepLabels.done, 100, '');
                App.hideProgress(progressId, 'success');
                App.showToast(t('snapshot_restored', snapshotId), 'success');
                document.getElementById('snap-status').textContent = t('snapshot_restored', snapshotId);
            }).catch(e => {
                App.hideProgress(progressId, 'error');
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function deleteSnapshot(snapshotId) {
        const envName = document.getElementById('snap-env').value;
        App.confirm(t('snapshot_confirm_delete', snapshotId)).then(ok => {
            if (!ok) return;
            BridgeAPI.deleteSnapshot(envName, snapshotId).then(function() {
                App.showToast(t('snapshot_deleted'), 'success');
                loadSnapshots();
            }).catch(function(e) { App.showToast(e.toString(), 'error'); });
        });
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    App.registerPage('snapshots', { render });
})();
