const KEY = "deadlock-dashboard:view:v1";

export function readTabState(storage) {
  try {
    storage ??= window.sessionStorage;
    const state = JSON.parse(storage.getItem(KEY));
    if (
      !state ||
      !/^\d+$/.test(state.account) ||
      !["all", "season1"].includes(state.scope) ||
      !Number.isSafeInteger(state.page) ||
      state.page < 1
    )
      return null;
    return state;
  } catch {
    return null;
  }
}

export function saveTabState(state, storage) {
  try {
    storage ??= window.sessionStorage;
    storage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Browsers may block storage; player lookup should still work.
  }
}
