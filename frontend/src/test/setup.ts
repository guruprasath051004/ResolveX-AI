import '@testing-library/jest-dom';

if (typeof window !== 'undefined') {
  if (!window.ResizeObserver) {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }

  // Enhance jsdom history.back / forward to update location and dispatch popstate synchronously
  if (window.history) {
    const sym = Object.getOwnPropertySymbols(window.history)[0];
    const impl = sym ? (window.history as any)[sym] : null;
    const sh = impl?._window?._sessionHistory;

    if (sh) {
      window.history.back = () => {
        if (sh._currentIndex > 0) {
          sh._currentIndex -= 1;
          const entry = sh._entries[sh._currentIndex];
          if (entry && entry.url) {
            const u = entry.url;
            const href =
              u.scheme +
              '://' +
              u.host +
              (u.port ? ':' + u.port : '') +
              '/' +
              (u.path || []).join('/') +
              (u.query ? '?' + u.query : '');
            window.history.replaceState(entry.stateObject, '', href);
            window.dispatchEvent(new PopStateEvent('popstate', { state: entry.stateObject }));
          }
        }
      };

      window.history.forward = () => {
        if (sh._currentIndex < sh._entries.length - 1) {
          sh._currentIndex += 1;
          const entry = sh._entries[sh._currentIndex];
          if (entry && entry.url) {
            const u = entry.url;
            const href =
              u.scheme +
              '://' +
              u.host +
              (u.port ? ':' + u.port : '') +
              '/' +
              (u.path || []).join('/') +
              (u.query ? '?' + u.query : '');
            window.history.replaceState(entry.stateObject, '', href);
            window.dispatchEvent(new PopStateEvent('popstate', { state: entry.stateObject }));
          }
        }
      };
    }
  }
}

