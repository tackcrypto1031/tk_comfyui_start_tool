/**
 * launcher.js — ComfyUI launcher page with tab switching
 * Tabs: Launcher (start/stop single env) | Running List (all running instances)
 */
(function() {

    let pollTimer = null;
    let selectedEnv = null;  // persist selected environment across tab switches
    let activeTab = 'launcher'; // 'launcher' or 'running'
    let currentLaunchSettings = null;
    let diagnosticResults = { deps: null, conflicts: null, duplicates: null };
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

                    <!-- Section A: Advanced Settings -->
                    <div class="card mt-6">
                        <div class="card-header cursor-pointer flex items-center justify-between" onclick="window.__launcherToggleCollapsible('advanced-settings')">
                            <span>${t('launch_advanced_settings')}</span>
                            <span class="material-symbols-outlined transition-transform" id="chevron-advanced-settings">expand_more</span>
                        </div>
                        <div id="section-advanced-settings" style="display:none" class="px-4 pb-4">
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px 24px;margin-top:12px">
                                <div>
                                    <label class="input-label">${t('launch_cross_attention')}</label>
                                    <select id="ls-cross-attention" class="select ls-control">
                                        <option value="auto">auto</option>
                                        <option value="pytorch">pytorch</option>
                                        <option value="split">split</option>
                                        <option value="quad">quad</option>
                                        <option value="sage">sage</option>
                                        <option value="flash">flash</option>
                                        <option value="disable_xformers">disable_xformers</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="input-label">${t('launch_vram_mode')}</label>
                                    <select id="ls-vram-mode" class="select ls-control">
                                        <option value="gpu_only">gpu_only</option>
                                        <option value="high">high</option>
                                        <option value="normal">normal</option>
                                        <option value="low">low</option>
                                        <option value="no">no</option>
                                        <option value="cpu">cpu</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="input-label">${t('launch_reserve_vram')}</label>
                                    <input type="number" id="ls-reserve-vram" class="input ls-control" min="0" step="0.1" placeholder="e.g. 1.0">
                                </div>
                                <div>
                                    <label class="input-label">${t('launch_async_offload')}</label>
                                    <select id="ls-async-offload" class="select ls-control">
                                        <option value="auto">auto</option>
                                        <option value="enable">enable</option>
                                        <option value="disable">disable</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="input-label">${t('launch_smart_memory')}</label>
                                    <label style="display:flex;align-items:center;gap:8px;margin-top:4px;cursor:pointer">
                                        <input type="checkbox" id="ls-smart-memory" class="ls-control" style="width:18px;height:18px;accent-color:#cc97ff">
                                        <span style="font-size:13px;color:#ccc">${t('launch_smart_memory')}</span>
                                    </label>
                                </div>
                                <div>
                                    <label class="input-label">${t('launch_listen_ip')}</label>
                                    <input type="text" id="ls-listen" class="input ls-control" placeholder="127.0.0.1">
                                </div>
                                <div>
                                    <label class="input-label">${t('launch_auto_open_browser')}</label>
                                    <label style="display:flex;align-items:center;gap:8px;margin-top:4px;cursor:pointer">
                                        <input type="checkbox" id="ls-auto-launch" class="ls-control" style="width:18px;height:18px;accent-color:#cc97ff">
                                        <span style="font-size:13px;color:#ccc">${t('launch_auto_open_browser')}</span>
                                    </label>
                                </div>
                            </div>
                            <!-- Network Advanced (sub-collapsible) -->
                            <div style="margin-top:16px;border:1px solid rgba(255,255,255,0.08);border-radius:8px">
                                <div style="padding:10px 14px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#999;text-transform:uppercase;letter-spacing:0.1em" onclick="window.__launcherToggleCollapsible('network-advanced')">
                                    <span>${t('launch_network_advanced')}</span>
                                    <span class="material-symbols-outlined transition-transform" id="chevron-network-advanced" style="font-size:18px">expand_more</span>
                                </div>
                                <div id="section-network-advanced" style="display:none;padding:0 14px 14px 14px">
                                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px">
                                        <div>
                                            <label class="input-label">${t('launch_cors')}</label>
                                            <input type="text" id="ls-cors-origin" class="input ls-control" placeholder="* or https://...">
                                        </div>
                                        <div></div>
                                        <div>
                                            <label class="input-label">${t('launch_tls_key')}</label>
                                            <input type="text" id="ls-tls-keyfile" class="input ls-control" placeholder="${t('launch_tls_key_placeholder')}">
                                        </div>
                                        <div>
                                            <label class="input-label">${t('launch_tls_cert')}</label>
                                            <input type="text" id="ls-tls-certfile" class="input ls-control" placeholder="${t('launch_tls_cert_placeholder')}">
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div style="margin-top:16px">
                                <label class="input-label">${t('launch_custom_args')}</label>
                                <textarea id="ls-custom-args" class="input ls-control" rows="2" style="resize:vertical;font-family:monospace;font-size:12px"></textarea>
                                <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px" id="ls-arg-chips">
                                    <span class="ls-chip" data-arg="--force-fp16">--force-fp16</span>
                                    <span class="ls-chip" data-arg="--force-fp32">--force-fp32</span>
                                    <span class="ls-chip" data-arg="--bf16-unet">--bf16-unet</span>
                                    <span class="ls-chip" data-arg="--fp8_e4m3fn-unet">--fp8_e4m3fn-unet</span>
                                    <span class="ls-chip" data-arg="--cpu-vae">--cpu-vae</span>
                                    <span class="ls-chip" data-arg="--fast">--fast</span>
                                    <span class="ls-chip" data-arg="--deterministic">--deterministic</span>
                                    <span class="ls-chip" data-arg="--disable-cuda-malloc">--disable-cuda-malloc</span>
                                </div>
                            </div>
                            <div style="margin-top:12px;text-align:right">
                                <span id="ls-save-status" style="font-size:12px;color:#66bb6a;opacity:0;transition:opacity 0.3s"></span>
                            </div>
                        </div>
                    </div>

                    <!-- Section B: Diagnostics -->
                    <div class="card mt-6">
                        <div class="card-header cursor-pointer flex items-center justify-between" onclick="window.__launcherToggleCollapsible('diagnostics')">
                            <span>${t('launch_diagnostics')}</span>
                            <span class="material-symbols-outlined transition-transform" id="chevron-diagnostics">expand_more</span>
                        </div>
                        <div id="section-diagnostics" style="display:none" class="px-4 pb-4">
                            <div style="margin-top:12px;margin-bottom:16px;display:flex;align-items:center;gap:8px">
                                <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                                    <input type="checkbox" id="ls-auto-diagnostics" style="width:18px;height:18px;accent-color:#cc97ff">
                                    <span style="font-size:13px;color:#ccc">${t('launch_diag_auto_toggle')}</span>
                                </label>
                            </div>
                            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
                                <div class="card" style="background:rgba(255,255,255,0.03)">
                                    <div style="padding:12px">
                                        <div style="font-size:13px;font-weight:500;margin-bottom:8px">${t('launch_diag_check_deps')}</div>
                                        <button class="btn btn-secondary diag-run-btn" data-diag="deps" style="width:100%;padding:6px 12px;font-size:12px">
                                            <span class="material-symbols-outlined text-[16px]">play_arrow</span>
                                            ${t('launch_diag_run')}
                                        </button>
                                        <div id="diag-result-deps" style="display:none;margin-top:8px;font-size:12px;max-height:150px;overflow-y:auto"></div>
                                    </div>
                                </div>
                                <div class="card" style="background:rgba(255,255,255,0.03)">
                                    <div style="padding:12px">
                                        <div style="font-size:13px;font-weight:500;margin-bottom:8px">${t('launch_diag_check_conflicts')}</div>
                                        <button class="btn btn-secondary diag-run-btn" data-diag="conflicts" style="width:100%;padding:6px 12px;font-size:12px">
                                            <span class="material-symbols-outlined text-[16px]">play_arrow</span>
                                            ${t('launch_diag_run')}
                                        </button>
                                        <div id="diag-result-conflicts" style="display:none;margin-top:8px;font-size:12px;max-height:150px;overflow-y:auto"></div>
                                    </div>
                                </div>
                                <div class="card" style="background:rgba(255,255,255,0.03)">
                                    <div style="padding:12px">
                                        <div style="font-size:13px;font-weight:500;margin-bottom:8px">${t('launch_diag_check_duplicates')}</div>
                                        <button class="btn btn-secondary diag-run-btn" data-diag="duplicates" style="width:100%;padding:6px 12px;font-size:12px">
                                            <span class="material-symbols-outlined text-[16px]">play_arrow</span>
                                            ${t('launch_diag_run')}
                                        </button>
                                        <div id="diag-result-duplicates" style="display:none;margin-top:8px;font-size:12px;max-height:150px;overflow-y:auto"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <style>
                        .ls-chip {
                            display:inline-block;padding:4px 10px;font-size:11px;font-family:monospace;
                            background:rgba(204,151,255,0.1);color:#cc97ff;border:1px solid rgba(204,151,255,0.25);
                            border-radius:12px;cursor:pointer;transition:background 0.2s;user-select:none;
                        }
                        .ls-chip:hover { background:rgba(204,151,255,0.25); }
                    </style>
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
            loadLaunchSettings(this.value);
            diagnosticResults = { deps: null, conflicts: null, duplicates: null };
            ['deps', 'conflicts', 'duplicates'].forEach(function(k) {
                var el = document.getElementById('diag-result-' + k);
                if (el) { el.style.display = 'none'; el.innerHTML = ''; }
            });
        });

        // Running list refresh
        document.getElementById('running-btn-refresh').addEventListener('click', loadRunningList);

        // Advanced settings change listeners
        document.querySelectorAll('.ls-control').forEach(function(el) {
            var evtType = (el.tagName === 'SELECT' || el.type === 'checkbox') ? 'change' : 'input';
            el.addEventListener(evtType, onSettingChanged);
        });

        // Arg chip click handlers
        document.querySelectorAll('.ls-chip').forEach(function(chip) {
            chip.addEventListener('click', function() {
                var textarea = document.getElementById('ls-custom-args');
                if (!textarea) return;
                var arg = this.dataset.arg;
                var current = textarea.value.trim();
                if (current.indexOf(arg) === -1) {
                    textarea.value = current ? current + ' ' + arg : arg;
                    onSettingChanged();
                }
            });
        });

        // Auto-diagnostics toggle
        var autoDiagEl = document.getElementById('ls-auto-diagnostics');
        if (autoDiagEl) {
            autoDiagEl.addEventListener('change', onSettingChanged);
        }

        // Diagnostic run buttons
        document.querySelectorAll('.diag-run-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                runDiagnostic(this.dataset.diag);
            });
        });

        // Expose toggleCollapsible globally for onclick handlers
        window.__launcherToggleCollapsible = toggleCollapsible;

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
        const envSelect = document.getElementById('launch-env');
        const portInput = document.getElementById('launch-port');
        if (!envSelect || !envSelect.value) { App.showToast(t('launch_select_env'), 'info'); return; }

        const envName = envSelect.value;
        const port = parseInt(portInput.value) || 8188;

        // Check auto_diagnostics setting
        if (currentLaunchSettings && currentLaunchSettings.auto_diagnostics) {
            document.getElementById('launch-btn-start').disabled = true;
            appendLog(t('launch_diagnostics') + '...');

            Promise.all([
                BridgeAPI.checkDependencies(envName).catch(function(e) { return { status: 'error', error: String(e) }; }),
                BridgeAPI.checkConflicts(envName).catch(function(e) { return { status: 'error', error: String(e) }; }),
                BridgeAPI.checkDuplicateNodes(envName).catch(function(e) { return { status: 'error', error: String(e) }; })
            ]).then(function(results) {
                diagnosticResults.deps = results[0];
                diagnosticResults.conflicts = results[1];
                diagnosticResults.duplicates = results[2];

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
            return;
        }

        doStartActual(envName, port);
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
            // Populate controls
            var el;
            el = document.getElementById('ls-cross-attention');
            if (el) el.value = settings.cross_attention || 'auto';
            el = document.getElementById('ls-vram-mode');
            if (el) el.value = settings.vram_mode || 'normal';
            el = document.getElementById('ls-reserve-vram');
            if (el) el.value = (settings.reserve_vram != null && settings.reserve_vram !== '') ? settings.reserve_vram : '';
            el = document.getElementById('ls-async-offload');
            if (el) el.value = settings.async_offload || 'auto';
            el = document.getElementById('ls-smart-memory');
            if (el) el.checked = !!settings.smart_memory;
            el = document.getElementById('ls-listen');
            if (el) el.value = settings.listen || '';
            // Update the top port input from launch_settings
            el = document.getElementById('launch-port');
            if (el && settings.port) el.value = settings.port;
            el = document.getElementById('ls-auto-launch');
            if (el) el.checked = !!settings.auto_launch;
            el = document.getElementById('ls-cors-origin');
            if (el) el.value = settings.cors_origin || '';
            el = document.getElementById('ls-tls-keyfile');
            if (el) el.value = settings.tls_keyfile || '';
            el = document.getElementById('ls-tls-certfile');
            if (el) el.value = settings.tls_certfile || '';
            el = document.getElementById('ls-custom-args');
            if (el) el.value = settings.custom_args || '';
            el = document.getElementById('ls-auto-diagnostics');
            if (el) el.checked = !!settings.auto_diagnostics;

        }).catch(function(e) {
            currentLaunchSettings = {};
        });
    }

    function onSettingChanged() {
        var settings = {};
        var el;
        el = document.getElementById('ls-cross-attention');
        if (el) settings.cross_attention = el.value;
        el = document.getElementById('ls-vram-mode');
        if (el) settings.vram_mode = el.value;
        el = document.getElementById('ls-reserve-vram');
        if (el) settings.reserve_vram = el.value !== '' ? parseFloat(el.value) : null;
        el = document.getElementById('ls-async-offload');
        if (el) settings.async_offload = el.value;
        el = document.getElementById('ls-smart-memory');
        if (el) settings.smart_memory = el.checked;
        el = document.getElementById('ls-listen');
        if (el) settings.listen = el.value;
        // Read port from the top input (single source of truth)
        el = document.getElementById('launch-port');
        if (el) settings.port = el.value ? parseInt(el.value) : 8188;
        el = document.getElementById('ls-auto-launch');
        if (el) settings.auto_launch = el.checked;
        el = document.getElementById('ls-cors-origin');
        if (el) settings.cors_origin = el.value;
        el = document.getElementById('ls-tls-keyfile');
        if (el) settings.tls_keyfile = el.value;
        el = document.getElementById('ls-tls-certfile');
        if (el) settings.tls_certfile = el.value;
        el = document.getElementById('ls-custom-args');
        if (el) settings.custom_args = el.value;
        el = document.getElementById('ls-auto-diagnostics');
        if (el) settings.auto_diagnostics = el.checked;

        currentLaunchSettings = settings;
        debounceSave();
    }

    function debounceSave() {
        if (saveDebounceTimer) clearTimeout(saveDebounceTimer);
        saveDebounceTimer = setTimeout(function() {
            if (!selectedEnv || !currentLaunchSettings) return;
            BridgeAPI.saveLaunchSettings(selectedEnv, currentLaunchSettings).then(function() {
                var statusEl = document.getElementById('ls-save-status');
                if (statusEl) {
                    statusEl.textContent = '\u2713 ' + t('launch_settings_saved');
                    statusEl.style.opacity = '1';
                    setTimeout(function() { statusEl.style.opacity = '0'; }, 2000);
                }
            }).catch(function(e) {
                App.showToast(String(e), 'error');
            });
        }, 500);
    }

    function toggleCollapsible(sectionId) {
        var section = document.getElementById('section-' + sectionId);
        var chevron = document.getElementById('chevron-' + sectionId);
        if (!section) return;
        var isHidden = section.style.display === 'none';
        section.style.display = isHidden ? 'block' : 'none';
        if (chevron) {
            chevron.style.transform = isHidden ? 'rotate(180deg)' : '';
        }
    }

    function runDiagnostic(type) {
        if (!selectedEnv) return;
        var resultEl = document.getElementById('diag-result-' + type);
        var btn = document.querySelector('.diag-run-btn[data-diag="' + type + '"]');
        if (btn) { btn.disabled = true; btn.textContent = '...'; }

        var promise;
        if (type === 'deps') {
            promise = BridgeAPI.checkDependencies(selectedEnv);
        } else if (type === 'conflicts') {
            promise = BridgeAPI.checkConflicts(selectedEnv);
        } else if (type === 'duplicates') {
            promise = BridgeAPI.checkDuplicateNodes(selectedEnv);
        } else {
            return;
        }

        promise.then(function(result) {
            diagnosticResults[type] = result;
            if (btn) { btn.disabled = false; btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">play_arrow</span> ' + t('launch_diag_run'); }
            if (!resultEl) return;
            resultEl.style.display = 'block';

            if (type === 'deps') {
                var depItems = Array.isArray(result.items) ? result.items : [];
                var missingItems = depItems.filter(function(item) {
                    return item && item.status === 'missing';
                });
                var pipCheckItems = depItems.filter(function(item) {
                    return item && item.status === 'pip_check_issue';
                });

                if (missingItems.length === 0 && pipCheckItems.length === 0) {
                    resultEl.innerHTML = '<div style="color:#66bb6a">\u2713 ' + t('launch_diag_no_issues') + '</div>';
                } else {
                    var issueCount = missingItems.length + pipCheckItems.length;
                    var html = '<div style="color:#ffb74d">' + t('launch_diag_issue_count', issueCount) + '</div>';
                    html += '<div style="margin-top:6px;max-height:80px;overflow-y:auto;font-family:monospace;font-size:11px;color:#ccc">';
                    missingItems.forEach(function(item) {
                        var pkgSpec = (item.required && item.required !== 'any')
                            ? (item.package + item.required)
                            : item.package;
                        html += '<div>' + t('launch_diag_missing_prefix') + ': ' + pkgSpec + '</div>';
                    });
                    pipCheckItems.forEach(function(item) {
                        html += '<div>' + t('launch_diag_pip_check_prefix') + ': ' + (item.installed || '') + '</div>';
                    });
                    html += '</div>';
                    if (missingItems.length > 0) {
                        html += '<button class="btn btn-secondary" style="margin-top:8px;padding:4px 10px;font-size:11px" id="diag-fix-deps">';
                        html += t('launch_diag_fix_btn') + '</button>';
                    }
                    resultEl.innerHTML = html;
                    var fixBtn = document.getElementById('diag-fix-deps');
                    if (fixBtn) {
                        var packagesToInstall = missingItems
                            .map(function(item) {
                                if (!item || !item.package) return '';
                                return (item.required && item.required !== 'any')
                                    ? (item.package + item.required)
                                    : item.package;
                            })
                            .filter(function(spec) { return !!spec; });
                        fixBtn.addEventListener('click', function() {
                            this.disabled = true;
                            this.textContent = '...';
                            BridgeAPI.fixMissingDeps(selectedEnv, packagesToInstall).then(function() {
                                App.showToast(t('launch_diag_fix_success'), 'success');
                                runDiagnostic('deps');
                            }).catch(function(e) { App.showToast(String(e), 'error'); });
                        });
                    }
                }
            } else if (type === 'conflicts') {
                if (!result.conflicts || result.conflicts.length === 0) {
                    resultEl.innerHTML = '<div style="color:#66bb6a">\u2713 ' + t('launch_diag_no_issues') + '</div>';
                } else {
                    var html = '<div style="color:#ffb74d">' + t('launch_diag_conflict_count', result.conflicts.length) + '</div>';
                    html += '<div style="margin-top:6px;max-height:80px;overflow-y:auto;font-size:11px;color:#ccc">';
                    result.conflicts.forEach(function(c) { html += '<div>' + (c.description || c.name || JSON.stringify(c)) + '</div>'; });
                    html += '</div>';
                    resultEl.innerHTML = html;
                }
            } else if (type === 'duplicates') {
                var hasDups = result.duplicates && result.duplicates.length > 0;
                var hasUnscannable = result.unscannable && result.unscannable.length > 0;
                if (!hasDups && !hasUnscannable) {
                    resultEl.innerHTML = '<div style="color:#66bb6a">\u2713 ' + t('launch_diag_no_issues') + '</div>';
                } else {
                    var html = '';
                    if (hasDups) {
                        html += '<div style="color:#ffb74d">' + t('launch_diag_duplicate_count', result.duplicates.length) + '</div>';
                        html += '<div style="margin-top:6px;max-height:80px;overflow-y:auto;font-size:11px;color:#ccc">';
                        result.duplicates.forEach(function(d) { html += '<div>' + (d.name || JSON.stringify(d)) + '</div>'; });
                        html += '</div>';
                    }
                    if (hasUnscannable) {
                        html += '<div style="color:#ababab;margin-top:6px">' + t('launch_diag_unscannable_count', result.unscannable.length) + '</div>';
                    }
                    resultEl.innerHTML = html;
                }
            }
        }).catch(function(e) {
            if (btn) { btn.disabled = false; btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">play_arrow</span> ' + t('launch_diag_run'); }
            if (resultEl) {
                resultEl.style.display = 'block';
                resultEl.innerHTML = '<div style="color:#ff6e84">' + String(e) + '</div>';
            }
        });
    }

    App.registerPage('launcher', { render });

})();
