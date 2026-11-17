import { afterEach, describe, expect, it, vi } from 'vitest';
import { getDashboardStats, logout, setAccessToken } from '../services/api';

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

describe('API authentication session', () => {
  it('sends authenticated logout to the shared auth endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
    setAccessToken('active-session-token');

    await logout();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/logout',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({}),
      }),
    );
    expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe(
      'Bearer active-session-token',
    );
  });

  it('clears a rejected token and notifies the app when the server returns 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response('{"detail":"Session expired"}', {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetchMock);
    setAccessToken('expired-session-token');
    const onExpired = vi.fn();
    window.addEventListener('resolvex:auth-expired', onExpired);

    try {
      await expect(getDashboardStats()).rejects.toThrow('Failed to fetch dashboard stats');
      expect(onExpired).toHaveBeenCalledOnce();

      await getDashboardStats();
      expect(fetchMock.mock.calls[1][1].headers.get('Authorization')).toBeNull();
    } finally {
      window.removeEventListener('resolvex:auth-expired', onExpired);
    }
  });
});
