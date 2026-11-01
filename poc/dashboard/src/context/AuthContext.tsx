import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  AuthUser,
  Organization,
  Department,
  LoginDto,
  RegisterOrgDto,
  AcceptInviteDto,
} from '../types/auth';
import {
  AUTH_TOKEN_KEY,
  AUTH_SESSION_KEY,
  loginOrganizationUser,
  registerOrganization,
  acceptOrgInvitation,
  getCurrentUserProfile,
} from '../services/api';
import { eventStream } from '../services/eventStream';

export interface AuthContextType {
  token: string | null;
  user: AuthUser | null;
  organization: Organization | null;
  departments: Department[];
  activeDepartmentId: string | null;
  setActiveDepartmentId: (id: string | null) => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginDto) => Promise<void>;
  register: (data: RegisterOrgDto) => Promise<void>;
  acceptInvitation: (data: AcceptInviteDto) => Promise<void>;
  logout: () => void;
  refreshUserProfile: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

const getDeptId = (d?: Department | null): string | null => {
  if (!d) return null;
  return d.id || d.department_id || null;
};

const normalizeDepartments = (list?: Department[] | null): Department[] =>
  (list || []).map((d) => {
    const resolvedId = getDeptId(d) || '';
    return {
      ...d,
      id: resolvedId,
      department_id: d.department_id || resolvedId,
    };
  });

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(AUTH_TOKEN_KEY));

  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const cached = localStorage.getItem(AUTH_SESSION_KEY);
      return cached ? JSON.parse(cached).user : null;
    } catch {
      return null;
    }
  });

  const [organization, setOrganization] = useState<Organization | null>(() => {
    try {
      const cached = localStorage.getItem(AUTH_SESSION_KEY);
      return cached ? JSON.parse(cached).organization : null;
    } catch {
      return null;
    }
  });

  const [departments, setDepartments] = useState<Department[]>(() => {
    try {
      const cached = localStorage.getItem(AUTH_SESSION_KEY);
      return cached ? normalizeDepartments(JSON.parse(cached).departments) : [];
    } catch {
      return [];
    }
  });

  const [activeDepartmentId, setActiveDepartmentId] = useState<string | null>(() => {
    try {
      const cached = localStorage.getItem(AUTH_SESSION_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        const normalized = normalizeDepartments(parsed.departments);
        if (normalized.length > 0) {
          return normalized[0].id;
        }
      }
      return null;
    } catch {
      return null;
    }
  });

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const isAuthenticated = Boolean(token && user);

  const saveAuthSession = (
    newToken: string,
    newUser: AuthUser,
    newOrg: Organization | null,
    newDepts: Department[]
  ) => {
    const normalizedDepts = normalizeDepartments(newDepts);
    localStorage.setItem(AUTH_TOKEN_KEY, newToken);
    localStorage.setItem(
      AUTH_SESSION_KEY,
      JSON.stringify({ user: newUser, organization: newOrg, departments: normalizedDepts })
    );
    setToken(newToken);
    setUser(newUser);
    setOrganization(newOrg);
    setDepartments(normalizedDepts);
    if (normalizedDepts.length > 0) {
      setActiveDepartmentId((prev) => {
        const exists = normalizedDepts.some((d) => d.id === prev);
        return exists ? prev : normalizedDepts[0].id;
      });
    }
  };

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    setToken(null);
    setUser(null);
    setOrganization(null);
    setDepartments([]);
    setActiveDepartmentId(null);
    eventStream.disconnect();
  }, []);

  const refreshUserProfile = useCallback(async () => {
    const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!storedToken) {
      logout();
      return;
    }
    try {
      const res = await getCurrentUserProfile();
      const { user: refreshedUser, organization: refreshedOrg, departments: refreshedDepts } = res.data;
      const normalizedDepts = normalizeDepartments(refreshedDepts);
      setUser(refreshedUser);
      setOrganization(refreshedOrg);
      setDepartments(normalizedDepts);
      localStorage.setItem(
        AUTH_SESSION_KEY,
        JSON.stringify({
          user: refreshedUser,
          organization: refreshedOrg,
          departments: normalizedDepts,
        })
      );
      if (normalizedDepts.length > 0) {
        setActiveDepartmentId((prev) => {
          const exists = normalizedDepts.some((d) => d.id === prev);
          return exists ? prev : normalizedDepts[0].id;
        });
      }
      eventStream.connect();
    } catch (err: any) {
      if (err.response?.status === 401) {
        logout();
      }
    }
  }, [logout]);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
      if (storedToken) {
        try {
          const res = await getCurrentUserProfile();
          const { user: refreshedUser, organization: refreshedOrg, departments: refreshedDepts } = res.data;
          const normalizedDepts = normalizeDepartments(refreshedDepts);
          setUser(refreshedUser);
          setOrganization(refreshedOrg);
          setDepartments(normalizedDepts);
          localStorage.setItem(
            AUTH_SESSION_KEY,
            JSON.stringify({
              user: refreshedUser,
              organization: refreshedOrg,
              departments: normalizedDepts,
            })
          );
          if (normalizedDepts.length > 0) {
            setActiveDepartmentId((prev) => {
              const exists = normalizedDepts.some((d) => d.id === prev);
              return exists ? prev : normalizedDepts[0].id;
            });
          }
          eventStream.connect();
        } catch (err: any) {
          if (err.response?.status === 401) {
            logout();
          }
        }
      } else {
        eventStream.disconnect();
      }
      setIsLoading(false);
    };

    initAuth();
  }, [logout]);

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, [logout]);

  const login = async (data: LoginDto) => {
    const res = await loginOrganizationUser(data);
    const { token: newToken, user: newUser, organization: newOrg, departments: newDepts } = res.data;
    saveAuthSession(newToken, newUser, newOrg, newDepts || []);
    eventStream.connect();
  };

  const register = async (data: RegisterOrgDto) => {
    const res = await registerOrganization(data);
    const { token: newToken, user: newUser, organization: newOrg, departments: newDepts } = res.data;
    saveAuthSession(newToken, newUser, newOrg, newDepts || []);
    eventStream.connect();
  };

  const acceptInvitation = async (data: AcceptInviteDto) => {
    const res = await acceptOrgInvitation(data);
    const { token: newToken, user: newUser, organization: newOrg, departments: newDepts } = res.data;
    saveAuthSession(newToken, newUser, newOrg, newDepts || []);
    eventStream.connect();
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        organization,
        departments,
        activeDepartmentId,
        setActiveDepartmentId,
        isAuthenticated,
        isLoading,
        login,
        register,
        acceptInvitation,
        logout,
        refreshUserProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
