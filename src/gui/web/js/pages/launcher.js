/**
 * launcher.js — ComfyUI launcher page with tab switching
 * Tabs: Launcher (start/stop single env) | Running List (all running instances)
 */
(function() {

    let pollTimer = null;
    let selectedEnv = null;  // persist selected environment across tab switches
    let activeTab = 'launcher'; // 'launcher' or 'running'

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
            <div class="fade-in space-y-6">
                <!-- Tab Bar -->
                <div class="tab-bar" id="launcher-tabs">
                    <button class="tab-item ${activeTab === 'launcher' ? 'active' : ''}" data-tab="launcher">
                        <span class="material-symbols-outlined text-[16px]">play_arrow</span>
                        ${t('launch_tab_launcher')}
                    </button>
                    <button class="tab-item ${activeTab === 'running' ? 'active' : ''}" data-tab="running">
                        <span class="material-symbols-outlined text-[16px]">monitor_heart</span>
                        ${t('launch_tab_running')}
                        <span class="tab-badge" id="running-count" style="display:none"></span>
                    </button>
                </div>

                <!-- Tab: Launcher -->
                <div id="tab-launcher" style="display: ${activeTab === 'launcher' ? 'block' : 'none'}">
                    <!-- Controls -->
                    <div class="card">
                        <div class="card-header">${t('launch_environment')}</div>
                        <div class="flex items-end gap-4 mt-3">
                            <div class="flex-1">
                                <label class="input-label">${t('launch_environment')}</label>
                                <select id="launch-env" class="select"></select>
                            </div>
                            <div class="w-32">
                                <label class="input-label">${t('launch_port')}</label>
                                <input type="number" id="launch-port" class="input" value="8188" min="1024" max="65535">
                            </div>
                            <button id="launch-btn-start" class="btn btn-primary">
                                <span class="material-symbols-outlined text-[18px]">play_arrow</span>
                                ${t('launch_start')}
                            </button>
                            <button id="launch-btn-stop" class="btn btn-danger" disabled>
                                <span class="material-symbols-outlined text-[18px]">stop</span>
                                ${t('launch_stop')}
                            </button>
                            <button id="launch-btn-refresh" class="btn btn-icon" title="${t('launch_refresh')}">
                                <span class="material-symbols-outlined">refresh</span>
                            </button>
                        </div>
                    </div>

                    <!-- Status -->
                    <div class="flex items-center gap-3 mt-6">
                        <span class="text-xs font-label uppercase tracking-wider text-on-surface-variant">${t('launch_status')}:</span>
                        <span id="launch-status" class="badge badge-primary">${t('launch_status_stopped')}</span>
                    </div>

                    <!-- Log output -->
                    <div class="mt-6">
                        <div class="text-xs font-label uppercase tracking-wider text-on-surface-variant mb-2">${t('launch_log')}</div>
                        <div id="launch-log" class="log-output h-80"></div>
                        <div class="mt-2 flex justify-end">
                            <button id="launch-btn-export-log" class="btn btn-secondary">
                                <span class="material-symbols-outlined text-[18px]">download</span>
                                ${t('launch_export_log')}
                            </button>
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

        // Tab switching
        document.querySelectorAll('#launcher-tabs .tab-item').forEach(function(tab) {
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
        });

        // Running list refresh
        document.getElementById('running-btn-refresh').addEventListener('click', loadRunningList);

        // Load data
        loadEnvs().then(pollStatus);
        loadRunningList();

        // Start background polling
        startPolling();
    }

    function switchTab(tabName) {
        activeTab = tabName;
        // Update tab buttons
        document.querySelectorAll('#launcher-tabs .tab-item').forEach(function(tab) {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        // Show/hide tab content
        document.getElementById('tab-launcher').style.display = tabName === 'launcher' ? 'block' : 'none';
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
                        <span class="material-symbols-outlined text-[48px] text-on-surface-variant mb-3" style="color:#484848">deployed_code</span>
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
                               style="color:#cc97ff;text-decoration:none;border-bottom:1px dashed #cc97ff">
                                ${inst.port}
                            </a>
                        </td>
                        <td style="color:#ababab;font-family:monospace;font-size:12px">${inst.pid}</td>
                        <td style="color:#ababab;font-size:12px">${version || '-'}</td>
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
            content.innerHTML = '<p style="color:#ff6e84;padding:12px">' + String(e) + '</p>';
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
        }).catch(function(e) {
            appendLog(`${t('error')}: ${e}`);
        });
    }

    function doStart() {
        const envSelect = document.getElementById('launch-env');
        const portInput = document.getElementById('launch-port');
        if (!envSelect || !envSelect.value) { App.showToast(t('launch_select_env'), 'info'); return; }

        const envName = envSelect.value;
        const port = parseInt(portInput.value) || 8188;

        console.log('Starting ComfyUI:', envName, port, typeof port);
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
            statusEl.textContent = 'STARTING... (PID: ' + info.pid + ')';
            document.getElementById('launch-btn-start').disabled = true;
            document.getElementById('launch-btn-stop').disabled = false;
            App.showToast(t('launch_started', info.pid, info.port), 'success');
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
        if (!statusEl) return;

        if (state === 'running') {
            statusEl.className = 'badge badge-success';
            statusEl.textContent = t('launch_status_running', pid, port);
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
        } else {
            statusEl.className = 'badge badge-primary';
            statusEl.textContent = t('launch_status_stopped');
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
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
                App.showToast(t('launch_export_no_log'), 'error');
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

    App.registerPage('launcher', { render });

})();
