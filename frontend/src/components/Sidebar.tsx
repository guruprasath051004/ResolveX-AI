import React from 'react';
import {
  LayoutDashboard,
  MessageSquare,
  AlertCircle,
  FileCheck2,
  Cpu,
  FlaskConical,
  Layers,
  ShieldAlert,
  Server,
  BookOpen,
  LogOut,
  UserCheck,
} from 'lucide-react';
import { User } from '../services/api';
import { AppPage, canAccessPage } from '../config/roleNavigation';

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  currentUser: User | null;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onNavigate,
  currentUser,
  onLogout,
}) => {
  const navItems: Array<{ id: AppPage; label: string; icon: typeof MessageSquare }> = [
    { id: 'home', label: 'Employee Home', icon: LayoutDashboard },
    { id: 'chat', label: 'AI Support', icon: MessageSquare },
    {
      id: 'dashboard',
      label: currentUser?.role === 'support_engineer' ? 'Operations Dashboard' : 'Administrator Dashboard',
      icon: LayoutDashboard,
    },
    { id: 'incidents', label: 'Incidents Queue', icon: AlertCircle },
    { id: 'approvals', label: 'Pending Approvals', icon: FileCheck2 },
    { id: 'command-center', label: 'Agent Command Center', icon: Cpu },
    { id: 'scenario-lab', label: 'Scenario Testing Lab', icon: FlaskConical },
    { id: 'mcp-monitor', label: 'MCP Server Monitor', icon: Layers },
    { id: 'sla', label: 'SLA Compliance', icon: ShieldAlert },
    { id: 'assets', label: 'Asset CMDB', icon: Server },
    { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen },
  ];
  const visibleNavItems = currentUser
    ? navItems.filter((item) => canAccessPage(currentUser.role, item.id))
    : [];

  return (
    <aside className="w-64 bg-navy-900 text-slate-200 flex flex-col h-screen select-none border-r border-slate-800">
      {/* Brand Header */}
      <div className="p-5 border-b border-navy-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-brand-blue to-brand-violet flex items-center justify-center font-bold text-white shadow-md shadow-brand-blue/30">
            RX
          </div>
          <div>
            <h1 className="font-bold text-white tracking-tight text-base leading-tight">ResolveX AI</h1>
            <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-brand-violet/20 text-brand-violet border border-brand-violet/30">
              Autonomous USM
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          Platform Modules
        </div>
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? 'bg-brand-blue text-white shadow-sm'
                  : 'text-slate-300 hover:bg-navy-800 hover:text-white'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Current User Session Card */}
      <div className="p-4 border-t border-navy-800 bg-navy-900/60">
        {currentUser ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5 overflow-hidden">
              <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs font-bold text-slate-200">
                {currentUser.email.slice(0, 2).toUpperCase()}
              </div>
              <div className="truncate">
                <p className="text-xs font-semibold text-white truncate">{currentUser.email}</p>
                <span className="text-[10px] text-brand-cyan capitalize flex items-center space-x-1">
                  <UserCheck className="w-2.5 h-2.5 inline mr-0.5" />
                  {currentUser.role.replace('_', ' ')}
                </span>
              </div>
            </div>
            <button
              onClick={onLogout}
              title="Logout"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-navy-800 rounded-md transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => onNavigate('login')}
            className="w-full py-2 px-3 text-xs font-semibold rounded bg-brand-blue text-white hover:bg-blue-600 transition"
          >
            Sign In / Switch Role
          </button>
        )}
      </div>
    </aside>
  );
};

