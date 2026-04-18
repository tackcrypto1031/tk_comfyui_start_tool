/**
 * settings.js — Settings page
 *
 * Hosts the per-environment advanced launch settings and the diagnostics
 * tools that used to live inside the launcher page. The launcher page is
 * kept focused on the primary launch flow (port / VRAM / cross-attention +
 * the launch button); everything configurable-but-rarely-touched moves
 * here per the Tack Launcher redesign.
 */
(function() {

    var selectedEnv = null;
    var currentLaunchSettings = null;
    var saveDebounceTimer = null;

    function render(container) {
        container.innerHTML =
            '<div class="ti-content fade-in">' +
                '<div class="ti-page-head">' +
                    '<div>' +
                        '<p class="ti-page-sub" id="settings-sub">' + (t('launch_advanced_settings') || '進階設定') + ' &middot; ' + (t('launch_diagnostics') || '診斷') + '</p>' +
                    '</div>' +
                    '<div class="ti-page-actions">' +
                        '<div class="ti-env-select">' +
                            '<label>' + t('launch_environment') + '</label>' +
                            '<select id="settings-env"></select>' +
                        '</div>' +
                    '</div>' +
                '</div>' +

                // Advanced Settings
                '<div class="ti-card" id="settings-advanced">' +
                    '<div class="ti-card-head">' +
                        '<span class="material-symbols-outlined">tune</span>' +
                        '<span class="ti-card-title">' + (t('launch_advanced_settings') || '進階設定') + '</span>' +
                        '<span id="settings-save-status" class="mono" style="margin-left:auto;font-size:11px;color:var(--accent);opacity:0;transition:opacity 0.3s">\u2713 ' + (t('launch_settings_saved') || '已儲存') + '</span>' +
                    '</div>' +
                    '<div class="ti-card-body">' +
                        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px 24px">' +
                            '<div class="ti-field">' +
                                '<label>' + (t('launch_reserve_vram') || '保留 VRAM') + '</label>' +
                                '<input type="number" id="ls-reserve-vram" class="ls-control text-input mono" min="0" step="0.1" placeholder="e.g. 1.0">' +
                            '</div>' +
                            '<div class="ti-field">' +
                                '<label>' + (t('launch_async_offload') || '非同步 Offload') + ' <span class="help-tip" data-tooltip="' + (t('launch_help_async_offload') || '') + '">?</span></label>' +
                                '<select id="ls-async-offload" class="ls-control select">' +
                                    '<option value="auto">' + t('launch_async_auto') + '</option>' +
                                    '<option value="enable">' + t('launch_async_enable') + '</option>' +
                                    '<option value="disable">' + t('launch_async_disable') + '</option>' +
                                '</select>' +
                            '</div>' +
                            '<div class="ti-field">' +
                                '<label style="display:flex;align-items:center;gap:8px;cursor:pointer">' +
                                    '<input type="checkbox" id="ls-smart-memory" class="ls-control">' +
                                    '<span>' + (t('launch_smart_memory') || 'Smart Memory') + '</span>' +
                                '</label>' +
                            '</div>' +
                            '<div class="ti-field">' +
                                '<label style="display:flex;align-items:center;gap:8px;cursor:pointer">' +
                                    '<input type="checkbox" id="ls-auto-launch" class="ls-control">' +
                                    '<span>' + (t('launch_auto_open_browser') || '自動開啟瀏覽器') + '</span>' +
                                '</label>' +
                            '</div>' +
                            '<div class="ti-field">' +
                                '<label style="display:flex;align-items:center;gap:8px;cursor:pointer">' +
                                    '<input type="checkbox" id="ls-listen-enable">' +
                                    '<span>' + (t('launch_listen_enable') || '允許 LAN 連線') + '</span>' +
                                '</label>' +
                                '<div class="hint">' + (t('launch_listen_enable_desc') || '') + '</div>' +
                            '</div>' +
                            '<div class="ti-field">' +
                                '<label>' + (t('launch_listen_ip') || '監聽位址') + '</label>' +
                                '<input type="text" id="ls-listen" class="ls-control text-input mono" placeholder="0.0.0.0" disabled>' +
                                '<div class="hint" id="ls-listen-error" style="display:none;color:var(--danger)"></div>' +
                            '</div>' +
                        '</div>' +

                        // Network Advanced (sub-collapsible)
                        '<div style="margin-top:16px;border:1px solid var(--border-1);border-radius:var(--radius-sm)">' +
                            '<div id="settings-network-head" style="padding:10px 14px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;font-family:var(--font-mono);font-size:11px;color:var(--text-3);text-transform:uppercase;letter-spacing:0.08em">' +
                                '<span>' + (t('launch_network_advanced') || '網路進階') + '</span>' +
                                '<span class="material-symbols-outlined" id="settings-network-chevron" style="font-size:18px;transition:transform 0.15s">expand_more</span>' +
                            '</div>' +
                            '<div id="settings-network-body" style="display:none;padding:0 14px 14px">' +
                                '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px">' +
                                    '<div class="ti-field">' +
                                        '<label>' + (t('launch_cors') || 'CORS Origin') + '</label>' +
                                        '<input type="text" id="ls-cors-origin" class="ls-control text-input" placeholder="* or https://...">' +
                                    '</div>' +
                                    '<div></div>' +
                                    '<div class="ti-field">' +
                                        '<label>' + (t('launch_tls_key') || 'TLS Key') + '</label>' +
                                        '<input type="text" id="ls-tls-keyfile" class="ls-control text-input" placeholder="' + (t('launch_tls_key_placeholder') || '') + '">' +
                                    '</div>' +
                                    '<div class="ti-field">' +
                                        '<label>' + (t('launch_tls_cert') || 'TLS Cert') + '</label>' +
                                        '<input type="text" id="ls-tls-certfile" class="ls-control text-input" placeholder="' + (t('launch_tls_cert_placeholder') || '') + '">' +
                                    '</div>' +
                                '</div>' +
                            '</div>' +
                        '</div>' +

                        // Custom args
                        '<div style="margin-top:16px">' +
                            '<label class="input-label" style="display:block;margin-bottom:6px">' + (t('launch_custom_args') || '自訂啟動參數') + '</label>' +
                            '<textarea id="ls-custom-args" class="ls-control text-input mono" rows="2" style="resize:vertical;width:100%;font-size:12px"></textarea>' +
                            '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px" id="ls-arg-chips">' +
                                chip('--force-fp16') + chip('--force-fp32') + chip('--bf16-unet') + chip('--fp8_e4m3fn-unet') +
                                chip('--cpu-vae') + chip('--fast') + chip('--deterministic') + chip('--disable-cuda-malloc') +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>' +

                // Diagnostics
                '<div style="height:16px"></div>' +
                '<div class="ti-card" id="settings-diagnostics">' +
                    '<div class="ti-card-head">' +
                        '<span class="material-symbols-outlined">troubleshoot</span>' +
                        '<span class="ti-card-title">' + (t('launch_diagnostics') || '診斷') + '</span>' +
                    '</div>' +
                    '<div class="ti-card-body">' +
                        '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:16px">' +
                            '<input type="checkbox" id="ls-auto-diagnostics">' +
                            '<span style="font-size:13px;color:var(--text-1)">' + (t('launch_diag_auto_toggle') || '啟動前自動執行診斷') + '</span>' +
                        '</label>' +
                        '<div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:12px">' +
                            diagCard('deps', t('launch_diag_check_deps')) +
                            diagCard('conflicts', t('launch_diag_check_conflicts')) +
                            diagCard('duplicates', t('launch_diag_check_duplicates')) +
                        '</div>' +
                    '</div>' +
                '</div>' +

                '<style>' +
                    '.ls-chip {' +
                        'display:inline-block;padding:4px 10px;font-size:11px;font-family:var(--font-mono);' +
                        'background:var(--accent-glow);color:var(--accent);border:1px solid var(--accent-dim);' +
                        'border-radius:12px;cursor:pointer;transition:background 0.2s;user-select:none;' +
                    '}' +
                    '.ls-chip:hover { background:oklch(0.82 0.17 128 / 0.25); }' +
                    '#settings-advanced .ti-field .text-input, #settings-advanced textarea { width:100%; }' +
                    '#settings-advanced .hint { font-size:11px;color:var(--text-3); }' +
                    '#settings-diagnostics .diag-card {' +
                        'background:var(--bg-2);border:1px solid var(--border-1);' +
                        'border-radius:var(--radius);padding:14px;' +
                    '}' +
                    '#settings-diagnostics .diag-card-title {' +
                        'font-size:13px;font-weight:500;color:var(--text-0);margin-bottom:10px;' +
                    '}' +
                    '#settings-diagnostics .diag-card .btn-secondary {' +
                        'width:100%;justify-content:center;padding:6px 12px;font-size:12px;' +
                    '}' +
                    '#settings-diagnostics .diag-result {' +
                        'display:none;margin-top:10px;font-size:12px;max-height:160px;overflow-y:auto;' +
                    '}' +
                '</style>' +
            '</div>';

        // Env selector
        document.getElementById('settings-env').addEventListener('change', function() {
            selectedEnv = this.value;
            loadLaunchSettings(this.value);
            // reset diag output for the new env
            ['deps', 'conflicts', 'duplicates'].forEach(function(k) {
                var el = document.getElementById('diag-result-' + k);
                if (el) { el.style.display = 'none'; el.innerHTML = ''; }
            });
        });

        // Network advanced collapsible
        document.getElementById('settings-network-head').addEventListener('click', function() {
            var body = document.getElementById('settings-network-body');
            var chev = document.getElementById('settings-network-chevron');
            var hidden = body.style.display === 'none';
            body.style.display = hidden ? 'block' : 'none';
            if (chev) chev.style.transform = hidden ? 'rotate(180deg)' : '';
        });

        // Advanced settings change listeners
        document.querySelectorAll('#settings-advanced .ls-control, #settings-diagnostics #ls-auto-diagnostics').forEach(function(el) {
            if (el.id === 'ls-listen-enable') return;  // handled separately
            var evtType = (el.tagName === 'SELECT' || el.type === 'checkbox') ? 'change' : 'input';
            el.addEventListener(evtType, onSettingChanged);
        });

        // LAN enable intercepts with confirmation modal (first time only)
        var lanCb = document.getElementById('ls-listen-enable');
        if (lanCb) {
            lanCb.addEventListener('change', async function(ev) {
                if (!ev.target.checked) {
                    _syncListenControls();
                    onSettingChanged();
                    return;
                }
                var flagJson;
                try { flagJson = await bridge.getUiFlag('listen_warning_dismissed'); }
                catch (e) { flagJson = 'null'; }
                var dismissed = false;
                try { dismissed = JSON.parse(flagJson) === true; } catch (e) {}
                if (dismissed) {
                    _syncListenControls();
                    onSettingChanged();
                    return;
                }
                ev.target.checked = false;
                _showListenConfirm(function(ok, dontAsk) {
                    if (!ok) {
                        _syncListenControls();
                        onSettingChanged();
                        return;
                    }
                    ev.target.checked = true;
                    if (dontAsk) bridge.setUiFlag('listen_warning_dismissed', true);
                    _syncListenControls();
                    onSettingChanged();
                });
            });
        }

        // Arg chip click handlers
        document.querySelectorAll('#settings-advanced .ls-chip').forEach(function(chipEl) {
            chipEl.addEventListener('click', function() {
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

        // Diagnostic run buttons
        document.querySelectorAll('#settings-diagnostics .diag-run-btn').forEach(function(btn) {
            btn.addEventListener('click', function() { runDiagnostic(this.dataset.diag); });
        });

        loadEnvs();
    }

    function chip(arg) {
        return '<span class="ls-chip" data-arg="' + arg + '">' + arg + '</span>';
    }

    function diagCard(id, title) {
        return '' +
            '<div class="diag-card">' +
                '<div class="diag-card-title">' + title + '</div>' +
                '<button class="btn btn-secondary diag-run-btn" data-diag="' + id + '">' +
                    '<span class="material-symbols-outlined" style="font-size:14px">play_arrow</span>' +
                    '<span>' + (t('launch_diag_run') || '執行') + '</span>' +
                '</button>' +
                '<div class="diag-result" id="diag-result-' + id + '"></div>' +
            '</div>';
    }

    function loadEnvs() {
        return BridgeAPI.listEnvironments().then(function(envs) {
            var select = document.getElementById('settings-env');
            if (!select) return;
            select.innerHTML = '';
            envs.forEach(function(env) {
                var opt = document.createElement('option');
                opt.value = env.name;
                opt.textContent = env.name;
                select.appendChild(opt);
            });
            if (selectedEnv) select.value = selectedEnv;
            var envName = select.value;
            if (envName) {
                selectedEnv = envName;
                loadLaunchSettings(envName);
            }
        });
    }

    function loadLaunchSettings(envName) {
        if (!envName) return;
        BridgeAPI.getLaunchSettings(envName).then(function(settings) {
            currentLaunchSettings = settings || {};
            var el;
            el = document.getElementById('ls-reserve-vram');
            if (el) el.value = (settings.reserve_vram != null && settings.reserve_vram !== '') ? settings.reserve_vram : '';
            el = document.getElementById('ls-async-offload');
            if (el) el.value = settings.async_offload || 'auto';
            el = document.getElementById('ls-smart-memory');
            if (el) el.checked = !!settings.smart_memory;
            el = document.getElementById('ls-auto-launch');
            if (el) el.checked = !!settings.auto_launch;
            el = document.getElementById('ls-listen-enable');
            if (el) el.checked = !!settings.listen_enabled;
            el = document.getElementById('ls-listen');
            if (el) el.value = settings.listen || '';
            _syncListenControls();
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
        }).catch(function() {
            currentLaunchSettings = {};
        });
    }

    function _isLoopbackIp(ip) {
        if (!ip) return false;
        var v = String(ip).trim().toLowerCase();
        return v === '127.0.0.1' || v === 'localhost' || v === '::1' || v.indexOf('127.') === 0;
    }

    function _showListenConfirm(onConfirm) {
        var overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:9999';
        overlay.innerHTML = (
            '<div class="modal" style="background:var(--bg-1);color:var(--text-0);padding:20px;border-radius:8px;max-width:420px;box-shadow:0 4px 24px rgba(0,0,0,.5);border:1px solid var(--border-2)">' +
            '  <h3 style="margin-top:0;font-size:15px;font-weight:600">' + t('launch_listen_confirm_title') + '</h3>' +
            '  <p style="font-size:13px;color:var(--text-2);line-height:1.5">' + t('launch_listen_confirm_body') + '</p>' +
            '  <label style="display:flex;gap:6px;align-items:center;margin:12px 0;font-size:12px">' +
            '    <input type="checkbox" id="listen-confirm-dontask"><span>' + t('launch_listen_confirm_dont_ask') + '</span>' +
            '  </label>' +
            '  <div style="display:flex;gap:8px;justify-content:flex-end">' +
            '    <button id="listen-confirm-cancel" class="btn btn-secondary">' + t('launch_listen_confirm_cancel') + '</button>' +
            '    <button id="listen-confirm-ok" class="btn btn-primary">' + t('launch_listen_confirm_ok') + '</button>' +
            '  </div>' +
            '</div>'
        );
        document.body.appendChild(overlay);
        document.getElementById('listen-confirm-cancel').addEventListener('click', function() {
            document.body.removeChild(overlay);
            onConfirm(false, false);
        });
        document.getElementById('listen-confirm-ok').addEventListener('click', function() {
            var dontAsk = document.getElementById('listen-confirm-dontask').checked;
            document.body.removeChild(overlay);
            onConfirm(true, dontAsk);
        });
    }

    function _syncListenControls() {
        var cb = document.getElementById('ls-listen-enable');
        var ipEl = document.getElementById('ls-listen');
        var errEl = document.getElementById('ls-listen-error');
        if (!cb || !ipEl) return true;
        var enabled = cb.checked;
        ipEl.disabled = !enabled;
        if (!enabled) {
            if (errEl) errEl.style.display = 'none';
            return true;
        }
        if (_isLoopbackIp(ipEl.value)) {
            if (errEl) {
                errEl.textContent = t('launch_listen_invalid_loopback');
                errEl.style.display = 'block';
            }
            return false;
        }
        if (errEl) errEl.style.display = 'none';
        return true;
    }

    function onSettingChanged() {
        _syncListenControls();
        var patch = {};
        var el;
        el = document.getElementById('ls-reserve-vram');
        if (el) patch.reserve_vram = el.value !== '' ? parseFloat(el.value) : null;
        el = document.getElementById('ls-async-offload');
        if (el) patch.async_offload = el.value;
        el = document.getElementById('ls-smart-memory');
        if (el) patch.smart_memory = el.checked;
        el = document.getElementById('ls-auto-launch');
        if (el) patch.auto_launch = el.checked;
        el = document.getElementById('ls-listen-enable');
        if (el) patch.listen_enabled = el.checked;
        el = document.getElementById('ls-listen');
        if (el) patch.listen = el.value;
        el = document.getElementById('ls-cors-origin');
        if (el) patch.cors_origin = el.value;
        el = document.getElementById('ls-tls-keyfile');
        if (el) patch.tls_keyfile = el.value;
        el = document.getElementById('ls-tls-certfile');
        if (el) patch.tls_certfile = el.value;
        el = document.getElementById('ls-custom-args');
        if (el) patch.custom_args = el.value;
        el = document.getElementById('ls-auto-diagnostics');
        if (el) patch.auto_diagnostics = el.checked;

        currentLaunchSettings = Object.assign({}, currentLaunchSettings || {}, patch);
        debounceSave();
    }

    function debounceSave() {
        if (saveDebounceTimer) clearTimeout(saveDebounceTimer);
        saveDebounceTimer = setTimeout(function() {
            if (!selectedEnv || !currentLaunchSettings) return;
            BridgeAPI.saveLaunchSettings(selectedEnv, currentLaunchSettings).then(function() {
                var statusEl = document.getElementById('settings-save-status');
                if (statusEl) {
                    statusEl.style.opacity = '1';
                    setTimeout(function() { statusEl.style.opacity = '0'; }, 2000);
                }
            }).catch(function(e) {
                App.showToast(String(e), 'error');
            });
        }, 500);
    }

    function runDiagnostic(type) {
        if (!selectedEnv) return;
        var resultEl = document.getElementById('diag-result-' + type);
        var btn = document.querySelector('.diag-run-btn[data-diag="' + type + '"]');
        var btnOrigHtml = btn ? btn.innerHTML : null;
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:14px">hourglass_top</span><span>...</span>'; }

        var promise;
        if (type === 'deps') promise = BridgeAPI.checkDependencies(selectedEnv);
        else if (type === 'conflicts') promise = BridgeAPI.checkConflicts(selectedEnv);
        else if (type === 'duplicates') promise = BridgeAPI.checkDuplicateNodes(selectedEnv);
        else return;

        function restoreBtn() {
            if (btn) { btn.disabled = false; btn.innerHTML = btnOrigHtml; }
        }

        promise.then(function(result) {
            restoreBtn();
            if (!resultEl) return;
            resultEl.style.display = 'block';

            if (type === 'deps') {
                var depItems = Array.isArray(result.items) ? result.items : [];
                var missingItems = depItems.filter(function(item) { return item && item.status === 'missing'; });
                var pipCheckItems = depItems.filter(function(item) { return item && item.status === 'pip_check_issue'; });

                if (missingItems.length === 0 && pipCheckItems.length === 0) {
                    resultEl.innerHTML = '<div style="color:var(--accent)">\u2713 ' + t('launch_diag_no_issues') + '</div>';
                } else {
                    var issueCount = missingItems.length + pipCheckItems.length;
                    var html = '<div style="color:var(--warn)">' + t('launch_diag_issue_count', issueCount) + '</div>';
                    html += '<div style="margin-top:6px;max-height:80px;overflow-y:auto;font-family:var(--font-mono);font-size:11px;color:var(--text-1)">';
                    missingItems.forEach(function(item) {
                        var pkgSpec = (item.required && item.required !== 'any') ? (item.package + item.required) : item.package;
                        html += '<div>' + t('launch_diag_missing_prefix') + ': ' + pkgSpec + '</div>';
                    });
                    pipCheckItems.forEach(function(item) {
                        html += '<div>' + t('launch_diag_pip_check_prefix') + ': ' + (item.installed || '') + '</div>';
                    });
                    html += '</div>';
                    if (missingItems.length > 0) {
                        html += '<button class="btn btn-secondary" style="margin-top:8px;padding:4px 10px;font-size:11px" id="diag-fix-deps">' + t('launch_diag_fix_btn') + '</button>';
                    }
                    resultEl.innerHTML = html;
                    var fixBtn = document.getElementById('diag-fix-deps');
                    if (fixBtn) {
                        var packagesToInstall = missingItems
                            .map(function(item) {
                                if (!item || !item.package) return '';
                                return (item.required && item.required !== 'any') ? (item.package + item.required) : item.package;
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
                    resultEl.innerHTML = '<div style="color:var(--accent)">\u2713 ' + t('launch_diag_no_issues') + '</div>';
                } else {
                    var html = '<div style="color:var(--warn)">' + t('launch_diag_conflict_count', result.conflicts.length) + '</div>';
                    html += '<div style="margin-top:6px;max-height:80px;overflow-y:auto;font-size:11px;color:var(--text-1)">';
                    result.conflicts.forEach(function(c) { html += '<div>' + (c.description || c.name || JSON.stringify(c)) + '</div>'; });
                    html += '</div>';
                    resultEl.innerHTML = html;
                }
            } else if (type === 'duplicates') {
                var hasDups = result.duplicates && result.duplicates.length > 0;
                var hasUnscannable = result.unscannable && result.unscannable.length > 0;
                if (!hasDups && !hasUnscannable) {
                    resultEl.innerHTML = '<div style="color:var(--accent)">\u2713 ' + t('launch_diag_no_issues') + '</div>';
                } else {
                    var html = '';
                    if (hasDups) {
                        html += '<div style="color:var(--warn)">' + t('launch_diag_duplicate_count', result.duplicates.length) + '</div>';
                        html += '<div style="margin-top:6px;max-height:80px;overflow-y:auto;font-size:11px;color:var(--text-1)">';
                        result.duplicates.forEach(function(d) { html += '<div>' + (d.name || JSON.stringify(d)) + '</div>'; });
                        html += '</div>';
                    }
                    if (hasUnscannable) {
                        html += '<div style="color:var(--text-3);margin-top:6px">' + t('launch_diag_unscannable_count', result.unscannable.length) + '</div>';
                    }
                    resultEl.innerHTML = html;
                }
            }
        }).catch(function(e) {
            restoreBtn();
            if (resultEl) {
                resultEl.style.display = 'block';
                resultEl.innerHTML = '<div style="color:var(--danger)">' + String(e) + '</div>';
            }
        });
    }

    App.registerPage('settings', { render: render });

})();
