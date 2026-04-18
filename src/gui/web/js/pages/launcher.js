/**
 * launcher.js — ComfyUI launcher page with tab switching
 * Tabs: Launcher (start/stop single env) | Running List (all running instances)
 */
(function() {

    let pollTimer = null;
    let selectedEnv = null;  // persist selected environment across tab switches
    let activeTab = 'launcher'; // 'launcher' or 'running'
    let currentLaunchSettings = null;
    let saveDebounceTimer = null;

    function render(container) {
        // Determine default tab based on running instances
        BridgeAPI.listRunning().then(function(list) {
            activeTab = (list && list.length > 0) ? 'running' : 'launcher';
            renderPage(container);
        }).catch(function() {
            activeTab = 'launcher';
            renderPage(container);
        });
    }

    function renderPage(container) {
        container.innerHTML = `
            <div class="ti-content fade-in">
                <!-- Page head -->
                <div class="ti-page-head">
                    <div>
                        <p class="ti-page-sub" id="launcher-sub">—</p>
                    </div>
                    <div class="ti-page-actions">
                        <div class="ti-env-select">
                            <label>${t('launch_environment')}</label>
                            <select id="launch-env"></select>
                        </div>
                        <div class="ti-launcher-tabs" id="launcher-tabs">
                            <button class="ti-launcher-tab ${activeTab === 'launcher' ? 'active' : ''}" data-tab="launcher">
                                <span class="material-symbols-outlined" style="font-size:13px">play_arrow</span>
                                <span>${t('launch_tab_launcher')}</span>
                            </button>
                            <button class="ti-launcher-tab ${activeTab === 'running' ? 'active' : ''}" data-tab="running">
                                <span class="material-symbols-outlined" style="font-size:13px">monitor_heart</span>
                                <span>${t('launch_tab_running')}</span>
                                <span class="tab-badge" id="running-count" style="display:none"></span>
                            </button>
                        </div>
                        <button id="launch-btn-refresh" class="btn btn-secondary" title="${t('launch_refresh')}">
                            <span class="material-symbols-outlined" style="font-size:14px">refresh</span>
                        </button>
                    </div>
                </div>

                <!-- Tab: Launcher — 2 column grid (left=params, right=launch state + logs) -->
                <div id="tab-launcher" style="display: ${activeTab === 'launcher' ? 'grid' : 'none'}; grid-template-columns: 1fr 360px; gap: 16px; align-items: start;">

                    <!-- ═══ LEFT: Launch params + Advanced + Diagnostics ═══ -->
                    <div style="min-width:0; display:flex; flex-direction:column; gap:16px">

                        <!-- Primary launch params card -->
                        <div class="ti-card">
                            <div class="ti-card-head">
                                <span class="material-symbols-outlined">terminal</span>
                                <span class="ti-card-title">${t('launch_params') || '啟動參數'}</span>
                                <span class="mono" id="launcher-env-tag" style="margin-left:auto;font-size:11px;color:var(--text-3)"></span>
                            </div>
                            <div class="ti-card-body">
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
                                    <div class="ti-field">
                                        <label>${t('launch_port')}</label>
                                        <input type="number" id="launch-port" class="mono" value="8188" min="1024" max="65535" style="width:100%">
                                    </div>
                                    <div class="ti-field">
                                        <label>${t('launch_listen_ip') || '監聽位址'}</label>
                                        <input type="text" id="ls-listen" class="ls-control mono" placeholder="0.0.0.0" style="width:100%" disabled>
                                        <div class="input-error" id="ls-listen-error" style="display:none;color:var(--danger);font-size:11px"></div>
                                    </div>
                                    <div class="ti-field">
                                        <label>${t('launch_vram_mode')}</label>
                                        <select id="ls-vram-mode" class="ls-control select" style="width:100%">
                                            <option value="gpu_only">${t('launch_vram_gpu_only')}</option>
                                            <option value="high">${t('launch_vram_high')}</option>
                                            <option value="normal">${t('launch_vram_normal')}</option>
                                            <option value="low">${t('launch_vram_low')}</option>
                                            <option value="no">${t('launch_vram_no')}</option>
                                            <option value="cpu">${t('launch_vram_cpu')}</option>
                                        </select>
                                    </div>
                                    <div class="ti-field">
                                        <label>${t('launch_cross_attention') || '精度'}</label>
                                        <select id="ls-cross-attention" class="ls-control select" style="width:100%">
                                            <option value="auto">${t('launch_cross_attn_auto')}</option>
                                            <option value="pytorch">${t('launch_cross_attn_pytorch')}</option>
                                            <option value="split">${t('launch_cross_attn_split')}</option>
                                            <option value="quad">${t('launch_cross_attn_quad')}</option>
                                            <option value="sage">${t('launch_cross_attn_sage')}</option>
                                            <option value="flash">${t('launch_cross_attn_flash')}</option>
                                            <option value="disable_xformers">${t('launch_cross_attn_disable_xformers')}</option>
                                        </select>
                                    </div>
                                </div>
                                <div id="ti-cmd-preview" style="margin-top:14px;padding:12px 14px;background:var(--bg-0);border:1px solid var(--border-1);border-radius:var(--radius-sm);font-family:var(--font-mono);font-size:11px;color:var(--text-2);line-height:1.6;overflow-x:auto;white-space:nowrap">
                                    <span style="color:var(--text-4)">$</span> python main.py <span style="color:var(--accent)">--port 8188 --auto-launch</span>
                                </div>
                            </div>
                        </div>

                        <!-- Advanced settings + diagnostics now live under Settings page -->
                    </div><!-- /LEFT column -->

                    <!-- ═══ RIGHT: Launch state + Logs ═══ -->
                    <div style="display:flex;flex-direction:column;gap:12px">
                        <div class="ti-card">
                            <div class="ti-card-body" style="padding:18px;display:flex;flex-direction:column;gap:12px">
                                <div class="ti-launch-state" id="launch-state-pill">
                                    <span class="led"></span>
                                    <span id="launch-status">${t('launch_status_stopped')}</span>
                                    <span class="port" id="launch-state-port" style="display:none"></span>
                                </div>
                                <button id="launch-btn-start" class="ti-launch-btn go">
                                    <span class="material-symbols-outlined" style="font-size:20px">play_arrow</span>
                                    <span>${t('launch_start')}</span>
                                </button>
                                <button id="launch-btn-stop" class="ti-launch-btn stop" style="display:none">
                                    <span class="material-symbols-outlined" style="font-size:16px">stop</span>
                                    <span>${t('launch_stop')}</span>
                                </button>
                                <div class="ti-launch-url" id="launch-url-row" style="display:none">
                                    <span class="label">URL</span>
                                    <span class="val" id="launch-url-val">—</span>
                                </div>
                            </div>
                        </div>

                        <div class="ti-log-panel">
                            <div class="ti-log-head">
                                <span>comfyui.log</span>
                                <span style="color:var(--text-4);margin-left:6px">·</span>
                                <span id="launch-log-live" style="color:var(--text-3);font-size:10px">idle</span>
                                <button id="launch-btn-export-log" class="btn btn-ghost btn-sm" style="margin-left:auto">
                                    <span class="material-symbols-outlined" style="font-size:13px">download</span>
                                </button>
                            </div>
                            <div id="launch-log" class="ti-log-body" style="max-height:340px"></div>
                        </div>
                    </div>
                </div>

                <!-- Tab: Running List -->
                <div id="tab-running" style="display: ${activeTab === 'running' ? 'block' : 'none'}">
                    <div class="card">
                        <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">
                            <span>${t('launch_tab_running')}</span>
                            <button id="running-btn-refresh" class="btn btn-icon" title="${t('launch_refresh')}">
                                <span class="material-symbols-outlined">refresh</span>
                            </button>
                        </div>
                        <div id="running-list-content"></div>
                    </div>
                </div>
            </div>
        `;

        // Tab switching — supports both legacy .tab-item and industrial .ti-launcher-tab
        document.querySelectorAll('#launcher-tabs .tab-item, #launcher-tabs .ti-launcher-tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                switchTab(this.dataset.tab);
            });
        });

        // Launcher tab events
        document.getElementById('launch-btn-start').addEventListener('click', doStart);
        document.getElementById('launch-btn-stop').addEventListener('click', doStop);
        document.getElementById('launch-btn-refresh').addEventListener('click', loadEnvs);
        document.getElementById('launch-btn-export-log').addEventListener('click', doExportLog);

        document.getElementById('launch-env').addEventListener('change', function() {
            selectedEnv = this.value;
            pollStatus();
            loadLaunchSettings(this.value);
        });

        // Running list refresh
        document.getElementById('running-btn-refresh').addEventListener('click', loadRunningList);

        // Launcher params change listeners (Port / VRAM / Cross-attention).
        // The legacy .ls-control matches LAN listen input too, but that stays
        // read-only on this page — users edit it from Settings now.
        document.querySelectorAll('#tab-launcher .ls-control').forEach(function(el) {
            var evtType = (el.tagName === 'SELECT' || el.type === 'checkbox') ? 'change' : 'input';
            el.addEventListener(evtType, onSettingChanged);
        });
        // Port input lives outside the advanced controls list
        var portEl = document.getElementById('launch-port');
        if (portEl) portEl.addEventListener('input', onSettingChanged);

        // Load data
        loadEnvs().then(function() {
            pollStatus();
            if (selectedEnv) loadLaunchSettings(selectedEnv);
        });
        loadRunningList();

        // Start background polling
        startPolling();
    }

    function switchTab(tabName) {
        activeTab = tabName;
        // Update tab buttons — support both legacy .tab-item and industrial .ti-launcher-tab
        document.querySelectorAll('#launcher-tabs .tab-item, #launcher-tabs .ti-launcher-tab').forEach(function(tab) {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        // Show/hide tab content. tab-launcher uses a 2-col grid in the industrial
        // redesign, so pick the right display mode.
        document.getElementById('tab-launcher').style.display = tabName === 'launcher' ? 'grid' : 'none';
        document.getElementById('tab-running').style.display = tabName === 'running' ? 'block' : 'none';

        // Refresh running list when switching to it
        if (tabName === 'running') {
            loadRunningList();
        }
    }

    function loadRunningList() {
        var content = document.getElementById('running-list-content');
        if (!content) return;

        BridgeAPI.listRunning().then(function(list) {
            // Update badge count
            var badge = document.getElementById('running-count');
            if (badge) {
                if (list && list.length > 0) {
                    badge.textContent = list.length;
                    badge.style.display = 'inline-flex';
                } else {
                    badge.style.display = 'none';
                }
            }

            if (!list || list.length === 0) {
                content.innerHTML = `
                    <div class="flex flex-col items-center justify-center py-12 text-center">
                        <span class="material-symbols-outlined text-[48px] text-on-surface-variant mb-3" style="color:rgb(var(--color-outline))">deployed_code</span>
                        <p style="color:#6b6b6b;font-size:13px">${t('launch_running_empty')}</p>
                    </div>
                `;
                return;
            }

            var html = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>${t('launch_running_env')}</th>
                            <th>${t('launch_running_port')}</th>
                            <th>${t('launch_running_pid')}</th>
                            <th>${t('launch_running_version')}</th>
                            <th>${t('launch_running_actions')}</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            list.forEach(function(inst) {
                var version = '';
                if (inst.branch) {
                    version = inst.branch;
                    if (inst.commit) {
                        version += ' / ' + inst.commit.substring(0, 7);
                    }
                }

                html += `
                    <tr data-env="${inst.env_name}">
                        <td style="font-weight:500">${inst.env_name}</td>
                        <td>
                            <a href="#" class="running-open-port" data-port="${inst.port}"
                               style="color:rgb(var(--color-primary));text-decoration:none;border-bottom:1px dashed rgb(var(--color-primary))">
                                ${inst.port}
                            </a>
                        </td>
                        <td style="color:rgb(var(--color-on-surface-variant));font-family:monospace;font-size:12px">${inst.pid}</td>
                        <td style="color:rgb(var(--color-on-surface-variant));font-size:12px">${version || '-'}</td>
                        <td>
                            <div style="display:flex;gap:8px">
                                <button class="btn btn-secondary running-btn-open" data-port="${inst.port}"
                                    style="padding:6px 12px;font-size:10px">
                                    <span class="material-symbols-outlined text-[14px]">open_in_browser</span>
                                    ${t('launch_running_open')}
                                </button>
                                <button class="btn btn-danger running-btn-stop" data-env="${inst.env_name}"
                                    style="padding:6px 12px;font-size:10px">
                                    <span class="material-symbols-outlined text-[14px]">stop</span>
                                    ${t('launch_running_stop')}
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table>';
            content.innerHTML = html;
            App.applyFallbackIcons();

            // Bind open browser buttons (port links + buttons)
            content.querySelectorAll('.running-open-port, .running-btn-open').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    var port = parseInt(this.dataset.port);
                    BridgeAPI.openBrowser(port);
                });
            });

            // Bind stop buttons
            content.querySelectorAll('.running-btn-stop').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    var envName = this.dataset.env;
                    this.disabled = true;
                    this.textContent = t('launch_running_stopping');
                    BridgeAPI.stopComfyUI(envName).then(function() {
                        App.showToast(t('launch_running_stopped_ok'), 'success');
                        loadRunningList();
                        // Also refresh launcher tab status if same env
                        pollStatus();
                    }).catch(function(e) {
                        App.showToast(String(e), 'error');
                        loadRunningList();
                    });
                });
            });
        }).catch(function(e) {
            content.innerHTML = '<p style="color:rgb(var(--color-error));padding:12px">' + String(e) + '</p>';
        });
    }

    function loadEnvs() {
        return BridgeAPI.listEnvironments().then(function(envs) {
            const select = document.getElementById('launch-env');
            if (!select) return;
            select.innerHTML = '';
            envs.forEach(env => {
                const opt = document.createElement('option');
                opt.value = env.name;
                opt.textContent = env.name;
                select.appendChild(opt);
            });
            // Restore remembered selection (persists across tab switches)
            if (selectedEnv) {
                select.value = selectedEnv;
            }
            // Load launch settings for the selected env
            var envName = select.value;
            if (envName) {
                selectedEnv = envName;
                loadLaunchSettings(envName);
            }
        }).catch(function(e) {
            appendLog(`${t('error')}: ${e}`);
        });
    }

    function doStart() {
        if (!_syncListenControls()) {
            return;  // Loopback IP with LAN enabled — don't start
        }
        const envSelect = document.getElementById('launch-env');
        const portInput = document.getElementById('launch-port');
        if (!envSelect || !envSelect.value) { App.showToast(t('launch_select_env'), 'info'); return; }

        const envName = envSelect.value;
        const port = parseInt(portInput.value) || 8188;

        // Flush any pending debounced settings save so the backend reads the
        // latest listen_enabled/listen values. Without this, toggling LAN and
        // immediately clicking Start races the 500ms debounce.
        if (saveDebounceTimer) {
            clearTimeout(saveDebounceTimer);
            saveDebounceTimer = null;
            if (selectedEnv && currentLaunchSettings) {
                BridgeAPI.saveLaunchSettings(selectedEnv, currentLaunchSettings).then(function() {
                    _doStartAfterFlush(envName, port);
                }).catch(function(e) {
                    App.showToast(String(e), 'error');
                });
                return;
            }
        }
        _doStartAfterFlush(envName, port);
    }

    function _doStartAfterFlush(envName, port) {
        // auto_diagnostics now lives on the Settings page — re-read settings
        // from backend so we always see the user's latest toggle, even if they
        // flipped it in Settings just before clicking start.
        BridgeAPI.getLaunchSettings(envName).then(function(settings) {
            currentLaunchSettings = settings || {};
            if (!settings || !settings.auto_diagnostics) {
                doStartActual(envName, port);
                return;
            }

            document.getElementById('launch-btn-start').disabled = true;
            appendLog(t('launch_diagnostics') + '...');

            Promise.all([
                BridgeAPI.checkDependencies(envName).catch(function(e) { return { status: 'error', error: String(e) }; }),
                BridgeAPI.checkConflicts(envName).catch(function(e) { return { status: 'error', error: String(e) }; }),
                BridgeAPI.checkDuplicateNodes(envName).catch(function(e) { return { status: 'error', error: String(e) }; })
            ]).then(function(results) {
                var issues = [];
                var depItems = (results[0] && Array.isArray(results[0].items)) ? results[0].items : [];
                var missingDepItems = depItems.filter(function(item) {
                    return item && item.status === 'missing';
                });
                var depCheckIssues = depItems.filter(function(item) {
                    return item && item.status === 'pip_check_issue';
                });

                if (missingDepItems.length > 0 || depCheckIssues.length > 0) {
                    var depIssueCount = missingDepItems.length + depCheckIssues.length;
                    issues.push(t('launch_diag_check_deps') + ': ' + t('launch_diag_issue_count', depIssueCount));
                }
                if (results[1] && results[1].conflicts && results[1].conflicts.length > 0) {
                    issues.push(t('launch_diag_check_conflicts') + ': ' + t('launch_diag_found_count', results[1].conflicts.length));
                }
                if (results[2] && results[2].duplicates && results[2].duplicates.length > 0) {
                    issues.push(t('launch_diag_check_duplicates') + ': ' + t('launch_diag_found_count', results[2].duplicates.length));
                }

                if (issues.length > 0) {
                    var issueHtml = '<div style="margin-bottom:12px">' + issues.map(function(i) {
                        return '<div style="padding:4px 0;color:#ffb74d">&#9888; ' + i + '</div>';
                    }).join('') + '</div>';

                    App.showModal(
                        t('launch_diagnostics'),
                        issueHtml,
                        [
                            {
                                text: t('launch_diag_launch_anyway'),
                                class: 'btn btn-primary',
                                onClick: function() { doStartActual(envName, port); }
                            },
                            {
                                text: t('cancel'),
                                class: 'btn btn-secondary',
                                onClick: function() { document.getElementById('launch-btn-start').disabled = false; }
                            }
                        ]
                    );
                } else {
                    doStartActual(envName, port);
                }
            });
        }).catch(function() {
            // If we can't read settings, fall back to launching directly.
            doStartActual(envName, port);
        });
    }

    function doStartActual(envName, port) {
        appendLog(`${t('launch_starting')} (${envName}:${port})`);
        document.getElementById('launch-btn-start').disabled = true;

        BridgeAPI.startComfyUI(envName, port).then(function(info) {
            appendLog(t('launch_started', info.pid, info.port));
            // Notify if port was auto-changed due to conflict
            if (info.port !== port) {
                App.showToast(t('launch_port_conflict', port, info.port), 'info');
                appendLog(t('launch_port_conflict', port, info.port));
            }
            // Show "starting" state — polling will update to "running" once healthy
            var statusEl = document.getElementById('launch-status');
            statusEl.className = 'badge badge-warning';
            statusEl.textContent = t('launch_status_starting', info.pid);
            document.getElementById('launch-btn-start').disabled = true;
            document.getElementById('launch-btn-stop').disabled = false;
            App.showToast(t('launch_started', info.pid, info.port), 'success');
            if (info && info.lan_url) {
                var lanMsg = t('launch_listen_toast_lan_url').replace('{url}', info.lan_url);
                App.showToast(lanMsg, 'info', 10000);
            }
            // Refresh running list
            loadRunningList();
        }).catch(function(e) {
            appendLog(`${t('error')}: ${e}`);
            document.getElementById('launch-btn-start').disabled = false;
            App.showToast(e.toString(), 'error');
        });
    }

    function doStop() {
        const envSelect = document.getElementById('launch-env');
        if (!envSelect || !envSelect.value) return;
        const envName = envSelect.value;

        appendLog(t('launch_stopping'));
        document.getElementById('launch-btn-stop').disabled = true;

        BridgeAPI.stopComfyUI(envName).then(function() {
            appendLog(t('launch_stopped'));
            updateStatus('stopped');
            App.showToast(t('launch_stopped'), 'success');
            // Refresh running list
            loadRunningList();
        }).catch(function(e) {
            appendLog(`${t('error')}: ${e}`);
            document.getElementById('launch-btn-stop').disabled = false;
        });
    }

    function updateStatus(state, pid, port) {
        const statusEl = document.getElementById('launch-status');
        const startBtn = document.getElementById('launch-btn-start');
        const stopBtn = document.getElementById('launch-btn-stop');
        const statePill = document.getElementById('launch-state-pill');
        const statePort = document.getElementById('launch-state-port');
        const urlRow = document.getElementById('launch-url-row');
        const urlVal = document.getElementById('launch-url-val');
        const liveTag = document.getElementById('launch-log-live');
        if (!statusEl) return;

        // Update state pill class — reuses design's .ti-launch-state with LED
        if (statePill) {
            statePill.classList.remove('stopped', 'starting', 'running');
            statePill.classList.add(state === 'running' ? 'running' : state === 'starting' ? 'starting' : 'stopped');
        }

        if (state === 'running') {
            statusEl.textContent = t('launch_state_running') || '運行中';
            if (statePort) { statePort.textContent = ':' + (port || ''); statePort.style.display = ''; }
            if (startBtn) { startBtn.style.display = 'none'; startBtn.disabled = true; }
            if (stopBtn)  { stopBtn.style.display = ''; stopBtn.disabled = false; }
            if (urlRow)   { urlRow.style.display = ''; }
            if (urlVal)   { urlVal.textContent = '127.0.0.1:' + (port || ''); }
            if (liveTag)  { liveTag.textContent = '● live'; liveTag.style.color = 'var(--accent)'; }
        } else if (state === 'starting') {
            statusEl.textContent = t('launch_state_starting') || '啟動中';
            if (statePort) statePort.style.display = 'none';
            // Swap to a "starting" look: dim-sweep animation via .starting class
            if (startBtn) {
                startBtn.style.display = '';
                startBtn.disabled = true;
                startBtn.classList.remove('go');
                startBtn.classList.add('starting');
                startBtn.innerHTML = '<span>' + (t('home_launch_starting') || '啟動中...') + '</span>';
            }
            if (stopBtn) stopBtn.style.display = 'none';
            if (urlRow)  urlRow.style.display = 'none';
            if (liveTag) { liveTag.textContent = '● starting'; liveTag.style.color = 'var(--warn)'; }
        } else {
            // stopped
            statusEl.textContent = t('launch_state_stopped') || '已停止';
            if (statePort) statePort.style.display = 'none';
            if (startBtn) {
                startBtn.style.display = '';
                startBtn.disabled = false;
                startBtn.classList.remove('starting');
                startBtn.classList.add('go');
                startBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:20px">play_arrow</span><span>' + (t('launch_start') || '啟動') + '</span>';
            }
            if (stopBtn) stopBtn.style.display = 'none';
            if (urlRow)  urlRow.style.display = 'none';
            if (liveTag) { liveTag.textContent = 'idle'; liveTag.style.color = 'var(--text-3)'; }
        }
    }

    function pollStatus() {
        const envSelect = document.getElementById('launch-env');
        if (!envSelect || !envSelect.value) return;
        BridgeAPI.getLaunchStatus(envSelect.value).then(function(status) {
            updateStatus(status.status, status.pid, status.port);
            // Show ComfyUI log if available
            if (status.last_log) {
                var log = document.getElementById('launch-log');
                if (log && log.dataset.lastLog !== status.last_log) {
                    log.dataset.lastLog = status.last_log;
                    log.textContent = status.last_log;
                    log.scrollTop = log.scrollHeight;
                }
            }
        }).catch(function(e) {
            // Silently ignore poll errors
        });

        // Also refresh running list badge count
        BridgeAPI.listRunning().then(function(list) {
            var badge = document.getElementById('running-count');
            if (badge) {
                if (list && list.length > 0) {
                    badge.textContent = list.length;
                    badge.style.display = 'inline-flex';
                } else {
                    badge.style.display = 'none';
                }
            }
            // If running tab is active, refresh the list too
            if (activeTab === 'running') {
                loadRunningList();
            }
        }).catch(function() {});
    }

    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(pollStatus, 5000);
    }

    function doExportLog() {
        const envSelect = document.getElementById('launch-env');
        if (!envSelect || !envSelect.value) {
            App.showToast(t('launch_select_env'), 'info');
            return;
        }
        BridgeAPI.exportLog(envSelect.value).then(function(result) {
            if (result.cancelled) {
                App.showToast(t('launch_export_cancelled'), 'info');
            } else {
                App.showToast(t('launch_export_success'), 'success');
            }
        }).catch(function(e) {
            if (String(e).indexOf('no_log') !== -1) {
                App.showToast(t('launch_export_no_log'), 'info');
            } else {
                App.showToast(String(e), 'error');
            }
        });
    }

    function appendLog(msg) {
        const log = document.getElementById('launch-log');
        if (!log) return;
        const timestamp = new Date().toLocaleTimeString();
        log.textContent += `[${timestamp}] ${msg}\n`;
        log.scrollTop = log.scrollHeight;
    }

    function loadLaunchSettings(envName) {
        if (!envName) return;
        BridgeAPI.getLaunchSettings(envName).then(function(settings) {
            currentLaunchSettings = settings || {};
            // Populate only the controls that live on the launcher page.
            // Advanced fields (reserve_vram, async_offload, smart_memory,
            // listen_enabled, CORS/TLS, custom_args, auto_diagnostics) are
            // owned by the Settings page now.
            var el;
            el = document.getElementById('ls-cross-attention');
            if (el) el.value = settings.cross_attention || 'auto';
            el = document.getElementById('ls-vram-mode');
            if (el) el.value = settings.vram_mode || 'normal';
            el = document.getElementById('ls-listen');
            if (el) {
                el.value = settings.listen || '';
                // Read-only on launcher — LAN listen config lives in Settings.
                el.disabled = true;
            }
            // Update the top port input from launch_settings
            el = document.getElementById('launch-port');
            if (el && settings.port) el.value = settings.port;
        }).catch(function(e) {
            currentLaunchSettings = {};
        });
    }

    function _syncListenControls() {
        // Listen-enable checkbox lives in Settings page now. Just keep the
        // read-only listen input disabled so users edit it from Settings.
        var ipEl = document.getElementById('ls-listen');
        if (ipEl) ipEl.disabled = true;
        return true;
    }

    function onSettingChanged() {
        // Merge just the launcher-owned fields into currentLaunchSettings so
        // we don't clobber advanced settings saved from the Settings page.
        var patch = {};
        var el;
        el = document.getElementById('ls-cross-attention');
        if (el) patch.cross_attention = el.value;
        el = document.getElementById('ls-vram-mode');
        if (el) patch.vram_mode = el.value;
        el = document.getElementById('launch-port');
        if (el) patch.port = el.value ? parseInt(el.value) : 8188;

        currentLaunchSettings = Object.assign({}, currentLaunchSettings || {}, patch);
        debounceSave();
    }

    function debounceSave() {
        if (saveDebounceTimer) clearTimeout(saveDebounceTimer);
        saveDebounceTimer = setTimeout(function() {
            if (!selectedEnv || !currentLaunchSettings) return;
            BridgeAPI.saveLaunchSettings(selectedEnv, currentLaunchSettings).catch(function(e) {
                App.showToast(String(e), 'error');
            });
        }, 500);
    }

    App.registerPage('launcher', { render });

})();
