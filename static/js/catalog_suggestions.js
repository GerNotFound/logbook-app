(function (window, document) {
    'use strict';

    const DEFAULT_DELAY = 160;
    const DEFAULT_LIMIT = 5;
    const SUPPORTS_ABORT_CONTROLLER = typeof window.AbortController === 'function';

    const normalizeText = (text) => {
        if (!text) {
            return '';
        }
        try {
            return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        } catch (error) {
            return text.toLowerCase();
        }
    };

    const createSuggestionFetcher = (endpoint, {delay = DEFAULT_DELAY, limit = DEFAULT_LIMIT, onError} = {}) => {
        let controller = null;
        let debounceId = null;

        return (term, callback) => {
            if (SUPPORTS_ABORT_CONTROLLER && controller) {
                controller.abort();
                controller = null;
            }

            if (debounceId) {
                clearTimeout(debounceId);
                debounceId = null;
            }

            if (!term) {
                callback([]);
                return;
            }

            debounceId = window.setTimeout(() => {
                if (SUPPORTS_ABORT_CONTROLLER) {
                    controller = new AbortController();
                }

                const fetchOptions = {
                    headers: {'Accept': 'application/json'},
                    credentials: 'same-origin',
                };

                if (SUPPORTS_ABORT_CONTROLLER && controller) {
                    fetchOptions.signal = controller.signal;
                }

                fetch(`${endpoint}?q=${encodeURIComponent(term)}`, fetchOptions)
                    .then((response) => (response.ok ? response.json() : {results: []}))
                    .then((data) => {
                        const rawResults = Array.isArray(data.results) ? data.results : [];
                        callback(rawResults.slice(0, limit));
                    })
                    .catch((error) => {
                        if (error.name !== 'AbortError') {
                            if (typeof onError === 'function') {
                                onError(error);
                            } else {
                                console.error('Errore durante il recupero dei suggerimenti:', error);
                            }
                        }
                        callback([]);
                    })
                    .finally(() => {
                        controller = null;
                    });
            }, delay);
        };
    };

    const attachSelectionHandler = (element, handler) => {
        const listener = (event) => {
            event.preventDefault();
            handler();
        };

        if (window.PointerEvent) {
            element.addEventListener('pointerdown', listener);
        } else {
            element.addEventListener('mousedown', listener);
            element.addEventListener('touchstart', listener);
        }
    };

    const generateElementId = (prefix = 'suggestions') => {
        return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
    };

    const setupField = ({
        input,
        hiddenInput,
        container,
        form = null,
        fetchSuggestions,
        globalIconLabel = 'Elemento globale',
        maxResults = DEFAULT_LIMIT,
    }) => {
        if (!input || !hiddenInput || !container || typeof fetchSuggestions !== 'function') {
            return null;
        }

        const root = container.closest('.suggestions-container') || container.parentElement || container;
        if (!container.id) {
            container.id = generateElementId();
        }

        container.setAttribute('role', 'listbox');
        input.setAttribute('aria-controls', container.id);
        input.setAttribute('aria-autocomplete', 'list');

        let currentItems = [];
        let activeIndex = -1;

        const ORIENTATION_CLASS = 'suggestions-list-up';

        const getMaxHeight = () => {
            try {
                const raw = window.getComputedStyle(container).maxHeight;
                const parsed = parseInt(raw, 10);
                return Number.isNaN(parsed) ? 220 : parsed;
            } catch (error) {
                return 220;
            }
        };

        const updateOrientation = () => {
            if (container.style.display !== 'block') {
                container.classList.remove(ORIENTATION_CLASS);
                return;
            }

            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            const inputRect = input.getBoundingClientRect();
            const spaceBelow = viewportHeight - inputRect.bottom;
            const spaceAbove = inputRect.top;
            const listHeight = Math.min(container.scrollHeight || 0, getMaxHeight());

            if (spaceBelow < listHeight + 12 && spaceAbove > listHeight + 12) {
                container.classList.add(ORIENTATION_CLASS);
            } else {
                container.classList.remove(ORIENTATION_CLASS);
            }
        };

        const handleResize = () => updateOrientation();
        let resizeListenerActive = false;

        const ensureResizeListener = () => {
            if (!resizeListenerActive) {
                window.addEventListener('resize', handleResize);
                resizeListenerActive = true;
            }
        };

        const removeResizeListener = () => {
            if (resizeListenerActive) {
                window.removeEventListener('resize', handleResize);
                resizeListenerActive = false;
            }
        };

        const hideSuggestions = () => {
            container.style.display = 'none';
            container.innerHTML = '';
            container.removeAttribute('aria-expanded');
            currentItems = [];
            activeIndex = -1;
            container.classList.remove(ORIENTATION_CLASS);
            removeResizeListener();
        };

        const clearActiveClasses = () => {
            container.querySelectorAll('.suggestion-item').forEach((item) => {
                item.classList.remove('active');
                item.removeAttribute('aria-selected');
            });
        };

        const setActiveIndex = (index) => {
            const items = container.querySelectorAll('.suggestion-item');
            if (!items.length) {
                activeIndex = -1;
                return;
            }

            if (index < 0) {
                index = items.length - 1;
            } else if (index >= items.length) {
                index = 0;
            }

            activeIndex = index;
            clearActiveClasses();

            const activeItem = items[index];
            if (activeItem) {
                activeItem.classList.add('active');
                activeItem.setAttribute('aria-selected', 'true');
                activeItem.scrollIntoView({block: 'nearest'});
            }
        };

        const applySelection = (item) => {
            input.value = item.name;
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
            hiddenInput.value = item.id;
            hiddenInput.dataset.selectedTerm = normalizeText(item.name);
            hideSuggestions();
        };

        const renderSuggestions = (items) => {
            currentItems = items.slice(0, maxResults);
            activeIndex = -1;

            if (!currentItems.length) {
                hideSuggestions();
                return;
            }

            const fragment = document.createDocumentFragment();

            currentItems.forEach((item, index) => {
                const suggestion = document.createElement('div');
                suggestion.className = 'suggestion-item';
                suggestion.setAttribute('role', 'option');
                suggestion.tabIndex = -1;

                const label = document.createElement('span');
                label.textContent = item.name;
                suggestion.appendChild(label);

                if (item.is_global) {
                    const icon = document.createElement('i');
                    icon.className = 'bi bi-globe2 global-icon';
                    icon.setAttribute('title', globalIconLabel);
                    icon.setAttribute('aria-label', globalIconLabel);
                    suggestion.appendChild(icon);
                }

                attachSelectionHandler(suggestion, () => applySelection(item));

                suggestion.addEventListener('keydown', (event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        applySelection(item);
                    }
                });

                suggestion.addEventListener('mouseenter', () => {
                    clearActiveClasses();
                    suggestion.classList.add('active');
                    suggestion.setAttribute('aria-selected', 'true');
                    activeIndex = index;
                });

                fragment.appendChild(suggestion);
            });

            container.innerHTML = '';
            container.appendChild(fragment);
            container.style.display = 'block';
            container.setAttribute('aria-expanded', 'true');
            container.scrollTop = 0;
            ensureResizeListener();
            if (typeof window.requestAnimationFrame === 'function') {
                window.requestAnimationFrame(updateOrientation);
            } else {
                updateOrientation();
            }
        };

        const moveActive = (direction) => {
            if (!currentItems.length) {
                return;
            }
            const items = container.querySelectorAll('.suggestion-item');
            if (!items.length) {
                return;
            }

            const nextIndex = activeIndex === -1 ? (direction > 0 ? 0 : items.length - 1) : activeIndex + direction;
            setActiveIndex(nextIndex);
        };

        const applyActiveSelection = () => {
            if (activeIndex < 0 || !currentItems[activeIndex]) {
                return false;
            }
            applySelection(currentItems[activeIndex]);
            return true;
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

            fetchSuggestions(term, renderSuggestions);
        };

        input.addEventListener('input', () => {
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
            requestSuggestions();
        });

        input.addEventListener('focus', requestSuggestions);

        input.addEventListener('keydown', (event) => {
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
                if (applyActiveSelection()) {
                    event.preventDefault();
                }
                return;
            }
            if (event.key === 'Escape') {
                hideSuggestions();
                hiddenInput.value = '';
                delete hiddenInput.dataset.selectedTerm;
            }
        });

        if (form) {
            form.addEventListener('submit', () => {
                if (hiddenInput.value) {
                    return;
                }

                const term = input.value.trim();
                if (!term) {
                    hideSuggestions();
                    input.classList.add('is-invalid');
                    input.setAttribute('aria-invalid', 'true');
                    return;
                }

                const normalizedTerm = normalizeText(term);
                const storedTerm = hiddenInput.dataset.selectedTerm || '';
                if (storedTerm && storedTerm === normalizedTerm) {
                    return;
                }

                if (currentItems.length) {
                    applySelection(currentItems[0]);
                }
            });
        }

        const outsideClickListener = (event) => {
            if (!root.contains(event.target)) {
                hideSuggestions();
            }
        };
        document.addEventListener('click', outsideClickListener);

        return {
            requestSuggestions,
            destroy: () => {
                document.removeEventListener('click', outsideClickListener);
                removeResizeListener();
            },
            clear: hideSuggestions,
        };
    };

    const initCollection = ({
        rootSelector,
        inputSelector,
        hiddenSelector,
        suggestionsSelector,
        endpoint,
        limit = DEFAULT_LIMIT,
        delay = DEFAULT_DELAY,
        globalIconLabel,
    }) => {
        const forms = document.querySelectorAll(rootSelector);
        const instances = [];

        forms.forEach((form) => {
            const input = form.querySelector(inputSelector);
            const hidden = form.querySelector(hiddenSelector);
            const container = form.querySelector(suggestionsSelector);
            const fetchSuggestions = createSuggestionFetcher(endpoint, {delay, limit});
            const instance = setupField({
                input,
                hiddenInput: hidden,
                container,
                form,
                fetchSuggestions,
                globalIconLabel,
                maxResults: limit,
            });
            if (instance) {
                instances.push(instance);
            }
        });

        return instances;
    };

    const initField = ({
        input,
        hiddenInput,
        container,
        form = null,
        endpoint,
        limit = DEFAULT_LIMIT,
        delay = DEFAULT_DELAY,
        globalIconLabel,
    }) => {
        const fetchSuggestions = createSuggestionFetcher(endpoint, {delay, limit});
        return setupField({
            input,
            hiddenInput,
            container,
            form,
            fetchSuggestions,
            globalIconLabel,
            maxResults: limit,
        });
    };

    window.LogbookCatalogSuggestions = {
        initCollection,
        initField,
        normalizeText,
    };

    const readyEventName = 'logbook:suggestions:ready';
    try {
        window.dispatchEvent(new CustomEvent(readyEventName, {detail: window.LogbookCatalogSuggestions}));
    } catch (error) {
        const fallbackEvent = document.createEvent('CustomEvent');
        fallbackEvent.initCustomEvent(readyEventName, false, false, window.LogbookCatalogSuggestions);
        window.dispatchEvent(fallbackEvent);
    }
})(window, document);
