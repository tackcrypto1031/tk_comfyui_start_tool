/**
 * environments.js — Environment management page
 */
(function() {

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-6">
                <!-- Toolbar -->
                <div class="flex items-center gap-3">
                    <button id="env-btn-create" class="btn btn-primary">
                        <span class="material-symbols-outlined text-[18px]">add</span>
                        ${t('env_create')}
                    </button>
                    <button id="env-btn-clone" class="btn btn-secondary">
                        <span class="material-symbols-outlined text-[18px]">content_copy</span>
                        ${t('env_clone')}
                    </button>
                    <button id="env-btn-edit" class="btn btn-secondary">
                        <span class="material-symbols-outlined text-[18px]">edit</span>
                        ${t('env_edit') || 'Edit'}
                    </button>
                    <button id="env-btn-delete" class="btn btn-danger">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                        ${t('env_delete')}
                    </button>
                    <div class="flex-1"></div>
                    <button id="env-btn-refresh" class="btn btn-icon" title="${t('env_refresh')}">
                        <span class="material-symbols-outlined">refresh</span>
                    </button>
                </div>

                <!-- Environment table -->
                <div class="border border-surface-container">
                    <table class="data-table" id="env-table">
                        <thead>
                            <tr>
                                <th>${t('env_col_name')}</th>
                                <th>${t('env_col_branch')}</th>
                                <th>${t('env_col_commit')}</th>
                                <th>${t('env_col_sandbox')}</th>
                                <th>${t('env_col_created')}</th>
                            </tr>
                        </thead>
                        <tbody id="env-table-body">
                            <!-- Populated by JS -->
                        </tbody>
                    </table>
                </div>

                <!-- Status -->
                <div id="env-status" class="text-xs font-label uppercase tracking-wider text-on-surface-variant"></div>
            </div>
        `;

        // Bind events
        document.getElementById('env-btn-create').addEventListener('click', showCreateDialog);
        document.getElementById('env-btn-clone').addEventListener('click', cloneSelected);
        document.getElementById('env-btn-edit').addEventListener('click', editSelected);
        document.getElementById('env-btn-delete').addEventListener('click', deleteSelected);
        document.getElementById('env-btn-refresh').addEventListener('click', loadEnvironments);

        // Load data
        loadEnvironments();
    }

    let selectedEnvName = null;

    function loadEnvironments() {
        const statusEl = document.getElementById('env-status');
        statusEl.textContent = t('loading');
        BridgeAPI.listEnvironments().then(function(envs) {
            const tbody = document.getElementById('env-table-body');
            tbody.innerHTML = '';
            envs.forEach(env => {
                const commitShort = env.comfyui_commit ? env.comfyui_commit.substring(0, 7) : '';
                const createdShort = env.created_at ? env.created_at.substring(0, 10) : '';
                const tr = document.createElement('tr');
                tr.className = 'cursor-pointer';
                tr.dataset.envName = env.name;
                tr.innerHTML =
                    `<td>${escapeHtml(env.name)}</td>` +
                    `<td class="text-on-surface-variant">${escapeHtml(env.comfyui_branch || '')}</td>` +
                    `<td class="font-mono text-xs text-on-surface-variant">${commitShort}</td>` +
                    `<td>${env.is_sandbox ? '<span class="badge badge-warning">SANDBOX</span>' : ''}</td>` +
                    `<td class="text-on-surface-variant text-xs">${createdShort}</td>`;
                tr.addEventListener('click', () => {
                    document.querySelectorAll('#env-table-body tr.selected').forEach(r => r.classList.remove('selected'));
                    tr.classList.add('selected');
                    selectedEnvName = env.name;
                });
                tbody.appendChild(tr);
            });
            statusEl.textContent = t('env_count', envs.length);
        }).catch(function(e) {
            statusEl.textContent = `${t('error')}: ${e}`;
            App.showToast(e.toString(), 'error');
        });
    }

    function showCreateDialog() {
        const bodyHtml =
            `<div class="space-y-4">
                <div>
                    <label class="input-label">${t('env_name')}</label>
                    <input type="text" id="create-name" class="input" placeholder="e.g. production, dev-test">
                </div>
                <div>
                    <label class="input-label">${t('version_type')}</label>
                    <div class="flex gap-4 mt-2">
                        <label class="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="radio" name="version-type" value="branch" checked class="accent-primary">
                            ${t('version_type_branch')}
                        </label>
                        <label class="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="radio" name="version-type" value="tag" class="accent-primary">
                            ${t('version_type_tag')}
                        </label>
                    </div>
                </div>
                <div id="create-branch-row">
                    <label class="input-label">${t('env_branch')}</label>
                    <select id="create-branch" class="select">
                        <option value="master">master</option>
                    </select>
                </div>
                <div id="create-tag-row" class="hidden">
                    <label class="input-label">${t('version_tag')}</label>
                    <select id="create-tag" class="select">
                        <option value="">-- ${t('loading')} --</option>
                    </select>
                </div>
                <div>
                    <label class="input-label">${t('env_commit')}</label>
                    <input type="text" id="create-commit" class="input" placeholder="${t('env_commit_placeholder')}">
                </div>
                <div id="create-status" class="text-xs text-on-surface-variant"></div>
            </div>`;

        App.showModal({
            title: t('env_create_title'),
            body: bodyHtml,
            buttons: [
                { text: t('cancel'), class: 'btn-secondary' },
                { text: t('env_create'), class: 'btn-primary', closeModal: false, onClick: doCreate },
            ],
        });

        // Bind radio toggle and fetch versions after modal renders
        setTimeout(() => {
            document.querySelectorAll('input[name="version-type"]').forEach(radio => {
                radio.addEventListener('change', () => {
                    document.getElementById('create-branch-row').classList.toggle('hidden', radio.value !== 'branch');
                    document.getElementById('create-tag-row').classList.toggle('hidden', radio.value !== 'tag');
                });
            });

            BridgeAPI.listRemoteVersions().then(function(versions) {
                const branchSelect = document.getElementById('create-branch');
                if (branchSelect) {
                    branchSelect.innerHTML = '';
                    versions.branches.forEach(b => {
                        const opt = document.createElement('option');
                        opt.value = b;
                        opt.textContent = b;
                        if (b === 'master' || b === 'main') opt.selected = true;
                        branchSelect.appendChild(opt);
                    });
                }
                const tagSelect = document.getElementById('create-tag');
                if (tagSelect) {
                    tagSelect.innerHTML = '';
                    versions.tags.forEach(tag => {
                        const opt = document.createElement('option');
                        opt.value = tag.name;
                        opt.textContent = `${tag.name}  (${tag.hash})`;
                        tagSelect.appendChild(opt);
                    });
                }
                const statusDiv = document.getElementById('create-status');
                if (statusDiv) {
                    statusDiv.textContent = `${t('version_branch_count', versions.branches.length)} / ${t('version_tag_count', versions.tags.length)}`;
                }
            }).catch(function(e) {
                const statusDiv = document.getElementById('create-status');
                if (statusDiv) statusDiv.textContent = t('version_fetch_failed', e.toString());
            });
        }, 100);
    }

    function doCreate() {
        const name = document.getElementById('create-name').value.trim();
        if (!name) { App.showToast(`${t('env_name')} required`, 'error'); return; }

        const versionType = document.querySelector('input[name="version-type"]:checked').value;
        let branch, commit;
        if (versionType === 'tag') {
            branch = 'master';
            commit = document.getElementById('create-tag').value;
        } else {
            branch = document.getElementById('create-branch').value || 'master';
            commit = document.getElementById('create-commit').value.trim() || '';
        }

        App.hideModal();

        var progressId = 'create-' + Date.now();
        var stepLabels = {
            venv: t('step_venv') || 'Creating virtual environment',
            clone: t('step_clone') || 'Cloning ComfyUI',
            pytorch: t('step_pytorch') || 'Installing PyTorch',
            dependencies: t('step_dependencies') || 'Installing dependencies',
            manager: t('step_manager') || 'Installing ComfyUI-Manager',
            finalize: t('step_finalize') || 'Finalizing',
            done: t('step_done') || 'Complete',
        };

        App.showProgress(progressId, t('env_creating', name));

        BridgeAPI.createEnvironment(name, branch, commit, function(msg) {
            App.updateProgress(
                progressId,
                stepLabels[msg.step] || msg.step,
                msg.percent,
                msg.detail
            );
        }).then(function() {
            App.updateProgress(progressId, stepLabels.done, 100, '');
            App.hideProgress(progressId, 'success');
            App.showToast('Environment created: ' + name, 'success');
            loadEnvironments();
        }).catch(function(e) {
            App.hideProgress(progressId, 'error');
            App.showToast(t('error') + ': ' + e, 'error', 10000);
        });
    }

    function cloneSelected() {
        if (!selectedEnvName) { App.showToast(t('env_select_to_clone') || 'Select an environment', 'info'); return; }
        const source = selectedEnvName;

        App.showModal({
            title: t('env_clone_title'),
            body: `<div class="space-y-4">
                <div>
                    <label class="input-label">${t('env_source')}</label>
                    <div class="text-on-surface py-2">${escapeHtml(source)}</div>
                </div>
                <div>
                    <label class="input-label">${t('env_new_name')}</label>
                    <input type="text" id="clone-name" class="input" value="${source}-sandbox">
                </div>
            </div>`,
            buttons: [
                { text: t('cancel'), class: 'btn-secondary' },
                {
                    text: t('env_clone'), class: 'btn-primary', closeModal: false, onClick: () => {
                        const newName = document.getElementById('clone-name').value.trim();
                        if (!newName) return;
                        App.hideModal();

                        var cloneProgressId = 'clone-' + Date.now();
                        var cloneStepLabels = {
                            venv: t('step_venv') || 'Creating virtual environment',
                            clone: t('step_clone') || 'Cloning ComfyUI',
                            pytorch: t('step_pytorch') || 'Installing PyTorch',
                            dependencies: t('step_dependencies') || 'Installing dependencies',
                            manager: t('step_manager') || 'Installing ComfyUI-Manager',
                            finalize: t('step_finalize') || 'Finalizing',
                            done: t('step_done') || 'Complete',
                        };

                        App.showProgress(cloneProgressId, t('env_cloning', source, newName));

                        BridgeAPI.cloneEnvironment(source, newName, function(msg) {
                            App.updateProgress(
                                cloneProgressId,
                                cloneStepLabels[msg.step] || msg.step,
                                msg.percent,
                                msg.detail
                            );
                        }).then(() => {
                            App.updateProgress(cloneProgressId, cloneStepLabels.done, 100, '');
                            App.hideProgress(cloneProgressId, 'success');
                            App.showToast(`Cloned: ${newName}`, 'success');
                            loadEnvironments();
                        }).catch(e => {
                            App.hideProgress(cloneProgressId, 'error');
                            App.showToast(`${t('error')}: ${e}`, 'error');
                        });
                    }
                },
            ],
        });
    }

    function deleteSelected() {
        if (!selectedEnvName) { App.showToast(t('env_select_to_delete') || 'Select an environment', 'info'); return; }
        const name = selectedEnvName;
        App.confirm(t('env_confirm_delete', name)).then(ok => {
            if (!ok) return;
            App.showToast(t('env_deleting', name), 'info');
            BridgeAPI.deleteEnvironment(name, true).then(() => {
                App.showToast(`Deleted: ${name}`, 'success');
                selectedEnvName = null;
                loadEnvironments();
            }).catch(e => {
                App.showToast(`${t('error')}: ${e}`, 'error');
            });
        });
    }

    function editSelected() {
        if (!selectedEnvName) {
            App.showToast('Select an environment first', 'info');
            return;
        }
        var envName = selectedEnvName;

        var bodyHtml =
            '<div class="space-y-4">' +
                '<div>' +
                    '<label class="input-label">' + (t('env_name') || 'Name') + '</label>' +
                    '<input type="text" id="edit-name" class="input" value="' + envName + '">' +
                '</div>' +
                '<div class="border-t border-outline/20 pt-4 mt-4">' +
                    '<label class="input-label">' + (t('version_switch') || 'Switch Version') + '</label>' +
                    '<div class="flex gap-4 mt-2">' +
                        '<label class="flex items-center gap-2 text-sm cursor-pointer">' +
                            '<input type="radio" name="edit-vtype" value="branch" checked class="accent-primary"> ' +
                            (t('version_type_branch') || 'Branch') +
                        '</label>' +
                        '<label class="flex items-center gap-2 text-sm cursor-pointer">' +
                            '<input type="radio" name="edit-vtype" value="tag" class="accent-primary"> ' +
                            (t('version_type_tag') || 'Tag') +
                        '</label>' +
                    '</div>' +
                '</div>' +
                '<div id="edit-branch-row">' +
                    '<label class="input-label">' + (t('env_branch') || 'Branch') + '</label>' +
                    '<select id="edit-branch" class="select"><option>Loading...</option></select>' +
                '</div>' +
                '<div id="edit-tag-row" class="hidden">' +
                    '<label class="input-label">' + (t('version_tag') || 'Tag') + '</label>' +
                    '<select id="edit-tag" class="select"><option>Loading...</option></select>' +
                '</div>' +
                '<div id="edit-status" class="text-xs text-on-surface-variant"></div>' +
            '</div>';

        App.showModal({
            title: (t('env_edit') || 'Edit Environment') + ': ' + envName,
            body: bodyHtml,
            buttons: [
                { text: t('cancel'), class: 'btn-secondary' },
                { text: t('yes') || 'Save', class: 'btn-primary', closeModal: false, onClick: function() { doEdit(envName); } },
            ],
        });

        // Toggle branch/tag visibility and fetch remote versions
        setTimeout(function() {
            document.querySelectorAll('input[name="edit-vtype"]').forEach(function(radio) {
                radio.addEventListener('change', function() {
                    document.getElementById('edit-branch-row').classList.toggle('hidden', radio.value !== 'branch');
                    document.getElementById('edit-tag-row').classList.toggle('hidden', radio.value !== 'tag');
                });
            });

            BridgeAPI.listRemoteVersions().then(function(versions) {
                var branchSelect = document.getElementById('edit-branch');
                if (branchSelect) {
                    branchSelect.innerHTML = '<option value="">-- No change --</option>';
                    versions.branches.forEach(function(b) {
                        var opt = document.createElement('option');
                        opt.value = b;
                        opt.textContent = b;
                        branchSelect.appendChild(opt);
                    });
                }
                var tagSelect = document.getElementById('edit-tag');
                if (tagSelect) {
                    tagSelect.innerHTML = '<option value="">-- No change --</option>';
                    versions.tags.forEach(function(tag) {
                        var opt = document.createElement('option');
                        opt.value = tag.name;
                        opt.textContent = tag.name + '  (' + tag.hash + ')';
                        tagSelect.appendChild(opt);
                    });
                }
                var statusDiv = document.getElementById('edit-status');
                if (statusDiv) {
                    statusDiv.textContent = (t('version_branch_count', versions.branches.length) || '') +
                        ' / ' + (t('version_tag_count', versions.tags.length) || '');
                }
            }).catch(function(e) {
                var statusDiv = document.getElementById('edit-status');
                if (statusDiv) statusDiv.textContent = 'Failed to fetch versions: ' + e;
            });
        }, 100);
    }

    function doEdit(originalName) {
        var newName = document.getElementById('edit-name').value.trim();
        var vtype = document.querySelector('input[name="edit-vtype"]:checked').value;
        var versionRef = '';
        if (vtype === 'tag') {
            versionRef = document.getElementById('edit-tag').value;
        } else {
            versionRef = document.getElementById('edit-branch').value;
        }

        App.hideModal();

        // Step 1: Rename if name changed
        var renamePromise;
        if (newName && newName !== originalName) {
            App.showToast('Renaming to ' + newName + '...', 'info');
            renamePromise = BridgeAPI.renameEnvironment(originalName, newName);
        } else {
            renamePromise = Promise.resolve();
            newName = originalName;
        }

        renamePromise.then(function() {
            // Step 2: Switch version if selected
            if (versionRef) {
                App.showToast(t('version_switching') || 'Switching version...', 'info');
                return BridgeAPI.switchVersion(newName, versionRef, 'comfyui');
            }
        }).then(function() {
            App.showToast('Environment updated!', 'success');
            selectedEnvName = newName;
            loadEnvironments();
        }).catch(function(e) {
            App.showToast(t('error') + ': ' + e, 'error');
            loadEnvironments();
        });
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    App.registerPage('environments', { render });

})();
