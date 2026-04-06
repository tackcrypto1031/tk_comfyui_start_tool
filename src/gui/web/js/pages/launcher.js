/**
 * launcher.js — ComfyUI launcher page
 */
(function() {

    let pollTimer = null;
    let selectedEnv = null;  // persist selected environment across tab switches

    function render(container) {
        container.innerHTML = `
            <div class="fade-in space-y-6">
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
                <div class="flex items-center gap-3">
                    <span class="text-xs font-label uppercase tracking-wider text-on-surface-variant">${t('launch_status')}:</span>
                    <span id="launch-status" class="badge badge-primary">${t('launch_status_stopped')}</span>
                </div>

                <!-- Log output -->
                <div>
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
        `;

        // Bind events
        document.getElementById('launch-btn-start').addEventListener('click', doStart);
        document.getElementById('launch-btn-stop').addEventListener('click', doStop);
        document.getElementById('launch-btn-refresh').addEventListener('click', loadEnvs);
        document.getElementById('launch-btn-export-log').addEventListener('click', doExportLog);

        // Dropdown change → remember selection + immediate status fetch
        document.getElementById('launch-env').addEventListener('change', function() {
            selectedEnv = this.value;
            pollStatus();
        });

        // Load environments, then immediately fetch status (don't wait for first 5s poll)
        loadEnvs().then(pollStatus);

        // Start background polling
        startPolling();
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
            // Show "starting" state — polling will update to "running" once healthy
            var statusEl = document.getElementById('launch-status');
            statusEl.className = 'badge badge-warning';
            statusEl.textContent = 'STARTING... (PID: ' + info.pid + ')';
            document.getElementById('launch-btn-start').disabled = true;
            document.getElementById('launch-btn-stop').disabled = false;
            App.showToast(t('launch_started', info.pid, info.port), 'success');
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
