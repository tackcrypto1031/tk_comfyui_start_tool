/**
 * plugins.js — Plugin management (Tack Industrial redesign)
 * Features kept: list + enable/disable/delete/update + update-all + analyze + install
 */
(function() {

    var _plugins = [];
    var _filter = '';
    var _lastRiskLevel = null;
    var _installOpen = false;

    function render(container) {
        container.innerHTML =
            '<div class="ti-content fade-in">' +
                '<div class="ti-page-head">' +
                    '<div>' +
                        '<p class="ti-page-sub" id="plug-sub">—</p>' +
                    '</div>' +
                    '<div class="ti-page-actions">' +
                        '<div class="ti-env-select">' +
                            '<label>' + h(t('plugin_environment')) + '</label>' +
                            '<select id="plug-env"></select>' +
                        '</div>' +
                        '<div class="ti-search-box">' +
                            '<span class="material-symbols-outlined">search</span>' +
                            '<input id="plug-search" type="text" placeholder="' + h(t('plugin_search_placeholder')) + '">' +
                        '</div>' +
                        '<button id="plug-btn-update-all" class="btn btn-secondary" title="' + h(t('plugin_update_all')) + '">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">update</span>' +
                            '<span>' + h(t('plugin_update_all')) + '</span>' +
                        '</button>' +
                        '<button id="plug-btn-refresh" class="btn btn-secondary" title="' + h(t('env_refresh')) + '">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">refresh</span>' +
                        '</button>' +
                        '<button id="plug-btn-new" class="btn btn-primary">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">add</span>' +
                            '<span>' + h(t('plugin_install')) + '</span>' +
                        '</button>' +
                    '</div>' +
                '</div>' +

                // Install / analyze card — hidden by default, toggled by the "Install" button
                '<div id="plug-install-card" class="ti-card" style="display:none;margin-bottom:20px">' +
                    '<div class="ti-card-head">' +
                        '<span class="material-symbols-outlined">download</span>' +
                        '<span class="ti-card-title">' + h(t('plugin_conflict_report')) + '</span>' +
                        '<button id="plug-btn-install-close" class="btn btn-ghost btn-sm" style="margin-left:auto">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">close</span>' +
                        '</button>' +
                    '</div>' +
                    '<div class="ti-card-body">' +
                        '<div class="ti-field">' +
                            '<label>Plugin URL / path</label>' +
                            '<input id="plug-path" type="text" placeholder="' + h(t('plugin_url_placeholder')) + '" style="width:100%">' +
                        '</div>' +
                        '<div style="display:flex;gap:8px">' +
                            '<button id="plug-btn-analyze" class="btn btn-secondary">' +
                                '<span class="material-symbols-outlined" style="font-size:14px">search</span>' +
                                '<span>' + h(t('plugin_analyze')) + '</span>' +
                            '</button>' +
                            '<button id="plug-btn-install" class="btn btn-primary" disabled>' +
                                '<span class="material-symbols-outlined" style="font-size:14px">download</span>' +
                                '<span>' + h(t('plugin_install')) + '</span>' +
                            '</button>' +
                        '</div>' +
                        '<div id="plug-results" style="display:none;margin-top:14px">' +
                            '<div id="plug-risk-banner" style="padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-2);display:flex;align-items:center;gap:10px;margin-bottom:10px"></div>' +
                            '<div id="plug-summary" style="font-size:13px;color:var(--text-2);margin-bottom:10px"></div>' +
                            '<div id="plug-recommendations" style="display:flex;flex-direction:column;gap:4px;margin-bottom:12px"></div>' +
                            '<div id="plug-conflicts-wrap"></div>' +
                        '</div>' +
                    '</div>' +
                '</div>' +

                // Installed plugin list
                '<div id="plug-list-wrap"></div>' +
                '<div id="plug-restart-hint" style="display:none;margin-top:10px;font-size:12px;color:var(--warn);font-family:var(--font-mono)"></div>' +
                '<div id="plug-status" style="margin-top:10px;font-family:var(--font-mono);font-size:11px;color:var(--text-4);text-transform:uppercase;letter-spacing:0.1em"></div>' +
            '</div>';

        document.getElementById('plug-btn-refresh').addEventListener('click', loadPlugins);
        document.getElementById('plug-btn-update-all').addEventListener('click', doUpdateAll);
        document.getElementById('plug-env').addEventListener('change', loadPlugins);

        document.getElementById('plug-btn-new').addEventListener('click', toggleInstallCard);
        document.getElementById('plug-btn-install-close').addEventListener('click', function() { setInstallCardOpen(false); });
        document.getElementById('plug-btn-analyze').addEventListener('click', doAnalyze);
        document.getElementById('plug-btn-install').addEventListener('click', doInstall);
        document.getElementById('plug-path').addEventListener('input', function() {
            document.getElementById('plug-btn-install').disabled = true;
            _lastRiskLevel = null;
        });

        var search = document.getElementById('plug-search');
        search.addEventListener('input', function() {
            _filter = search.value.trim().toLowerCase();
            renderList();
        });

        loadEnvs();
    }

    function toggleInstallCard() { setInstallCardOpen(!_installOpen); }
    function setInstallCardOpen(open) {
        _installOpen = !!open;
        document.getElementById('plug-install-card').style.display = _installOpen ? '' : 'none';
        if (_installOpen) {
            setTimeout(function() {
                var i = document.getElementById('plug-path');
                if (i) i.focus();
            }, 50);
        }
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            var select = document.getElementById('plug-env');
            select.innerHTML = (envs || []).map(function(e) {
                return '<option value="' + h(e.name) + '">' + h(e.name) + '</option>';
            }).join('');
            loadPlugins();
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function loadPlugins() {
        var envName = document.getElementById('plug-env').value;
        if (!envName) { renderList(); return; }
        document.getElementById('plug-status').textContent = t('loading');
        BridgeAPI.listPlugins(envName).then(function(plugins) {
            _plugins = plugins || [];
            document.getElementById('plug-status').textContent = '';
            renderList();
        }).catch(function(e) {
            document.getElementById('plug-status').textContent = t('error') + ': ' + e;
        });
    }

    function renderList() {
        var wrap = document.getElementById('plug-list-wrap');
        var envName = document.getElementById('plug-env').value;
        var filtered = _plugins.filter(function(p) {
            if (!_filter) return true;
            return (p.name || '').toLowerCase().indexOf(_filter) !== -1
                || (p.author || '').toLowerCase().indexOf(_filter) !== -1;
        });

        var sub = document.getElementById('plug-sub');
        var total = _plugins.length;
        var enabled = _plugins.filter(function(p) { return p.status === 'enabled'; }).length;
        sub.innerHTML = '<span class="accent">' + h(envName || '—') + '</span> · ' + h(t('plugin_enabled_ratio', enabled, total));

        if (!filtered.length) {
            wrap.innerHTML =
                '<div class="ti-list-empty">' +
                    '<span class="material-symbols-outlined">extension</span>' +
                    '<div>' + h(t('plugin_no_plugins')) + '</div>' +
                '</div>';
            return;
        }

        var rowsHtml = '<div class="ti-plugin-list">' +
            '<div class="ti-plugin-list-head">' +
                '<span></span>' +
                '<span>' + h(t('plugin_col_name')) + '</span>' +
                '<span>' + h(t('plugin_col_status')) + '</span>' +
                '<span></span>' +
                '<span style="text-align:right">' + h(t('plugin_col_actions')) + '</span>' +
            '</div>';

        filtered.forEach(function(p) {
            var name = p.name || p.node_name || '';
            var status = p.status || 'untracked';
            var isEnabled = status === 'enabled';
            var canUpdate = isEnabled && p.repo_url && p.has_update === true;
            var statusChip = isEnabled
                ? '<span class="chip accent">● ' + h(t('plugin_chip_enabled')) + '</span>'
                : (status === 'disabled' ? '<span class="chip" style="color:var(--warn);border-color:var(--warn);background:transparent">○ ' + h(t('plugin_chip_disabled')) + '</span>'
                                         : '<span class="chip">· ' + h(t('plugin_status_untracked')) + '</span>');
            var updateChip = canUpdate ? '<span class="chip accent">● ' + h(t('plugin_chip_update')) + '</span>' : '';
            rowsHtml +=
                '<div class="ti-plugin-row" data-name="' + h(name) + '">' +
                    '<div class="ti-plugin-check ' + (isEnabled ? 'on' : '') + '" data-toggle="' + h(name) + '" data-status="' + h(status) + '">' +
                        (isEnabled ? '<span class="material-symbols-outlined">check</span>' : '') +
                    '</div>' +
                    '<div>' +
                        '<div class="ti-plugin-name" title="' + h(name) + '">' + h(name) + '</div>' +
                        (p.author ? '<div class="ti-plugin-author">by ' + h(p.author) + '</div>' : '') +
                    '</div>' +
                    '<div class="ti-plugin-version">' + statusChip + '</div>' +
                    '<div>' + updateChip + '</div>' +
                    '<div class="ti-plugin-actions">' +
                        (canUpdate ?
                            '<button class="btn btn-secondary btn-sm" data-update="' + h(name) + '" title="' + h(t('plugin_update')) + '">' +
                                '<span class="material-symbols-outlined" style="font-size:13px">arrow_upward</span>' +
                            '</button>' : '') +
                        (p.repo_url ?
                            '<button class="btn btn-ghost btn-sm" data-open="' + h(p.repo_url) + '" title="Open repo">' +
                                '<span class="material-symbols-outlined" style="font-size:13px">open_in_new</span>' +
                            '</button>' : '') +
                        '<button class="btn btn-danger btn-sm" data-delete="' + h(name) + '" title="' + h(t('plugin_delete')) + '">' +
                            '<span class="material-symbols-outlined" style="font-size:13px">delete</span>' +
                        '</button>' +
                    '</div>' +
                '</div>';
        });
        rowsHtml += '</div>';
        wrap.innerHTML = rowsHtml;

        // Bind
        wrap.querySelectorAll('[data-toggle]').forEach(function(el) {
            el.addEventListener('click', function() {
                doTogglePlugin(envName, el.getAttribute('data-toggle'), el.getAttribute('data-status'));
            });
        });
        wrap.querySelectorAll('[data-delete]').forEach(function(el) {
            el.addEventListener('click', function() { doDeletePlugin(envName, el.getAttribute('data-delete')); });
        });
        wrap.querySelectorAll('[data-update]').forEach(function(el) {
            el.addEventListener('click', function() { doUpdatePlugin(envName, el.getAttribute('data-update')); });
        });
        wrap.querySelectorAll('[data-open]').forEach(function(el) {
            el.addEventListener('click', function() {
                if (BridgeAPI.openUrl) BridgeAPI.openUrl(el.getAttribute('data-open'));
            });
        });
    }

    // ── Enable / disable / delete / update (same logic as before) ────────

    function doTogglePlugin(envName, nodeName, currentStatus) {
        var isManager = nodeName === 'ComfyUI-Manager';
        var isDisabling = currentStatus !== 'disabled';
        if (isManager) {
            var confirmMsg = isDisabling ? t('plugin_confirm_manager_disable') : t('plugin_confirm_manager_disable');
            if (!confirm(confirmMsg)) return;
        }
        var action = isDisabling
            ? BridgeAPI.disablePlugin(envName, nodeName)
            : BridgeAPI.enablePlugin(envName, nodeName);
        action.then(function() {
            var msg = isDisabling
                ? t('plugin_disabled_success', nodeName)
                : t('plugin_enabled_success', nodeName);
            App.showToast(msg, 'info');
            showRestartHint();
            loadPlugins();
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function doDeletePlugin(envName, nodeName) {
        var isManager = nodeName === 'ComfyUI-Manager';
        var confirmMsg = t('plugin_confirm_delete', nodeName);
        if (isManager) confirmMsg += '\n\n' + t('plugin_confirm_manager_delete');
        if (!confirm(confirmMsg)) return;
        BridgeAPI.deletePlugin(envName, nodeName).then(function() {
            App.showToast(t('plugin_deleted_success', nodeName), 'info');
            showRestartHint();
            loadPlugins();
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function doUpdatePlugin(envName, nodeName) {
        var statusEl = document.getElementById('plug-status');
        statusEl.textContent = t('plugin_update') + ': ' + nodeName + '...';
        BridgeAPI.updatePlugin(envName, nodeName, function(msg) {
            statusEl.textContent = msg;
        }).then(function(result) {
            if (result && result.updated) { App.showToast(t('plugin_updated_success', nodeName), 'success'); showRestartHint(); }
            else { App.showToast(t('plugin_already_latest', nodeName), 'info'); }
            loadPlugins();
            statusEl.textContent = '';
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
            statusEl.textContent = '';
        });
    }

    function doUpdateAll() {
        var envName = document.getElementById('plug-env').value;
        if (!envName) return;
        var statusEl = document.getElementById('plug-status');
        var btn = document.getElementById('plug-btn-update-all');
        btn.disabled = true;
        statusEl.textContent = t('plugin_update_all') + '...';
        BridgeAPI.updateAllPlugins(envName, function(msg) { statusEl.textContent = msg; }).then(function(result) {
            if (!result || result.total === 0) App.showToast(t('plugin_update_all_no_targets'), 'info');
            else {
                App.showToast(t('plugin_update_all_result', result.updated, result.skipped, result.failed),
                    result.failed > 0 ? 'warning' : 'success');
                if (result.updated > 0) showRestartHint();
            }
            loadPlugins();
            statusEl.textContent = '';
            btn.disabled = false;
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
            statusEl.textContent = '';
            btn.disabled = false;
        });
    }

    function showRestartHint() {
        var hint = document.getElementById('plug-restart-hint');
        hint.textContent = t('plugin_restart_hint');
        hint.style.display = '';
    }

    function isGitUrl(url) { return url.startsWith('http') || url.startsWith('git@'); }

    function doAnalyze() {
        var envName = document.getElementById('plug-env').value;
        var pluginPath = document.getElementById('plug-path').value.trim();
        if (!envName || !pluginPath) { App.showToast(t('plugin_select_env_and_path'), 'info'); return; }
        var statusEl = document.getElementById('plug-status');
        statusEl.textContent = t('plugin_analyzing');
        document.getElementById('plug-btn-analyze').disabled = true;
        document.getElementById('plug-btn-install').disabled = true;
        document.getElementById('plug-results').style.display = 'none';
        _lastRiskLevel = null;
        BridgeAPI.analyzePlugin(envName, pluginPath).then(function(report) {
            renderReport(report);
            statusEl.textContent = t('plugin_analysis_complete');
            document.getElementById('plug-btn-analyze').disabled = false;
            _lastRiskLevel = report.risk_level;
            if (isGitUrl(pluginPath)) document.getElementById('plug-btn-install').disabled = false;
        }).catch(function(e) {
            statusEl.textContent = t('error') + ': ' + e;
            document.getElementById('plug-btn-analyze').disabled = false;
            App.showToast(e.toString(), 'error');
        });
    }

    function doInstall() {
        var envName = document.getElementById('plug-env').value;
        var gitUrl = document.getElementById('plug-path').value.trim();
        var statusEl = document.getElementById('plug-status');
        var installBtn = document.getElementById('plug-btn-install');
        if (_lastRiskLevel === 'HIGH' || _lastRiskLevel === 'CRITICAL') {
            if (!confirm(t('plugin_confirm_high_risk', _lastRiskLevel))) return;
        }
        installBtn.disabled = true;
        statusEl.textContent = t('plugin_cloning');
        BridgeAPI.installPlugin(envName, gitUrl, function(msg) { statusEl.textContent = msg; }).then(function() {
            App.showToast(t('plugin_install_done'), 'success');
            showRestartHint();
            loadPlugins();
            statusEl.textContent = '';
            setInstallCardOpen(false);
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
            installBtn.disabled = false;
        });
    }

    function renderReport(report) {
        document.getElementById('plug-results').style.display = '';
        var banner = document.getElementById('plug-risk-banner');
        var riskColors = {
            GREEN:   { bg: 'oklch(0.82 0.17 128 / 0.12)', border: 'var(--accent-dim)', color: 'var(--accent)', icon: 'check_circle' },
            YELLOW:  { bg: 'oklch(0.82 0.14 75 / 0.12)',  border: 'var(--warn)',       color: 'var(--warn)',   icon: 'warning' },
            HIGH:    { bg: 'oklch(0.78 0.16 55 / 0.12)',  border: 'var(--warn)',       color: 'var(--warn)',   icon: 'error' },
            CRITICAL:{ bg: 'oklch(0.70 0.18 25 / 0.12)',  border: 'var(--danger)',     color: 'var(--danger)', icon: 'dangerous' },
        };
        var rc = riskColors[report.risk_level] || riskColors.GREEN;
        banner.style.background = rc.bg;
        banner.style.borderColor = rc.border;
        banner.innerHTML =
            '<span class="material-symbols-outlined" style="font-size:20px;color:' + rc.color + '">' + rc.icon + '</span>' +
            '<div>' +
                '<div style="font-family:var(--font-mono);font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:' + rc.color + '">' +
                    h(t('plugin_risk_level')) + ': ' + h(report.risk_level) +
                '</div>' +
                '<div style="font-size:13px;color:var(--text-1);margin-top:2px">' + h(report.plugin_name || '') + '</div>' +
            '</div>';

        document.getElementById('plug-summary').textContent = report.summary || '';

        var recs = document.getElementById('plug-recommendations');
        recs.innerHTML = '';
        if (report.recommendations && report.recommendations.length) {
            report.recommendations.forEach(function(r) {
                var div = document.createElement('div');
                div.style.cssText = 'display:flex;align-items:flex-start;gap:6px;font-size:13px;color:var(--text-2)';
                div.innerHTML = '<span class="material-symbols-outlined" style="font-size:14px;color:var(--accent);margin-top:1px">arrow_right</span><span>' + h(r) + '</span>';
                recs.appendChild(div);
            });
        }

        var cwrap = document.getElementById('plug-conflicts-wrap');
        if (report.conflicts && report.conflicts.length) {
            var rowsHtml = '<div class="ti-plugin-list" style="margin-top:8px">' +
                '<div class="ti-plugin-list-head" style="grid-template-columns: minmax(180px, 1.4fr) 100px 100px 110px 110px">' +
                    '<span>' + h(t('plugin_col_package')) + '</span>' +
                    '<span>' + h(t('plugin_col_current')) + '</span>' +
                    '<span>' + h(t('plugin_col_new')) + '</span>' +
                    '<span>' + h(t('plugin_col_type')) + '</span>' +
                    '<span style="text-align:right">' + h(t('plugin_col_risk')) + '</span>' +
                '</div>';
            report.conflicts.forEach(function(c) {
                rowsHtml += '<div class="ti-plugin-row" style="grid-template-columns: minmax(180px, 1.4fr) 100px 100px 110px 110px">' +
                    '<div class="ti-plugin-name ' + (c.is_critical ? '' : '') + '" style="' + (c.is_critical ? 'color:var(--accent)' : '') + '">' + h(c.package) + '</div>' +
                    '<div class="ti-plugin-version">' + h(c.current_version || '—') + '</div>' +
                    '<div class="ti-plugin-version">' + h(c.required_version || '—') + '</div>' +
                    '<div><span class="chip">' + h(c.change_type || '') + '</span></div>' +
                    '<div style="text-align:right"><span class="chip" style="color:' + (riskColors[c.risk_level] || riskColors.GREEN).color + '">' + h(c.risk_level || '') + '</span></div>' +
                '</div>';
            });
            rowsHtml += '</div>';
            cwrap.innerHTML = rowsHtml;
        } else {
            cwrap.innerHTML = '<div class="ti-list-empty" style="padding:20px"><span class="material-symbols-outlined">check_circle</span><div>No conflicts detected</div></div>';
        }
    }

    function h(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    App.registerPage('plugins', { render: render });
})();
