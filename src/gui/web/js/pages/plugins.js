/**
 * plugins.js — Plugin management page (installed list + analyze + install)
 */
(function() {

    var lastRiskLevel = null;

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-6">

                <!-- Analyze + Install -->
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
                        <button id="plug-btn-analyze" class="btn btn-secondary">
                            <span class="material-symbols-outlined text-[16px]">search</span>
                            ${t('plugin_analyze')}
                        </button>
                        <button id="plug-btn-install" class="btn btn-primary" disabled>
                            <span class="material-symbols-outlined text-[16px]">download</span>
                            ${t('plugin_install')}
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

                <!-- Installed Plugins -->
                <div class="card">
                    <div class="card-header flex items-center justify-between">
                        <span>${t('plugin_installed_title')}</span>
                        <div class="flex items-center gap-2">
                            <button id="plug-btn-update-all" class="btn btn-primary btn-sm inline-flex items-center gap-1">
                                <span class="material-symbols-outlined text-[16px]">update</span>
                                ${t('plugin_update_all')}
                            </button>
                            <button id="plug-btn-refresh" class="btn btn-secondary btn-sm">
                                <span class="material-symbols-outlined text-[16px]">refresh</span>
                                ${t('env_refresh')}
                            </button>
                        </div>
                    </div>
                    <div class="mt-4 border border-surface-container">
                        <table class="data-table" style="table-layout:fixed;width:100%">
                            <colgroup>
                                <col>
                                <col style="width:100px">
                                <col style="width:320px">
                            </colgroup>
                            <thead>
                                <tr>
                                    <th>${t('plugin_col_name')}</th>
                                    <th style="text-align:center">${t('plugin_col_status')}</th>
                                    <th style="text-align:center">${t('plugin_col_actions')}</th>
                                </tr>
                            </thead>
                            <tbody id="plug-installed-body">
                                <tr><td colspan="3" class="text-center text-on-surface-variant py-4">${t('loading')}</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div id="plug-restart-hint" class="hidden mt-2 text-xs text-yellow-400"></div>
                </div>
            </div>
        `;

        document.getElementById('plug-btn-analyze').addEventListener('click', doAnalyze);
        document.getElementById('plug-btn-install').addEventListener('click', doInstall);
        document.getElementById('plug-btn-refresh').addEventListener('click', function() {
            loadPlugins();
        });
        document.getElementById('plug-btn-update-all').addEventListener('click', doUpdateAll);
        document.getElementById('plug-path').addEventListener('input', function() {
            document.getElementById('plug-btn-install').disabled = true;
            lastRiskLevel = null;
        });
        document.getElementById('plug-env').addEventListener('change', function() {
            loadPlugins();
        });

        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            var select = document.getElementById('plug-env');
            select.innerHTML = '';
            envs.forEach(function(env) {
                var opt = document.createElement('option');
                opt.value = env.name;
                opt.textContent = env.name;
                select.appendChild(opt);
            });
            loadPlugins();
        }).catch(function(e) { App.showToast(e.toString(), 'error'); });
    }

    function loadPlugins() {
        var envName = document.getElementById('plug-env').value;
        if (!envName) return;
        var tbody = document.getElementById('plug-installed-body');
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-on-surface-variant py-4">' + t('loading') + '</td></tr>';

        BridgeAPI.listPlugins(envName).then(function(plugins) {
            renderInstalledPlugins(plugins, envName);
        }).catch(function(e) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-on-surface-variant py-4">' + escapeHtml(e.toString()) + '</td></tr>';
        });
    }

    function renderInstalledPlugins(plugins, envName) {
        var tbody = document.getElementById('plug-installed-body');
        tbody.innerHTML = '';

        if (!plugins || plugins.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-on-surface-variant py-4">' + t('plugin_no_plugins') + '</td></tr>';
            return;
        }

        plugins.forEach(function(plugin) {
            var nodeName = plugin.name || plugin.node_name || '';
            var status = plugin.status || 'untracked';

            var badgeHtml;
            if (status === 'enabled') {
                badgeHtml = '<span class="badge badge-success">' + t('plugin_status_enabled') + '</span>';
            } else if (status === 'disabled') {
                badgeHtml = '<span class="badge badge-warning">' + t('plugin_status_disabled') + '</span>';
            } else {
                badgeHtml = '<span class="badge badge-primary">' + t('plugin_status_untracked') + '</span>';
            }

            var toggleLabel, toggleIcon;
            if (status === 'disabled') {
                toggleLabel = t('plugin_enable');
                toggleIcon = 'check_circle';
            } else {
                toggleLabel = t('plugin_disable');
                toggleIcon = 'block';
            }

            var canUpdate = status === 'enabled' && plugin.repo_url && plugin.has_update === true;
            var updateBtnHtml = canUpdate
                ? '<button class="btn btn-sm plug-update-btn" data-name="' + escapeHtml(nodeName) + '" title="' + t('plugin_update') + '" style="width:32px;padding:4px 6px;background:transparent;border:1px solid #4ade80;color:#4ade80"><span class="material-symbols-outlined text-[16px]">arrow_upward</span></button>'
                : '<span style="display:inline-block;width:32px"></span>';

            var tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(nodeName)}">${escapeHtml(nodeName)}</td>
                <td style="text-align:center">${badgeHtml}</td>
                <td class="whitespace-nowrap">
                    <div class="flex items-center justify-center gap-2">
                        ${updateBtnHtml}
                        <button class="btn btn-secondary btn-sm plug-toggle-btn inline-flex items-center gap-1" data-name="${escapeHtml(nodeName)}" data-status="${escapeHtml(status)}">
                            <span class="material-symbols-outlined text-[16px]">${toggleIcon}</span>
                            ${toggleLabel}
                        </button>
                        <button class="btn btn-danger btn-sm plug-delete-btn inline-flex items-center gap-1" data-name="${escapeHtml(nodeName)}">
                            <span class="material-symbols-outlined text-[16px]">delete</span>
                            ${t('plugin_delete')}
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.plug-toggle-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var name = btn.getAttribute('data-name');
                var status = btn.getAttribute('data-status');
                doTogglePlugin(envName, name, status);
            });
        });

        tbody.querySelectorAll('.plug-delete-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var name = btn.getAttribute('data-name');
                doDeletePlugin(envName, name);
            });
        });

        tbody.querySelectorAll('.plug-update-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var name = btn.getAttribute('data-name');
                doUpdatePlugin(envName, name);
            });
        });
    }

    function doTogglePlugin(envName, nodeName, currentStatus) {
        var isManager = nodeName === 'ComfyUI-Manager';
        var isDisabling = currentStatus !== 'disabled';

        if (isManager) {
            var confirmMsg = isDisabling
                ? t('plugin_confirm_manager_disable')
                : t('plugin_confirm_manager_disable');
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
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function doDeletePlugin(envName, nodeName) {
        var isManager = nodeName === 'ComfyUI-Manager';
        var confirmMsg = t('plugin_confirm_delete', nodeName);
        if (isManager) {
            confirmMsg += '\n\n' + t('plugin_confirm_manager_delete');
        }
        if (!confirm(confirmMsg)) return;

        BridgeAPI.deletePlugin(envName, nodeName).then(function() {
            App.showToast(t('plugin_deleted_success', nodeName), 'info');
            showRestartHint();
            loadPlugins();
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function doUpdatePlugin(envName, nodeName) {
        var statusEl = document.getElementById('plug-status');
        statusEl.textContent = t('plugin_update') + ': ' + nodeName + '...';

        BridgeAPI.updatePlugin(envName, nodeName, function(msg) {
            statusEl.textContent = msg;
        }).then(function(result) {
            if (result && result.updated) {
                App.showToast(t('plugin_updated_success', nodeName), 'success');
                showRestartHint();
            } else {
                App.showToast(t('plugin_already_latest', nodeName), 'info');
            }
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

        BridgeAPI.updateAllPlugins(envName, function(msg) {
            statusEl.textContent = msg;
        }).then(function(result) {
            if (!result || result.total === 0) {
                App.showToast(t('plugin_update_all_no_targets'), 'info');
            } else {
                App.showToast(
                    t('plugin_update_all_result', result.updated, result.skipped, result.failed),
                    result.failed > 0 ? 'warning' : 'success'
                );
                if (result.updated > 0) {
                    showRestartHint();
                }
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
        hint.classList.remove('hidden');
    }

    function isGitUrl(url) {
        return url.startsWith('http') || url.startsWith('git@');
    }

    function doAnalyze() {
        var envName = document.getElementById('plug-env').value;
        var pluginPath = document.getElementById('plug-path').value.trim();
        if (!envName || !pluginPath) {
            App.showToast(t('plugin_select_env_and_path'), 'info');
            return;
        }

        var statusEl = document.getElementById('plug-status');
        statusEl.textContent = t('plugin_analyzing');
        document.getElementById('plug-btn-analyze').disabled = true;
        document.getElementById('plug-btn-install').disabled = true;
        document.getElementById('plug-results').classList.add('hidden');
        lastRiskLevel = null;

        BridgeAPI.analyzePlugin(envName, pluginPath).then(function(report) {
            renderReport(report);
            statusEl.textContent = t('plugin_analysis_complete');
            document.getElementById('plug-btn-analyze').disabled = false;
            lastRiskLevel = report.risk_level;
            if (isGitUrl(pluginPath)) {
                document.getElementById('plug-btn-install').disabled = false;
            }
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

        if (lastRiskLevel === 'HIGH' || lastRiskLevel === 'CRITICAL') {
            if (!confirm(t('plugin_confirm_high_risk', lastRiskLevel))) return;
        }

        installBtn.disabled = true;
        statusEl.textContent = t('plugin_cloning');

        BridgeAPI.installPlugin(envName, gitUrl, function(msg) {
            statusEl.textContent = msg;
        }).then(function() {
            App.showToast(t('plugin_install_done'), 'success');
            showRestartHint();
            loadPlugins();
            statusEl.textContent = '';
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
            installBtn.disabled = false;
        });
    }

    function renderReport(report) {
        document.getElementById('plug-results').classList.remove('hidden');

        // Risk banner
        var banner = document.getElementById('plug-risk-banner');
        var riskColors = {
            GREEN: { border: 'border-green-500', bg: 'bg-green-500/10', text: 'text-green-400', icon: 'check_circle' },
            YELLOW: { border: 'border-yellow-500', bg: 'bg-yellow-500/10', text: 'text-yellow-400', icon: 'warning' },
            HIGH: { border: 'border-orange-500', bg: 'bg-orange-500/10', text: 'text-orange-400', icon: 'error' },
            CRITICAL: { border: 'border-red-500', bg: 'bg-red-500/10', text: 'text-red-400', icon: 'dangerous' },
        };
        var rc = riskColors[report.risk_level] || riskColors.GREEN;
        banner.className = 'card ' + rc.border + ' ' + rc.bg + ' border-l-4 p-4 flex items-center gap-3';
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
        var recsContainer = document.getElementById('plug-recommendations');
        recsContainer.innerHTML = '';
        if (report.recommendations && report.recommendations.length > 0) {
            report.recommendations.forEach(function(rec) {
                var div = document.createElement('div');
                div.className = 'flex items-start gap-2 text-sm text-on-surface-variant';
                div.innerHTML = '<span class="material-symbols-outlined text-[16px] text-primary mt-0.5">arrow_right</span><span>' + escapeHtml(rec) + '</span>';
                recsContainer.appendChild(div);
            });
        }

        // Conflicts table
        var tbody = document.getElementById('plug-conflicts-body');
        tbody.innerHTML = '';
        if (report.conflicts && report.conflicts.length > 0) {
            report.conflicts.forEach(function(conflict) {
                var riskBadgeClass = {
                    GREEN: 'badge-success',
                    YELLOW: 'badge-warning',
                    HIGH: 'badge-warning',
                    CRITICAL: 'badge-danger',
                }[conflict.risk_level] || 'badge-primary';

                var tr = document.createElement('tr');
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
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    App.registerPage('plugins', { render });
})();
