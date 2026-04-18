/**
 * settings.js — Settings page module
 * Placeholder while settings features are under development.
 */
(function() {

    function render(container) {
        container.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;min-height:360px;">'
          +   '<div style="text-align:center;color:rgb(var(--color-on-surface-variant));">'
          +     '<div class="material-symbols-outlined" style="font-size:48px;opacity:0.5;margin-bottom:12px;">construction</div>'
          +     '<div class="font-label" style="font-size:15px;font-weight:600;color:rgb(var(--color-on-surface));" data-i18n="settings_coming_soon">'
          +       t('settings_coming_soon')
          +     '</div>'
          +     '<div style="font-size:12px;margin-top:6px;" data-i18n="settings_coming_soon_desc">'
          +       t('settings_coming_soon_desc')
          +     '</div>'
          +   '</div>'
          + '</div>';
    }

    App.registerPage('settings', { render: render });

})();
