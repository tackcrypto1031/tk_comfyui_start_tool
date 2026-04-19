/**
 * versions.js — Git branch/tag/commit control + PyTorch Engine sub-tab
 */
(function() {

    var _envs = [];
    var _tags = [];
    var _selectedRef = null;
    var _selectedLabel = null;
    var _currentCommit = '';

    // ── PyTorch Engine tab state ──────────────────────────────────────────
    var _ptEnvs = [];
    var _ptPacks = [];
    var _ptAddonRegistry = [];

    function render(container) {
        container.innerHTML =
            '<div class="ti-content fade-in">' +
                // Sub-tab switcher
                '<div class="versions-tabs">' +
                    '<button class="versions-tab-btn active" data-tab="comfy">' + h(t('versions.tab_comfy') || 'ComfyUI Version') + '</button>' +
                    '<button class="versions-tab-btn" data-tab="pytorch">' + h(t('versions.tab_pytorch') || 'PyTorch Engine') + '</button>' +
                '</div>' +

                // ComfyUI Version tab content
                '<div class="versions-tab-content active" id="tab-comfy">' +
                    '<div class="ti-page-head">' +
                        '<div>' +
                            '<p class="ti-page-sub" id="ver-sub">—</p>' +
                        '</div>' +
                        '<div class="ti-page-actions">' +
                            '<div class="ti-env-select">' +
                                '<label>' + h(t('version_environment')) + '</label>' +
                                '<select id="ver-env"></select>' +
                            '</div>' +
                            '<button id="ver-btn-refresh" class="btn btn-secondary" title="' + h(t('env_refresh')) + '">' +
                                '<span class="material-symbols-outlined" style="font-size:14px">refresh</span>' +
                            '</button>' +
                        '</div>' +
                    '</div>' +

                    '<div class="ti-card-grid-2">' +
                        '<div class="ti-card">' +
                            '<div class="ti-card-head">' +
                                '<span class="material-symbols-outlined">tag</span>' +
                                '<span class="ti-card-title">' + h(t('version_available_tags')) + '</span>' +
                                '<button id="ver-btn-fetch" class="btn btn-ghost btn-sm" style="margin-left:auto">' +
                                    '<span class="material-symbols-outlined" style="font-size:13px">cloud_download</span>' +
                                    '<span>' + h(t('version_refresh_versions')) + '</span>' +
                                '</button>' +
                            '</div>' +
                            '<div class="ti-card-body">' +
                                '<div id="ver-tags-status" style="font-size:11px;color:var(--text-3);font-family:var(--font-mono)">—</div>' +
                                '<div id="ver-tags-list" class="ti-tag-list" style="margin-top:10px"></div>' +
                                '<div id="ver-current-notice" style="font-size:11px;color:var(--warn);font-family:var(--font-mono);display:none;margin-top:10px"></div>' +
                                '<button id="ver-btn-switch" class="btn btn-primary" style="width:100%;justify-content:center;margin-top:12px">' +
                                    '<span class="material-symbols-outlined" style="font-size:14px">download</span>' +
                                    '<span>' + h(t('version_switch')) + '</span>' +
                                '</button>' +
                            '</div>' +
                        '</div>' +
                        '<div class="ti-card">' +
                            '<div class="ti-card-head">' +
                                '<span class="material-symbols-outlined">refresh</span>' +
                                '<span class="ti-card-title">' + h(t('version_update')) + '</span>' +
                            '</div>' +
                            '<div class="ti-card-body">' +
                                '<div id="ver-update-status" style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-3)">' +
                                    '<span class="chip">—</span>' +
                                '</div>' +
                                '<button id="ver-btn-update" class="btn btn-primary" style="width:100%;justify-content:center;margin-top:12px">' +
                                    '<span class="material-symbols-outlined" style="font-size:14px">arrow_forward</span>' +
                                    '<span>' + h(t('version_update')) + '</span>' +
                                '</button>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +

                    '<div class="ti-section-head">' +
                        '<h2>' + h(t('version_recent_commits') || '最近 Commits') + '</h2>' +
                        '<div class="line"></div>' +
                    '</div>' +
                    '<div id="ver-commits" class="ti-card"></div>' +
                    '<div id="ver-status" style="margin-top:10px;font-family:var(--font-mono);font-size:11px;color:var(--text-4);text-transform:uppercase;letter-spacing:0.1em"></div>' +
                '</div>' +

                // PyTorch Engine tab content
                '<div class="versions-tab-content" id="tab-pytorch">' +
                    '<div id="pt-panel"></div>' +
                '</div>' +
            '</div>';

        // Tab switching
        container.querySelectorAll('.versions-tab-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                container.querySelectorAll('.versions-tab-btn').forEach(function(b) { b.classList.remove('active'); });
                container.querySelectorAll('.versions-tab-content').forEach(function(c) { c.classList.remove('active'); });
                btn.classList.add('active');
                var target = container.querySelector('#tab-' + btn.dataset.tab);
                if (target) target.classList.add('active');
                // Lazy-load PyTorch panel on first open
                if (btn.dataset.tab === 'pytorch') {
                    var panel = container.querySelector('#pt-panel');
                    if (panel && !panel.dataset.loaded) {
                        panel.dataset.loaded = '1';
                        renderPyTorchPanel(panel);
                    }
                }
            });
        });

        // ComfyUI tab bindings
        document.getElementById('ver-btn-refresh').addEventListener('click', loadEnvs);
        document.getElementById('ver-btn-fetch').addEventListener('click', fetchTags);
        document.getElementById('ver-btn-switch').addEventListener('click', switchToSelected);
        document.getElementById('ver-btn-update').addEventListener('click', updateToLatest);
        document.getElementById('ver-env').addEventListener('change', onEnvChange);

        loadEnvs();
    }

    // ── PyTorch Engine panel ──────────────────────────────────────────────

    function renderPyTorchPanel(container) {
        container.innerHTML = '<div style="color:var(--text-3);font-size:13px;padding:20px">' + h(t('loading')) + '</div>';

        Promise.all([
            BridgeAPI.listEnvironments(),
            BridgeAPI.listTorchPacks ? BridgeAPI.listTorchPacks() : Promise.resolve('{"ok":false,"packs":[]}'),
            BridgeAPI.listAddons ? BridgeAPI.listAddons() : Promise.resolve('{"ok":false,"addons":[]}'),
        ]).then(function(results) {
            _ptEnvs = results[0] || [];
            try {
                var packsRes = typeof results[1] === 'string' ? JSON.parse(results[1]) : results[1];
                _ptPacks = (packsRes && packsRes.packs) ? packsRes.packs : [];
            } catch(e) { _ptPacks = []; }
            try {
                var addonsRes = typeof results[2] === 'string' ? JSON.parse(results[2]) : results[2];
                _ptAddonRegistry = (addonsRes && addonsRes.addons) ? addonsRes.addons : [];
            } catch(e) { _ptAddonRegistry = []; }

            _renderPtPanelHtml(container);
        }).catch(function(e) {
            container.innerHTML = '<div style="color:var(--danger);font-size:13px;padding:20px">' + h(t('error') + ': ' + e) + '</div>';
        });
    }

    function _renderPtPanelHtml(container) {
        var envOptions = _ptEnvs.map(function(e) {
            return '<option value="' + h(e.name) + '">' + h(e.name) + '</option>';
        }).join('');

        var packRows = _ptPacks.map(function(p) {
            var recTag = p.recommended ? '<span class="pt-pack-tag">' + h(t('versions.pytorch.recommended') || 'Recommended') + '</span>' : '';
            return '<label class="pt-pack-row">' +
                '<input type="radio" name="pt-pack" value="' + h(p.id) + '" style="flex-shrink:0">' +
                '<span class="pt-pack-label">' + h(p.label || p.id) + '</span>' +
                recTag +
            '</label>';
        }).join('');

        if (!packRows) {
            packRows = '<div style="padding:14px;color:var(--text-3);font-size:13px">' + h(t('version_no_tags') || 'No packs found. Click Refresh List.') + '</div>';
        }

        container.innerHTML =
            '<div class="ti-card-grid-2" style="margin-bottom:16px">' +
                '<div>' +
                    '<div class="ti-env-select" style="width:100%;margin-bottom:10px">' +
                        '<label>' + h(t('versions.pytorch.env') || 'Environment') + '</label>' +
                        '<select id="pt-env">' + envOptions + '</select>' +
                    '</div>' +
                    '<div id="pt-current" class="pt-current-info"></div>' +
                    '<div id="pt-compiled-warn"></div>' +
                '</div>' +
                '<div>' +
                    '<div class="pt-pack-list" id="pt-pack-list">' + packRows + '</div>' +
                '</div>' +
            '</div>' +
            '<div class="pt-actions">' +
                '<button id="pt-refresh" class="btn btn-secondary">' +
                    '<span class="material-symbols-outlined" style="font-size:14px">refresh</span>' +
                    '<span>' + h(t('versions.pytorch.refresh') || 'Refresh List') + '</span>' +
                '</button>' +
                '<button id="pt-switch" class="btn btn-primary">' +
                    '<span class="material-symbols-outlined" style="font-size:14px">swap_horiz</span>' +
                    '<span>' + h(t('versions.pytorch.switch') || 'Switch') + '</span>' +
                '</button>' +
            '</div>' +
            '<div id="pt-status" style="margin-top:8px;font-family:var(--font-mono);font-size:11px;color:var(--text-4)"></div>';

        // Bind env selector
        var envSel = container.querySelector('#pt-env');
        if (envSel) {
            envSel.addEventListener('change', function() { _ptRefreshCurrent(container); });
            _ptRefreshCurrent(container);
        }

        // Refresh list button
        var refreshBtn = container.querySelector('#pt-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                refreshBtn.disabled = true;
                (BridgeAPI.refreshTorchPacks ? BridgeAPI.refreshTorchPacks() : Promise.resolve('{"ok":false,"error":"not available"}'))
                    .then(function(res) {
                        var parsed = {};
                        try { parsed = typeof res === 'string' ? JSON.parse(res) : res; } catch(e) {}
                        if (parsed.ok) {
                            App.showToast(t('versions.pytorch.refreshed') || 'Refreshed', 'success');
                            // Reload packs then re-render
                            return BridgeAPI.listTorchPacks();
                        } else {
                            App.showToast(parsed.error || 'Refresh failed', 'error');
                        }
                    }).then(function(packsJson) {
                        if (!packsJson) return;
                        try {
                            var pr = typeof packsJson === 'string' ? JSON.parse(packsJson) : packsJson;
                            _ptPacks = (pr && pr.packs) ? pr.packs : _ptPacks;
                        } catch(e) {}
                        _renderPtPanelHtml(container);
                    }).catch(function(e) {
                        App.showToast(t('error') + ': ' + e, 'error');
                    }).finally ? (function() { refreshBtn.disabled = false; })() : null;
                // ensure re-enable even if .finally not available
                setTimeout(function() { if (refreshBtn) refreshBtn.disabled = false; }, 5000);
            });
        }

        // Switch button
        var switchBtn = container.querySelector('#pt-switch');
        if (switchBtn) {
            switchBtn.addEventListener('click', function() { _ptDoSwitch(container); });
        }
    }

    function _ptRefreshCurrent(container) {
        var envSel = container.querySelector('#pt-env');
        if (!envSel) return;
        var envName = envSel.value;
        var env = _ptEnvs.find(function(e) { return e.name === envName; });
        var currentEl = container.querySelector('#pt-current');
        var warnEl = container.querySelector('#pt-compiled-warn');

        if (currentEl) {
            if (env && env.torch_pack) {
                var pack = _ptPacks.find(function(p) { return p.id === env.torch_pack; });
                currentEl.innerHTML = '<p>' + h(t('versions.pytorch.current') || 'Current') + ': <strong>' +
                    h(pack ? pack.label : env.torch_pack) + '</strong> \u2705</p>';
            } else if (env) {
                currentEl.innerHTML = '<p>' + h(t('versions.pytorch.custom') || 'Custom version') +
                    ' (torch ' + h(env.pytorch_version || '?') + ') \u26a0\ufe0f</p>';
            } else {
                currentEl.innerHTML = '';
            }
        }

        if (warnEl) {
            var compiledIds = new Set(_ptAddonRegistry.filter(function(a) { return a.requires_compile; }).map(function(a) { return a.id; }));
            var installedAddons = (env && env.installed_addons) ? env.installed_addons : [];
            var compiled = installedAddons.filter(function(a) { return compiledIds.has(a.id || a); });
            if (compiled.length) {
                warnEl.innerHTML = '<div class="pt-banner-warn">' +
                    h(t('versions.pytorch.compiled_warn') || 'Switching will uninstall these compiled add-ons (you can reinstall afterward):') +
                    '<ul>' + compiled.map(function(c) { return '<li>' + h(c.id || c) + '</li>'; }).join('') + '</ul>' +
                '</div>';
            } else {
                warnEl.innerHTML = '';
            }
        }
    }

    function _ptDoSwitch(container) {
        var envSel = container.querySelector('#pt-env');
        var picked = container.querySelector('input[name="pt-pack"]:checked');
        if (!envSel) return;
        var envName = envSel.value;
        if (!envName) { App.showToast(t('launch_select_env'), 'info'); return; }
        if (!picked) { App.showToast(t('versions.pytorch.pick_pack') || 'Pick a Pack first', 'info'); return; }

        var env = _ptEnvs.find(function(e) { return e.name === envName; });
        var compiledIds = new Set(_ptAddonRegistry.filter(function(a) { return a.requires_compile; }).map(function(a) { return a.id; }));
        var installedAddons = (env && env.installed_addons) ? env.installed_addons : [];
        var compiled = installedAddons.filter(function(a) { return compiledIds.has(a.id || a); }).map(function(a) { return a.id || a; });

        var confirmMsg = t('versions.pytorch.confirm') || 'Switch Pack now? A snapshot will be created first.';
        if (compiled.length) {
            confirmMsg += '\n\n' + (t('versions.pytorch.confirm_compiled_removal') || 'The following compiled add-ons will be uninstalled (you can reinstall afterward):') + ' ' + compiled.join(', ');
        }

        App.confirm(confirmMsg).then(function(ok) {
            if (!ok) return;
            var statusEl = container.querySelector('#pt-status');
            if (statusEl) statusEl.textContent = t('version_switching');

            var progressId = 'pt-switch-' + Date.now();
            App.showProgress(progressId, t('version_switching'));

            (BridgeAPI.switchTorchPack ? BridgeAPI.switchTorchPack(envName, picked.value, function(msg) {
                App.updateProgress(progressId, msg.step || msg, msg.percent || 0, msg.detail || '');
            }) : Promise.reject('switchTorchPack not available'))
                .then(function() {
                    App.hideProgress(progressId, 'success');
                    App.showToast(t('versions.pytorch.switched') || 'Pack switched', 'success');
                    if (statusEl) statusEl.textContent = t('versions.pytorch.switched') || 'Pack switched';
                    // Refresh env list and re-render current indicator
                    BridgeAPI.listEnvironments().then(function(envs) {
                        _ptEnvs = envs || [];
                        _ptRefreshCurrent(container);
                    });
                }).catch(function(e) {
                    App.hideProgress(progressId, 'error');
                    App.showToast(t('error') + ': ' + e, 'error');
                    if (statusEl) statusEl.textContent = t('error') + ': ' + e;
                });
        });
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            _envs = envs || [];
            var select = document.getElementById('ver-env');
            var prev = select.value;
            select.innerHTML = _envs.map(function(e) {
                return '<option value="' + h(e.name) + '">' + h(e.name) + '</option>';
            }).join('');
            if (prev) select.value = prev;
            onEnvChange();
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function currentEnv() {
        var name = document.getElementById('ver-env').value;
        return _envs.find(function(e) { return e.name === name; }) || null;
    }

    function onEnvChange() {
        var env = currentEnv();
        _currentCommit = env ? (env.comfyui_commit || '') : '';
        var sub = document.getElementById('ver-sub');
        if (env) {
            sub.innerHTML = '<span class="accent">' + h(env.name) + '</span> · 當前 commit <span class="mono" style="color:var(--text-1)">' + h((_currentCommit || '—').substring(0, 7)) + '</span>';
        } else {
            sub.textContent = '—';
        }
        // Load commits for this env
        loadCommits();
        // Re-render tags (for highlight)
        if (_tags.length) renderTags();
    }

    function loadCommits() {
        var env = currentEnv();
        if (!env) { document.getElementById('ver-commits').innerHTML = ''; return; }
        if (!BridgeAPI.listCommits) return;
        BridgeAPI.listCommits(env.name).then(function(commits) {
            renderCommits(commits || []);
        }).catch(function() { /* silent */ });
    }

    function renderCommits(commits) {
        var wrap = document.getElementById('ver-commits');
        if (!wrap) return;
        if (!commits.length) {
            wrap.innerHTML = '<div class="ti-list-empty"><span class="material-symbols-outlined">history</span><div>—</div></div>';
            return;
        }
        wrap.innerHTML = commits.slice(0, 20).map(function(c) {
            var hash = (c.hash || c.id || '').substring(0, 7);
            return '<div class="ti-commit-row">' +
                '<span class="hash">' + h(hash) + '</span>' +
                '<span class="msg" title="' + h(c.message || c.msg || '') + '">' + h(c.message || c.msg || '') + '</span>' +
                '<span class="author">' + h(c.author || '') + '</span>' +
                '<span class="date">' + h(c.date || c.relative || '') + '</span>' +
            '</div>';
        }).join('');
    }

    function fetchTags() {
        var statusEl = document.getElementById('ver-tags-status');
        statusEl.textContent = t('version_fetching');
        document.getElementById('ver-btn-fetch').disabled = true;
        BridgeAPI.listRemoteVersions().then(function(versions) {
            _tags = (versions && versions.tags) || [];
            renderTags();
            statusEl.textContent = t('version_tag_count', _tags.length);
            document.getElementById('ver-btn-fetch').disabled = false;
            // update pull-latest card
            updatePullStatus(versions);
        }).catch(function(e) {
            statusEl.textContent = t('version_fetch_failed', e.toString());
            document.getElementById('ver-btn-fetch').disabled = false;
        });
    }

    function updatePullStatus(versions) {
        var el = document.getElementById('ver-update-status');
        if (!el) return;
        var behind = versions && versions.commits_behind;
        if (behind && behind > 0) {
            el.innerHTML = '<span class="chip accent">● ' + (t('version_has_update') || '有新版本') + '</span>' +
                '<span style="font-size:12px;color:var(--text-3)">' + behind + ' 個 commit 落後</span>';
        } else {
            el.innerHTML = '<span class="chip">已是最新</span>';
        }
    }

    function renderTags() {
        var wrap = document.getElementById('ver-tags-list');
        if (!wrap) return;
        var currentFull = _currentCommit;
        var matched = false;

        if (!_tags.length) {
            wrap.innerHTML = '<div class="ti-list-empty" style="border:0;padding:20px"><span class="material-symbols-outlined">tag</span><div>點擊右上角 "更新版本列表" 來載入</div></div>';
            return;
        }

        wrap.innerHTML = _tags.map(function(tag) {
            var isCurrent = currentFull && tag.hash && tag.hash === currentFull;
            if (isCurrent) matched = true;
            var selected = (_selectedRef === tag.name) ? ' selected' : '';
            return '<div class="ti-tag-row' + selected + '" data-ref="' + h(tag.name) + '">' +
                '<span class="tag-name">' + h(tag.name) +
                    (isCurrent ? ' <span class="current-badge">← ' + h(t('version_current') || 'current') + '</span>' : '') +
                '</span>' +
                '<span class="tag-date">' + h(tag.date || (tag.hash ? tag.hash.substring(0, 7) : '—')) + '</span>' +
            '</div>';
        }).join('');

        wrap.querySelectorAll('.ti-tag-row').forEach(function(r) {
            r.addEventListener('click', function() {
                wrap.querySelectorAll('.ti-tag-row.selected').forEach(function(n) { n.classList.remove('selected'); });
                r.classList.add('selected');
                _selectedRef = r.getAttribute('data-ref');
                _selectedLabel = _selectedRef;
            });
        });

        var notice = document.getElementById('ver-current-notice');
        if (notice) {
            if (!matched && currentFull) {
                notice.textContent = t('version_not_on_tag', currentFull.substring(0, 7));
                notice.style.display = '';
            } else {
                notice.style.display = 'none';
            }
        }
    }

    function switchToSelected() {
        var env = currentEnv();
        if (!env) { App.showToast(t('launch_select_env'), 'info'); return; }
        if (!_selectedRef) { App.showToast(t('version_select_commit'), 'info'); return; }

        App.confirm(t('version_confirm_switch', _selectedRef)).then(function(ok) {
            if (!ok) return;
            var statusEl = document.getElementById('ver-status');
            statusEl.textContent = t('version_switching');
            BridgeAPI.switchVersion(env.name, _selectedRef).then(function() {
                statusEl.textContent = t('version_switched');
                App.showToast(t('version_switched'), 'success');
                loadEnvs();
            }).catch(function(e) {
                statusEl.textContent = t('error') + ': ' + e;
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function updateToLatest() {
        var env = currentEnv();
        if (!env) { App.showToast(t('launch_select_env'), 'info'); return; }
        App.confirm(t('version_confirm_update')).then(function(ok) {
            if (!ok) return;
            document.getElementById('ver-status').textContent = t('version_updating');
            BridgeAPI.updateComfyUI(env.name).then(function() {
                document.getElementById('ver-status').textContent = t('version_updated');
                App.showToast(t('version_updated'), 'success');
                loadEnvs();
            }).catch(function(e) {
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function h(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    App.registerPage('versions', { render: render });
})();
