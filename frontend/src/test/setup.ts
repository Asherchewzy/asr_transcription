import '@testing-library/jest-dom';
import { vi, afterEach, beforeAll } from 'vitest';

// cleanup after each test
afterEach(() => {
  vi.clearAllMocks();
  vi.clearAllTimers();
});

// mock window.matchMedia for responsive tests
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

// mock IntersectionObserver
beforeAll(() => {
  const mockIntersectionObserver = vi.fn();
  mockIntersectionObserver.mockReturnValue({
    observe: () => null,
    unobserve: () => null,
    disconnect: () => null,
  });
  window.IntersectionObserver = mockIntersectionObserver as unknown as typeof IntersectionObserver;
});

// mock URL.createObjectURL for file handling tests
beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  URL.revokeObjectURL = vi.fn();
});

// mock DataTransfer for multi-file upload tests
beforeAll(() => {
  (window as unknown as { DataTransfer: typeof DataTransfer }).DataTransfer = class DataTransfer {
    items: { add: ReturnType<typeof vi.fn>; length: number };
    files: { length: number; [Symbol.iterator]: () => Generator<never, void, unknown> };
    constructor() {
      this.items = {
        add: vi.fn(),
        length: 0,
      };
      this.files = {
        length: 0,
        [Symbol.iterator]: function* () {
          yield* [];
        },
      };
    }
  } as unknown as typeof DataTransfer;
});

// suppress console errors in tests (optional - uncomment if needed)
// vi.spyOn(console, 'error').mockImplementation(() => {});
// vi.spyOn(console, 'warn').mockImplementation(() => {});
