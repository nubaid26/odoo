// Simple hash-based SPA router

type RouteHandler = () => void;

const routes: Map<string, RouteHandler> = new Map();
let notFoundHandler: RouteHandler = () => {
  document.getElementById('app')!.innerHTML = '<div class="empty-state"><h3>404</h3><p>Page not found</p></div>';
};

export function route(path: string, handler: RouteHandler) {
  routes.set(path, handler);
}

export function navigate(path: string) {
  window.location.hash = `#${path}`;
}

export function currentRoute(): string {
  return window.location.hash.slice(1) || '/login';
}

export function startRouter() {
  const handleRoute = () => {
    const path = currentRoute();
    // Check exact match first
    const handler = routes.get(path);
    if (handler) {
      handler();
      return;
    }
    // Check parameterized routes (e.g., /expenses/:id)
    for (const [pattern, h] of routes) {
      if (pattern.includes(':')) {
        const regex = new RegExp('^' + pattern.replace(/:([^/]+)/g, '([^/]+)') + '$');
        if (regex.test(path)) {
          h();
          return;
        }
      }
    }
    notFoundHandler();
  };

  window.addEventListener('hashchange', handleRoute);
  handleRoute();
}

export function getParam(pattern: string, paramName: string): string | null {
  const path = currentRoute();
  const paramNames: string[] = [];
  const regex = new RegExp('^' + pattern.replace(/:([^/]+)/g, (_, name) => {
    paramNames.push(name);
    return '([^/]+)';
  }) + '$');
  const match = path.match(regex);
  if (!match) return null;
  const idx = paramNames.indexOf(paramName);
  return idx >= 0 ? match[idx + 1] : null;
}

export function onNotFound(handler: RouteHandler) {
  notFoundHandler = handler;
}
