(function (window, document) {
    'use strict';

    const DEFAULT_LIMIT = 8;
    const DEFAULT_DELAY = 150;

    const normalizeText = (text) => {
        if (!text) {
            return '';
        }
        try {
            return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        } catch (error) {
            return String(text).toLowerCase();
        }
    };

    const generateElementId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;

    const createRemoteFetcher = (endpoint, limit, delay) => {
        let timerId = null;

        return (term) => new Promise((resolve) => {
            if (timerId) {
                window.clearTimeout(timerId);
                timerId = null;
            }

            if (!term) {
                resolve([]);
                return;
            }

            timerId = window.setTimeout(() => {
                fetch(`${endpoint}?q=${encodeURIComponent(term)}`, {
                    headers: {'Accept': 'application/json'},
                    credentials: 'same-origin',
                })
                    .then((response) => (response.ok ? response.json() : {results: []}))
                    .then((payload) => {
                        const results = Array.isArray(payload.results) ? payload.results : [];
                        resolve(results.slice(0, limit));
                    })
                    .catch(() => resolve([]));
            }, delay);
        });
    };

    const createLocalSource = (items, limit) => {
        if (!Array.isArray(items) || !items.length) {
            return null;
        }

        const indexed = items
            .filter((item) => item && typeof item.name === 'string' && item.id !== undefined)
            .map((item) => ({
                id: item.id,
                name: item.name,
                is_global: Boolean(item.is_global),
                normalized: normalizeText(item.name),
            }));

        if (!indexed.length) {
            return null;
        }

        const exactMap = new Map();
        indexed.forEach((item) => {
            if (!exactMap.has(item.normalized)) {
                exactMap.set(item.normalized, item);
            }
        });

        const request = (term) => {
            const normalizedTerm = normalizeText(term);
            if (!normalizedTerm) {
                return Promise.resolve([]);
            }

            const matches = indexed
                .map((item) => {
                    const index = item.normalized.indexOf(normalizedTerm);
                    return index === -1 ? null : {item, index};
                })
                .filter(Boolean)
                .sort((a, b) => {
                    const aStarts = a.index === 0;
                    const bStarts = b.index === 0;
                    if (aStarts !== bStarts) {
                        return aStarts ? -1 : 1;
                    }
                    if (a.index !== b.index) {
                        return a.index - b.index;
                    }
                    return a.item.name.localeCompare(b.item.name, 'it', {sensitivity: 'base'});
                })
                .slice(0, limit)
                .map((entry) => entry.item);

            return Promise.resolve(matches);
        };

        return {
            type: 'local',
            request,
            exactLookup: (normalizedName) => exactMap.get(normalizedName) || null,
        };
    };

    const createRemoteSource = (endpoint, limit, delay) => {
        if (!endpoint) {
            return null;
        }

        const fetcher = createRemoteFetcher(endpoint, limit, delay);

        return {
            type: 'remote',
            request: (term) => fetcher(term).then((results) =>
                (Array.isArray(results) ? results : []).map((item) => ({
                    id: item.id,
                    name: item.name,
                    is_global: Boolean(item.is_global),
                    normalized: normalizeText(item.name),
                }))),
            exactLookup: () => null,
        };
    };

    const setupField = ({
        input,
        hiddenInput,
        container,
        form = null,
        items = null,
        endpoint = null,
        limit = DEFAULT_LIMIT,
        delay = DEFAULT_DELAY,
        globalIconLabel = 'Elemento globale',
    }) => {
        if (!input || !hiddenInput || !container) {
            return null;
        }

        const source =
            createLocalSource(items, limit) ||
            createRemoteSource(endpoint, limit, delay);

        if (!source) {
            return null;
        }

        if (!container.id) {
            container.id = generateElementId('suggestions');
        }

        container.setAttribute('role', 'listbox');
        input.setAttribute('aria-controls', container.id);
        input.setAttribute('aria-autocomplete', 'list');

        const cleanupFns = [];
        const state = {
            matches: [],
            activeIndex: -1,
            requestToken: 0,
        };

        const root = container.closest('.suggestions-container') || container.parentElement || input.parentElement || container;

        const clearInvalidState = () => {
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
        };

        const hideSuggestions = () => {
            container.classList.remove('is-visible', 'suggestions-list-up');
            container.style.display = 'none';
            container.removeAttribute('aria-expanded');
            input.removeAttribute('aria-expanded');
            container.innerHTML = '';
            state.matches = [];
            state.activeIndex = -1;
        };

        const clearActiveClasses = () => {
            container.querySelectorAll('.suggestion-item').forEach((item) => {
                item.classList.remove('active');
                item.removeAttribute('aria-selected');
            });
        };

        const setActiveIndex = (index) => {
            const itemsNodes = container.querySelectorAll('.suggestion-item');
            if (!itemsNodes.length) {
                state.activeIndex = -1;
                return;
            }

            let nextIndex = index;
            if (nextIndex < 0) {
                nextIndex = itemsNodes.length - 1;
            } else if (nextIndex >= itemsNodes.length) {
                nextIndex = 0;
            }

            state.activeIndex = nextIndex;
            clearActiveClasses();
            const activeItem = itemsNodes[nextIndex];
            if (activeItem) {
                activeItem.classList.add('active');
                activeItem.setAttribute('aria-selected', 'true');
                if (typeof activeItem.scrollIntoView === 'function') {
                    activeItem.scrollIntoView({block: 'nearest'});
                }
            }
        };

        const updateOrientation = () => {
            if (!container.classList.contains('is-visible')) {
                container.classList.remove('suggestions-list-up');
                return;
            }

            let maxHeight = 220;
            try {
                const raw = window.getComputedStyle(container).maxHeight;
                const parsed = parseInt(raw, 10);
                if (!Number.isNaN(parsed)) {
                    maxHeight = parsed;
                }
            } catch (error) {
                // ignore
            }

            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            const inputRect = input.getBoundingClientRect();
            const spaceBelow = viewportHeight - inputRect.bottom;
            const spaceAbove = inputRect.top;
            const listHeight = Math.min(container.scrollHeight || 0, maxHeight);

            if (spaceBelow < listHeight + 12 && spaceAbove > spaceBelow) {
                container.classList.add('suggestions-list-up');
            } else {
                container.classList.remove('suggestions-list-up');
            }
        };

        const selectItem = (item) => {
            if (!item) {
                return;
            }
            input.value = item.name;
            hiddenInput.value = item.id;
            hiddenInput.dataset.selectedTerm = item.normalized;
            clearInvalidState();
            hideSuggestions();
        };

        const renderSuggestions = (itemsList) => {
            state.matches = Array.isArray(itemsList) ? itemsList.slice() : [];
            state.activeIndex = -1;

            if (!state.matches.length) {
                hideSuggestions();
                return;
            }

            container.innerHTML = '';

            state.matches.forEach((item, index) => {
                const option = document.createElement('div');
                option.className = 'suggestion-item';
                option.setAttribute('role', 'option');
                option.tabIndex = -1;

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

                option.addEventListener('click', (event) => {
                    event.preventDefault();
                    selectItem(item);
                });

                option.addEventListener('mouseenter', () => {
                    state.activeIndex = index;
                    clearActiveClasses();
                    option.classList.add('active');
                    option.setAttribute('aria-selected', 'true');
                });

                container.appendChild(option);
            });

            container.style.display = 'block';
            container.classList.add('is-visible');
            container.setAttribute('aria-expanded', 'true');
            input.setAttribute('aria-expanded', 'true');
            container.scrollTop = 0;
            updateOrientation();
        };

        const requestSuggestions = () => {
            const term = input.value.trim();
            const normalizedTerm = normalizeText(term);
            const storedTerm = hiddenInput.dataset.selectedTerm || '';

            if (storedTerm !== normalizedTerm) {
                hiddenInput.value = '';
                delete hiddenInput.dataset.selectedTerm;
            }

            if (!term) {
                hideSuggestions();
                return;
            }

            const token = ++state.requestToken;
            source
                .request(term)
                .then((results) => {
                    if (token !== state.requestToken) {
                        return;
                    }
                    renderSuggestions(results.slice(0, limit));
                })
                .catch(() => {
                    if (token !== state.requestToken) {
                        return;
                    }
                    hideSuggestions();
                });
        };

        const moveActive = (direction) => {
            if (!state.matches.length) {
                return;
            }
            setActiveIndex(state.activeIndex === -1 ? (direction > 0 ? 0 : state.matches.length - 1) : state.activeIndex + direction);
        };

        const handleInput = () => {
            clearInvalidState();
            requestSuggestions();
        };

        const handleKeydown = (event) => {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                moveActive(1);
                return;
            }
            if (event.key === 'ArrowUp') {
                event.preventDefault();
                moveActive(-1);
                return;
            }
            if (event.key === 'Enter') {
                if (state.activeIndex >= 0 && state.matches[state.activeIndex]) {
                    event.preventDefault();
                    selectItem(state.matches[state.activeIndex]);
                }
                return;
            }
            if (event.key === 'Escape') {
                hideSuggestions();
            }
        };

        const handleFocus = () => {
            if (input.value.trim()) {
                requestSuggestions();
            }
        };

        const handleSubmit = (event) => {
            if (hiddenInput.value) {
                return;
            }

            const term = input.value.trim();
            if (!term) {
                hideSuggestions();
                input.classList.add('is-invalid');
                input.setAttribute('aria-invalid', 'true');
                event.preventDefault();
                return;
            }

            const normalizedTerm = normalizeText(term);
            const storedTerm = hiddenInput.dataset.selectedTerm || '';
            if (storedTerm && storedTerm === normalizedTerm) {
                return;
            }

            if (typeof source.exactLookup === 'function') {
                const exact = source.exactLookup(normalizedTerm);
                if (exact) {
                    selectItem(exact);
                    return;
                }
            }

            input.classList.add('is-invalid');
            input.setAttribute('aria-invalid', 'true');
            event.preventDefault();
            requestSuggestions();
            input.focus();
        };

        const outsideClickListener = (event) => {
            if (!root.contains(event.target)) {
                hideSuggestions();
            }
        };

        const resizeListener = () => updateOrientation();

        input.addEventListener('input', handleInput);
        input.addEventListener('keydown', handleKeydown);
        input.addEventListener('focus', handleFocus);

        cleanupFns.push(() => {
            input.removeEventListener('input', handleInput);
            input.removeEventListener('keydown', handleKeydown);
            input.removeEventListener('focus', handleFocus);
        });

        if (form) {
            form.addEventListener('submit', handleSubmit);
            cleanupFns.push(() => form.removeEventListener('submit', handleSubmit));
        }

        document.addEventListener('mousedown', outsideClickListener);
        cleanupFns.push(() => document.removeEventListener('mousedown', outsideClickListener));

        window.addEventListener('resize', resizeListener);
        cleanupFns.push(() => window.removeEventListener('resize', resizeListener));

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
        delay = DEFAULT_DELAY,
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
                delay,
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
        normalizeText,
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
