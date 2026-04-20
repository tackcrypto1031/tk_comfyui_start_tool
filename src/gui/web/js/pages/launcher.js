/**
 * launcher.js — Running list page
 *
 * The sidebar env pill already handles "which environment is active" and the
 * Home page owns the primary start/stop flow, so this page is now a single-
 * purpose running-instances view. All tunable launch parameters (port, VRAM
 * mode, cross-attention, listen IP, diagnostics, etc.) live under Settings.
 */
(function() {

    var pollTimer = null;

    function render(container) {
        container.innerHTML = ''
            + '<div class="ti-content fade-in">'
            +     '<div class="ti-page-head">'
            +         '<div>'
            +             '<p class="ti-page-sub" id="launcher-sub">' + t('launch_tab_running') + '</p>'
            +         '</div>'
            +         '<div class="ti-page-actions">'
            +             '<button id="running-btn-refresh" class="btn btn-secondary" title="' + t('launch_refresh') + '">'
            +                 '<span class="material-symbols-outlined" style="font-size:14px">refresh</span>'
            +             '</button>'
            +         '</div>'
            +     '</div>'

            +     '<div class="card">'
            +         '<div class="card-header">'
            +             '<span>' + t('launch_tab_running') + '</span>'
            +             '<span class="tab-badge" id="running-count" style="display:none;margin-left:8px"></span>'
            +         '</div>'
            +         '<div id="running-list-content"></div>'
            +     '</div>'
            + '</div>';

        document.getElementById('running-btn-refresh').addEventListener('click', loadRunningList);

        loadRunningList();
        startPolling();
    }

    function loadRunningList() {
        var content = document.getElementById('running-list-content');
        if (!content) return;

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

            if (!list || list.length === 0) {
                content.innerHTML = ''
                    + '<div class="flex flex-col items-center justify-center py-12 text-center">'
                    +     '<span class="material-symbols-outlined text-[48px] text-on-surface-variant mb-3" style="color:rgb(var(--color-outline))">deployed_code</span>'
                    +     '<p style="color:#6b6b6b;font-size:13px">' + t('launch_running_empty') + '</p>'
                    + '</div>';
                return;
            }

            var html = ''
                + '<table class="data-table">'
                +     '<thead>'
                +         '<tr>'
                +             '<th>' + t('launch_running_env') + '</th>'
                +             '<th>' + t('launch_running_port') + '</th>'
                +             '<th>' + t('launch_running_pid') + '</th>'
                +             '<th>' + t('launch_running_version') + '</th>'
                +             '<th>' + t('launch_running_actions') + '</th>'
                +         '</tr>'
                +     '</thead>'
                +     '<tbody>';

            list.forEach(function(inst) {
                var version = '';
                if (inst.branch) {
                    version = inst.branch;
                    if (inst.commit) version += ' / ' + inst.commit.substring(0, 7);
                }
                html += ''
                    + '<tr data-env="' + inst.env_name + '">'
                    +     '<td style="font-weight:500">' + inst.env_name + '</td>'
                    +     '<td>'
                    +         '<a href="#" class="running-open-port" data-port="' + inst.port + '"'
                    +             ' style="color:rgb(var(--color-primary));text-decoration:none;border-bottom:1px dashed rgb(var(--color-primary))">'
                    +             inst.port
                    +         '</a>'
                    +     '</td>'
                    +     '<td style="color:rgb(var(--color-on-surface-variant));font-family:monospace;font-size:12px">' + inst.pid + '</td>'
                    +     '<td style="color:rgb(var(--color-on-surface-variant));font-size:12px">' + (version || '-') + '</td>'
                    +     '<td>'
                    +         '<div style="display:flex;gap:8px">'
                    +             '<button class="btn btn-secondary running-btn-open" data-port="' + inst.port + '" style="padding:6px 12px;font-size:10px">'
                    +                 '<span class="material-symbols-outlined text-[14px]">open_in_browser</span>'
                    +                 t('launch_running_open')
                    +             '</button>'
                    +             '<button class="btn btn-danger running-btn-stop" data-env="' + inst.env_name + '" style="padding:6px 12px;font-size:10px">'
                    +                 '<span class="material-symbols-outlined text-[14px]">stop</span>'
                    +                 t('launch_running_stop')
                    +             '</button>'
                    +         '</div>'
                    +     '</td>'
                    + '</tr>';
            });
            html += '</tbody></table>';
            content.innerHTML = html;
            App.applyFallbackIcons();

            content.querySelectorAll('.running-open-port, .running-btn-open').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    var port = parseInt(this.dataset.port);
                    BridgeAPI.openBrowser(port);
                });
            });

            content.querySelectorAll('.running-btn-stop').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    var envName = this.dataset.env;
                    this.disabled = true;
                    this.textContent = t('launch_running_stopping');
                    BridgeAPI.stopComfyUI(envName).then(function() {
                        App.showToast(t('launch_running_stopped_ok'), 'success');
                        loadRunningList();
                        if (window.HomePageAPI && HomePageAPI.refresh) HomePageAPI.refresh();
                    }).catch(function(e) {
                        App.showToast(String(e), 'error');
                        loadRunningList();
                    });
                });
            });
        }).catch(function(e) {
            content.innerHTML = '<p style="color:rgb(var(--color-error));padding:12px">' + String(e) + '</p>';
        });
    }

    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(function() {
            // Only poll while this page is the current view.
            if (document.getElementById('running-list-content')) {
                loadRunningList();
            } else {
                clearInterval(pollTimer);
                pollTimer = null;
            }
        }, 5000);
    }

    App.registerPage('launcher', { render: render });

})();
