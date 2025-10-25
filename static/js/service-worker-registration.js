(function (window, document) {
    'use strict';

    const NAMESPACE = 'LogbookServiceWorkerRegistration';
    if (window[NAMESPACE]) {
        return;
    }

    function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            return;
        }
        const swUrl = document.body?.dataset?.swUrl || '/service-worker.js';
        navigator.serviceWorker.register(swUrl)
            .then(() => {
                console.log('Service Worker registrato.');
            })
            .catch((error) => {
                console.log('Registrazione Service Worker fallita:', error);
            });
    }

    window.addEventListener('load', registerServiceWorker);

    window[NAMESPACE] = Object.freeze({
        register: registerServiceWorker
    });
})(window, document);
