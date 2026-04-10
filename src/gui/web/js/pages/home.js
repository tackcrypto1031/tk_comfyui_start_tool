/**
 * home.js — Homepage with banner and action cards
 */
(function() {

    var selectedEnv = '';

    var actionCards = [
        { id: 'output',       i18nKey: 'home_btn_output',      icon: 'image',         type: 'folder', subfolder: 'output' },
        { id: 'models',       i18nKey: 'home_btn_models',       icon: 'deployed_code', type: 'folder', subfolder: 'models' },
        { id: 'root',         i18nKey: 'home_btn_root',         icon: 'folder_open',   type: 'folder', subfolder: '' },
        { id: 'custom_nodes', i18nKey: 'home_btn_nodes',        icon: 'extension',     type: 'folder', subfolder: 'custom_nodes' },
        { id: 'registry',     i18nKey: 'home_btn_registry',     icon: 'store',         type: 'link',   url: 'https://github.com/tackcrypto1031/tk_comfyui_start_tool' },
        { id: 'recommend',    i18nKey: 'home_btn_recommended',  icon: 'recommend',     type: 'link',   url: 'https://www.google.com' }
    ];

    // Gradient colors for placeholder card backgrounds
    function _getGradients() {
        var cs = getComputedStyle(document.documentElement);
        var start = cs.getPropertyValue('--color-hero-gradient-start').trim();
        var end = cs.getPropertyValue('--color-hero-gradient-end').trim();
        return [
            'linear-gradient(135deg, rgb(' + start + ' / 0.6) 0%, rgb(' + end + ') 100%)',
            'linear-gradient(135deg, rgb(' + start + ' / 0.5) 0%, rgb(' + end + ') 100%)',
            'linear-gradient(135deg, rgb(' + start + ' / 0.4) 0%, rgb(' + end + ') 100%)',
            'linear-gradient(135deg, rgb(' + start + ' / 0.3) 0%, rgb(' + end + ') 100%)',
            'linear-gradient(135deg, rgb(' + start + ' / 0.4) 0%, rgb(' + end + ') 100%)',
            'linear-gradient(135deg, rgb(' + start + ' / 0.5) 0%, rgb(' + end + ') 100%)',
        ];
    }

    function render(container) {
        container.innerHTML =
            '<div class="fade-in" style="padding: 0;">' +

                // ── Banner ──
                '<div id="home-banner" style="' +
                    'position: relative; height: 280px; overflow: hidden; border-radius: 8px; ' +
                    'background: url(../../../assets/banner.jpg) center/cover no-repeat, ' +
                    'linear-gradient(135deg, rgb(var(--color-hero-gradient-start) / 0.6) 0%, rgb(var(--color-hero-gradient-end)) 60%, rgb(var(--color-hero-gradient-start) / 0.3) 100%); ' +
                    'margin: 16px 24px 0 24px;' +
                '">' +
                    // Bottom gradient overlay
                    '<div style="' +
                        'position: absolute; inset: 0; ' +
                        'background: linear-gradient(to top, rgb(var(--color-hero-gradient-end)) 0%, transparent 60%); ' +
                        'pointer-events: none; z-index: 1;' +
                    '"></div>' +
                    // Env selector (top-right)
                    '<div style="position: absolute; top: 16px; right: 16px; z-index: 2;">' +
                        '<select id="home-env-select" class="select" style="' +
                            'width: 220px; ' +
                            'background-color: rgba(0,0,0,0.7); ' +
                            'backdrop-filter: blur(8px); ' +
                            'border-color: rgba(72,72,72,0.4); ' +
                            'color: #ffffff;' +
                        '">' +
                            '<option value="">' + t('home_select_env') + '</option>' +
                        '</select>' +
                    '</div>' +
                '</div>' +

                // ── Action Cards ──
                '<div style="padding: 0 24px 24px 24px; margin-top: 32px;">' +
                    '<div id="home-cards-grid" style="' +
                        'display: grid; ' +
                        'grid-template-columns: repeat(3, 1fr); ' +
                        'gap: 16px;' +
                    '">' +
                        buildCardsHTML() +
                    '</div>' +
                '</div>' +

            '</div>';

        loadEnvironments();
        bindEvents();
    }

    function buildCardsHTML() {
        var html = '';
        for (var i = 0; i < actionCards.length; i++) {
            var card = actionCards[i];
            var isFolder = card.type === 'folder';
            var disabledClass = isFolder ? ' home-card-disabled' : '';
            var disabledAttr = isFolder ? ' data-requires-env="true"' : '';

            html +=
                '<div class="home-card' + disabledClass + '" data-action="' + card.id + '"' + disabledAttr + ' style="' +
                    'position: relative; height: 140px; overflow: hidden; cursor: pointer; ' +
                    'border: 1px solid transparent; transition: all 0.2s; border-radius: 8px; ' +
                    'background: ' + _getGradients()[i] + ';' +
                '">' +
                    // Gradient overlay at bottom
                    '<div style="' +
                        'position: absolute; inset: 0; ' +
                        'background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 60%); ' +
                        'pointer-events: none;' +
                    '"></div>' +
                    // Icon + label
                    '<div style="' +
                        'position: absolute; bottom: 16px; left: 16px; z-index: 1; ' +
                        'display: flex; align-items: center; gap: 8px;' +
                    '">' +
                        '<span class="material-symbols-outlined" style="font-size: 20px; color:rgb(var(--color-primary));">' +
                            card.icon +
                        '</span>' +
                        '<span style="' +
                            'font-family: \'Space Grotesk\', sans-serif; font-size: 14px; ' +
                            'font-weight: 700; letter-spacing: 0.1em; ' +
                            'text-transform: uppercase; color: #ffffff;' +
                        '">' + t(card.i18nKey) + '</span>' +
                    '</div>' +
                    // External link indicator
                    (card.type === 'link' ?
                        '<div style="position: absolute; top: 12px; right: 12px; z-index: 1;">' +
                            '<span class="material-symbols-outlined" style="font-size: 16px; color:rgb(var(--color-on-surface-variant));">open_in_new</span>' +
                        '</div>' : '') +
                '</div>';
        }
        return html;
    }

    function loadEnvironments() {
        BridgeAPI.listEnvironments().then(function(envs) {
            var select = document.getElementById('home-env-select');
            if (!select) return;

            var options = '<option value="">' + t('home_select_env') + '</option>';
            var envNames = [];
            if (envs && envs.length) {
                for (var i = 0; i < envs.length; i++) {
                    var name = typeof envs[i] === 'string' ? envs[i] : envs[i].name;
                    envNames.push(name);
                    options += '<option value="' + name + '">' + name + '</option>';
                }
            }
            select.innerHTML = options;

            // Restore previously selected env, clear if no longer exists
            if (selectedEnv && envNames.indexOf(selectedEnv) !== -1) {
                select.value = selectedEnv;
                updateCardStates();
            } else {
                selectedEnv = '';
                updateCardStates();
            }
        }).catch(function() {
            App.showToast(t('home_no_envs'), 'info');
        });
    }

    function updateCardStates() {
        var cards = document.querySelectorAll('.home-card[data-requires-env]');
        for (var i = 0; i < cards.length; i++) {
            if (selectedEnv) {
                cards[i].classList.remove('home-card-disabled');
            } else {
                cards[i].classList.add('home-card-disabled');
            }
        }
    }

    function bindEvents() {
        var select = document.getElementById('home-env-select');
        if (select) {
            select.addEventListener('change', function() {
                selectedEnv = this.value;
                updateCardStates();
            });
        }

        var cards = document.querySelectorAll('.home-card');
        cards.forEach(function(cardEl) {
            cardEl.addEventListener('click', function() {
                var actionId = this.getAttribute('data-action');
                var card = null;
                for (var i = 0; i < actionCards.length; i++) {
                    if (actionCards[i].id === actionId) { card = actionCards[i]; break; }
                }
                if (!card) return;

                if (card.type === 'folder') {
                    if (!selectedEnv) {
                        App.showToast(t('home_no_env_selected'), 'info');
                        return;
                    }
                    BridgeAPI.openFolder(selectedEnv, card.subfolder).catch(function() {
                        App.showToast(t('home_folder_not_found'), 'error');
                    });
                } else if (card.type === 'link') {
                    BridgeAPI.openUrl(card.url).catch(function() {
                        App.showToast('Failed to open link', 'error');
                    });
                }
            });

            // Hover effects
            cardEl.addEventListener('mouseenter', function() {
                if (this.classList.contains('home-card-disabled')) return;
                this.style.borderColor = 'rgb(var(--color-primary))';
            });
            cardEl.addEventListener('mouseleave', function() {
                this.style.borderColor = 'transparent';
            });
        });
    }

    App.registerPage('home', { render });
})();
