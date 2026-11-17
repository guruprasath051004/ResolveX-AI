import { User } from '../services/api';

export const ROLE_PAGES = {
  employee: ['home', 'chat'],
  support_engineer: [
    'dashboard',
    'incidents',
    'approvals',
    'command-center',
    'mcp-monitor',
    'sla',
    'assets',
  ],
  administrator: [
    'dashboard',
    'incidents',
    'approvals',
    'command-center',
    'scenario-lab',
    'mcp-monitor',
    'sla',
    'assets',
    'knowledge',
  ],
} as const satisfies Record<User['role'], readonly string[]>;

export type AppPage = typeof ROLE_PAGES[keyof typeof ROLE_PAGES][number];

export function getDefaultPage(role: User['role']): AppPage {
  return role === 'employee' ? 'home' : 'dashboard';
}

export function canAccessPage(role: User['role'], page: string): page is AppPage {
  return ROLE_PAGES[role].some((allowedPage) => allowedPage === page);
}
