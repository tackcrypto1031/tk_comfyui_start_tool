/**
 * versions.js — Git branch/tag/commit control (Tack Industrial redesign)
 */
(function() {

    var _envs = [];
    var _tags = [];
    var _selectedRef = null;
    var _selectedLabel = null;
    var _currentCommit = '';

    function render(container) {
        container.innerHTML =
            '<div class="ti-content fade-in">' +
                '<div class="ti-page-head">' +
                    '<div>' +
                        '<p class="ti-page-sub" id="ver-sub">—</p>' +
                    '</div>' +
                    '<div class="ti-page-actions">' +
                        '<div class="ti-env-select">' +
                            '<label>' + h(t('version_environment')) + '</label>' +
                            '<select id="ver-env"></select>' +
                        '</div>' +
                        '<button id="ver-btn-refresh" class="btn btn-secondary" title="' + h(t('env_refresh')) + '">' +
                            '<span class="material-symbols-outlined" style="font-size:14px">refresh</span>' +
                        '</button>' +
                    '</div>' +
                '</div>' +

                '<div class="ti-card-grid-2">' +
                    // Left: branch / tag switcher
                    '<div class="ti-card">' +
                        '<div class="ti-card-head">' +
                            '<span class="material-symbols-outlined">tag</span>' +
                            '<span class="ti-card-title">' + h(t('version_available_tags')) + '</span>' +
                            '<button id="ver-btn-fetch" class="btn btn-ghost btn-sm" style="margin-left:auto">' +
                                '<span class="material-symbols-outlined" style="font-size:13px">cloud_download</span>' +
                                '<span>' + h(t('version_refresh_versions')) + '</span>' +
                            '</button>' +
                        '</div>' +
                        '<div class="ti-card-body">' +
                            '<div id="ver-tags-status" style="font-size:11px;color:var(--text-3);font-family:var(--font-mono)">—</div>' +
                            '<div id="ver-tags-list" class="ti-tag-list" style="margin-top:10px"></div>' +
                            '<div id="ver-current-notice" style="font-size:11px;color:var(--warn);font-family:var(--font-mono);display:none;margin-top:10px"></div>' +
                            '<button id="ver-btn-switch" class="btn btn-primary" style="width:100%;justify-content:center;margin-top:12px">' +
                                '<span class="material-symbols-outlined" style="font-size:14px">download</span>' +
                                '<span>' + h(t('version_switch')) + '</span>' +
                            '</button>' +
                        '</div>' +
                    '</div>' +
                    // Right: pull latest
                    '<div class="ti-card">' +
                        '<div class="ti-card-head">' +
                            '<span class="material-symbols-outlined">refresh</span>' +
                            '<span class="ti-card-title">' + h(t('version_update')) + '</span>' +
                        '</div>' +
                        '<div class="ti-card-body">' +
                            '<div id="ver-update-status" style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-3)">' +
                                '<span class="chip">—</span>' +
                            '</div>' +
                            '<button id="ver-btn-update" class="btn btn-primary" style="width:100%;justify-content:center;margin-top:12px">' +
                                '<span class="material-symbols-outlined" style="font-size:14px">arrow_forward</span>' +
                                '<span>' + h(t('version_update')) + '</span>' +
                            '</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +

                '<div class="ti-section-head">' +
                    '<h2>' + h(t('version_recent_commits') || '最近 Commits') + '</h2>' +
                    '<div class="line"></div>' +
                '</div>' +
                '<div id="ver-commits" class="ti-card"></div>' +

                '<div id="ver-status" style="margin-top:10px;font-family:var(--font-mono);font-size:11px;color:var(--text-4);text-transform:uppercase;letter-spacing:0.1em"></div>' +
            '</div>';

        document.getElementById('ver-btn-refresh').addEventListener('click', loadEnvs);
        document.getElementById('ver-btn-fetch').addEventListener('click', fetchTags);
        document.getElementById('ver-btn-switch').addEventListener('click', switchToSelected);
        document.getElementById('ver-btn-update').addEventListener('click', updateToLatest);
        document.getElementById('ver-env').addEventListener('change', onEnvChange);

        loadEnvs();
    }

    function loadEnvs() {
        BridgeAPI.listEnvironments().then(function(envs) {
            _envs = envs || [];
            var select = document.getElementById('ver-env');
            var prev = select.value;
            select.innerHTML = _envs.map(function(e) {
                return '<option value="' + h(e.name) + '">' + h(e.name) + '</option>';
            }).join('');
            if (prev) select.value = prev;
            onEnvChange();
        }).catch(function(e) {
            App.showToast(e.toString(), 'error');
        });
    }

    function currentEnv() {
        var name = document.getElementById('ver-env').value;
        return _envs.find(function(e) { return e.name === name; }) || null;
    }

    function onEnvChange() {
        var env = currentEnv();
        _currentCommit = env ? (env.comfyui_commit || '') : '';
        var sub = document.getElementById('ver-sub');
        if (env) {
            sub.innerHTML = '<span class="accent">' + h(env.name) + '</span> · 當前 commit <span class="mono" style="color:var(--text-1)">' + h((_currentCommit || '—').substring(0, 7)) + '</span>';
        } else {
            sub.textContent = '—';
        }
        // Load commits for this env
        loadCommits();
        // Re-render tags (for highlight)
        if (_tags.length) renderTags();
    }

    function loadCommits() {
        var env = currentEnv();
        if (!env) { document.getElementById('ver-commits').innerHTML = ''; return; }
        if (!BridgeAPI.listCommits) return;
        BridgeAPI.listCommits(env.name).then(function(commits) {
            renderCommits(commits || []);
        }).catch(function() { /* silent */ });
    }

    function renderCommits(commits) {
        var wrap = document.getElementById('ver-commits');
        if (!wrap) return;
        if (!commits.length) {
            wrap.innerHTML = '<div class="ti-list-empty"><span class="material-symbols-outlined">history</span><div>—</div></div>';
            return;
        }
        wrap.innerHTML = commits.slice(0, 20).map(function(c) {
            var hash = (c.hash || c.id || '').substring(0, 7);
            return '<div class="ti-commit-row">' +
                '<span class="hash">' + h(hash) + '</span>' +
                '<span class="msg" title="' + h(c.message || c.msg || '') + '">' + h(c.message || c.msg || '') + '</span>' +
                '<span class="author">' + h(c.author || '') + '</span>' +
                '<span class="date">' + h(c.date || c.relative || '') + '</span>' +
            '</div>';
        }).join('');
    }

    function fetchTags() {
        var statusEl = document.getElementById('ver-tags-status');
        statusEl.textContent = t('version_fetching');
        document.getElementById('ver-btn-fetch').disabled = true;
        BridgeAPI.listRemoteVersions().then(function(versions) {
            _tags = (versions && versions.tags) || [];
            renderTags();
            statusEl.textContent = t('version_tag_count', _tags.length);
            document.getElementById('ver-btn-fetch').disabled = false;
            // update pull-latest card
            updatePullStatus(versions);
        }).catch(function(e) {
            statusEl.textContent = t('version_fetch_failed', e.toString());
            document.getElementById('ver-btn-fetch').disabled = false;
        });
    }

    function updatePullStatus(versions) {
        var el = document.getElementById('ver-update-status');
        if (!el) return;
        var behind = versions && versions.commits_behind;
        if (behind && behind > 0) {
            el.innerHTML = '<span class="chip accent">● ' + (t('version_has_update') || '有新版本') + '</span>' +
                '<span style="font-size:12px;color:var(--text-3)">' + behind + ' 個 commit 落後</span>';
        } else {
            el.innerHTML = '<span class="chip">已是最新</span>';
        }
    }

    function renderTags() {
        var wrap = document.getElementById('ver-tags-list');
        if (!wrap) return;
        var currentFull = _currentCommit;
        var matched = false;

        if (!_tags.length) {
            wrap.innerHTML = '<div class="ti-list-empty" style="border:0;padding:20px"><span class="material-symbols-outlined">tag</span><div>點擊右上角 "更新版本列表" 來載入</div></div>';
            return;
        }

        wrap.innerHTML = _tags.map(function(tag) {
            var isCurrent = currentFull && tag.hash && tag.hash === currentFull;
            if (isCurrent) matched = true;
            var selected = (_selectedRef === tag.name) ? ' selected' : '';
            return '<div class="ti-tag-row' + selected + '" data-ref="' + h(tag.name) + '">' +
                '<span class="tag-name">' + h(tag.name) +
                    (isCurrent ? ' <span class="current-badge">← ' + h(t('version_current') || 'current') + '</span>' : '') +
                '</span>' +
                '<span class="tag-date">' + h(tag.date || (tag.hash ? tag.hash.substring(0, 7) : '—')) + '</span>' +
            '</div>';
        }).join('');

        wrap.querySelectorAll('.ti-tag-row').forEach(function(r) {
            r.addEventListener('click', function() {
                wrap.querySelectorAll('.ti-tag-row.selected').forEach(function(n) { n.classList.remove('selected'); });
                r.classList.add('selected');
                _selectedRef = r.getAttribute('data-ref');
                _selectedLabel = _selectedRef;
            });
        });

        var notice = document.getElementById('ver-current-notice');
        if (notice) {
            if (!matched && currentFull) {
                notice.textContent = t('version_not_on_tag', currentFull.substring(0, 7));
                notice.style.display = '';
            } else {
                notice.style.display = 'none';
            }
        }
    }

    function switchToSelected() {
        var env = currentEnv();
        if (!env) { App.showToast(t('launch_select_env'), 'info'); return; }
        if (!_selectedRef) { App.showToast(t('version_select_commit'), 'info'); return; }

        App.confirm(t('version_confirm_switch', _selectedRef)).then(function(ok) {
            if (!ok) return;
            var statusEl = document.getElementById('ver-status');
            statusEl.textContent = t('version_switching');
            BridgeAPI.switchVersion(env.name, _selectedRef).then(function() {
                statusEl.textContent = t('version_switched');
                App.showToast(t('version_switched'), 'success');
                loadEnvs();
            }).catch(function(e) {
                statusEl.textContent = t('error') + ': ' + e;
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function updateToLatest() {
        var env = currentEnv();
        if (!env) { App.showToast(t('launch_select_env'), 'info'); return; }
        App.confirm(t('version_confirm_update')).then(function(ok) {
            if (!ok) return;
            document.getElementById('ver-status').textContent = t('version_updating');
            BridgeAPI.updateComfyUI(env.name).then(function() {
                document.getElementById('ver-status').textContent = t('version_updated');
                App.showToast(t('version_updated'), 'success');
                loadEnvs();
            }).catch(function(e) {
                App.showToast(e.toString(), 'error');
            });
        });
    }

    function h(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    App.registerPage('versions', { render: render });
})();
