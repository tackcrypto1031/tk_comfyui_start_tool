/**
 * home.js — Hero launch panel + quick action tiles + env stats
 *
 * Design: Claude Design handoff (Tack Launcher.html), Linear/Warp-inspired
 * industrial dark theme with oklch lime accent.
 */
(function() {

    var state = {
        envs: [],
        activeEnv: null,      // { name, status: 'running'|'stopped'|'starting', port, python, cuda, pytorch, plugins, size, commit, branch, lastUsed }
        runningEnv: null,
        logs: [],
    };

    var _logPollTimer = null;

    // ─── Public: render ───────────────────────────────────────────

    function render(container) {
        container.innerHTML =
            '<div class="ti-content fade-in">' +
                '<div id="ti-home-hero"></div>' +
                '<div class="ti-section-head">' +
                    '<h2 data-i18n="home_section_quick">快速動作</h2>' +
                    '<div class="line"></div>' +
                '</div>' +
                '<div id="ti-home-tiles" class="ti-tile-grid"></div>' +
                '<div class="ti-section-head">' +
                    '<h2 data-i18n="home_section_stats">環境狀態</h2>' +
                    '<div class="line"></div>' +
                '</div>' +
                '<div id="ti-home-stats" class="ti-stats"></div>' +
                '<div id="ti-home-logs-section" style="display:none">' +
                    '<div class="ti-section-head">' +
                        '<h2 data-i18n="home_section_logs">即時日誌</h2>' +
                        '<div class="line"></div>' +
                        '<button class="ti-section-action" id="ti-home-full-log">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">terminal</span>' +
                            '<span data-i18n="home_full_log">完整日誌</span>' +
                        '</button>' +
                    '</div>' +
                    '<div class="ti-log-panel">' +
                        '<div class="ti-log-head">' +
                            '<span>comfyui.log</span>' +
                            '<span style="color:var(--text-4); margin-left:8px">·</span>' +
                            '<span style="color:var(--accent)">● live</span>' +
                        '</div>' +
                        '<div class="ti-log-body" id="ti-home-log-body"></div>' +
                    '</div>' +
                '</div>' +
            '</div>';

        loadEnvs().then(function() {
            renderAll();
        });

        var fullLogBtn = document.getElementById('ti-home-full-log');
        if (fullLogBtn) {
            fullLogBtn.addEventListener('click', function() {
                App.navigate('launcher');
            });
        }
    }

    // ─── Data loading ─────────────────────────────────────────────

    function loadEnvs() {
        return BridgeAPI.listEnvironments().then(function(envs) {
            var normalized = (envs || []).map(normalizeEnv);
            return mergeRunningState(normalized);
        }).then(function(envs) {
            state.envs = envs;
            // Resolve active env — prefer the user's last selection, else the running one, else first.
            var saved = localStorage.getItem('ti_active_env');
            var active = null;
            if (saved) active = findEnv(saved);
            if (!active) active = state.envs.find(function(e) { return e.status === 'running'; });
            if (!active) active = state.envs[0] || null;
            state.activeEnv = active;
            state.runningEnv = state.envs.find(function(e) { return e.status === 'running'; }) || null;
            if (active) localStorage.setItem('ti_active_env', active.name);
            updateSidebarPill();
            return state;
        }).catch(function() {
            state.envs = [];
            state.activeEnv = null;
            state.runningEnv = null;
            return state;
        });
    }

    function mergeRunningState(envs) {
        if (!window.BridgeAPI || !BridgeAPI.listRunning) return Promise.resolve(envs);
        return BridgeAPI.listRunning().then(function(running) {
            var runMap = {};
            (running || []).forEach(function(r) {
                var name = typeof r === 'string' ? r : (r.name || r.env || '');
                if (!name) return;
                runMap[name] = r && typeof r === 'object' ? r : { name: name };
            });
            return envs.map(function(e) {
                if (runMap[e.name]) {
                    e.status = 'running';
                    if (runMap[e.name].port) e.port = runMap[e.name].port;
                }
                return e;
            });
        }).catch(function() { return envs; });
    }

    function normalizeEnv(e) {
        if (typeof e === 'string') e = { name: e };
        var pluginCount = 0;
        if (typeof e.plugin_count === 'number') pluginCount = e.plugin_count;
        else if (typeof e.plugins === 'number') pluginCount = e.plugins;
        else if (Array.isArray(e.custom_nodes)) {
            pluginCount = e.custom_nodes.filter(function(n) {
                return !n || typeof n !== 'object' || n.enabled !== false;
            }).length;
        }
        return {
            name: e.name || 'comfyui',
            status: e.status || (e.running ? 'running' : 'stopped'),
            port: e.port || 8188,
            python: e.python || e.python_version || '—',
            cuda: e.cuda || e.cuda_tag || '—',
            pytorch: e.pytorch || e.pytorch_version || e.torch || '—',
            plugins: pluginCount,
            size: e.size || '—',
            commit: e.commit || e.comfyui_commit || e.head_commit || '',
            branch: e.branch || e.comfyui_branch || 'master',
            lastUsed: e.lastUsed || e.last_used || e.created_at || '—',
        };
    }

    function findEnv(name) {
        return state.envs.find(function(e) { return e.name === name; }) || null;
    }

    // ─── Render parts ─────────────────────────────────────────────

    function renderAll() {
        renderHero();
        renderTiles();
        renderStats();
        renderLogs();
        updateSidebarPill();
        updateNavRunDot();
    }

    function renderHero() {
        var el = document.getElementById('ti-home-hero');
        if (!el) return;
        var e = state.activeEnv;
        if (!e) {
            el.innerHTML =
                '<div class="ti-hero">' +
                    '<div class="ti-hero-grid-bg"></div>' +
                    '<div class="ti-hero-glow"></div>' +
                    '<div class="ti-hero-inner">' +
                        '<div class="ti-hero-col">' +
                            '<div class="ti-hero-eyebrow"><span class="dot"></span><span>EMPTY</span></div>' +
                            '<h1 class="ti-hero-title">' + safeText(t('home_empty_title')) + '</h1>' +
                            '<p class="ti-hero-sub">' + safeText(t('home_empty_sub')) + '</p>' +
                            '<div style="margin-top:22px">' +
                                '<button class="btn btn-primary" id="ti-home-create">' +
                                    '<span class="material-symbols-outlined" style="font-size:14px">add</span>' +
                                    '<span data-i18n="home_create_env">建立新環境</span>' +
                                '</button>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>';
            var c = document.getElementById('ti-home-create');
            if (c) c.addEventListener('click', function() { App.navigate('environments'); });
            return;
        }

        var st = e.status;
        var statusLabel = st === 'running' ? 'RUNNING' : st === 'starting' ? 'STARTING' : 'READY';
        var subText = st === 'running'
            ? ('ComfyUI 已在 port ' + e.port + ' 運行。點擊右側按鈕在瀏覽器中開啟。')
            : '一鍵啟動 ComfyUI — 你的模型與輸出都已經準備好。';

        var launchHtml = '';
        if (st === 'stopped') {
            launchHtml =
                '<button class="ti-launch-btn go" id="ti-home-launch">' +
                    '<span class="material-symbols-outlined" style="font-size:20px">play_arrow</span>' +
                    '<span>' + safeText(t('home_btn_launch')) + '</span>' +
                '</button>';
        } else if (st === 'starting') {
            launchHtml =
                '<button class="ti-launch-btn starting">' +
                    '<span>' + safeText(t('home_launch_starting')) + '</span>' +
                '</button>';
        } else if (st === 'running') {
            launchHtml =
                '<button class="ti-launch-btn go" id="ti-home-open-browser">' +
                    '<span class="material-symbols-outlined" style="font-size:18px">open_in_new</span>' +
                    '<span>' + safeText(t('home_btn_open_browser')) + '</span>' +
                '</button>' +
                '<button class="ti-launch-btn stop" id="ti-home-stop">' +
                    '<span class="material-symbols-outlined" style="font-size:16px">stop</span>' +
                    '<span>' + safeText(t('home_btn_stop')) + '</span>' +
                '</button>' +
                '<div class="ti-launch-url">' +
                    '<span class="label">URL</span>' +
                    '<span class="val">127.0.0.1:' + e.port + '</span>' +
                '</div>';
        }

        el.innerHTML =
            '<div class="ti-hero">' +
                '<div class="ti-hero-grid-bg"></div>' +
                '<div class="ti-hero-glow"></div>' +
                '<div class="ti-hero-inner">' +
                    '<div class="ti-hero-col">' +
                        '<div class="ti-hero-eyebrow">' +
                            '<span class="dot ' + (st === 'running' ? 'on' : '') + '"></span>' +
                            '<span>當前環境 · ' + statusLabel + '</span>' +
                        '</div>' +
                        '<h1 class="ti-hero-title">' +
                            safeText(t('home_hello')) + '<br/>' +
                            '<span class="env-name">' + safeText(e.name) + '</span> ' +
                            (st === 'running' ? safeText(t('home_is_running')) : safeText(t('home_ready_to_launch'))) +
                        '</h1>' +
                        '<p class="ti-hero-sub">' + safeText(subText) + '</p>' +
                        '<div class="ti-hero-meta">' +
                            metaKV('Python', e.python) +
                            metaKV('CUDA', e.cuda) +
                            metaKV('PyTorch', e.pytorch) +
                            metaKV('Plugins', String(e.plugins)) +
                        '</div>' +
                    '</div>' +
                    '<div class="ti-launch-panel">' +
                        '<div class="ti-launch-state ' + st + '">' +
                            '<span class="led"></span>' +
                            '<span>' + safeText(launchStateLabel(st)) + '</span>' +
                            (st === 'running' ? '<span class="port">:' + e.port + '</span>' : '') +
                        '</div>' +
                        launchHtml +
                        '<div class="ti-launch-small">' +
                            '<button class="btn btn-secondary" data-ti-open="output">' +
                                '<span class="material-symbols-outlined" style="font-size:13px">image</span>' +
                                '<span>' + safeText(t('home_btn_output')) + '</span>' +
                            '</button>' +
                            '<button class="btn btn-secondary" data-ti-open="models">' +
                                '<span class="material-symbols-outlined" style="font-size:13px">deployed_code</span>' +
                                '<span>' + safeText(t('home_btn_models')) + '</span>' +
                            '</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';

        // Bindings
        bind('ti-home-launch', 'click', function() { doLaunch(); });
        bind('ti-home-stop', 'click', function() { doStop(); });
        bind('ti-home-open-browser', 'click', function() { doOpenBrowser(); });

        var folderBtns = el.querySelectorAll('[data-ti-open]');
        folderBtns.forEach(function(b) {
            b.addEventListener('click', function() {
                openFolder(b.getAttribute('data-ti-open'));
            });
        });
    }

    function renderTiles() {
        var el = document.getElementById('ti-home-tiles');
        if (!el) return;
        var e = state.activeEnv;
        var envName = e ? e.name : '—';
        var pluginCount = e ? e.plugins : 0;
        el.innerHTML = [
            tile('image', t('home_btn_output'), './output', 'output'),
            tile('deployed_code', t('home_btn_models'), 'shared/models', 'models'),
            tile('folder_open', t('home_btn_root'), './environments/' + envName, 'root'),
            tile('extension', t('home_btn_nodes'), pluginCount + ' plugins', 'plugins-nav'),
        ].join('');
        var tiles = el.querySelectorAll('.ti-tile');
        tiles.forEach(function(tn) {
            tn.addEventListener('click', function() {
                var a = tn.getAttribute('data-ti-tile');
                if (a === 'plugins-nav') App.navigate('plugins');
                else openFolder(a === 'root' ? '' : a);
            });
        });
    }

    function tile(icon, title, sub, action) {
        return '<div class="ti-tile" data-ti-tile="' + escapeAttr(action) + '">' +
            '<div class="ti-tile-icon"><span class="material-symbols-outlined">' + icon + '</span></div>' +
            '<div class="ti-tile-title">' + safeText(title) + '</div>' +
            '<div class="ti-tile-sub">' + safeText(sub) + '</div>' +
        '</div>';
    }

    function renderStats() {
        var el = document.getElementById('ti-home-stats');
        if (!el) return;
        var e = state.activeEnv;

        var gpu = state.gpu || '—';
        var vramUsed = state.vramUsed || 0;
        var vramTotal = state.vramTotal || 0;
        var vramPct = vramTotal ? Math.round((vramUsed / vramTotal) * 100) : 0;

        el.innerHTML =
            statCell(t('home_stat_gpu'), gpu, e ? (e.cuda || '') : '') +
            statCell(t('home_stat_vram'),
                vramTotal ? (vramUsed.toFixed(1) + '<span class="unit">/ ' + vramTotal + ' GB</span>') : '—',
                vramTotal ? ('<span style="color:var(--accent)">● ' + vramPct + '%</span>') : '') +
            statCell(t('home_stat_size'), e ? e.size : '—', 'venv + ComfyUI') +
            statCell(t('home_stat_last'), e ? e.lastUsed : '—', e && e.commit ? ('commit ' + e.commit) : '');

        // Ask backend for GPU info if available (non-blocking)
        if (window.BridgeAPI && BridgeAPI.detectGpu && !state._gpuRequested) {
            state._gpuRequested = true;
            BridgeAPI.detectGpu().then(function(info) {
                if (!info) return;
                state.gpu = info.name || info.gpu || info.model || '—';
                state.vramTotal = info.vram_total_gb || info.total_gb || info.vram_gb || 0;
                state.vramUsed = info.vram_used_gb || 0;
                renderStats();
            }).catch(function() { /* silent */ });
        }
    }

    function statCell(k, v, sub) {
        return '<div class="ti-stat">' +
            '<div class="ti-stat-k">' + safeText(k) + '</div>' +
            '<div class="ti-stat-v">' + v + '</div>' +
            '<div class="ti-stat-sub">' + (sub || '') + '</div>' +
        '</div>';
    }

    function renderLogs() {
        // The backend doesn't yet expose a streaming log API to the bridge
        // wrapper — keep the hero log section hidden and route users to the
        // Launcher page (which manages full logs) via the "完整日誌" button.
        var section = document.getElementById('ti-home-logs-section');
        if (section) section.style.display = 'none';
    }

    // ─── Sidebar env pill + run dot ───────────────────────────────

    function updateSidebarPill() {
        var pill = document.getElementById('ti-env-pill');
        if (!pill) return;
        var e = state.activeEnv;
        if (!e) { pill.style.display = 'none'; return; }
        pill.style.display = '';

        var dot = pill.querySelector('.ti-env-dot');
        dot.className = 'ti-env-dot ' + e.status;
        document.getElementById('ti-env-pill-name').textContent = e.name;
        var meta = document.getElementById('ti-env-pill-meta');
        meta.textContent = e.status === 'running'
            ? (':' + e.port + ' · 運行中')
            : e.status === 'starting' ? '啟動中...' : e.branch;

        if (!pill._tiBound) {
            pill._tiBound = true;
            pill.addEventListener('click', function(ev) {
                if (ev.target.closest('.ti-env-menu')) return;
                togglePillMenu();
            });
        }
        renderPillMenu();
    }

    function togglePillMenu() {
        var pill = document.getElementById('ti-env-pill');
        var menu = document.getElementById('ti-env-menu');
        var open = pill.classList.toggle('open');
        menu.style.display = open ? '' : 'none';
        if (open) {
            setTimeout(function() {
                var off = function(e) {
                    if (!pill.contains(e.target)) {
                        pill.classList.remove('open');
                        menu.style.display = 'none';
                        document.removeEventListener('click', off, true);
                    }
                };
                document.addEventListener('click', off, true);
            }, 0);
        }
    }

    function renderPillMenu() {
        var menu = document.getElementById('ti-env-menu');
        if (!menu) return;
        menu.innerHTML = state.envs.map(function(e) {
            return '<div class="ti-env-menu-item" data-name="' + escapeAttr(e.name) + '">' +
                '<span class="ti-env-dot ' + e.status + '"></span>' +
                '<span class="name">' + safeText(e.name) + '</span>' +
                '<span class="branch">' + safeText(e.branch || '') + '</span>' +
            '</div>';
        }).join('') +
        '<div class="ti-env-menu-sep"></div>' +
        '<div class="ti-env-menu-action" id="ti-env-menu-new">' +
            '<span class="material-symbols-outlined" style="font-size:14px">add</span>' +
            '<span>建立新環境</span>' +
        '</div>';

        menu.querySelectorAll('.ti-env-menu-item').forEach(function(it) {
            it.addEventListener('click', function(ev) {
                ev.stopPropagation();
                var name = it.getAttribute('data-name');
                switchEnv(name);
                document.getElementById('ti-env-pill').classList.remove('open');
                menu.style.display = 'none';
            });
        });
        var act = document.getElementById('ti-env-menu-new');
        if (act) act.addEventListener('click', function(ev) {
            ev.stopPropagation();
            App.navigate('environments');
            document.getElementById('ti-env-pill').classList.remove('open');
            menu.style.display = 'none';
        });
    }

    function updateNavRunDot() {
        var d = document.getElementById('ti-nav-run-dot');
        if (!d) return;
        d.classList.toggle('on', !!state.runningEnv);
    }

    // ─── Actions ──────────────────────────────────────────────────

    function switchEnv(name) {
        var e = findEnv(name);
        if (!e) return;
        state.activeEnv = e;
        localStorage.setItem('ti_active_env', name);
        App.showToast(t('home_switched_to').replace('{0}', name), 'info');
        renderAll();
    }

    function doLaunch() {
        if (!state.activeEnv) return;
        var name = state.activeEnv.name;

        // If another env is running, stop it first (optimistic UI)
        if (state.runningEnv && state.runningEnv.name !== name) {
            var prev = state.runningEnv.name;
            if (BridgeAPI.stopComfyUI) BridgeAPI.stopComfyUI(prev).catch(function(){});
            var prevEnv = findEnv(prev);
            if (prevEnv) prevEnv.status = 'stopped';
        }

        state.activeEnv.status = 'starting';
        state.runningEnv = state.activeEnv;
        renderAll();
        App.showToast(t('home_starting').replace('{0}', name), 'info');

        if (!BridgeAPI.startComfyUI) {
            App.showToast('startComfyUI not available', 'error');
            return;
        }
        BridgeAPI.startComfyUI(name, state.activeEnv.port || '').then(function() {
            loadEnvs().then(renderAll);
            App.showToast(t('home_started').replace('{0}', name), 'success');
        }).catch(function(err) {
            if (state.activeEnv) state.activeEnv.status = 'stopped';
            state.runningEnv = null;
            renderAll();
            App.showToast(String(err || 'Launch failed'), 'error');
        });
    }

    function doStop() {
        if (!state.activeEnv) return;
        var name = state.activeEnv.name;
        if (!BridgeAPI.stopComfyUI) {
            App.showToast('stopComfyUI not available', 'error');
            return;
        }
        BridgeAPI.stopComfyUI(name).then(function() {
            loadEnvs().then(renderAll);
            App.showToast(t('home_stopped').replace('{0}', name), 'info');
        }).catch(function(err) {
            App.showToast(String(err || 'Stop failed'), 'error');
        });
    }

    function doOpenBrowser() {
        if (!state.activeEnv) return;
        if (BridgeAPI.openBrowser) {
            BridgeAPI.openBrowser(state.activeEnv.port || 8188);
        } else if (BridgeAPI.openUrl) {
            BridgeAPI.openUrl('http://127.0.0.1:' + (state.activeEnv.port || 8188));
        }
    }

    function openFolder(kind) {
        if (!state.activeEnv) {
            App.showToast(t('home_no_env_selected'), 'info');
            return;
        }
        if (!BridgeAPI.openFolder) {
            App.showToast('openFolder not available', 'error');
            return;
        }
        var sub = '';
        if (kind === 'output') sub = 'output';
        else if (kind === 'models') sub = 'models';
        else if (kind === 'custom_nodes') sub = 'custom_nodes';
        BridgeAPI.openFolder(state.activeEnv.name, sub).catch(function() {
            App.showToast(t('home_folder_not_found'), 'error');
        });
    }

    // ─── Helpers ──────────────────────────────────────────────────

    function metaKV(k, v) {
        return '<div class="kv"><span class="k">' + safeText(k) + '</span><span class="v">' + safeText(v || '—') + '</span></div>';
    }

    function launchStateLabel(st) {
        if (st === 'running') return t('home_state_running');
        if (st === 'starting') return t('home_state_starting');
        return t('home_state_stopped');
    }

    function bind(id, evt, handler) {
        var el = document.getElementById(id);
        if (el) el.addEventListener(evt, handler);
    }

    function safeText(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function escapeAttr(s) { return safeText(s); }

    // Expose a small API so App / command palette can hook in
    window.HomePageAPI = {
        getActiveEnv: function() { return state.activeEnv; },
        getRunningEnv: function() { return state.runningEnv; },
        getEnvs: function() { return state.envs; },
        launch: doLaunch,
        stop: doStop,
        openBrowser: doOpenBrowser,
        openFolder: openFolder,
        refresh: function() { return loadEnvs().then(renderAll); },
    };

    App.registerPage('home', { render: render });
})();
