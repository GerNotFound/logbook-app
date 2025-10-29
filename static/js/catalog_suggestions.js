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

    const sanitizeItems = (items) => {
        if (!Array.isArray(items)) {
            return {list: [], exact: new Map()};
        }

        const list = [];
        const exact = new Map();

        items.forEach((raw) => {
            if (!raw || raw.id == null || typeof raw.name !== 'string') {
                return;
            }

            const name = raw.name.trim();
            if (!name) {
                return;
            }

            const normalized = safeNormalize(name);
            if (!normalized) {
                return;
            }

            const entry = {
                id: raw.id,
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

        return (term) => new Promise((resolve) => {
            if (timer) {
                window.clearTimeout(timer);
                timer = null;
            }

            const cleaned = (term || '').trim();
            if (!cleaned) {
                resolve([]);
                return;
            }

            timer = window.setTimeout(() => {
                fetch(`${endpoint}?q=${encodeURIComponent(cleaned)}`, {
                    credentials: 'same-origin',
                    headers: {'Accept': 'application/json'},
                })
                    .then((response) => (response.ok ? response.json() : {results: []}))
                    .then((payload) => {
                        const rows = Array.isArray(payload.results) ? payload.results : [];
                        resolve(rows.slice(0, limit));
                    })
                    .catch(() => resolve([]));
            }, REMOTE_DELAY);
        });
    };

    const generateId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;

    const setupField = ({
        input,
        hiddenInput,
        container,
        form = null,
        items = null,
        endpoint = null,
        limit = DEFAULT_LIMIT,
        globalIconLabel = 'Elemento globale',
    }) => {
        if (!input || !hiddenInput || !container) {
            return null;
        }

        const localData = sanitizeItems(items);
        const remoteFetcher = localData.list.length ? null : createRemoteFetcher(endpoint, limit);

        if (!localData.list.length && !remoteFetcher) {
            return null;
        }

        if (!container.id) {
            container.id = generateId('suggestions');
        }

        input.setAttribute('aria-controls', container.id);
        input.setAttribute('aria-autocomplete', 'list');
        container.setAttribute('role', 'listbox');

        let activeIndex = -1;
        let matches = [];
        let requestToken = 0;
        const cleanupFns = [];

        const hideSuggestions = () => {
            matches = [];
            activeIndex = -1;
            container.innerHTML = '';
            container.classList.remove('is-visible', 'suggestions-list-up');
            container.style.display = 'none';
            container.style.visibility = 'hidden';
            container.removeAttribute('aria-expanded');
            input.removeAttribute('aria-expanded');
        };

        const clearInvalid = () => {
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
        };

        const setHiddenSelection = (item) => {
            hiddenInput.value = item ? item.id : '';
            if (item) {
                hiddenInput.dataset.normalized = item.normalized;
            } else {
                delete hiddenInput.dataset.normalized;
            }
        };

        const highlightActive = () => {
            const nodes = container.querySelectorAll('.suggestion-item');
            nodes.forEach((node, index) => {
                if (index === activeIndex) {
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
        };

        const ensureOrientation = () => {
            if (!container.classList.contains('is-visible')) {
                container.classList.remove('suggestions-list-up');
                return;
            }

            const maxHeight = Math.min(container.scrollHeight || 0, 220);
            const viewport = window.innerHeight || document.documentElement.clientHeight || 0;
            const rect = input.getBoundingClientRect();
            const spaceBelow = viewport - rect.bottom;
            const spaceAbove = rect.top;

            if (spaceBelow < maxHeight + 12 && spaceAbove > spaceBelow) {
                container.classList.add('suggestions-list-up');
            } else {
                container.classList.remove('suggestions-list-up');
            }
        };

        const renderSuggestions = (itemsList) => {
            matches = Array.isArray(itemsList) ? itemsList.slice(0, limit) : [];
            activeIndex = -1;
            container.innerHTML = '';

            if (!matches.length) {
                hideSuggestions();
                return;
            }

            const fragment = document.createDocumentFragment();

            matches.forEach((item, index) => {
                const option = document.createElement('button');
                option.type = 'button';
                option.className = 'suggestion-item';
                option.setAttribute('role', 'option');
                option.dataset.index = index;

                const label = document.createElement('span');
                label.textContent = item.name;
                option.appendChild(label);

                if (item.is_global) {
                    const icon = document.createElement('i');
                    icon.className = 'bi bi-globe2 global-icon';
                    icon.setAttribute('title', globalIconLabel);
                    icon.setAttribute('aria-label', globalIconLabel);
                    option.appendChild(icon);
                }

                option.addEventListener('mousedown', (event) => {
                    event.preventDefault();
                    selectItem(item);
                });

                option.addEventListener('mouseenter', () => {
                    activeIndex = index;
                    highlightActive();
                });

                fragment.appendChild(option);
            });

            container.appendChild(fragment);
            container.scrollTop = 0;
            container.style.display = 'block';
            container.style.visibility = 'visible';
            container.classList.add('is-visible');
            container.setAttribute('aria-expanded', 'true');
            input.setAttribute('aria-expanded', 'true');

            ensureOrientation();
        };

        const filterLocal = (term) => {
            const normalized = safeNormalize(term);
            if (!normalized) {
                return [];
            }

            return localData.list
                .map((item) => ({item, position: item.normalized.indexOf(normalized)}))
                .filter((entry) => entry.position !== -1)
                .sort((a, b) => {
                    const aStarts = a.position === 0;
                    const bStarts = b.position === 0;
                    if (aStarts !== bStarts) {
                        return aStarts ? -1 : 1;
                    }
                    if (a.position !== b.position) {
                        return a.position - b.position;
                    }
                    return a.item.name.localeCompare(b.item.name, 'it', {sensitivity: 'base'});
                })
                .map((entry) => entry.item);
        };

        const selectItem = (item) => {
            if (!item) {
                return;
            }

            input.value = item.name;
            setHiddenSelection(item);
            clearInvalid();
            hideSuggestions();
        };

        const requestSuggestions = () => {
            const term = input.value || '';
            const normalized = safeNormalize(term);

            if (!term.trim()) {
                setHiddenSelection(null);
                hideSuggestions();
                return;
            }

            if (hiddenInput.dataset.normalized !== normalized) {
                setHiddenSelection(null);
            }

            const token = ++requestToken;

            if (localData.list.length) {
                renderSuggestions(filterLocal(term));
                return;
            }

            remoteFetcher(term)
                .then((results) => {
                    if (token !== requestToken) {
                        return;
                    }

                    const sanitized = sanitizeItems(results);

                    sanitized.list.forEach((entry) => {
                        localData.exact.set(entry.normalized, entry);
                    });

                    renderSuggestions(sanitized.list);
                })
                .catch(() => {
                    if (token === requestToken) {
                        hideSuggestions();
                    }
                });
        };

        const moveActive = (offset) => {
            if (!matches.length) {
                return;
            }

            if (activeIndex === -1) {
                activeIndex = offset > 0 ? 0 : matches.length - 1;
            } else {
                activeIndex = (activeIndex + offset + matches.length) % matches.length;
            }

            highlightActive();
        };

        const handleInput = () => {
            clearInvalid();
            requestSuggestions();
        };

        const handleFocus = () => {
            if (input.value.trim()) {
                requestSuggestions();
            }
        };

        const handleKeydown = (event) => {
            switch (event.key) {
                case KEY_ARROW_DOWN:
                    event.preventDefault();
                    moveActive(1);
                    break;
                case KEY_ARROW_UP:
                    event.preventDefault();
                    moveActive(-1);
                    break;
                case KEY_ENTER:
                    if (activeIndex >= 0 && matches[activeIndex]) {
                        event.preventDefault();
                        selectItem(matches[activeIndex]);
                    }
                    break;
                case KEY_ESCAPE:
                    hideSuggestions();
                    break;
                default:
                    break;
            }
        };

        const handleSubmit = (event) => {
            const term = input.value || '';
            const normalized = safeNormalize(term);

            if (hiddenInput.dataset.normalized === normalized && hiddenInput.value) {
                return;
            }

            const exactMatch = localData.exact.get(normalized);
            if (exactMatch) {
                selectItem(exactMatch);
                return;
            }

            input.classList.add('is-invalid');
            input.setAttribute('aria-invalid', 'true');
            requestSuggestions();
            event.preventDefault();
            event.stopPropagation();
        };

        const handleOutsideClick = (event) => {
            if (!container.contains(event.target) && event.target !== input) {
                hideSuggestions();
            }
        };

        const handleBlur = () => {
            window.setTimeout(() => {
                if (!container.matches(':hover') && document.activeElement !== input) {
                    hideSuggestions();
                }
            }, 120);
        };

        input.addEventListener('input', handleInput);
        input.addEventListener('focus', handleFocus);
        input.addEventListener('keydown', handleKeydown);
        input.addEventListener('blur', handleBlur);

        cleanupFns.push(() => {
            input.removeEventListener('input', handleInput);
            input.removeEventListener('focus', handleFocus);
            input.removeEventListener('keydown', handleKeydown);
            input.removeEventListener('blur', handleBlur);
        });

        if (form) {
            form.addEventListener('submit', handleSubmit);
            cleanupFns.push(() => form.removeEventListener('submit', handleSubmit));
        }

        document.addEventListener('mousedown', handleOutsideClick);
        cleanupFns.push(() => document.removeEventListener('mousedown', handleOutsideClick));

        window.addEventListener('resize', ensureOrientation);
        cleanupFns.push(() => window.removeEventListener('resize', ensureOrientation));

        return {
            requestSuggestions,
            clear: hideSuggestions,
            destroy: () => {
                hideSuggestions();
                while (cleanupFns.length) {
                    const cleanup = cleanupFns.pop();
                    if (typeof cleanup === 'function') {
                        cleanup();
                    }
                }
            },
        };
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
