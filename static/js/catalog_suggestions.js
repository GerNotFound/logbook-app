(function (window, document) {
    'use strict';

    const KEY_ENTER = 'Enter';
    const KEY_ESCAPE = 'Escape';
    const KEY_ARROW_UP = 'ArrowUp';
    const KEY_ARROW_DOWN = 'ArrowDown';

    const DEFAULT_LIMIT = 12;
    const REMOTE_DELAY = 220;

    const safeNormalize = (value) => {
        if (typeof value !== 'string') {
            value = value == null ? '' : String(value);
        }

        value = value.trim();
        if (!value) {
            return '';
        }

        try {
            return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        } catch (error) {
            return value.toLowerCase();
        }
    };

    const buildCatalog = (items) => {
        if (!Array.isArray(items)) {
            return {list: [], exact: new Map()};
        }

        const list = [];
        const exact = new Map();

        items.forEach((raw) => {
            if (!raw || raw.id == null) {
                return;
            }

            const name = typeof raw.name === 'string' ? raw.name.trim() : '';
            if (!name) {
                return;
            }

            const normalized = safeNormalize(name);
            if (!normalized) {
                return;
            }

            const entry = {
                id: String(raw.id),
                rawId: raw.id,
                name,
                normalized,
                is_global: Boolean(raw.is_global),
            };

            list.push(entry);
            if (!exact.has(normalized)) {
                exact.set(normalized, entry);
            }
        });

        return {list, exact};
    };

    const createRemoteFetcher = (endpoint, limit) => {
        if (!endpoint) {
            return null;
        }

        let timer = null;
        let requestId = 0;

        return (term) => new Promise((resolve) => {
            if (timer) {
                window.clearTimeout(timer);
                timer = null;
            }

            const cleaned = (term || '').trim();
            if (!cleaned) {
                resolve({list: [], exact: new Map(), token: ++requestId});
                return;
            }

            const token = ++requestId;
            timer = window.setTimeout(() => {
                fetch(`${endpoint}?q=${encodeURIComponent(cleaned)}`, {
                    credentials: 'same-origin',
                    headers: {'Accept': 'application/json'},
                })
                    .then((response) => (response.ok ? response.json() : {results: []}))
                    .then((payload) => {
                        const rows = Array.isArray(payload.results) ? payload.results.slice(0, limit) : [];
                        resolve({
                            ...buildCatalog(rows),
                            token,
                        });
                    })
                    .catch(() => {
                        resolve({list: [], exact: new Map(), token});
                    });
            }, REMOTE_DELAY);
        });
    };

    const generateId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;

    class SuggestionsField {
        constructor({
            input,
            hiddenInput,
            container,
            form = null,
            items = null,
            endpoint = null,
            limit = DEFAULT_LIMIT,
            globalIconLabel = 'Elemento globale',
        }) {
            this.input = input;
            this.hiddenInput = hiddenInput;
            this.container = container;
            this.form = form;
            this.limit = limit;
            this.globalIconLabel = globalIconLabel;

            this.localCatalog = buildCatalog(items);
            this.remoteFetcher = this.localCatalog.list.length ? null : createRemoteFetcher(endpoint, limit);
            this.remoteCatalog = {list: [], exact: new Map()};

            if (!this.container.id) {
                this.container.id = generateId('suggestions');
            }

            this.input.setAttribute('aria-controls', this.container.id);
            this.input.setAttribute('aria-autocomplete', 'list');
            this.container.setAttribute('role', 'listbox');

            this.matches = [];
            this.activeIndex = -1;
            this.latestToken = 0;
            this.cleanupFns = [];
            this.preferredIds = new Set();

            this.registerEvents();
        }

        registerEvents() {
            const handleInput = () => {
                this.clearInvalid();
                this.requestSuggestions();
            };

            const handleFocus = () => {
                this.requestSuggestions({allowEmpty: true});
            };

            const handleKeydown = (event) => {
                switch (event.key) {
                    case KEY_ARROW_DOWN:
                        event.preventDefault();
                        this.moveActive(1);
                        break;
                    case KEY_ARROW_UP:
                        event.preventDefault();
                        this.moveActive(-1);
                        break;
                    case KEY_ENTER:
                        if (this.activeIndex >= 0 && this.matches[this.activeIndex]) {
                            event.preventDefault();
                            this.selectItem(this.matches[this.activeIndex]);
                        }
                        break;
                    case KEY_ESCAPE:
                        this.hideSuggestions();
                        break;
                    default:
                        break;
                }
            };

            const handleBlur = () => {
                window.setTimeout(() => {
                    if (!this.container.matches(':hover') && document.activeElement !== this.input) {
                        this.hideSuggestions();
                    }
                }, 120);
            };

            this.input.addEventListener('input', handleInput);
            this.input.addEventListener('focus', handleFocus);
            this.input.addEventListener('keydown', handleKeydown);
            this.input.addEventListener('blur', handleBlur);

            this.cleanupFns.push(() => {
                this.input.removeEventListener('input', handleInput);
                this.input.removeEventListener('focus', handleFocus);
                this.input.removeEventListener('keydown', handleKeydown);
                this.input.removeEventListener('blur', handleBlur);
            });

            const handleOutsideClick = (event) => {
                if (!this.container.contains(event.target) && event.target !== this.input) {
                    this.hideSuggestions();
                }
            };

            document.addEventListener('mousedown', handleOutsideClick);
            this.cleanupFns.push(() => document.removeEventListener('mousedown', handleOutsideClick));

            const handleResize = () => this.ensureOrientation();
            window.addEventListener('resize', handleResize);
            this.cleanupFns.push(() => window.removeEventListener('resize', handleResize));

            if (this.form) {
                const handleSubmit = (event) => {
                    if (this.validateSelection()) {
                        return;
                    }

                    this.input.classList.add('is-invalid');
                    this.input.setAttribute('aria-invalid', 'true');
                    this.requestSuggestions({allowEmpty: true});
                    event.preventDefault();
                    event.stopPropagation();
                };

                this.form.addEventListener('submit', handleSubmit);
                this.cleanupFns.push(() => this.form.removeEventListener('submit', handleSubmit));
            }
        }

        destroy() {
            this.hideSuggestions();
            while (this.cleanupFns.length) {
                const cleanup = this.cleanupFns.pop();
                if (typeof cleanup === 'function') {
                    cleanup();
                }
            }
        }

        clearInvalid() {
            this.input.classList.remove('is-invalid');
            this.input.removeAttribute('aria-invalid');
        }

        setHiddenSelection(item) {
            if (item) {
                this.hiddenInput.value = item.id;
                this.hiddenInput.dataset.normalized = item.normalized;
            } else {
                this.hiddenInput.value = '';
                delete this.hiddenInput.dataset.normalized;
            }
        }

        setPreferredIds(ids) {
            if (Array.isArray(ids) && ids.length) {
                const normalizedIds = ids
                    .map((value) => {
                        if (value == null) {
                            return null;
                        }

                        return String(value);
                    })
                    .filter((value) => value !== null && value !== '');

                this.preferredIds = new Set(normalizedIds);
            } else {
                this.preferredIds = new Set();
            }
        }

        orderByPreference(items = []) {
            if (!Array.isArray(items) || !this.preferredIds.size) {
                return Array.isArray(items) ? items.slice() : [];
            }

            const preferred = [];
            const others = [];

            items.forEach((item) => {
                if (item && this.preferredIds.has(item.id)) {
                    preferred.push(item);
                } else if (item) {
                    others.push(item);
                }
            });

            return preferred.concat(others);
        }

        ensureOrientation() {
            if (!this.container.classList.contains('is-visible')) {
                this.container.classList.remove('suggestions-list-up');
                return;
            }

            const maxHeight = Math.min(this.container.scrollHeight || 0, 220);
            const viewport = window.innerHeight || document.documentElement.clientHeight || 0;
            const rect = this.input.getBoundingClientRect();
            const spaceBelow = viewport - rect.bottom;
            const spaceAbove = rect.top;

            if (spaceBelow < maxHeight + 12 && spaceAbove > spaceBelow) {
                this.container.classList.add('suggestions-list-up');
            } else {
                this.container.classList.remove('suggestions-list-up');
            }
        }

        highlightActive() {
            const nodes = this.container.querySelectorAll('.suggestion-item');
            nodes.forEach((node, index) => {
                if (index === this.activeIndex) {
                    node.classList.add('active');
                    node.setAttribute('aria-selected', 'true');
                    if (typeof node.scrollIntoView === 'function') {
                        node.scrollIntoView({block: 'nearest'});
                    }
                } else {
                    node.classList.remove('active');
                    node.removeAttribute('aria-selected');
                }
            });
        }

        hideSuggestions() {
            this.matches = [];
            this.activeIndex = -1;
            this.container.innerHTML = '';
            this.container.classList.remove('is-visible', 'suggestions-list-up');
            this.container.style.display = 'none';
            this.container.style.visibility = 'hidden';
            this.container.removeAttribute('aria-expanded');
            this.input.removeAttribute('aria-expanded');
        }

        renderSuggestions(items) {
            const baseItems = Array.isArray(items) ? items : [];
            const orderedItems = this.orderByPreference(baseItems);
            this.matches = orderedItems.slice(0, this.limit);
            this.activeIndex = -1;
            this.container.innerHTML = '';

            if (!this.matches.length) {
                this.hideSuggestions();
                return;
            }

            const fragment = document.createDocumentFragment();

            this.matches.forEach((item, index) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'suggestion-item';
                button.setAttribute('role', 'option');
                button.dataset.index = String(index);

                const label = document.createElement('span');
                label.textContent = item.name;
                button.appendChild(label);

                if (item.is_global) {
                    const icon = document.createElement('i');
                    icon.className = 'bi bi-globe2 global-icon';
                    icon.setAttribute('title', this.globalIconLabel);
                    icon.setAttribute('aria-label', this.globalIconLabel);
                    button.appendChild(icon);
                }

                button.addEventListener('mousedown', (event) => {
                    event.preventDefault();
                    this.selectItem(item);
                });

                button.addEventListener('mouseenter', () => {
                    this.activeIndex = index;
                    this.highlightActive();
                });

                fragment.appendChild(button);
            });

            this.container.appendChild(fragment);
            this.container.scrollTop = 0;
            this.container.style.display = 'block';
            this.container.style.visibility = 'visible';
            this.container.classList.add('is-visible');
            this.container.setAttribute('aria-expanded', 'true');
            this.input.setAttribute('aria-expanded', 'true');

            this.ensureOrientation();
        }

        filterLocal(term) {
            const normalized = safeNormalize(term);
            if (!normalized) {
                return this.orderByPreference(this.localCatalog.list);
            }

            const entries = this.localCatalog.list
                .map((item) => ({item, position: item.normalized.indexOf(normalized)}))
                .filter((entry) => entry.position !== -1);

            entries.sort((a, b) => {
                const aPreferred = this.preferredIds.size && this.preferredIds.has(a.item.id);
                const bPreferred = this.preferredIds.size && this.preferredIds.has(b.item.id);
                if (aPreferred !== bPreferred) {
                    return aPreferred ? -1 : 1;
                }

                const aStarts = a.position === 0;
                const bStarts = b.position === 0;
                if (aStarts !== bStarts) {
                    return aStarts ? -1 : 1;
                }

                if (a.position !== b.position) {
                    return a.position - b.position;
                }

                return a.item.name.localeCompare(b.item.name, 'it', {sensitivity: 'base'});
            });

            return entries.map((entry) => entry.item);
        }

        selectItem(item) {
            if (!item) {
                return;
            }

            this.input.value = item.name;
            this.setHiddenSelection(item);
            this.clearInvalid();
            this.hideSuggestions();
        }

        requestSuggestions(options = {}) {
            const allowEmpty = Boolean(options.allowEmpty);
            const term = this.input.value || '';
            const normalized = safeNormalize(term);

            if (!term.trim()) {
                this.setHiddenSelection(null);
                if (allowEmpty) {
                    if (this.localCatalog.list.length) {
                        this.renderSuggestions(this.localCatalog.list);
                        return;
                    }

                    if (this.remoteCatalog.list.length) {
                        this.renderSuggestions(this.remoteCatalog.list);
                        return;
                    }

                    if (this.remoteFetcher) {
                        this.remoteFetcher('').then((result) => {
                            if (!result || typeof result !== 'object') {
                                this.hideSuggestions();
                                return;
                            }

                            const {list, exact, token} = result;
                            if (token && token < this.latestToken) {
                                return;
                            }

                            this.latestToken = token || this.latestToken;
                            this.remoteCatalog = {
                                list: Array.isArray(list) ? list : [],
                                exact: exact instanceof Map ? exact : new Map(),
                            };

                            this.renderSuggestions(this.remoteCatalog.list);
                        });
                        return;
                    }

                    this.hideSuggestions();
                    return;
                }

                this.hideSuggestions();
                return;
            }

            if (this.hiddenInput.dataset.normalized !== normalized) {
                this.setHiddenSelection(null);
            }

            if (this.localCatalog.list.length) {
                this.renderSuggestions(this.filterLocal(term));
                return;
            }

            if (!this.remoteFetcher) {
                this.renderSuggestions([]);
                return;
            }

            this.remoteFetcher(term).then((result) => {
                if (!result || typeof result !== 'object') {
                    return;
                }

                const {list, exact, token} = result;
                if (token && token < this.latestToken) {
                    return;
                }

                this.latestToken = token || this.latestToken;
                this.remoteCatalog = {
                    list: Array.isArray(list) ? list : [],
                    exact: exact instanceof Map ? exact : new Map(),
                };

                this.renderSuggestions(this.remoteCatalog.list);
            });
        }

        moveActive(offset) {
            if (!this.matches.length) {
                return;
            }

            if (this.activeIndex === -1) {
                this.activeIndex = offset > 0 ? 0 : this.matches.length - 1;
            } else {
                this.activeIndex = (this.activeIndex + offset + this.matches.length) % this.matches.length;
            }

            this.highlightActive();
        }

        getExactMatch(normalized) {
            if (!normalized) {
                return null;
            }

            if (this.hiddenInput.dataset.normalized === normalized && this.hiddenInput.value) {
                return {
                    id: this.hiddenInput.value,
                    name: this.input.value,
                    normalized,
                    is_global: false,
                };
            }

            if (this.localCatalog.exact.has(normalized)) {
                return this.localCatalog.exact.get(normalized);
            }

            if (this.remoteCatalog.exact.has(normalized)) {
                return this.remoteCatalog.exact.get(normalized);
            }

            return null;
        }

        validateSelection() {
            const term = this.input.value || '';
            const normalized = safeNormalize(term);
            const exact = this.getExactMatch(normalized);

            if (exact) {
                this.selectItem(exact);
                return true;
            }

            return false;
        }
    }

    const setupField = (config) => {
        if (!config || !config.input || !config.hiddenInput || !config.container) {
            return null;
        }

        const items = Array.isArray(config.items) ? config.items : [];
        const endpoint = config.endpoint || null;

        if (!items.length && !endpoint) {
            return null;
        }

        return new SuggestionsField(config);
    };

    const initField = (config) => setupField(config);

    const initCollection = ({
        rootSelector,
        inputSelector,
        hiddenSelector,
        suggestionsSelector,
        formSelector = null,
        items = null,
        endpoint = null,
        limit = DEFAULT_LIMIT,
        globalIconLabel = 'Elemento globale',
    }) => {
        const roots = document.querySelectorAll(rootSelector);
        const instances = [];

        roots.forEach((root) => {
            const input = root.querySelector(inputSelector);
            const hiddenInput = root.querySelector(hiddenSelector);
            const container = root.querySelector(suggestionsSelector);
            const form = formSelector ? root.querySelector(formSelector) : root;

            const instance = setupField({
                input,
                hiddenInput,
                container,
                form,
                items,
                endpoint,
                limit,
                globalIconLabel,
            });

            if (instance) {
                instances.push(instance);
            }
        });

        return instances;
    };

    window.LogbookCatalogSuggestions = {
        initField,
        initCollection,
        safeNormalize,
    };

    const readyEventName = 'logbook:suggestions:ready';

    try {
        window.dispatchEvent(new CustomEvent(readyEventName, {detail: window.LogbookCatalogSuggestions}));
    } catch (error) {
        const fallback = document.createEvent('CustomEvent');
        fallback.initCustomEvent(readyEventName, false, false, window.LogbookCatalogSuggestions);
        window.dispatchEvent(fallback);
    }
})(window, document);
