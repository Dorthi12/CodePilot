export interface User {
  id: string;
  github_id: string;
  username: string;
  name: string | null;
  email: string | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface GitHubStatus {
  connected: boolean;
  provider: string;
  username?: string | null;
  scopes?: string | null;
  connected_at?: string | null;
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  loginWithGitHub: () => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}
