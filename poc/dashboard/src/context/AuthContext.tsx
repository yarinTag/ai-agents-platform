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
      return cached ? JSON.parse(cached).departments || [] : [];
    } catch {
      return [];
    }
  });

  const [activeDepartmentId, setActiveDepartmentId] = useState<string | null>(() => {
    try {
      const cached = localStorage.getItem(AUTH_SESSION_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed.departments && parsed.departments.length > 0) {
          return parsed.departments[0].id || parsed.departments[0].department_id;
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
    localStorage.setItem(AUTH_TOKEN_KEY, newToken);
    localStorage.setItem(
      AUTH_SESSION_KEY,
      JSON.stringify({ user: newUser, organization: newOrg, departments: newDepts })
    );
    setToken(newToken);
    setUser(newUser);
    setOrganization(newOrg);
    setDepartments(newDepts);
    if (newDepts.length > 0) {
      setActiveDepartmentId((prev) => {
        const exists = newDepts.some((d) => (d.id || (d as any).department_id) === prev);
        return exists ? prev : (newDepts[0].id || (newDepts[0] as any).department_id);
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
      setUser(refreshedUser);
      setOrganization(refreshedOrg);
      setDepartments(refreshedDepts || []);
      localStorage.setItem(
        AUTH_SESSION_KEY,
        JSON.stringify({
          user: refreshedUser,
          organization: refreshedOrg,
          departments: refreshedDepts || [],
        })
      );
      if (refreshedDepts && refreshedDepts.length > 0) {
        setActiveDepartmentId((prev) => {
          const exists = refreshedDepts.some((d) => (d.id || (d as any).department_id) === prev);
          return exists ? prev : (refreshedDepts[0].id || (refreshedDepts[0] as any).department_id);
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
          setUser(refreshedUser);
          setOrganization(refreshedOrg);
          setDepartments(refreshedDepts || []);
          localStorage.setItem(
            AUTH_SESSION_KEY,
            JSON.stringify({
              user: refreshedUser,
              organization: refreshedOrg,
              departments: refreshedDepts || [],
            })
          );
          if (refreshedDepts && refreshedDepts.length > 0) {
            setActiveDepartmentId(refreshedDepts[0].id || (refreshedDepts[0] as any).department_id);
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
