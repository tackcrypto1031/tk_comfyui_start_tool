/**
 * app.js — SPA router, modal/toast utilities, and initialization
 */
const App = (function() {

    var currentPage = null;
    var pageModules = {};  // Registered by page scripts

    // ── Page Registration ──

    function registerPage(name, module) {
        pageModules[name] = module;
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

    // ── Toast System ──

    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration !== undefined ? duration : 4000;
        var container = document.getElementById('toast-container');
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(function() {
            toast.style.animation = 'toast-out 0.3s ease-in forwards';
            setTimeout(function() { toast.remove(); }, 300);
        }, duration);
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
        detailEl.textContent = text.length > 30 ? text.substring(0, 30) + '...' : text;
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
            var dismissBtn = document.createElement('button');
            dismissBtn.className = 'progress-panel-dismiss';
            dismissBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">close</span>';
            dismissBtn.addEventListener('click', function() {
                panel.remove();
                delete _progressPanels[id];
            });
            panel.querySelector('.progress-panel-actions').appendChild(dismissBtn);
        } else {
            panel.remove();
            delete _progressPanels[id];
        }
    }

    // ── Initialization ──

    function init() {
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
            // Debug info
            return BridgeAPI.debugInfo();
        }).then(function(info) {
            console.log('Bridge debug:', JSON.stringify(info));
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
    };
})();
