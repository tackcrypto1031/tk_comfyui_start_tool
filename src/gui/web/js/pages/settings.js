/**
 * settings.js — Settings page module
 * Provides UI color scheme selection.
 */
(function() {

    var THEMES = [
        {
            id: 'obsidian',
            nameKey: 'theme_obsidian',
            descKey: 'theme_obsidian_desc',
            preview: {
                sidebar: 'rgb(10,10,10)',
                sidebarBorder: 'rgb(25,25,25)',
                content: 'rgb(14,14,14)',
                accent: 'rgb(204,151,255)',
                text: 'rgb(171,171,171)',
                btnPrimary: 'rgb(204,151,255)',
                btnSecondary: 'rgb(25,25,25)',
                btnSecondaryBorder: 'rgb(72,72,72)',
            },
            dots: ['rgb(204,151,255)', 'rgb(14,14,14)', 'rgb(19,19,19)', 'rgb(255,110,132)'],
        },
        {
            id: 'claude',
            nameKey: 'theme_claude',
            descKey: 'theme_claude_desc',
            preview: {
                sidebar: 'rgb(250,249,245)',
                sidebarBorder: 'rgb(240,238,230)',
                content: 'rgb(245,244,237)',
                accent: 'rgb(201,100,66)',
                text: 'rgb(94,93,89)',
                btnPrimary: 'rgb(201,100,66)',
                btnSecondary: 'rgb(232,230,220)',
                btnSecondaryBorder: 'rgb(232,230,220)',
            },
            dots: ['rgb(201,100,66)', 'rgb(245,244,237)', 'rgb(250,249,245)', 'rgb(181,51,51)'],
        },
        {
            id: 'minimax',
            nameKey: 'theme_minimax',
            descKey: 'theme_minimax_desc',
            preview: {
                sidebar: 'rgb(240,240,240)',
                sidebarBorder: 'rgb(229,231,235)',
                content: 'rgb(255,255,255)',
                accent: 'rgb(20,86,240)',
                text: 'rgb(69,81,94)',
                btnPrimary: 'rgb(24,30,37)',
                btnSecondary: 'rgb(240,240,240)',
                btnSecondaryBorder: 'rgb(229,231,235)',
            },
            dots: ['rgb(20,86,240)', 'rgb(255,255,255)', 'rgb(24,30,37)', 'rgb(234,94,193)'],
        },
        {
            id: 'ollama',
            nameKey: 'theme_ollama',
            descKey: 'theme_ollama_desc',
            preview: {
                sidebar: 'rgb(250,250,250)',
                sidebarBorder: 'rgb(229,229,229)',
                content: 'rgb(255,255,255)',
                accent: 'rgb(0,0,0)',
                text: 'rgb(115,115,115)',
                btnPrimary: 'rgb(0,0,0)',
                btnSecondary: 'rgb(229,229,229)',
                btnSecondaryBorder: 'rgb(229,229,229)',
            },
            dots: ['rgb(0,0,0)', 'rgb(255,255,255)', 'rgb(250,250,250)', 'rgb(115,115,115)'],
        },
    ];

    function _currentTheme() {
        return document.documentElement.getAttribute('data-theme') || 'obsidian';
    }

    function _applyTheme(themeId) {
        document.documentElement.setAttribute('data-theme', themeId);
        localStorage.setItem('color_scheme', themeId);
        BridgeAPI.setConfig('color_scheme', themeId).catch(function(e) {
            console.warn('Failed to persist theme:', e);
        });
    }

    function _renderMiniPreview(p) {
        return '<div style="background:' + p.content + ';border:1px solid ' + p.sidebarBorder + ';padding:10px;height:80px;display:flex;gap:8px;">'
            + '<div style="width:40px;background:' + p.sidebar + ';border-right:1px solid ' + p.sidebarBorder + ';">'
            +   '<div style="width:12px;height:2px;background:' + p.accent + ';margin:8px auto 3px;"></div>'
            +   '<div style="width:12px;height:2px;background:' + p.text + ';margin:0 auto 3px;"></div>'
            +   '<div style="width:12px;height:2px;background:' + p.text + ';margin:0 auto;"></div>'
            + '</div>'
            + '<div style="flex:1;">'
            +   '<div style="width:60%;height:3px;background:' + p.accent + ';margin-bottom:6px;"></div>'
            +   '<div style="width:80%;height:2px;background:' + p.text + ';margin-bottom:4px;"></div>'
            +   '<div style="width:70%;height:2px;background:' + p.text + ';margin-bottom:8px;"></div>'
            +   '<div style="display:flex;gap:4px;">'
            +     '<div style="width:32px;height:10px;background:' + p.btnPrimary + ';"></div>'
            +     '<div style="width:32px;height:10px;background:' + p.btnSecondary + ';border:1px solid ' + p.btnSecondaryBorder + ';"></div>'
            +   '</div>'
            + '</div>'
            + '</div>';
    }

    function _renderDots(dots) {
        var html = '<div style="display:flex;gap:4px;margin-top:8px;">';
        dots.forEach(function(color) {
            var border = color === 'rgb(255,255,255)' || color === 'rgb(250,250,250)' || color === 'rgb(245,244,237)' || color === 'rgb(250,249,245)'
                ? 'border:1px solid rgb(var(--color-outline));' : '';
            html += '<div style="width:16px;height:16px;border-radius:50%;background:' + color + ';' + border + '"></div>';
        });
        html += '</div>';
        return html;
    }

    function render(container) {
        var current = _currentTheme();

        var html = '<div class="space-y-8">';

        // Section: Color Scheme
        html += '<div>';
        html += '<div class="section-title mb-4"><span data-i18n="settings_color_scheme">' + t('settings_color_scheme') + '</span></div>';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">';

        THEMES.forEach(function(theme) {
            var isActive = theme.id === current;
            var borderStyle = isActive
                ? 'border:2px solid rgb(var(--color-primary))'
                : 'border:1px solid rgb(var(--color-surface-container))';

            html += '<div class="theme-card" data-theme-id="' + theme.id + '" style="background:rgb(var(--color-surface-container-low));' + borderStyle + ';padding:16px;cursor:pointer;transition:all 0.15s;">';

            // Mini preview
            html += _renderMiniPreview(theme.preview);

            // Label row
            html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px;">';
            html += '<div>';
            html += '<div class="font-label" style="font-size:13px;font-weight:600;" data-i18n="' + theme.nameKey + '">' + t(theme.nameKey) + '</div>';
            html += '<div style="font-size:11px;color:rgb(var(--color-on-surface-variant));" data-i18n="' + theme.descKey + '">' + t(theme.descKey) + '</div>';
            html += '</div>';

            if (isActive) {
                html += '<div style="width:18px;height:18px;border-radius:50%;background:rgb(var(--color-primary));display:flex;align-items:center;justify-content:center;">'
                    + '<span style="color:rgb(var(--color-on-primary));font-size:11px;font-weight:bold;">✓</span>'
                    + '</div>';
            }

            html += '</div>';

            // Color dots
            html += _renderDots(theme.dots);

            html += '</div>';
        });

        html += '</div>';
        html += '</div>';

        html += '</div>';

        container.innerHTML = html;

        // Bind click handlers
        container.querySelectorAll('.theme-card').forEach(function(card) {
            card.addEventListener('click', function() {
                var themeId = card.getAttribute('data-theme-id');
                if (themeId === _currentTheme()) return;
                _applyTheme(themeId);
                App.showToast(t('theme_applied'), 'success');
                // Re-render to update selection state
                render(container);
            });
        });
    }

    App.registerPage('settings', { render: render });

})();
