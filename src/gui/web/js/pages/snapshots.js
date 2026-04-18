/**
 * snapshots.js — Snapshot management page (Tack Industrial redesign)
 */
(function() {

    var _envs = [];
    var _snaps = [];

    function render(container) {
        container.innerHTML =
            '<div class="ti-content fade-in">' +
                '<div class="ti-page-head">' +
                    '<div>' +
                        '<h1>' + h(t('sidebar_snapshots')) + '</h1>' +
                        '<p class="ti-page-sub" id="snap-sub">—</p>' +
                    '</div>' +
                    '<div class="ti-page-actions">' +
                        '<div class="ti-env-select">' +
                            '<label>' + h(t('snapshot_environment')) + '</label>' +
                            '<select id="snap-env"></select>' +
                        '</div>' +
                        '<button id="snap-btn-refresh" class="btn btn-secondary" title="' + h(t('snapshot_refresh')) + '">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">refresh</span>' +
                        '</button>' +
                        '<button id="snap-btn-create" class="btn btn-primary">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">add_a_photo</span>' +
                            '<span>' + h(t('snapshot_create')) + '</span>' +
                        '</button>' +
                    '</div>' +
                '</div>' +
                '<div id="snap-list-wrap"></div>' +
                '<div id="snap-status" style="margin-top:10px;font-family:var(--font-mono);font-size:11px;color:var(--text-4);text-transform:uppercase;letter-spacing:0.1em"></div>' +
            '</div>';

        document.getElementById('snap-btn-create').addEventListener('click', createSnapshot);
        document.getElementById('snap-btn-refresh').addEventListener('click', loadSnapshots);
        document.getElementById('snap-env').addEventListener('change', loadSnapshots);

        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            _envs = envs || [];
            var select = document.getElementById('snap-env');
            select.innerHTML = _envs.map(function(e) {
                return '<option value="' + h(e.name) + '">' + h(e.name) + '</option>';
            }).join('');
            if (_envs.length > 0) loadSnapshots();
            else renderEmpty();
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function loadSnapshots() {
        var envName = document.getElementById('snap-env').value;
        if (!envName) return;

        var statusEl = document.getElementById('snap-status');
        statusEl.textContent = t('loading');

        BridgeAPI.listSnapshots(envName).then(function(snaps) {
            _snaps = snaps || [];
            renderList();
            statusEl.textContent = t('snapshot_count', _snaps.length);
            document.getElementById('snap-sub').innerHTML =
                _snaps.length + ' 個快照 · <span class="accent">' + h(envName) + '</span>';
        }).catch(function(e) {
            statusEl.textContent = t('error') + ': ' + e;
            App.showToast(e.toString(), 'error');
        });
    }

    function renderList() {
        var wrap = document.getElementById('snap-list-wrap');
        if (!wrap) return;
        if (!_snaps.length) { renderEmpty(); return; }

        wrap.innerHTML = '<div class="ti-snap-list">' + _snaps.map(function(s) {
            var dateStr = s.created_at ? new Date(s.created_at).toLocaleString() : '—';
            var trigger = (s.trigger || '').toUpperCase();
            var py = s.python_version || 'N/A';
            var cuda = s.cuda_version || 'N/A';
            return '<div class="ti-snap-row">' +
                '<div class="ti-snap-icon"><span class="material-symbols-outlined">inventory_2</span></div>' +
                '<div>' +
                    '<div class="ti-snap-label">' + h(s.env_name || s.id) + ' <span class="chip" style="margin-left:6px">' + h(trigger) + '</span></div>' +
                    '<div class="ti-snap-meta">' + h(s.id) + ' · py ' + h(py) + ' · ' + h(cuda) + '</div>' +
                '</div>' +
                '<span class="ti-snap-date">' + h(dateStr) + '</span>' +
                '<div class="ti-snap-actions">' +
                    '<button class="btn btn-secondary btn-sm" data-snap-restore="' + h(s.id) + '">' +
                        '<span class="material-symbols-outlined" style="font-size:13px">restore</span>' +
                        '<span>' + h(t('snapshot_restore')) + '</span>' +
                    '</button>' +
                    '<button class="btn btn-danger btn-sm" data-snap-delete="' + h(s.id) + '">' +
                        '<span class="material-symbols-outlined" style="font-size:13px">delete</span>' +
                    '</button>' +
                '</div>' +
            '</div>';
        }).join('') + '</div>';

        wrap.querySelectorAll('[data-snap-restore]').forEach(function(b) {
            b.addEventListener('click', function() { restoreSnapshot(b.getAttribute('data-snap-restore')); });
        });
        wrap.querySelectorAll('[data-snap-delete]').forEach(function(b) {
            b.addEventListener('click', function() { deleteSnapshot(b.getAttribute('data-snap-delete')); });
        });
    }

    function renderEmpty() {
        var wrap = document.getElementById('snap-list-wrap');
        if (!wrap) return;
        wrap.innerHTML =
            '<div class="ti-list-empty">' +
                '<span class="material-symbols-outlined">inventory_2</span>' +
                '<div>' + h(t('snapshot_count', 0)) + '</div>' +
            '</div>';
    }

    function createSnapshot() {
        var envName = document.getElementById('snap-env').value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }

        BridgeAPI.createSnapshot(envName, 'manual').then(function(result) {
            App.showToast(t('snapshot_created', result.id), 'success');
            loadSnapshots();
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function restoreSnapshot(snapshotId) {
        var envName = document.getElementById('snap-env').value;
        App.confirm(t('snapshot_confirm_restore', snapshotId)).then(function(ok) {
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
                App.updateProgress(progressId, stepLabels[msg.step] || msg.step, msg.percent, msg.detail);
            }).then(function() {
                App.updateProgress(progressId, stepLabels.done, 100, '');
                App.hideProgress(progressId, 'success');
                App.showToast(t('snapshot_restored', snapshotId), 'success');
                document.getElementById('snap-status').textContent = t('snapshot_restored', snapshotId);
            }).catch(function(e) {
                App.hideProgress(progressId, 'error');
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function deleteSnapshot(snapshotId) {
        var envName = document.getElementById('snap-env').value;
        App.confirm(t('snapshot_confirm_delete', snapshotId)).then(function(ok) {
            if (!ok) return;
            BridgeAPI.deleteSnapshot(envName, snapshotId).then(function() {
                App.showToast(t('snapshot_deleted'), 'success');
                loadSnapshots();
            }).catch(function(e) { App.showToast(e.toString(), 'error'); });
        });
    }

    function h(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    App.registerPage('snapshots', { render: render });
})();
