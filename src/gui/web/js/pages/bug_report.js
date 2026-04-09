/**
 * bug_report.js — Bug Report page module
 * Displays errors collected from App.showToast('error') calls.
 */
(function() {

    function render(container) {
        App.clearBugUnread();
        var bugs = App.getBugs();

        var html = '<div class="fade-in space-y-6">';

        // Header with clear button
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
            // Empty state
            html += '<div class="flex flex-col items-center justify-center py-20 text-on-surface-variant">'
                + '<span class="material-symbols-outlined text-[48px] text-primary/40 mb-4">check_circle</span>'
                + '<p class="text-[15px] font-medium">' + t('bug_report_empty') + '</p>'
                + '<p class="text-[13px] mt-1 opacity-60">' + t('bug_report_empty_sub') + '</p>'
                + '</div>';
        } else {
            // Bug count
            html += '<div class="text-[12px] text-on-surface-variant font-label uppercase tracking-wider">'
                + t('bug_report_count', bugs.length) + '</div>';

            // Bug cards
            html += '<div class="space-y-3">';
            bugs.forEach(function(bug, index) {
                html += '<div class="bug-card">'
                    + '<div class="bug-card-header">'
                        + '<div class="bug-card-meta">'
                            + '<span class="bug-card-time">' + bug.timestamp + '</span>'
                            + '<span class="bug-card-source">' + bug.source + '</span>'
                        + '</div>'
                        + '<button class="btn-copy-bug" data-bug-index="' + index + '">'
                            + t('bug_report_copy')
                        + '</button>'
                    + '</div>'
                    + '<div class="bug-card-message">' + _escapeHtml(bug.message) + '</div>'
                + '</div>';
            });
            html += '</div>';
        }

        html += '</div>';
        container.innerHTML = html;

        // Bind events
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

        // Copy buttons
        container.querySelectorAll('.btn-copy-bug').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var index = parseInt(btn.dataset.bugIndex);
                var bug = App.getBugs()[index];
                if (!bug) return;
                var text = '[' + t('bug_report_time') + '] ' + bug.timestamp
                    + '\n[' + t('bug_report_source') + '] ' + bug.source
                    + '\n[' + t('bug_report_error') + '] ' + bug.message;
                _copyText(text, btn);
            });
        });
    }

    function _escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
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
