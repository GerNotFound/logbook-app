(function (window, document) {
    'use strict';

    const DEFAULT_LIMIT = 8;
    const DEFAULT_DELAY = 160;

    const KEY_ENTER = 'Enter';
    const KEY_ESCAPE = 'Escape';
    const KEY_ARROW_UP = 'ArrowUp';
    const KEY_ARROW_DOWN = 'ArrowDown';

    const normalizeText = (text) => {
        if (!text) {
            return '';
        }

        try {
            return text
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase();
        } catch (error) {
            return String(text).toLowerCase();
        }
    };

    const sanitizeItem = (raw) => {
        if (!raw || typeof raw.name !== 'string' || raw.id === undefined || raw.id === null) {
            return null;
        }

        const trimmedName = raw.name.trim();
        if (!trimmedName) {
            return null;
        }

        const normalized = normalizeText(trimmedName);
        if (!normalized) {
            return null;
        }

        return {
            id: raw.id,
            name: trimmedName,
            is_global: Boolean(raw.is_global),
            normalized,
        };
    };

    const prepareLocalItems = (items) => {
        if (!Array.isArray(items)) {
            return {list: [], exact: new Map()};
        }

        const list = [];
        const exact = new Map();

        items.forEach((raw) => {
            const item = sanitizeItem(raw);
            if (!item) {
                return;
            }
            list.push(item);
            if (!exact.has(item.normalized)) {
                exact.set(item.normalized, item);
            }
        });

        return {list, exact};
    };

    const createRemoteFetcher = (endpoint, limit, delay) => {
        if (!endpoint) {
            return null;
        }

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
                        const sanitized = results
                            .map((item) => sanitizeItem(item))
                            .filter(Boolean)
                            .slice(0, limit);
                        resolve(sanitized);
                    })
                    .catch(() => resolve([]));
            }, delay);
        });
    };

    const buildLocalMatcher = (items, limit) => {
        const {list, exact} = prepareLocalItems(items);
        if (!list.length) {
            return null;
        }

        const match = (term) => {
            const normalizedTerm = normalizeText(term);
            if (!normalizedTerm) {
                return [];
            }

            return list
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
        };

        return {
            match,
            exact,
        };
    };

    const generateElementId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;

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

        const localSource = buildLocalMatcher(items, limit);
        const remoteFetcher = localSource ? null : createRemoteFetcher(endpoint, limit, delay);

        if (!localSource && !remoteFetcher) {
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

        const exactMap = localSource ? new Map(localSource.exact) : new Map();

        const root =
            container.closest('.suggestions-container') ||
            container.parentElement ||
            input.parentElement ||
            container;

        const clearInvalidState = () => {
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
        };

        const hideSuggestions = () => {
            container.classList.remove('is-visible', 'suggestions-list-up');
            container.style.display = 'none';
            container.style.visibility = 'hidden';
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
                // ignore style inspection errors
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
            exactMap.set(item.normalized, item);
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

                container.appendChild(option);

                option.addEventListener('mouseenter', () => setActiveIndex(index));
                option.addEventListener('focus', () => setActiveIndex(index));
            });

            container.style.display = 'block';
            container.style.visibility = 'visible';
            container.classList.add('is-visible');
            container.setAttribute('aria-expanded', 'true');
            input.setAttribute('aria-expanded', 'true');
            container.scrollTop = 0;
            updateOrientation();
        };

        const resolveLocalExact = (term) => {
            if (!term) {
                return null;
            }
            return exactMap.get(normalizeText(term)) || null;
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

            const handleResults = (results, token) => {
                if (token !== state.requestToken) {
                    return;
                }
                const validResults = (Array.isArray(results) ? results : [])
                    .map((item) => sanitizeItem(item))
                    .filter(Boolean)
                    .slice(0, limit);

                validResults.forEach((item) => {
                    exactMap.set(item.normalized, item);
                });

                renderSuggestions(validResults);
            };

            const token = ++state.requestToken;

            if (localSource) {
                const results = localSource.match(term);
                handleResults(results, token);
                return;
            }

            if (!remoteFetcher) {
                hideSuggestions();
                return;
            }

            remoteFetcher(term)
                .then((results) => handleResults(results, token))
                .catch(() => {
                    if (token === state.requestToken) {
                        hideSuggestions();
                    }
                });
        };

        const moveActive = (direction) => {
            if (!state.matches.length) {
                return;
            }
            if (state.activeIndex === -1) {
                setActiveIndex(direction > 0 ? 0 : state.matches.length - 1);
            } else {
                setActiveIndex(state.activeIndex + direction);
            }
        };

        const handleInput = () => {
            clearInvalidState();
            requestSuggestions();
        };

        const handleKeydown = (event) => {
            if (event.key === KEY_ARROW_DOWN) {
                event.preventDefault();
                moveActive(1);
                return;
            }
            if (event.key === KEY_ARROW_UP) {
                event.preventDefault();
                moveActive(-1);
                return;
            }
            if (event.key === KEY_ENTER) {
                if (state.activeIndex >= 0 && state.matches[state.activeIndex]) {
                    event.preventDefault();
                    selectItem(state.matches[state.activeIndex]);
                }
                return;
            }
            if (event.key === KEY_ESCAPE) {
                hideSuggestions();
            }
        };

        const handleFocus = () => {
            if (input.value.trim()) {
                requestSuggestions();
            }
        };

        const handleContainerClick = (event) => {
            const target = event.target.closest('.suggestion-item');
            if (!target) {
                return;
            }
            event.preventDefault();
            const index = Number.parseInt(target.dataset.index, 10);
            if (Number.isNaN(index) || !state.matches[index]) {
                return;
            }
            selectItem(state.matches[index]);
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

            const exact = resolveLocalExact(term);
            if (exact) {
                selectItem(exact);
                return;
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
        container.addEventListener('mousedown', handleContainerClick);
        container.addEventListener('click', handleContainerClick);

        cleanupFns.push(() => {
            input.removeEventListener('input', handleInput);
            input.removeEventListener('keydown', handleKeydown);
            input.removeEventListener('focus', handleFocus);
            container.removeEventListener('mousedown', handleContainerClick);
            container.removeEventListener('click', handleContainerClick);
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
