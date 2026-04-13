/**
 * app.js — SPA router, modal/toast utilities, and initialization
 */
const App = (function() {

    var currentPage = null;
    var pageModules = {};  // Registered by page scripts
    var _updateInfo = null;  // Cached update check result
    var _fallbackIconMap = {
        home: '⌂',
        dns: '◫',
        rocket_launch: '↗',
        extension: '✦',
        history: '⟲',
        inventory_2: '☰',
        translate: '文',
        progress_activity: '◌',
        refresh: '⟳',
        add: '+',
        content_copy: '⧉',
        edit: '✎',
        delete: '✕',
        play_arrow: '▶',
        stop: '■',
        open_in_new: '↗',
        download: '⇩',
        search: '⌕',
        close: '✕',
        cloud_download: '⇩',
        store: '◎',
        image: '◼',
        folder_open: '▣',
        deployed_code: '◇',
        recommend: '★',
        arrow_upward: '↑',
        arrow_right: '›',
        chevron_right: '›',
        expand_more: '⌄',
        expand_less: '⌃',
        open_in_browser: '↗',
        monitor_heart: '◉',
        memory: '▤',
        restore: '↺',
        add_a_photo: '⊞',
        update: '⟳',
        bug_report: '⚠',
        check_circle: '✓',
        block: '⊘',
        minimize: '—',
        settings: '⚙'
    };

    // ── Page Registration ──

    function registerPage(name, module) {
        pageModules[name] = module;
    }

    function _applyFallbackIcons() {
        if (!document.documentElement.classList.contains('material-icons-missing')) return;
        document.querySelectorAll('.material-symbols-outlined').forEach(function(el) {
            if (el.dataset.fallbackIcon) return;
            var token = (el.textContent || '').trim();
            el.dataset.fallbackIcon = _fallbackIconMap[token] || '•';
        });
    }

    function _setupMaterialIconFallback() {
        function isLoaded() {
            try {
                return !!(document.fonts && document.fonts.check
                    && document.fonts.check('16px "Material Symbols Outlined"'));
            } catch (e) {
                return false;
            }
        }

        // Avoid repeated class toggles that can cause visible repaint flicker.
        // We only apply fallback once if the icon font is still unavailable.
        if (isLoaded()) {
            return;
        }

        var applied = false;
        function applyOnceIfMissing() {
            if (applied) return;
            if (!isLoaded()) {
                document.documentElement.classList.add('material-icons-missing');
                _applyFallbackIcons();
            }
            applied = true;
        }

        // Give font loading a short grace period before switching to fallback.
        var timer = setTimeout(applyOnceIfMissing, 2500);
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(function() {
                clearTimeout(timer);
                applyOnceIfMissing();
            });
        }
    }

    // ── Navigation ──

    function navigate(pageName) {
        if (currentPage === pageName) return;
        currentPage = pageName;

        // Update sidebar
        document.querySelectorAll('.nav-item').forEach(function(item) {
            item.classList.toggle('active', item.dataset.page === pageName);
        });

        // Update page title
        var titleEl = document.getElementById('page-title');
        var sidebarKey = 'sidebar_' + (pageName === 'launcher' ? 'launch' : pageName);
        titleEl.dataset.i18n = sidebarKey;
        titleEl.textContent = t(sidebarKey);

        // Render page
        var container = document.getElementById('main-content');
        container.innerHTML = '';

        var module = pageModules[pageName];
        if (module && module.render) {
            module.render(container);
            _applyFallbackIcons();
        } else {
            container.innerHTML = '<div class="text-on-surface-variant text-center py-20">Page "' + pageName + '" not found</div>';
        }
    }

    // ── Modal System ──

    function showModal(options) {
        // options: { title, body (HTML string), buttons: [{text, class, onClick, closeModal}] }
        var overlay = document.getElementById('modal-overlay');
        var container = document.getElementById('modal-container');

        var buttonsHtml = '';
        if (options.buttons) {
            buttonsHtml = '<div class="flex justify-end gap-3 mt-6">';
            options.buttons.forEach(function(btn, i) {
                buttonsHtml += '<button class="btn ' + (btn.class || 'btn-secondary') + '" data-modal-btn="' + i + '">' + btn.text + '</button>';
            });
            buttonsHtml += '</div>';
        }

        container.innerHTML = '<div class="modal-enter">'
            + '<div class="px-6 py-4 border-b border-outline/20">'
            + '<h3 class="font-headline text-sm font-bold uppercase tracking-wider">' + (options.title || '') + '</h3>'
            + '</div>'
            + '<div class="px-6 py-5">'
            + (options.body || '')
            + buttonsHtml
            + '</div>'
            + '</div>';

        // Bind button clicks
        if (options.buttons) {
            options.buttons.forEach(function(btn, i) {
                var el = container.querySelector('[data-modal-btn="' + i + '"]');
                if (el) {
                    el.addEventListener('click', function() {
                        if (btn.onClick) btn.onClick();
                        if (btn.closeModal !== false) hideModal();
                    });
                }
            });
        }

        // Close on overlay click
        overlay.onclick = function(e) {
            if (e.target === overlay) hideModal();
        };

        overlay.classList.remove('hidden');
    }

    function hideModal() {
        document.getElementById('modal-overlay').classList.add('hidden');
    }

    // ── Confirm Dialog ──

    function confirm(message, title) {
        return new Promise(function(resolve) {
            showModal({
                title: title || t('confirm'),
                body: '<p class="text-on-surface-variant">' + message + '</p>',
                buttons: [
                    { text: t('cancel'), class: 'btn-secondary', onClick: function() { resolve(false); } },
                    { text: t('yes'), class: 'btn-primary', onClick: function() { resolve(true); } },
                ],
            });
        });
    }

    // ── Bug Collection ──

    var _bugs = [];
    var _bugUnreadCount = 0;
    var _BUG_MAX = 100;

    function addBug(entry) {
        _bugs.unshift(entry);
        if (_bugs.length > _BUG_MAX) _bugs.pop();
        _bugUnreadCount++;
        _updateBugBadge();
    }

    function getBugs() { return _bugs; }

    function clearBugs() {
        _bugs = [];
        _bugUnreadCount = 0;
        _updateBugBadge();
    }

    function clearBugUnread() {
        _bugUnreadCount = 0;
        _updateBugBadge();
    }

    function _updateBugBadge() {
        var badge = document.getElementById('bug-report-badge');
        if (!badge) return;
        if (_bugUnreadCount > 0) {
            badge.textContent = _bugUnreadCount > 99 ? '99+' : _bugUnreadCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    function _recordBug(messageOrError, errorObj, origin) {
        var pageName = currentPage || 'unknown';
        var sidebarKey = 'sidebar_' + (pageName === 'launcher' ? 'launch' : pageName);
        var message = '';
        var stack = '';
        var errorType = '';
        var fileInfo = '';

        // Normalize input
        var err = errorObj;
        if (messageOrError instanceof Error) {
            err = messageOrError;
            message = err.message || String(err);
        } else if (messageOrError && typeof messageOrError === 'object' && messageOrError.message) {
            message = String(messageOrError.message);
            if (!err && messageOrError.stack) { err = messageOrError; }
        } else {
            message = String(messageOrError);
        }

        if (err) {
            if (err.name) errorType = err.name;
            if (err.stack) stack = String(err.stack);
            if (err.fileName || err.filename) {
                fileInfo = (err.fileName || err.filename) + ':' + (err.lineNumber || err.lineno || '?') + ':' + (err.columnNumber || err.colno || '?');
            }
        }

        // Try to pull file:line from the stack's first frame if not provided directly
        if (!fileInfo && stack) {
            var m = stack.match(/at\s+(?:[^()\s]+\s+\()?([^()\n]+):(\d+):(\d+)/);
            if (m) fileInfo = m[1] + ':' + m[2] + ':' + m[3];
        }

        addBug({
            timestamp: new Date().toLocaleString(),
            source: t(sidebarKey),
            source_page: pageName,
            origin: origin || 'unknown',
            error_type: errorType,
            message: message,
            file_info: fileInfo,
            stack: stack,
            user_agent: (navigator && navigator.userAgent) || '',
            app_version: (window.APP_VERSION || ''),
        });
    }

    // Global error handlers — capture everything, not only explicit toast('error')
    window.addEventListener('error', function(ev) {
        if (!ev) return;
        var err = ev.error || null;
        var msg = ev.message || (err && err.message) || 'Unknown error';
        var fallbackFile = ev.filename ? ev.filename + ':' + (ev.lineno || '?') + ':' + (ev.colno || '?') : '';
        if (err) {
            _recordBug(err, err, 'window.onerror');
        } else {
            addBug({
                timestamp: new Date().toLocaleString(),
                source: t('sidebar_' + ((currentPage || 'unknown') === 'launcher' ? 'launch' : (currentPage || 'unknown'))),
                source_page: currentPage || 'unknown',
                origin: 'window.onerror',
                error_type: '',
                message: String(msg),
                file_info: fallbackFile,
                stack: '',
                user_agent: (navigator && navigator.userAgent) || '',
                app_version: (window.APP_VERSION || ''),
            });
        }
    });

    window.addEventListener('unhandledrejection', function(ev) {
        var reason = ev && ev.reason;
        if (reason instanceof Error) {
            _recordBug(reason, reason, 'unhandledrejection');
        } else {
            _recordBug(reason === undefined ? 'Unhandled promise rejection' : reason, null, 'unhandledrejection');
        }
    });

    // ── Toast System ──

    function _dismissToast(toast) {
        toast.style.animation = 'toast-out 0.3s ease-in forwards';
        setTimeout(function() { toast.remove(); }, 300);
    }

    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration !== undefined ? duration : 4000;
        var container = document.getElementById('toast-container');
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;

        var msgSpan = document.createElement('span');
        msgSpan.className = 'toast-message';
        msgSpan.textContent = message;

        var closeBtn = document.createElement('span');
        closeBtn.className = 'toast-close';
        closeBtn.textContent = '\u00d7';
        closeBtn.addEventListener('click', function() { _dismissToast(toast); });

        toast.appendChild(msgSpan);
        toast.appendChild(closeBtn);
        container.appendChild(toast);

        // Collect error bugs
        if (type === 'error') {
            _recordBug(message, null, 'toast');
        }

        // Error toasts: no auto-dismiss. Others: auto-dismiss.
        if (type !== 'error') {
            setTimeout(function() { _dismissToast(toast); }, duration);
        }
    }

    // ── Loading State ──

    function setLoading(container, loading) {
        loading = loading !== undefined ? loading : true;
        if (loading) {
            var loader = document.createElement('div');
            loader.className = 'loading-overlay flex items-center justify-center py-8';
            loader.innerHTML = '<span class="material-symbols-outlined text-3xl text-primary spinner">progress_activity</span>';
            container.appendChild(loader);
        } else {
            var overlay = container.querySelector('.loading-overlay');
            if (overlay) overlay.remove();
        }
    }

    // ── Progress Panel System ──

    var _progressPanels = {};

    function showProgress(id, title) {
        var container = document.getElementById('progress-container');
        var panel = document.createElement('div');
        panel.id = 'progress-panel-' + id;
        panel.className = 'progress-panel';
        panel.innerHTML =
            '<div class="progress-panel-header">' +
                '<div class="progress-panel-title">' + title + '</div>' +
                '<div class="progress-panel-actions">' +
                    '<span class="progress-panel-percent-mini" id="progress-pct-mini-' + id + '">0%</span>' +
                    '<button class="progress-panel-toggle" title="Minimize">' +
                        '<span class="material-symbols-outlined text-[16px]">minimize</span>' +
                    '</button>' +
                '</div>' +
            '</div>' +
            '<div class="progress-panel-body">' +
                '<div class="progress-panel-step" id="progress-step-' + id + '">Preparing...</div>' +
                '<div class="progress-panel-bar-container">' +
                    '<div class="progress-panel-bar" id="progress-bar-' + id + '" style="width: 0%"></div>' +
                '</div>' +
                '<div class="progress-panel-footer">' +
                    '<span class="progress-panel-detail" id="progress-detail-' + id + '"></span>' +
                    '<span class="progress-panel-percent" id="progress-pct-' + id + '">0%</span>' +
                '</div>' +
            '</div>';

        // Minimize/expand toggle
        var minimized = false;
        var toggleBtn = panel.querySelector('.progress-panel-toggle');
        var bodyEl = panel.querySelector('.progress-panel-body');
        var miniPct = panel.querySelector('.progress-panel-percent-mini');
        miniPct.classList.add('hidden');
        toggleBtn.addEventListener('click', function() {
            minimized = !minimized;
            bodyEl.classList.toggle('hidden', minimized);
            miniPct.classList.toggle('hidden', !minimized);
            panel.classList.toggle('progress-panel-minimized', minimized);
            toggleBtn.querySelector('span').textContent = minimized ? 'expand_less' : 'minimize';
            toggleBtn.title = minimized ? 'Expand' : 'Minimize';
        });

        container.appendChild(panel);
        _progressPanels[id] = panel;
    }

    function updateProgress(id, step, percent, detail) {
        var stepEl = document.getElementById('progress-step-' + id);
        var barEl = document.getElementById('progress-bar-' + id);
        var pctEl = document.getElementById('progress-pct-' + id);
        var miniPctEl = document.getElementById('progress-pct-mini-' + id);
        var detailEl = document.getElementById('progress-detail-' + id);
        if (stepEl) stepEl.textContent = step;
        if (barEl) barEl.style.width = percent + '%';
        if (pctEl) pctEl.textContent = percent + '%';
        if (miniPctEl) miniPctEl.textContent = percent + '%';
        if (detailEl) {
            var text = detail || '';
            detailEl.textContent = text;
            detailEl.title = text;
        }
    }

    function hideProgress(id, status) {
        var panel = _progressPanels[id];
        if (!panel) return;

        if (status === 'success') {
            panel.classList.add('progress-panel-success');
            setTimeout(function() {
                panel.style.animation = 'toast-out 0.3s ease-in forwards';
                setTimeout(function() {
                    panel.remove();
                    delete _progressPanels[id];
                }, 300);
            }, 3000);
        } else if (status === 'error') {
            panel.classList.add('progress-panel-error');

            // Dismiss helper — remove panel and clean up auto-dismiss timer
            var autoDismissTimer = null;
            function dismissPanel() {
                if (autoDismissTimer) clearTimeout(autoDismissTimer);
                panel.style.animation = 'toast-out 0.3s ease-in forwards';
                setTimeout(function() {
                    panel.remove();
                    delete _progressPanels[id];
                }, 300);
            }

            // Add a clearly visible dismiss button (use × character, not icon font)
            var dismissBtn = document.createElement('button');
            dismissBtn.className = 'progress-panel-dismiss';
            dismissBtn.innerHTML = '\u00d7';
            dismissBtn.title = 'Dismiss';
            dismissBtn.addEventListener('click', dismissPanel);
            panel.querySelector('.progress-panel-actions').appendChild(dismissBtn);

            // Auto-dismiss error panels after 15 seconds
            autoDismissTimer = setTimeout(dismissPanel, 15000);
        } else {
            panel.remove();
            delete _progressPanels[id];
        }
    }

    // ── Version Check & Update ──

    function _checkUpdate() {
        BridgeAPI.checkUpdate().then(function(info) {
            console.log('Update check:', JSON.stringify(info));
            if (info && info.local_version) { window.APP_VERSION = info.local_version; }
            var label = document.getElementById('version-label');
            if (label) label.textContent = 'v' + info.local_version;
            if (info.has_update) {
                _updateInfo = info;
                var block = document.getElementById('version-block');
                if (block) block.classList.add('has-update');
            }
        }).catch(function(e) {
            console.warn('Update check failed:', e);
        });
    }

    function _showUpdateModal() {
        if (!_updateInfo) {
            showToast(t('update_latest'), 'info');
            return;
        }

        if (!_updateInfo.git_available) {
            showToast(t('update_no_git'), 'error');
            return;
        }

        var changesHtml = '';
        var changesI18n = _updateInfo.changes_i18n;
        var rawChanges = _updateInfo.changes;
        var changes;
        var lang = I18N.getLanguage() || 'en';
        if (changesI18n && typeof changesI18n === 'object') {
            changes = changesI18n[lang] || changesI18n['zh-TW'] || changesI18n['en'] || [];
        } else if (rawChanges && typeof rawChanges === 'object' && !Array.isArray(rawChanges)) {
            changes = rawChanges[lang] || rawChanges['zh-TW'] || rawChanges['en'] || [];
        } else {
            changes = rawChanges || [];
        }
        if (changes && changes.length > 0) {
            changesHtml = '<div class="mt-4"><div class="text-[12px] font-label uppercase tracking-wider text-on-surface-variant mb-2">' + t('update_changes') + '</div>'
                + '<ul class="space-y-1 text-[13px] text-on-surface-variant">';
            changes.forEach(function(c) {
                changesHtml += '<li class="flex items-start gap-2"><span class="text-primary mt-0.5">•</span><span>' + c + '</span></li>';
            });
            changesHtml += '</ul></div>';
        }

        var body = '<div>'
            + changesHtml
            + '</div>';

        showModal({
            title: t('update_available', _updateInfo.remote_version),
            body: body,
            buttons: [
                { text: t('cancel'), class: 'btn-secondary' },
                { text: t('update_btn'), class: 'btn-primary', closeModal: false, onClick: function() { _doUpdate(); } },
            ],
        });
    }

    function _doUpdate() {
        // Replace modal content with progress
        var container = document.getElementById('modal-container');
        var steps = [
            { key: 'pull', label: t('update_step_pull') },
            { key: 'deps', label: t('update_step_deps') },
            { key: 'restart', label: t('update_step_restart') },
        ];
        var completed = {};

        function renderProgress() {
            var html = '<div class="modal-enter"><div class="px-6 py-4 border-b border-outline/20">'
                + '<h3 class="font-headline text-sm font-bold uppercase tracking-wider">' + t('update_progress_title') + '</h3>'
                + '</div><div class="px-6 py-5 space-y-3">';
            steps.forEach(function(s) {
                var icon, cls;
                if (completed[s.key] === 'done') {
                    icon = '✓'; cls = 'text-primary';
                } else if (completed[s.key] === 'active') {
                    icon = '●'; cls = 'text-primary animate-pulse';
                } else {
                    icon = '○'; cls = 'text-on-surface-variant/40';
                }
                html += '<div class="flex items-center gap-3 ' + cls + '">'
                    + '<span class="text-[14px] w-5 text-center">' + icon + '</span>'
                    + '<span class="text-[13px]">' + s.label + '</span>'
                    + '</div>';
            });
            html += '</div></div>';
            container.innerHTML = html;
        }

        // Disable overlay click to close
        var overlay = document.getElementById('modal-overlay');
        overlay.onclick = null;

        completed['pull'] = 'active';
        renderProgress();

        BridgeAPI.doUpdate(function(progress) {
            // onProgress callback
            if (progress.step === 'pull' && progress.percent >= 40) {
                completed['pull'] = 'done';
                completed['deps'] = 'active';
                renderProgress();
            }
            if (progress.step === 'deps' && progress.percent >= 90) {
                completed['deps'] = 'done';
                completed['restart'] = 'active';
                renderProgress();
            }
        }).then(function() {
            completed['deps'] = 'done';
            completed['restart'] = 'active';
            renderProgress();
            // Trigger restart after a brief pause
            setTimeout(function() {
                BridgeAPI.restartApp();
            }, 1000);
        }).catch(function(e) {
            hideModal();
            showToast(t('update_failed', e), 'error');
        });
    }

    // ── Initialization ──

    function init() {
        _setupMaterialIconFallback();

        // Init bridge FIRST, then do everything else
        BridgeAPI.init().then(function() {
            console.log('Bridge connected');
            // Get config and set language AFTER bridge is ready
            return BridgeAPI.getConfig();
        }).then(function(config) {
            if (config && config.language) {
                I18N.setLanguage(config.language);
                var switcher = document.getElementById('lang-switcher');
                if (switcher) switcher.value = config.language;
            }
            // Theme reconciliation: config.json is authoritative
            if (config && config.color_scheme) {
                var stored = localStorage.getItem('color_scheme') || 'obsidian';
                if (stored !== config.color_scheme) {
                    document.documentElement.setAttribute('data-theme', config.color_scheme);
                    localStorage.setItem('color_scheme', config.color_scheme);
                }
            }
            // Debug info
            return BridgeAPI.debugInfo();
        }).then(function(info) {
            console.log('Bridge debug:', JSON.stringify(info));
            // Background version check (non-blocking)
            _checkUpdate();
            // One-shot startup toast for shared-model rescan (non-blocking)
            try {
                BridgeAPI.getLastRescanResult().then(function(result) {
                    if (!result || !result.added || result.added.length === 0) return;
                    showToast(
                        t('rescan_found_new')
                            .replace('{0}', result.added.length)
                            .replace('{1}', result.synced_envs || 0),
                        'success'
                    );
                }).catch(function() { /* silent */ });
            } catch (e) { /* silent */ }
        }).catch(function(e) {
            console.warn('Init failed:', e);
            showToast('Backend connection failed: ' + e, 'error');
        }).finally(function() {
            // Navigate to first page AFTER bridge is ready (or failed)
            navigate('home');
        });

        // Sidebar navigation
        document.querySelectorAll('.nav-item').forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                navigate(item.dataset.page);
            });
        });

        // Version block click
        var versionBlock = document.getElementById('version-block');
        if (versionBlock) {
            versionBlock.addEventListener('click', function() {
                _showUpdateModal();
            });
        }

        // Language switcher
        var langSwitcher = document.getElementById('lang-switcher');
        if (langSwitcher) {
            langSwitcher.addEventListener('change', function(e) {
                I18N.setLanguage(e.target.value);
                // Re-render current page
                if (currentPage) {
                    var module = pageModules[currentPage];
                    if (module && module.render) {
                        var container = document.getElementById('main-content');
                        container.innerHTML = '';
                        module.render(container);
                    }
                }
            });
        }

        // Navigation is now triggered in the .finally() block above
    }

    // Run init when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOMContentLoaded already fired, wait a tick for other scripts to register
        setTimeout(init, 0);
    }

    return {
        registerPage: registerPage,
        navigate: navigate,
        showModal: showModal,
        hideModal: hideModal,
        confirm: confirm,
        showToast: showToast,
        setLoading: setLoading,
        showProgress: showProgress,
        updateProgress: updateProgress,
        hideProgress: hideProgress,
        addBug: addBug,
        getBugs: getBugs,
        clearBugs: clearBugs,
        clearBugUnread: clearBugUnread,
        applyFallbackIcons: _applyFallbackIcons,
    };
})();
