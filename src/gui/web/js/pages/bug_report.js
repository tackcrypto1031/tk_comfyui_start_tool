/**
 * bug_report.js — Bug Report page module
 * Displays errors collected via App.showToast('error') AND window.onerror / unhandledrejection.
 */
(function() {

    function render(container) {
        App.clearBugUnread();
        var bugs = App.getBugs();

        var html = '<div class="fade-in space-y-6">';

        html += '<div class="flex items-center justify-between">'
            + '<div class="section-title">' + t('bug_report_title') + '</div>';
        if (bugs.length > 0) {
            html += '<button id="bug-clear-all" class="btn btn-danger">'
                + '<span class="material-symbols-outlined text-[16px]">delete</span>'
                + t('bug_report_clear')
                + '</button>';
        }
        html += '</div>';

        if (bugs.length === 0) {
            html += '<div class="flex flex-col items-center justify-center py-20 text-on-surface-variant">'
                + '<span class="material-symbols-outlined text-[48px] text-primary/40 mb-4">check_circle</span>'
                + '<p class="text-[15px] font-medium">' + t('bug_report_empty') + '</p>'
                + '<p class="text-[13px] mt-1 opacity-60">' + t('bug_report_empty_sub') + '</p>'
                + '</div>';
        } else {
            html += '<div class="text-[12px] text-on-surface-variant font-label uppercase tracking-wider">'
                + t('bug_report_count', bugs.length) + '</div>';

            html += '<div class="space-y-3">';
            bugs.forEach(function(bug, index) {
                var hasDetail = !!(bug.stack || bug.file_info || bug.error_type || bug.origin);
                html += '<div class="bug-card">'
                    + '<div class="bug-card-header">'
                        + '<div class="bug-card-meta">'
                            + '<span class="bug-card-time">' + _escapeHtml(bug.timestamp || '') + '</span>'
                            + '<span class="bug-card-source">' + _escapeHtml(bug.source || '') + '</span>'
                            + (bug.error_type ? '<span class="bug-card-source">' + _escapeHtml(bug.error_type) + '</span>' : '')
                        + '</div>'
                        + '<button class="btn-copy-bug" data-bug-index="' + index + '">'
                            + t('bug_report_copy')
                        + '</button>'
                    + '</div>'
                    + '<div class="bug-card-message">' + _escapeHtml(bug.message || '') + '</div>';

                if (hasDetail) {
                    html += '<details class="bug-card-details mt-2 text-xs">'
                        + '<summary class="cursor-pointer text-on-surface-variant">' + t('bug_report_details') + '</summary>'
                        + '<div class="mt-2 space-y-1 font-mono text-[11px] text-on-surface-variant">';
                    if (bug.origin) html += '<div><b>origin:</b> ' + _escapeHtml(bug.origin) + '</div>';
                    if (bug.file_info) html += '<div><b>at:</b> ' + _escapeHtml(bug.file_info) + '</div>';
                    if (bug.source_page) html += '<div><b>page:</b> ' + _escapeHtml(bug.source_page) + '</div>';
                    if (bug.app_version) html += '<div><b>version:</b> v' + _escapeHtml(bug.app_version) + '</div>';
                    if (bug.stack) {
                        html += '<div class="mt-2"><b>stack:</b></div>'
                            + '<pre class="whitespace-pre-wrap break-all text-[11px] mt-1 p-2 bg-surface-container rounded">' + _escapeHtml(bug.stack) + '</pre>';
                    }
                    html += '</div></details>';
                }

                html += '</div>';
            });
            html += '</div>';
        }

        html += '</div>';
        container.innerHTML = html;

        var clearBtn = document.getElementById('bug-clear-all');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                App.confirm(t('bug_report_clear_confirm')).then(function(yes) {
                    if (yes) {
                        App.clearBugs();
                        render(container);
                    }
                });
            });
        }

        container.querySelectorAll('.btn-copy-bug').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var index = parseInt(btn.dataset.bugIndex);
                var bug = App.getBugs()[index];
                if (!bug) return;
                var lines = [
                    '[' + t('bug_report_time') + '] ' + (bug.timestamp || ''),
                    '[' + t('bug_report_source') + '] ' + (bug.source || '') + (bug.source_page ? ' (' + bug.source_page + ')' : ''),
                    '[version] v' + (bug.app_version || ''),
                    '[origin] ' + (bug.origin || ''),
                ];
                if (bug.error_type) lines.push('[type] ' + bug.error_type);
                if (bug.file_info) lines.push('[at] ' + bug.file_info);
                lines.push('[' + t('bug_report_error') + '] ' + (bug.message || ''));
                if (bug.stack) lines.push('[stack]\n' + bug.stack);
                if (bug.user_agent) lines.push('[ua] ' + bug.user_agent);
                _copyText(lines.join('\n'), btn);
            });
        });
    }

    function _escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str == null ? '' : String(str);
        return div.innerHTML;
    }

    function _copyText(text, btn) {
        BridgeAPI.copyToClipboard(text).then(function() {
            _showCopied(btn);
        }).catch(function() {
            // silent fallback failure
        });
    }

    function _showCopied(btn) {
        var original = btn.textContent;
        btn.textContent = t('bug_report_copied');
        btn.classList.add('copied');
        setTimeout(function() {
            btn.textContent = original;
            btn.classList.remove('copied');
        }, 1500);
    }

    App.registerPage('bug_report', {
        render: render
    });
})();
