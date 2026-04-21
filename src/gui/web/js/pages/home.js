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
                '<div id="ti-home-addons-section">' +
                    '<div class="ti-section-head">' +
                        '<h2>' + safeText(t('addonRegistry.tabTitle')) + '</h2>' +
                        '<div class="line"></div>' +
                    '</div>' +
                    '<div id="ti-home-addon-cards" class="ti-addon-grid"></div>' +
                '</div>' +
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
            renderAddons();
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
                var name = typeof r === 'string' ? r : (r.env_name || r.name || r.env || '');
                if (!name) return;
                runMap[name] = r && typeof r === 'object' ? r : { name: name };
            });
            return envs.map(function(e) {
                var r = runMap[e.name];
                if (r) {
                    e.status = r.status === 'starting' ? 'starting' : 'running';
                    if (r.port) e.port = r.port;
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
            torch_pack: e.torch_pack || null,
            installed_addons: Array.isArray(e.installed_addons) ? e.installed_addons : [],
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
            ? t('home_sub_running').replace('{0}', e.port)
            : t('home_sub_ready');

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
                            '<span>' + safeText(t('home_current_env_label')) + ' · ' + statusLabel + '</span>' +
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
            ? t('home_pill_meta_running').replace('{0}', e.port)
            : e.status === 'starting' ? t('home_pill_meta_starting') : e.branch;

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
            '<span>' + safeText(t('home_create_new_env')) + '</span>' +
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

    // ─── Addon Registry ───────────────────────────────────────────

    // State for addon rendering
    var _addonState = {
        addons: [],
        packs: [],
        currentPackId: null,  // active pack for the current env
        envName: null,
    };

    function renderAddons() {
        var envName = state.activeEnv ? state.activeEnv.name : null;
        var section = document.getElementById('ti-home-addons-section');
        var cardsEl = document.getElementById('ti-home-addon-cards');
        if (!section || !cardsEl) return;

        if (!envName) {
            section.style.display = 'none';
            return;
        }
        section.style.display = '';
        cardsEl.innerHTML = '<div style="font-size:12px;color:var(--text-4);padding:8px 0">' + safeText(t('loading')) + '</div>';

        Promise.all([
            BridgeAPI.listAddons(),
            BridgeAPI.listTorchPacks(),
        ]).then(function(results) {
            var addonsResult = results[0];
            var packsResult = results[1];
            var rawAddons = (addonsResult && addonsResult.addons) || addonsResult || [];
            // Merge per-env installed state: list_addons() returns the global
            // registry; whether each addon is installed lives on the env
            // (env_meta.json → installed_addons). Flag each registry entry
            // whose id appears in the active env's installed_addons list.
            var installedIds = {};
            var activeEnvForAddons = state.activeEnv;
            if (activeEnvForAddons && Array.isArray(activeEnvForAddons.installed_addons)) {
                activeEnvForAddons.installed_addons.forEach(function(entry) {
                    var id = entry && (entry.id || entry);
                    if (id) installedIds[id] = true;
                });
            }
            _addonState.addons = rawAddons.map(function(a) {
                return Object.assign({}, a, { installed: !!installedIds[a.id] });
            });
            _addonState.packs = (packsResult && packsResult.packs) || packsResult || [];
            _addonState.envName = envName;

            // Determine current pack from env.torch_pack (set by Python Environment dataclass).
            // Fall back to cuda_tag heuristic for legacy envs that predate torch_pack.
            var activeEnv = state.activeEnv;
            var currentPackId = activeEnv && activeEnv.torch_pack ? activeEnv.torch_pack : null;
            if (!currentPackId && _addonState.packs.length > 0) {
                // Legacy fallback: match by cuda tag substring
                var envCuda = (activeEnv && (activeEnv.cuda || '')).toLowerCase();
                var matched = _addonState.packs.find(function(p) {
                    return p.cuda_tag && envCuda && envCuda.indexOf(p.cuda_tag.toLowerCase()) !== -1;
                });
                currentPackId = matched ? matched.id : (_addonState.packs[0] ? _addonState.packs[0].id : null);
            }
            _addonState.currentPackId = currentPackId;

            _renderAddonCards(cardsEl);
        }).catch(function(e) {
            cardsEl.innerHTML = '<div style="font-size:12px;color:var(--danger);padding:8px 0">' + safeText(t('error') + ': ' + String(e)) + '</div>';
        });
    }

    function _renderAddonCards(cardsEl) {
        var addons = _addonState.addons;
        var packs = _addonState.packs;
        var currentPackId = _addonState.currentPackId;
        var envName = _addonState.envName;

        if (!addons.length) {
            cardsEl.innerHTML = '<div style="font-size:12px;color:var(--text-4);padding:8px 0">—</div>';
            return;
        }

        // Build a pack id→label map for display
        var packMap = {};
        packs.forEach(function(p) { packMap[p.id] = p.label || p.id; });

        cardsEl.innerHTML = '';
        addons.forEach(function(addon) {
            var card = document.createElement('div');
            card.className = 'ti-addon-card';

            var addonLabel = addon.label || addon.id || '?';
            var addonDesc = addon.description || '';
            var isInstalled = !!addon.installed;
            var compatPacks = addon.compatible_packs || [];
            var packPinned = !!addon.pack_pinned;
            var riskNote = addon.risk_note || '';

            // Determine button state
            var btnHtml = '';
            var needsSwitchPackId = null;
            var needsSwitchPackLabel = '';

            if (isInstalled) {
                // Installed: show Uninstall button
                btnHtml = '<button class="btn btn-ghost addon-btn" data-action="uninstall" style="font-size:12px;padding:4px 10px">' +
                    safeText(t('addonCard.uninstall')) + '</button>';
            } else if (compatPacks.length === 0) {
                // Not compatible with any known pack
                btnHtml = '<button class="btn btn-ghost addon-btn" disabled style="font-size:12px;padding:4px 10px;opacity:0.5">' +
                    safeText(t('addonCard.notCompatible')) + '</button>';
            } else if (currentPackId && compatPacks.indexOf(currentPackId) !== -1) {
                // Compatible with current pack — direct install
                btnHtml = '<button class="btn btn-primary addon-btn" data-action="install" style="font-size:12px;padding:4px 10px">' +
                    safeText(t('plugin_install')) + '</button>';
            } else {
                // Needs pack switch — Task 12: needs-switch state
                // GPU-aware selection: prefer the compatible pack whose cuda_tag matches the env's cuda string
                var activeEnvForSwitch = state.activeEnv;
                if (activeEnvForSwitch && activeEnvForSwitch.cuda && Array.isArray(packs)) {
                    var envCudaForSwitch = activeEnvForSwitch.cuda.toLowerCase();
                    var bestMatch = packs.find(function(p) {
                        return compatPacks.indexOf(p.id) !== -1
                            && p.cuda_tag && envCudaForSwitch.indexOf(p.cuda_tag.toLowerCase()) !== -1;
                    });
                    if (bestMatch) needsSwitchPackId = bestMatch.id;
                }
                if (!needsSwitchPackId) needsSwitchPackId = compatPacks[0]; // fallback
                needsSwitchPackLabel = packMap[needsSwitchPackId] || needsSwitchPackId || '?';
                var btnLabel = t('addonCard.installNeedsSwitch').replace('{pack}', needsSwitchPackLabel);
                btnHtml = '<button class="btn btn-secondary addon-btn addon-needs-switch" data-action="needs-switch" ' +
                    'style="font-size:12px;padding:4px 10px;border-color:oklch(0.82 0.17 128 / 0.4);color:oklch(0.82 0.17 128)">' +
                    safeText(btnLabel) + '</button>';
            }

            var packPinnedBadge = packPinned
                ? '<span style="font-size:10px;padding:1px 6px;border-radius:4px;background:var(--accent-glow);color:var(--accent);font-family:var(--font-mono);margin-left:4px">' +
                    safeText(t('addonRegistry.packPinned')) + '</span>'
                : '';

            card.innerHTML =
                '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">' +
                    '<div style="min-width:0">' +
                        '<div style="font-size:13px;font-weight:500;color:var(--text-0)">' + safeText(addonLabel) + packPinnedBadge + '</div>' +
                        (addonDesc ? '<div style="font-size:11px;color:var(--text-3);margin-top:2px;line-height:1.4">' + safeText(addonDesc) + '</div>' : '') +
                        (riskNote ? '<div style="font-size:11px;color:var(--warn);margin-top:4px">' + safeText(t('addonSwitch.riskNote') + ' ' + riskNote) + '</div>' : '') +
                    '</div>' +
                    '<div style="flex-shrink:0">' + btnHtml + '</div>' +
                '</div>';

            // Bind button actions
            var btn = card.querySelector('.addon-btn');
            if (btn) {
                var action = btn.getAttribute('data-action');
                if (action === 'install') {
                    btn.addEventListener('click', function() {
                        _doDirectInstall(envName, addon, btn);
                    });
                } else if (action === 'needs-switch') {
                    (function(targetPackId, targetPackLabel) {
                        btn.addEventListener('click', function() {
                            openAddonSwitchInstallDialog(envName, addon, targetPackId, targetPackLabel, packs, currentPackId, packMap);
                        });
                    })(needsSwitchPackId, needsSwitchPackLabel);
                }
            }

            cardsEl.appendChild(card);
        });
    }

    function _doDirectInstall(envName, addon, btn) {
        if (btn) btn.disabled = true;
        var progressId = 'addon-install-' + Date.now();
        App.showProgress(progressId, safeText(t('addonSwitch.stage2').replace('{addon}', addon.label || addon.id)));
        BridgeAPI.installAddon(envName, addon.id, function(msg) {
            App.updateProgress(progressId, msg.step || '', msg.percent || 0, msg.detail || '');
        }).then(function() {
            App.hideProgress(progressId, 'success');
            App.showToast(safeText(addon.label || addon.id) + ' installed.', 'success');
            renderAddons();
        }).catch(function(e) {
            App.hideProgress(progressId, 'error');
            App.showToast(t('error') + ': ' + String(e), 'error');
            if (btn) btn.disabled = false;
        });
    }

    // ─── Task 13: AddonSwitchInstallDialog ────────────────────────

    function openAddonSwitchInstallDialog(envName, addon, targetPackId, targetPackLabel, packs, currentPackId, packMap) {
        var currentPackLabel = (currentPackId && packMap[currentPackId]) || currentPackId || '—';
        var addonLabel = addon.label || addon.id;

        // Build side-effects list
        var removedPinned = [];
        // Find addons that are pack_pinned and compatible only with current pack (will be removed)
        (_addonState.addons || []).forEach(function(a) {
            if (a.pack_pinned && a.installed) {
                var compatPacks = a.compatible_packs || [];
                if (compatPacks.indexOf(targetPackId) === -1) {
                    removedPinned.push(a.label || a.id);
                }
            }
        });

        var sideEffectsHtml =
            '<div style="font-size:12px;color:var(--text-2);margin-top:10px">' +
                '<div style="font-size:11px;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:0.08em;color:var(--text-4);margin-bottom:6px">' +
                    safeText(t('addonSwitch.sideEffectsHeader')) +
                '</div>' +
                '<div style="line-height:1.8">' +
                    '<div>' + safeText(t('addonSwitch.snapshot')) + '</div>' +
                    '<div>' + safeText(t('addonSwitch.reinstallTorch')) + '</div>' +
                    '<div>' + safeText(t('addonSwitch.reapplyPinned')) + '</div>' +
                    (removedPinned.length > 0
                        ? '<div style="color:var(--warn)">' + safeText(t('addonSwitch.removePinned').replace('{list}', removedPinned.join(', '))) + '</div>'
                        : '') +
                    '<div style="color:var(--accent)">' + safeText(t('addonSwitch.installTarget').replace('{addon}', addonLabel)) + '</div>' +
                '</div>' +
            '</div>';

        var etaHtml = '<div style="font-size:11px;color:var(--text-4);margin-top:10px;font-style:italic">' +
            safeText(t('addonSwitch.etaHeader'));
        if (addon.requires_compile) {
            etaHtml += ' +20min (CUDA compile)';
        }
        etaHtml += '</div>';

        var riskHtml = addon.risk_note
            ? '<div style="font-size:11px;color:var(--warn);margin-top:8px">' +
                safeText(t('addonSwitch.riskNote') + ' ' + addon.risk_note) + '</div>'
            : '';

        var bodyHtml =
            '<div>' +
                '<div style="font-size:13px;color:var(--text-1)">' +
                    safeText(t('addonSwitch.currentEnv').replace('{env}', envName).replace('{pack}', currentPackLabel)) +
                '</div>' +
                '<div style="font-size:13px;color:var(--accent);margin-top:2px">' +
                    safeText(t('addonSwitch.targetPack').replace('{pack}', targetPackLabel)) +
                '</div>' +
                sideEffectsHtml +
                etaHtml +
                riskHtml +
            '</div>';

        App.showModal({
            title: t('addonSwitch.title').replace('{addon}', addonLabel),
            body: bodyHtml,
            buttons: [
                { text: t('addonSwitch.cancel'), class: 'btn-secondary' },
                {
                    text: t('addonSwitch.confirm'),
                    class: 'btn-primary',
                    closeModal: true,
                    onClick: function() {
                        _runSwitchAndInstall(envName, addon, targetPackId, targetPackLabel);
                    }
                },
            ],
        });
    }

    function _runSwitchAndInstall(envName, addon, targetPackId, targetPackLabel) {
        var addonLabel = addon.label || addon.id;
        var progressId = 'switch-install-' + Date.now();

        // Stage tracking: 0-60% = switch, 60-100% = install
        App.showProgress(progressId, safeText(t('addonSwitch.stage1')));

        BridgeAPI.switchPackAndInstallAddon(envName, targetPackId, addon.id, function(msg) {
            var rawPct = typeof msg.percent === 'number' ? msg.percent : 0;
            var stagePct, stageLabel;
            // Backend reports 0-100 for each stage; we'll use failed_at or step prefix to determine stage
            // If the step name contains 'install' or percent is above the midpoint of total, we're in stage 2
            if (msg.stage === 2 || (msg.step && msg.step.indexOf('install') !== -1)) {
                stagePct = 60 + Math.round(rawPct * 0.4);
                stageLabel = t('addonSwitch.stage2').replace('{addon}', addonLabel);
            } else {
                stagePct = Math.round(rawPct * 0.6);
                stageLabel = t('addonSwitch.stage1');
            }
            App.updateProgress(progressId, stageLabel, stagePct, msg.detail || '');
        }).then(function(result) {
            // result: {ok, noop, removed_addons, installed_addon, failed_at, error}
            if (result && result.failed_at === 'switch') {
                // Switch failed
                App.hideProgress(progressId, 'error');
                App.showToast(t('addonSwitch.failedSwitchTitle') + ': ' + (result.error || ''), 'error');
            } else if (result && result.failed_at === 'install') {
                // Pack switched but install failed — show 3-button recovery dialog
                App.hideProgress(progressId, 'error');
                _showInstallFailureDialog(envName, addon, targetPackId, targetPackLabel, result);
            } else {
                // Full success
                App.updateProgress(progressId, t('addonSwitch.stage2').replace('{addon}', addonLabel), 100, '');
                App.hideProgress(progressId, 'success');
                App.showToast(addonLabel + ' installed on ' + targetPackLabel + '.', 'success');
                renderAddons();
                if (result && result.removed_addons && result.removed_addons.length) {
                    maybeShowReinstallDialog(envName, result.removed_addons, targetPackId, targetPackLabel, addon.id);
                }
            }
        }).catch(function(e) {
            App.hideProgress(progressId, 'error');
            App.showToast(t('error') + ': ' + String(e), 'error');
        });
    }

    function _showInstallFailureDialog(envName, addon, targetPackId, targetPackLabel, result) {
        var addonLabel = addon.label || addon.id;
        var errMsg = result.error || '?';

        var bodyHtml =
            '<p style="font-size:13px;color:var(--text-1)">' +
                safeText(t('addonSwitch.failedInstallMessage')
                    .replace('{pack}', targetPackLabel)
                    .replace('{addon}', addonLabel)
                    .replace('{error}', errMsg)) +
            '</p>';

        // We need a 3-button dialog. App.showModal supports arbitrary buttons.
        App.showModal({
            title: t('addonSwitch.failedInstallTitle'),
            body: bodyHtml,
            buttons: [
                {
                    text: t('addonSwitch.restoreSnapshot'),
                    class: 'btn-secondary',
                    onClick: function() {
                        _restoreLatestSnapshot(envName);
                    }
                },
                {
                    text: t('addonSwitch.retryInstall'),
                    class: 'btn-primary',
                    onClick: function() {
                        _doDirectInstall(envName, addon, null);
                    }
                },
                {
                    text: t('addonSwitch.keepCurrent'),
                    class: 'btn-ghost',
                    onClick: function() {
                        renderAddons();
                    }
                },
            ],
        });
    }

    function maybeShowReinstallDialog(envName, removedAddonIds, newPackId, newPackLabel, justInstalledId) {
        // Filter to addons that are compatible with the new pack and weren't just installed
        var eligible = (_addonState.addons || []).filter(function(a) {
            if (a.id === justInstalledId) return false;
            if (removedAddonIds.indexOf(a.id) === -1) return false;
            var compatPacks = a.compatible_packs || [];
            return compatPacks.indexOf(newPackId) !== -1;
        });

        if (!eligible.length) return;

        // Build checkbox list HTML
        var checkboxesHtml = '<div style="margin-top:12px;display:flex;flex-direction:column;gap:8px;">';
        eligible.forEach(function(a) {
            var desc = a.description ? ' \u2014 ' + safeText(a.description) : '';
            checkboxesHtml +=
                '<label style="display:flex;align-items:baseline;gap:8px;cursor:pointer;font-size:13px;">' +
                '<input type="checkbox" class="reinstall-cb" data-id="' + safeText(a.id) + '" checked style="flex-shrink:0;margin-top:2px;">' +
                '<span>' + safeText(a.label || a.id) + desc + '</span>' +
                '</label>';
        });
        checkboxesHtml += '</div>';

        var bodyHtml =
            '<p style="font-size:13px;color:var(--text-1)">' +
                safeText(t('addonReinstall.body').replace('{pack}', newPackLabel)) +
            '</p>' +
            checkboxesHtml;

        // Use static confirm label showing total eligible count (dynamic label requires
        // post-render DOM wiring; acceptable fallback per spec)
        var confirmLabel = t('addonReinstall.confirm').replace('{n}', String(eligible.length));

        App.showModal({
            title: t('addonReinstall.title'),
            body: bodyHtml,
            buttons: [
                {
                    text: t('addonReinstall.skip'),
                    class: 'btn-ghost',
                    onClick: function() { /* close, do nothing */ }
                },
                {
                    text: confirmLabel,
                    class: 'btn-primary',
                    closeModal: false,
                    onClick: function() {
                        var overlay = document.getElementById('modal-overlay');
                        var checked = [];
                        var cbs = overlay ? overlay.querySelectorAll('.reinstall-cb') : [];
                        for (var i = 0; i < cbs.length; i++) {
                            if (cbs[i].checked) checked.push(cbs[i].getAttribute('data-id'));
                        }
                        App.hideModal ? App.hideModal() : (function() {
                            document.getElementById('modal-overlay').classList.add('hidden');
                        })();
                        if (!checked.length) return;

                        var progressId = 'reinstall-' + Date.now();
                        App.showProgress(progressId, t('addonReinstall.title'));
                        BridgeAPI.reinstallAddons(envName, checked, function(msg) {
                            App.updateProgress(progressId, msg.step || t('addonReinstall.title'), msg.percent || 0, msg.detail || '');
                        }).then(function(result) {
                            App.hideProgress(progressId, 'success');
                            var results = (result && result.results) || [];
                            var total = results.length;
                            var ok = results.filter(function(r) { return r.ok; }).length;
                            var toastKey = ok === total ? 'addonReinstall.toastSuccess' : 'addonReinstall.toastPartial';
                            App.showToast(
                                t(toastKey).replace('{done}', String(ok)).replace('{total}', String(total)),
                                ok === total ? 'success' : 'warning'
                            );
                            renderAddons();
                        }).catch(function(e) {
                            App.hideProgress(progressId, 'error');
                            App.showToast(t('error') + ': ' + String(e), 'error');
                        });
                    }
                },
            ],
        });
    }

    function _restoreLatestSnapshot(envName) {
        BridgeAPI.listSnapshots(envName).then(function(result) {
            var snapshots = (result && result.snapshots) || result || [];
            if (!snapshots.length) {
                App.showToast(t('snapshot_select_to_restore'), 'error');
                return;
            }
            // Use the most recent snapshot (first in list)
            var snap = snapshots[0];
            var progressId = 'restore-' + Date.now();
            App.showProgress(progressId, t('snapshot_restoring'));
            BridgeAPI.restoreSnapshot(envName, snap.id, function(msg) {
                App.updateProgress(progressId, msg.step || '', msg.percent || 0, msg.detail || '');
            }).then(function() {
                App.hideProgress(progressId, 'success');
                App.showToast(t('snapshot_restored').replace('{}', snap.id), 'success');
                renderAddons();
            }).catch(function(e) {
                App.hideProgress(progressId, 'error');
                App.showToast(t('error') + ': ' + String(e), 'error');
            });
        }).catch(function(e) {
            App.showToast(t('error') + ': ' + String(e), 'error');
        });
    }

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
