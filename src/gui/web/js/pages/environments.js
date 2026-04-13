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

                <!-- Shared Model Path -->
                <div id="shared-model-section" class="p-4 border border-surface-container rounded-lg" style="background: rgba(255,255,255,0.03);">
                    <div class="flex items-center gap-2 mb-3">
                        <span class="material-symbols-outlined text-[18px]" style="color:rgb(var(--color-primary));">folder_shared</span>
                        <span class="text-sm font-semibold">${t('shared_model_title')}</span>
                    </div>
                    <div class="flex items-center gap-4 mb-2">
                        <label class="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="radio" name="shared-model-mode" value="default" checked class="accent-primary">
                            ${t('shared_model_default')}
                        </label>
                        <label class="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="radio" name="shared-model-mode" value="custom" class="accent-primary">
                            ${t('shared_model_custom')}
                        </label>
                    </div>
                    <div class="flex items-center gap-2">
                        <input type="text" id="shared-model-path" class="input flex-1 font-mono text-xs" readonly placeholder="${t('shared_model_path_placeholder')}">
                        <button id="shared-model-browse" class="btn btn-secondary hidden" style="padding:6px 10px;">
                            <span class="material-symbols-outlined text-[16px]">folder_open</span>
                        </button>
                        <button id="shared-model-save" class="btn btn-primary hidden" style="padding:6px 14px;">
                            <span class="material-symbols-outlined text-[16px]">save</span>
                        </button>
                        <button id="shared-model-rescan" class="btn btn-secondary" style="padding:6px 14px;" title="${t('rescan_shared_models_tooltip')}">
                            <span class="material-symbols-outlined text-[16px]">refresh</span>
                            <span class="ml-1 text-xs">${t('rescan_shared_models')}</span>
                        </button>
                    </div>
                </div>

                <!-- Environment table -->
                <div class="border border-surface-container">
                    <table class="data-table" id="env-table">
                        <thead>
                            <tr>
                                <th>${t('env_col_name')}</th>
                                <th>${t('env_col_branch')}</th>
                                <th>${t('env_col_commit')}</th>
                                <th>${t('env_col_created')}</th>
                                <th class="text-center" style="white-space:nowrap;">
                                    <div class="flex items-center justify-center gap-2">
                                        <span>${t('shared_model_col')}</span>
                                        <div id="shared-model-header-toggle" class="toggle-switch" data-state="on" title="Toggle all"></div>
                                    </div>
                                </th>
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
        // Preload remote versions cache so Edit/Create dialogs open instantly
        BridgeAPI.listRemoteVersions().catch(function() {});

        // Load shared model config
        loadSharedModelConfig();

        // Bind shared model mode radio
        document.querySelectorAll('input[name="shared-model-mode"]').forEach(function(radio) {
            radio.addEventListener('change', function() {
                var isCustom = radio.value === 'custom';
                var pathInput = document.getElementById('shared-model-path');
                var browseBtn = document.getElementById('shared-model-browse');
                var saveBtn = document.getElementById('shared-model-save');
                pathInput.readOnly = !isCustom;
                browseBtn.classList.toggle('hidden', !isCustom);
                saveBtn.classList.toggle('hidden', !isCustom);
                if (!isCustom) {
                    saveSharedModelConfig('default', '');
                }
            });
        });

        // Browse button
        document.getElementById('shared-model-browse').addEventListener('click', function() {
            BridgeAPI.browseFolder().then(function(folder) {
                if (folder) {
                    document.getElementById('shared-model-path').value = folder;
                }
            });
        });

        // Save button (custom path)
        document.getElementById('shared-model-save').addEventListener('click', function() {
            var path = document.getElementById('shared-model-path').value.trim();
            if (!path) {
                App.showToast(t('shared_model_path_empty'), 'error');
                return;
            }
            saveSharedModelConfig('custom', path);
        });

        // Rescan button
        document.getElementById('shared-model-rescan').addEventListener('click', function() {
            var btn = document.getElementById('shared-model-rescan');
            btn.disabled = true;
            BridgeAPI.rescanSharedModelSubdirs().then(function(result) {
                if (result && result.skipped) {
                    App.showToast(
                        t('rescan_skipped').replace('{0}', result.reason || ''),
                        'warning'
                    );
                } else if (result && result.added && result.added.length > 0) {
                    App.showToast(
                        t('rescan_found_new')
                            .replace('{0}', result.added.length)
                            .replace('{1}', result.synced_envs || 0),
                        'success'
                    );
                } else if (result && result.synced_envs > 0) {
                    App.showToast(
                        t('rescan_forced_regen').replace('{0}', result.synced_envs),
                        'success'
                    );
                } else {
                    App.showToast(t('rescan_up_to_date'), 'info');
                }
            }).catch(function(e) {
                var msg = (e && e.message) ? e.message : String(e);
                App.showToast(t('rescan_failed').replace('{0}', msg), 'error');
            }).finally(function() {
                btn.disabled = false;
            });
        });
    }

    function loadSharedModelConfig() {
        BridgeAPI.getSharedModelConfig().then(function(config) {
            var pathInput = document.getElementById('shared-model-path');
            var browseBtn = document.getElementById('shared-model-browse');
            var saveBtn = document.getElementById('shared-model-save');
            var radios = document.querySelectorAll('input[name="shared-model-mode"]');

            if (config.mode === 'custom' && config.path) {
                radios.forEach(function(r) { r.checked = r.value === 'custom'; });
                pathInput.value = config.path;
                pathInput.readOnly = false;
                browseBtn.classList.remove('hidden');
                saveBtn.classList.remove('hidden');
            } else {
                radios.forEach(function(r) { r.checked = r.value === 'default'; });
                pathInput.value = config.default_path;
                pathInput.readOnly = true;
                browseBtn.classList.add('hidden');
                saveBtn.classList.add('hidden');
            }
        }).catch(function(e) {
            console.error('Failed to load shared model config:', e);
        });
    }

    function saveSharedModelConfig(mode, path) {
        BridgeAPI.getSharedModelConfig().then(function(currentConfig) {
            // First, count enabled environments
            return BridgeAPI.listEnvironments().then(function(envs) {
                var enabledCount = envs.filter(function(e) { return e.shared_model_enabled !== false; }).length;

                if (enabledCount > 0) {
                    // Show confirmation dialog
                    App.showModal({
                        title: t('shared_model_title'),
                        body: '<p>' + t('shared_model_confirm_sync', enabledCount) + '</p>' +
                              '<p class="text-xs text-on-surface-variant mt-2">' + t('shared_model_confirm_sync_detail') + '</p>',
                        buttons: [
                            { text: t('cancel'), class: 'btn-secondary', onClick: function() {
                                // Only update config, no sync
                                BridgeAPI.setSharedModelConfig(mode, path, false).then(function() {
                                    App.showToast(t('shared_model_updated'), 'success');
                                    loadSharedModelConfig();
                                });
                            }},
                            { text: t('confirm'), class: 'btn-primary', onClick: function() {
                                // Update config and sync all enabled environments
                                BridgeAPI.setSharedModelConfig(mode, path, true).then(function() {
                                    App.showToast(t('shared_model_updated'), 'success');
                                    loadSharedModelConfig();
                                    loadEnvironments();
                                });
                            }},
                        ],
                    });
                } else {
                    // No enabled environments, just update config
                    BridgeAPI.setSharedModelConfig(mode, path, false).then(function() {
                        App.showToast(t('shared_model_updated'), 'success');
                        loadSharedModelConfig();
                    });
                }
            });
        });
    }

    function createToggleSwitch(isOn, onClick) {
        var el = document.createElement('div');
        el.className = 'toggle-switch';
        el.dataset.state = isOn ? 'on' : 'off';
        el.style.cssText = 'width:36px;height:20px;border-radius:10px;position:relative;cursor:pointer;display:inline-block;transition:background 0.2s;' +
            (isOn ? 'background:rgb(var(--color-primary));' : 'background:rgb(var(--color-outline));');
        var knob = document.createElement('div');
        knob.style.cssText = 'width:16px;height:16px;border-radius:50%;position:absolute;top:2px;transition:left 0.2s,right 0.2s;' +
            (isOn ? 'right:2px;left:auto;background:#fff;' : 'left:2px;right:auto;background:#999;');
        el.appendChild(knob);
        el.addEventListener('click', function(e) {
            e.stopPropagation();
            onClick(el);
        });
        return el;
    }

    function setToggleState(el, isOn) {
        el.dataset.state = isOn ? 'on' : 'off';
        el.style.background = isOn ? 'rgb(var(--color-primary))' : 'rgb(var(--color-outline))';
        var knob = el.firstChild;
        if (isOn) {
            knob.style.right = '2px';
            knob.style.left = 'auto';
            knob.style.background = '#fff';
        } else {
            knob.style.left = '2px';
            knob.style.right = 'auto';
            knob.style.background = '#999';
        }
    }

    function updateHeaderToggle() {
        var rows = document.querySelectorAll('#env-table-body tr');
        var allOn = rows.length > 0;
        rows.forEach(function(row) {
            var toggle = row.querySelector('td:last-child .toggle-switch');
            if (toggle && toggle.dataset.state !== 'on') {
                allOn = false;
            }
        });
        var headerToggle = document.getElementById('shared-model-header-toggle');
        if (headerToggle) {
            setToggleState(headerToggle, allOn);
        }
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
                    `<td class="text-on-surface-variant text-xs">${createdShort}</td>` +
                    `<td class="text-center"></td>`;

                // Add toggle to the last cell
                var toggleCell = tr.querySelector('td:last-child');
                var isEnabled = env.shared_model_enabled !== false;
                var toggle = createToggleSwitch(isEnabled, function(el) {
                    var newState = el.dataset.state !== 'on';
                    BridgeAPI.toggleSharedModel(env.name, newState).then(function() {
                        setToggleState(el, newState);
                        updateHeaderToggle();
                        App.showToast(
                            newState ? t('shared_model_toggled_on', env.name) : t('shared_model_toggled_off', env.name),
                            'success'
                        );
                        App.showToast(t('shared_model_next_launch'), 'info');
                    }).catch(function(e) {
                        App.showToast(e.toString(), 'error');
                    });
                });
                toggleCell.appendChild(toggle);

                tr.addEventListener('click', () => {
                    document.querySelectorAll('#env-table-body tr.selected').forEach(r => r.classList.remove('selected'));
                    tr.classList.add('selected');
                    selectedEnvName = env.name;
                });
                tbody.appendChild(tr);
            });

            // Setup header toggle
            var headerToggle = document.getElementById('shared-model-header-toggle');
            if (headerToggle) {
                var allEnabled = envs.length > 0 && envs.every(function(e) { return e.shared_model_enabled !== false; });
                headerToggle.innerHTML = '';
                var hToggle = createToggleSwitch(allEnabled, function(el) {
                    var newState = el.dataset.state !== 'on';
                    BridgeAPI.toggleAllSharedModel(newState).then(function() {
                        App.showToast(
                            newState ? t('shared_model_all_on') : t('shared_model_all_off'),
                            'success'
                        );
                        App.showToast(t('shared_model_next_launch'), 'info');
                        loadEnvironments();
                    }).catch(function(e) {
                        App.showToast(e.toString(), 'error');
                    });
                });
                headerToggle.parentNode.replaceChild(hToggle, headerToggle);
                hToggle.id = 'shared-model-header-toggle';
            }

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
                            <input type="radio" name="version-type" value="branch" class="accent-primary">
                            ${t('version_type_branch')}
                        </label>
                        <label class="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="radio" name="version-type" value="tag" checked class="accent-primary">
                            ${t('version_type_tag')}
                        </label>
                    </div>
                </div>
                <div id="create-branch-row" class="hidden">
                    <label class="input-label">${t('env_branch')}</label>
                    <select id="create-branch" class="select">
                        <option value="master">master</option>
                    </select>
                </div>
                <div id="create-tag-row">
                    <label class="input-label">${t('version_tag')}</label>
                    <select id="create-tag" class="select">
                        <option value="">-- ${t('loading')} --</option>
                    </select>
                </div>
                <div class="border-t border-outline/20 pt-3 mt-3">
                    <div id="create-advanced-toggle" class="flex items-center gap-2 cursor-pointer select-none" style="color:rgb(var(--color-on-surface-variant));">
                        <span class="material-symbols-outlined text-[16px]" id="create-advanced-arrow">chevron_right</span>
                        <span class="text-sm font-label uppercase tracking-wider">${t('env_advanced_options')}</span>
                    </div>
                    <div id="create-advanced-body" class="hidden mt-3 space-y-4">
                        <div class="flex gap-4">
                            <label class="flex items-center gap-2 text-sm cursor-pointer">
                                <input type="radio" name="env-mode" value="recommended" checked class="accent-primary">
                                ${t('env_mode_recommended')}
                            </label>
                            <label class="flex items-center gap-2 text-sm cursor-pointer">
                                <input type="radio" name="env-mode" value="custom" class="accent-primary">
                                ${t('env_mode_custom')}
                            </label>
                        </div>
                        <div id="create-recommended-info" class="text-sm text-on-surface-variant p-3 rounded" style="background: rgba(255,255,255,0.05);">
                            ${t('loading')}
                        </div>
                        <div id="create-custom-body" class="hidden space-y-4">
                            <div>
                                <label class="input-label">${t('env_python_version')}</label>
                                <select id="create-python" class="select">
                                    <option value="">${t('loading')}</option>
                                </select>
                            </div>
                            <div>
                                <label class="input-label">${t('env_cuda_version')}</label>
                                <select id="create-cuda" class="select">
                                    <option value="">${t('loading')}</option>
                                </select>
                            </div>
                            <div>
                                <label class="input-label">${t('env_pytorch_version')}</label>
                                <select id="create-pytorch" class="select">
                                    <option value="">${t('loading')}</option>
                                </select>
                            </div>
                            <div class="flex items-center gap-3">
                                <button id="create-refresh-versions" class="btn btn-secondary text-xs" style="padding: 4px 12px;">
                                    <span class="material-symbols-outlined text-[14px]">refresh</span> ${t('env_refresh_versions')}
                                </button>
                                <span id="create-version-hint" class="text-xs text-on-surface-variant"></span>
                            </div>
                        </div>
                        <div class="border-t border-outline/20 pt-3 mt-3">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="material-symbols-outlined text-[14px]" style="color:rgb(var(--color-primary));">folder_shared</span>
                                <span class="text-xs font-label uppercase tracking-wider">${t('shared_model_create_info')}</span>
                            </div>
                            <div id="create-model-path" class="text-xs text-on-surface-variant font-mono p-2 rounded" style="background: rgba(255,255,255,0.05);"></div>
                        </div>
                    </div>
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

            // Load and display shared model path (read-only)
            BridgeAPI.getSharedModelConfig().then(function(config) {
                var pathEl = document.getElementById('create-model-path');
                if (pathEl) {
                    if (config.mode === 'custom' && config.path) {
                        pathEl.textContent = config.path + ' (' + t('shared_model_custom') + ')';
                    } else {
                        pathEl.textContent = config.default_path + ' (' + t('shared_model_default') + ')';
                    }
                }
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

            // Advanced options toggle
            var advToggle = document.getElementById('create-advanced-toggle');
            var advBody = document.getElementById('create-advanced-body');
            var advArrow = document.getElementById('create-advanced-arrow');
            if (advToggle) {
                advToggle.addEventListener('click', function() {
                    var hidden = advBody.classList.toggle('hidden');
                    advArrow.textContent = hidden ? 'chevron_right' : 'expand_more';
                });
            }

            // Mode toggle: recommended vs custom
            var recommendedInfo = document.getElementById('create-recommended-info');
            var customBody = document.getElementById('create-custom-body');
            document.querySelectorAll('input[name="env-mode"]').forEach(function(radio) {
                radio.addEventListener('change', function() {
                    var isCustom = radio.value === 'custom';
                    recommendedInfo.classList.toggle('hidden', isCustom);
                    customBody.classList.toggle('hidden', !isCustom);
                    if (isCustom) {
                        // Trigger PyTorch version load when switching to custom
                        loadPytorchVersions();
                    }
                });
            });

            // Helper: load PyTorch versions based on current CUDA + Python selection
            function loadPytorchVersions() {
                var cudaSelect = document.getElementById('create-cuda');
                var pySelect = document.getElementById('create-python');
                var ptSelect = document.getElementById('create-pytorch');
                if (!cudaSelect || !ptSelect || !pySelect) return;
                var cudaTag = cudaSelect.value;
                var pyVer = pySelect.value;
                if (!cudaTag) return;
                ptSelect.innerHTML = '<option value="">' + t('loading') + '</option>';
                BridgeAPI.getPytorchVersions(cudaTag, pyVer).then(function(versions) {
                    ptSelect.innerHTML = '';
                    if (versions.length === 0) {
                        ptSelect.innerHTML = '<option value="">--</option>';
                        return;
                    }
                    versions.forEach(function(ver, idx) {
                        var opt = document.createElement('option');
                        opt.value = ver;
                        opt.textContent = 'PyTorch ' + ver;
                        if (idx === 0) opt.selected = true;
                        ptSelect.appendChild(opt);
                    });
                }).catch(function(e) {
                    console.error('Failed to load PyTorch versions:', e);
                    ptSelect.innerHTML = '<option value="">--</option>';
                });
            }

            // Load version lists and GPU info for advanced options
            Promise.all([
                BridgeAPI.getVersionLists(),
                BridgeAPI.detectGpu(),
            ]).then(function(results) {
                var lists = results[0];
                var gpu = results[1];
                var preset = lists.recommended_preset;

                // Show recommended preset info
                if (recommendedInfo && preset) {
                    recommendedInfo.textContent = t('env_recommended_preset_desc', preset.label_en || (preset.python_version + ' + ' + preset.cuda_tag + ' + PyTorch ' + preset.pytorch_version));
                }

                // Populate Python dropdown
                var pySelect = document.getElementById('create-python');
                if (pySelect) {
                    pySelect.innerHTML = '';
                    lists.python.forEach(function(py) {
                        var opt = document.createElement('option');
                        opt.value = py.version;
                        opt.textContent = py.display || ('Python ' + py.version);
                        pySelect.appendChild(opt);
                    });
                    // Listen for Python version change to reload PyTorch versions
                    pySelect.addEventListener('change', function() {
                        loadPytorchVersions();
                    });
                }

                // Populate CUDA dropdown
                var cudaSelect = document.getElementById('create-cuda');
                if (cudaSelect) {
                    cudaSelect.innerHTML = '';
                    var recommendedTag = gpu.recommended_cuda_tag || 'cpu';
                    console.log('GPU detection result:', JSON.stringify(gpu), 'recommended:', recommendedTag);
                    lists.cuda_tags.forEach(function(tag) {
                        var opt = document.createElement('option');
                        opt.value = tag;
                        opt.textContent = tag === 'cpu' ? 'CPU Only' : tag.toUpperCase();
                        if (tag === recommendedTag) {
                            opt.textContent += ' (' + t('env_recommended') + ')';
                        }
                        cudaSelect.appendChild(opt);
                    });
                    cudaSelect.value = recommendedTag;
                    // Listen for CUDA tag change to reload PyTorch versions
                    cudaSelect.addEventListener('change', function() {
                        loadPytorchVersions();
                    });
                }

                // Version hint
                var hint = document.getElementById('create-version-hint');
                if (hint) {
                    if (lists.cache_info) {
                        hint.textContent = t('env_version_hint_cached', lists.cache_info.substring(0, 10));
                    } else {
                        hint.textContent = t('env_version_hint_offline');
                    }
                }
            }).catch(function(e) {
                console.error('Failed to load version lists or detect GPU:', e);
            });

            // Refresh button
            var refreshBtn = document.getElementById('create-refresh-versions');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function() {
                    refreshBtn.disabled = true;
                    refreshBtn.textContent = t('loading');
                    BridgeAPI.refreshVersionLists().then(function(data) {
                        App.showToast(t('env_refresh_success'), 'success');
                        refreshBtn.textContent = t('env_refresh_versions');
                        refreshBtn.disabled = false;
                        var hint = document.getElementById('create-version-hint');
                        if (hint) hint.textContent = t('env_version_hint_cached', data.last_updated.substring(0, 10));

                        // Update recommended preset info
                        if (recommendedInfo && data.recommended_preset) {
                            var p = data.recommended_preset;
                            recommendedInfo.textContent = t('env_recommended_preset_desc', p.label_en || (p.python_version + ' + ' + p.cuda_tag + ' + PyTorch ' + p.pytorch_version));
                        }

                        // Update Python dropdown
                        var pySelect = document.getElementById('create-python');
                        if (pySelect && data.python) {
                            var currentVal = pySelect.value;
                            pySelect.innerHTML = '';
                            data.python.forEach(function(py) {
                                var opt = document.createElement('option');
                                opt.value = py.version;
                                opt.textContent = py.display || ('Python ' + py.version);
                                pySelect.appendChild(opt);
                            });
                            pySelect.value = currentVal;
                        }
                        // Update CUDA dropdown
                        var cudaSelect = document.getElementById('create-cuda');
                        if (cudaSelect && data.cuda_tags) {
                            var currentCuda = cudaSelect.value;
                            cudaSelect.innerHTML = '';
                            data.cuda_tags.forEach(function(tag) {
                                var opt = document.createElement('option');
                                opt.value = tag;
                                opt.textContent = tag === 'cpu' ? 'CPU Only' : tag.toUpperCase();
                                cudaSelect.appendChild(opt);
                            });
                            cudaSelect.value = currentCuda;
                        }
                        // Reload PyTorch versions
                        loadPytorchVersions();
                    }).catch(function() {
                        App.showToast(t('env_refresh_failed'), 'error');
                        refreshBtn.textContent = t('env_refresh_versions');
                        refreshBtn.disabled = false;
                    });
                });
            }
        }, 100);
    }

    function doCreate() {
        const name = document.getElementById('create-name').value.trim();
        if (!name) { App.showToast(`${t('env_name')} required`, 'info'); return; }

        const versionType = document.querySelector('input[name="version-type"]:checked').value;
        let branch, commit;
        if (versionType === 'tag') {
            branch = 'master';
            commit = document.getElementById('create-tag').value;
        } else {
            branch = document.getElementById('create-branch').value || 'master';
            commit = '';
        }

        // Read advanced options based on mode
        var envMode = document.querySelector('input[name="env-mode"]:checked');
        var isRecommended = !envMode || envMode.value === 'recommended';
        var pythonVersion, cudaTag, pytorchVersion;

        if (isRecommended) {
            // Use recommended preset values — bridge will read them from RECOMMENDED_PRESET
            pythonVersion = '__recommended__';
            cudaTag = '';
            pytorchVersion = '';
        } else {
            var pySelect = document.getElementById('create-python');
            var cudaSelect = document.getElementById('create-cuda');
            var ptSelect = document.getElementById('create-pytorch');
            pythonVersion = pySelect ? pySelect.value : '';
            cudaTag = cudaSelect ? cudaSelect.value : '';
            pytorchVersion = ptSelect ? ptSelect.value : '';
        }

        App.hideModal();

        var progressId = 'create-' + Date.now();
        var displayPython = (pythonVersion === '__recommended__') ? '' : pythonVersion;
        var stepLabels = {
            python_download: t('env_downloading_python', displayPython) || 'Downloading Python',
            venv: t('step_venv') || 'Creating virtual environment',
            clone: t('step_clone') || 'Cloning ComfyUI',
            pytorch: t('step_pytorch') || 'Installing PyTorch',
            dependencies: t('step_dependencies') || 'Installing dependencies',
            manager: t('step_manager') || 'Installing ComfyUI-Manager',
            finalize: t('step_finalize') || 'Finalizing',
            done: t('step_done') || 'Complete',
        };

        App.showProgress(progressId, t('env_creating', name));

        BridgeAPI.createEnvironmentV2(name, branch, commit, pythonVersion, cudaTag, pytorchVersion, function(msg) {
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
                    <input type="text" id="clone-name" class="input" value="${source}-copy">
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
