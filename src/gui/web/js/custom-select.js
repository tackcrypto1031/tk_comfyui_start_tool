/**
 * CustomSelect — replaces native <select> popups with div-based dropdowns.
 *
 * The native <select> stays in the DOM (hidden) so existing code that reads
 * .value, sets .innerHTML, appends <option>, or listens for 'change' keeps
 * working. A MutationObserver syncs the custom UI whenever options change.
 */
(function () {
    'use strict';

    var ACTIVE_DROPDOWN = null;   // only one open at a time

    // ── helpers ───────────────────────────────────────────────────────
    function textOf(opt) {
        return opt.textContent || opt.innerText || '';
    }

    function closeActive() {
        if (ACTIVE_DROPDOWN) {
            ACTIVE_DROPDOWN.close();
            ACTIVE_DROPDOWN = null;
        }
    }

    // close on click outside
    document.addEventListener('mousedown', function (e) {
        if (ACTIVE_DROPDOWN && !ACTIVE_DROPDOWN.wrap.contains(e.target)) {
            closeActive();
        }
    });

    // close on Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeActive();
    });

    // ── CustomSelect class ───────────────────────────────────────────
    function CustomSelect(sel) {
        this.sel = sel;
        this.open = false;
        this._build();
        this._sync();
        this._observe();
        this._listen();
    }

    CustomSelect.prototype._build = function () {
        // Wrapper
        var wrap = document.createElement('div');
        wrap.className = 'cs-wrap';

        // Copy width classes from original select
        var cls = this.sel.className.split(/\s+/);
        for (var i = 0; i < cls.length; i++) {
            if (/^(w-|flex-|max-w-|min-w-)/.test(cls[i])) {
                wrap.classList.add(cls[i]);
            }
        }
        // Copy inline width if set (e.g. style="width: 220px")
        if (this.sel.style.width) {
            wrap.style.width = this.sel.style.width;
        }

        // Display (shows selected text)
        var display = document.createElement('div');
        display.className = 'cs-display';

        // Copy inline style from select (e.g. home-env-select has inline styles)
        // but skip width (wrapper handles it) to avoid double-width issues
        if (this.sel.style.cssText) {
            display.style.cssText = this.sel.style.cssText;
            display.style.width = '';
        }
        // Copy small-text class
        for (var j = 0; j < cls.length; j++) {
            if (/^(py-|text-\[)/.test(cls[j])) {
                display.classList.add(cls[j]);
            }
        }

        var arrow = document.createElement('span');
        arrow.className = 'cs-arrow';
        arrow.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ababab" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>';

        var label = document.createElement('span');
        label.className = 'cs-label';

        display.appendChild(label);
        display.appendChild(arrow);

        // Dropdown list
        var list = document.createElement('div');
        list.className = 'cs-list';

        // Insert wrapper before select, move select inside, hide it
        this.sel.parentNode.insertBefore(wrap, this.sel);
        wrap.appendChild(this.sel);
        wrap.appendChild(display);
        wrap.appendChild(list);

        this.wrap = wrap;
        this.display = display;
        this.label = label;
        this.arrowEl = arrow;
        this.list = list;
    };

    /** Rebuild the dropdown items from native <option> elements */
    CustomSelect.prototype._sync = function () {
        var self = this;
        var list = this.list;
        list.innerHTML = '';

        var opts = this.sel.options;
        for (var i = 0; i < opts.length; i++) {
            (function (opt, idx) {
                var item = document.createElement('div');
                item.className = 'cs-item';
                item.textContent = textOf(opt);
                item.setAttribute('data-value', opt.value);
                if (opt.disabled) item.classList.add('cs-disabled');
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (opt.disabled) return;
                    self.sel.selectedIndex = idx;
                    self.sel.dispatchEvent(new Event('change', { bubbles: true }));
                    self._updateLabel();
                    self.close();
                });
                list.appendChild(item);
            })(opts[i], i);
        }
        this._updateLabel();
    };

    /** Update display label to match current value */
    CustomSelect.prototype._updateLabel = function () {
        var sel = this.sel;
        var idx = sel.selectedIndex;
        if (idx >= 0 && sel.options[idx]) {
            this.label.textContent = textOf(sel.options[idx]);
        } else {
            this.label.textContent = '';
        }
        // highlight active item
        var items = this.list.children;
        for (var i = 0; i < items.length; i++) {
            if (i === idx) {
                items[i].classList.add('cs-active');
            } else {
                items[i].classList.remove('cs-active');
            }
        }
    };

    /** Watch for option additions / removals / innerHTML replacement */
    CustomSelect.prototype._observe = function () {
        var self = this;
        this._observer = new MutationObserver(function () {
            self._sync();
        });
        this._observer.observe(this.sel, { childList: true, subtree: true, characterData: true });

        // Also watch value changes via property override
        var desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
        var selEl = this.sel;
        var origSet = desc.set;
        Object.defineProperty(selEl, 'value', {
            get: desc.get,
            set: function (v) {
                origSet.call(selEl, v);
                self._updateLabel();
            },
            configurable: true
        });
    };

    /** Attach click / keyboard listeners */
    CustomSelect.prototype._listen = function () {
        var self = this;

        // Open / close on display click
        this.display.addEventListener('mousedown', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (self.sel.disabled) return;
            if (self.open) {
                self.close();
            } else {
                self.toggle();
            }
        });

        // Sync label when 'change' fires (e.g. from external code)
        this.sel.addEventListener('change', function () {
            self._updateLabel();
        });
    };

    CustomSelect.prototype.toggle = function () {
        if (this.open) {
            this.close();
        } else {
            closeActive();
            this.open = true;
            ACTIVE_DROPDOWN = this;
            this.list.classList.add('cs-open');
            this.display.classList.add('cs-focus');
            this._positionList();
            this._scrollToActive();
        }
    };

    CustomSelect.prototype.close = function () {
        this.open = false;
        this.list.classList.remove('cs-open');
        this.display.classList.remove('cs-focus');
        if (ACTIVE_DROPDOWN === this) ACTIVE_DROPDOWN = null;
    };

    /** Position dropdown above or below depending on viewport space */
    CustomSelect.prototype._positionList = function () {
        var rect = this.display.getBoundingClientRect();
        var listH = this.list.scrollHeight;
        var maxH = 260;
        var spaceBelow = window.innerHeight - rect.bottom - 8;
        var spaceAbove = rect.top - 8;

        this.list.style.maxHeight = maxH + 'px';

        if (spaceBelow >= Math.min(listH, maxH) || spaceBelow >= spaceAbove) {
            // open below
            this.list.classList.remove('cs-above');
            this.list.style.top = this.display.offsetHeight + 'px';
            this.list.style.bottom = 'auto';
        } else {
            // open above
            this.list.classList.add('cs-above');
            this.list.style.bottom = this.display.offsetHeight + 'px';
            this.list.style.top = 'auto';
        }
    };

    /** Scroll active item into view */
    CustomSelect.prototype._scrollToActive = function () {
        var active = this.list.querySelector('.cs-active');
        if (active) {
            active.scrollIntoView({ block: 'nearest' });
        }
    };

    // ── Public API ───────────────────────────────────────────────────

    /**
     * Upgrade a single <select> element.
     * Safe to call multiple times — skips already-upgraded selects.
     */
    function upgrade(sel) {
        if (sel._customSelect) return sel._customSelect;
        var cs = new CustomSelect(sel);
        sel._customSelect = cs;
        return cs;
    }

    /**
     * Upgrade all <select class="select"> on the page.
     * Call after page content renders or after dynamic content is added.
     */
    function upgradeAll(root) {
        var container = root || document;
        var selects = container.querySelectorAll('select.select');
        for (var i = 0; i < selects.length; i++) {
            upgrade(selects[i]);
        }
    }

    // Expose globally
    window.CustomSelect = {
        upgrade: upgrade,
        upgradeAll: upgradeAll
    };
})();
