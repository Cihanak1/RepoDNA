import '@testing-library/jest-dom';

// Polyfill localStorage in JSDOM / Node 22 if unavailable
if (typeof window !== 'undefined') {
  try {
    if (!window.localStorage || typeof window.localStorage.getItem !== 'function') {
      const memoryStore = new Map<string, string>();
      const mockStorage = {
        getItem: (k: string) => memoryStore.get(k) ?? null,
        setItem: (k: string, v: string) => memoryStore.set(k, String(v)),
        removeItem: (k: string) => memoryStore.delete(k),
        clear: () => memoryStore.clear(),
        key: (i: number) => Array.from(memoryStore.keys())[i] ?? null,
        get length() {
          return memoryStore.size;
        },
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockStorage,
        configurable: true,
        writable: true,
      });
    }
  } catch {
    // ignore
  }
}

// Polyfill ResizeObserver and HTMLDialogElement methods for jsdom unit tests
if (typeof window !== 'undefined') {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver = window.ResizeObserver || ResizeObserverStub;

  if (typeof HTMLDialogElement !== 'undefined') {
    HTMLDialogElement.prototype.showModal =
      HTMLDialogElement.prototype.showModal ||
      function (this: HTMLDialogElement) {
        this.open = true;
      };
    HTMLDialogElement.prototype.close =
      HTMLDialogElement.prototype.close ||
      function (this: HTMLDialogElement) {
        this.open = false;
        this.dispatchEvent(new Event('close'));
      };
  }
}

import { afterEach, vi } from 'vitest';

afterEach(() => {
  vi.restoreAllMocks();
});

